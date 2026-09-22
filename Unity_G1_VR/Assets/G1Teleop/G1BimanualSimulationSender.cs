using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Opt-in paired wrist input. Fixed loopback destination, simulation schema only.</summary>
[DefaultExecutionOrder(500)]
public class G1BimanualSimulationSender : MonoBehaviour
{
    public const float TrackedMarkerDiameter = .060f;
    public const float TargetMarkerDiameter = .055f;
    public static readonly Color TrackedMarkerColor = new Color(0, .90f, 1, 1);
    public static Color AlignmentColor(bool active, bool aligned)
        => active ? Color.green : aligned ? Color.yellow : Color.white;

    public static bool CanEngage(bool fresh, bool ready, bool tracked, bool inZones,
        bool pinch, bool mustLeave, float leftProgress, float rightProgress)
        => fresh && ready && tracked && inZones && !pinch && !mustLeave
            && leftProgress >= 1 && rightProgress >= 1;

    public static double RememberReady(double now, double until, bool eligible, float progress)
    {
        if (!eligible) return double.NegativeInfinity;
        return progress >= 1 ? now + 4 : until;
    }

    public static bool CanClearMustLeave(bool backendReady, bool tracked, bool inZones, bool pinch)
        => backendReady && tracked && !inZones && !pinch;
    private double leftReadyUntil = double.NegativeInfinity;
    private double rightReadyUntil = double.NegativeInfinity;

    public bool useExistingScene;
    public G1ExistingHandTargetBinder rightBinder;
    public G1ExistingHandTargetBinder leftBinder;
    public G1ExistingTargetUdpSender existingSender;
    public bool UsesExistingScene => useExistingScene;
    public bool IsTracking => active && backendState == "tracking";
    public float[] LatestJoints { get; private set; }
    public string[] LatestJointNames { get; private set; }
    public bool HasFreshJoints => LatestJoints != null && Time.realtimeSinceStartupAsDouble-lastFeedback < .75;
    private bool ikTargetValid;
    private Vector3 leftIkDelta, rightIkDelta;
    private bool worldTargetValid;
    private Vector3 leftWorldTarget, rightWorldTarget;
    private Quaternion rightWorldRotation;
    private G1OmniBodyHeading Omni => rightBinder == null || rightBinder.head_camera_alignment == null
        ? null : rightBinder.head_camera_alignment.OmniBodyHeading;

    public bool TryGetIkTarget(bool left, out Vector3 position)
    {
        var binder = left ? leftBinder : rightBinder;
        position = Vector3.zero;
        if (!IsTracking || !HasFreshJoints || !ikTargetValid || binder == null) return false;
        if (useExistingScene && !worldTargetValid) return false;
        if (worldTargetValid)
        {
            position = left ? leftWorldTarget : rightWorldTarget;
            return true;
        }
        position = binder.EngagementTargetPosition + binder.OperatorHeading *
            (left ? leftIkDelta : rightIkDelta);
        return true;
    }

    public bool TryGetRightIkRotation(out Quaternion rotation)
    {
        rotation = rightWorldRotation;
        return IsTracking && HasFreshJoints && worldTargetValid;
    }

    private static bool ValidRotation(float[] q)
    {
        if (q == null || q.Length != 4) return false;
        float norm = 0;
        foreach (float v in q) { if (float.IsNaN(v) || float.IsInfinity(v)) return false; norm += v*v; }
        return Mathf.Abs(norm-1) < .001f;
    }

    private static bool ValidDelta(float[] values)
    {
        if (values == null || values.Length != 3) return false;
        foreach (float value in values)
            if (float.IsNaN(value) || float.IsInfinity(value)) return false;
        return true;
    }

    private void LogTargetOffset(bool left)
    {
        Vector3 goal;
        if (!TryGetIkTarget(left, out goal)) return;
        var binder = left ? leftBinder : rightBinder;
        Debug.Log(string.Format("[BIMANUAL TARGET] {0} frame=omni_world_v1 yaw_deg={1:F1} gap_cm={2:F2} raw={3} ik={4}",
            left ? "L" : "R", Omni == null ? 0 : Omni.OperatorBodyYawDegrees,
            Vector3.Distance(goal, binder.TrackedWristPosition)*100,
            binder.TrackedWristPosition.ToString("F3"), goal.ToString("F3")));
    }

    public static bool IsSimulationSceneLoaded()
    {
        // BeforeSceneLoad sees deserialized scene objects before their Awake.
        // Include inactive objects so disabling the UI cannot enable locomotion.
        foreach (var sender in Resources.FindObjectsOfTypeAll<G1BimanualSimulationSender>())
            if (sender.gameObject.scene.IsValid() && (!sender.useExistingScene || sender.UsesExistingScene)) return true;
        return false;
    }

    public Transform head;
    public OVRHand leftHand;
    public OVRHand rightHand;
    public OVRSkeleton leftSkeleton;
    public OVRSkeleton rightSkeleton;
    public int port = 5020;
    public string Status { get; private set; } = "WAIT: start IK backend";

    [Serializable] private class HandPacket
    {
        public bool tracked;
        public float[] position_m = new float[3];
        public float[] engage_offset_m = new float[3];
        public float[] quaternion_wxyz = new float[] { 1, 0, 0, 0 };
    }
    [Serializable] private class Packet
    {
        public string schema = "g1.bimanual.unity.sim.v2";
        public bool simulation_only = true;
        public string session;
        public long sequence;
        public double sender_time_s;
        public bool engage;
        public bool return_home;
        public string input_frame = "omni_world_v1";
        public float base_yaw_rad;
        public HandPacket left = new HandPacket();
        public HandPacket right = new HandPacket();
    }
    [Serializable] private class Feedback
    {
        public string schema;
        public bool simulation_only;
        public string backend_id;
        public long backend_started_ns;
        public long feedback_sequence;
        public string session;
        public long sequence;
        public string state;
        public string reason;
        public string[] joint_names;
        public float[] q_rad;
        public bool ik_target_valid;
        public float[] left_ik_target_world_m, right_ik_target_world_m;
        public float[] right_ik_target_world_wxyz;
        public string input_frame;
        public float[] left_ik_target_operator_delta;
        public float[] right_ik_target_operator_delta;
    }

    private UdpClient client;
    private Packet packet;
    private Quaternion heading;
    private Vector3 origin;
    private bool frameSet;
    private bool active;
    private bool mustLeaveZones;
    private bool returnPending;
    private long returnSequence = -1;
    private double lastSend;
    private double lastFeedback = double.NegativeInfinity;
    private long feedbackSequence = -1;
    private G1BimanualFeedbackGate feedbackGate = new G1BimanualFeedbackGate();
    private float alignmentTime;
    private double lastDiagnostic;
    private float pinchTime;
    private string backendState = "waiting";
    private GameObject leftMarker, rightMarker;
    private GameObject leftTrackedMarker;
    private RectTransform statusBar;
    private Text leftStatus, rightStatus, cycleStatus;
    private Font statusFont;
    private G1HeadCameraPiP statusCamera;
    private double nextCameraSearch;

    private void Awake()
    {
        if (!useExistingScene) return;
        if (leftBinder != null) leftBinder.enabled = UsesExistingScene;
        if (UsesExistingScene)
        {
            // Repair scenes created by the first same-scene installer without
            // asking the operator to recreate the scene or reset its tuning.
            if (leftBinder != null && rightBinder != null)
            {
                leftBinder.reference_transform = rightBinder.reference_transform;
                leftBinder.head_camera_alignment = rightBinder.head_camera_alignment;
            }
            if (existingSender != null) existingSender.enabled = false;
            if (rightBinder != null) rightBinder.auto_calibrate_on_first_track = false;
            if (leftBinder != null) leftBinder.auto_calibrate_on_first_track = false;
        }
    }

    private void OnEnable()
    {
        if (useExistingScene && !UsesExistingScene) return;
        if (head == null || leftHand == null || rightHand == null ||
            leftSkeleton == null || rightSkeleton == null)
        {
            Debug.LogError("Bimanual input requires headset and both OVR hand/skeleton references.");
            enabled = false;
            return;
        }
        packet = new Packet { session = Guid.NewGuid().ToString("N") };
        frameSet = active = returnPending = mustLeaveZones = false;
        alignmentTime = pinchTime = 0;
        backendState = "waiting";
        lastFeedback = double.NegativeInfinity;
        feedbackSequence = -1;
        feedbackGate = new G1BimanualFeedbackGate();
        LatestJoints = null;
        LatestJointNames = null;
        returnSequence = -1;
        leftReadyUntil = rightReadyUntil = double.NegativeInfinity;
        client = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
        client.Client.Blocking = false;
        // Suppress Windows UDP ICMP reset when Python is not running yet.
        if (Application.platform == RuntimePlatform.WindowsEditor || Application.platform == RuntimePlatform.WindowsPlayer)
            client.Client.IOControl((IOControlCode)(-1744830452), new byte[] { 0 }, null);
        leftMarker = MakeMarker("Left engage / IK goal");
        leftMarker.GetComponent<Renderer>().material.color = Color.green;
        if (useExistingScene)
        {
            leftTrackedMarker = MakeMarker("Left tracked wrist");
            leftTrackedMarker.GetComponent<Renderer>().material.color = TrackedMarkerColor;
            leftTrackedMarker.transform.localScale = Vector3.one * TrackedMarkerDiameter;
        }
        if (!useExistingScene) rightMarker = MakeMarker("Right engage zone");
        CreateStatusBar();
    }

    private GameObject MakeMarker(string name)
    {
        var marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        marker.name = name;
        marker.transform.localScale = Vector3.one * TargetMarkerDiameter;
        var shader = Shader.Find("Unlit/Color");
        if (shader != null) marker.GetComponent<Renderer>().material = new Material(shader);
        Destroy(marker.GetComponent<Collider>());
        return marker;
    }

    private Transform Wrist(OVRSkeleton skeleton)
    {
        if (skeleton.Bones != null)
            foreach (OVRBone bone in skeleton.Bones)
                if (bone != null && bone.Id == OVRSkeleton.BoneId.Hand_WristRoot)
                    return bone.Transform;
        return null; // Never switch to a different pose source while tracking.
    }

    private bool ReadHand(OVRHand hand, Transform wrist, HandPacket output)
    {
        output.tracked = wrist != null && hand.IsTracked && hand.IsDataHighConfidence;
        if (!output.tracked) return false;
        Vector3 p = Quaternion.Inverse(heading) * (wrist.position - origin);
        Quaternion q = Quaternion.Inverse(heading) * wrist.rotation;
        output.position_m = new[] { p.x, p.y, p.z };
        output.quaternion_wxyz = new[] { q.w, q.x, q.y, q.z };
        return true;
    }

    private bool ReadBinder(G1ExistingHandTargetBinder binder, HandPacket output)
    {
        output.tracked = binder != null && binder.IsTrackingValid;
        if (!output.tracked) return false;
        // Already aligned at Play: send absolute wrist pose in that world.
        Vector3 p = binder.TrackedWristPosition;
        Quaternion q = binder.TrackedWristRotation;
        output.engage_offset_m = new float[3];
        output.position_m = new[] { p.x, p.y, p.z };
        output.quaternion_wxyz = new[] { q.w, q.x, q.y, q.z };
        return true;
    }

    private void ResetBinders()
    {
        leftReadyUntil = rightReadyUntil = double.NegativeInfinity;
        if (!useExistingScene) return;
        if (rightBinder != null && rightBinder.IsCalibrated) rightBinder.ResetCalibration();
        if (leftBinder != null && leftBinder.IsCalibrated) leftBinder.ResetCalibration();
    }

    private bool ValidJoints(Feedback feedback)
    {
        string[] suffix = { "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow", "wrist_roll", "wrist_pitch", "wrist_yaw" };
        if (feedback.q_rad == null || feedback.q_rad.Length != 14 ||
            feedback.joint_names == null || feedback.joint_names.Length != 14) return false;
        for (int i=0; i<14; ++i)
            if (feedback.joint_names[i] != (i<7 ? "left_" : "right_") + suffix[i%7] + "_joint"
                || float.IsNaN(feedback.q_rad[i]) || float.IsInfinity(feedback.q_rad[i])) return false;
        return true;
    }

    private void LateUpdate()
    {
        if (client == null) return;
        double now = Time.realtimeSinceStartupAsDouble;
        for (int i = 0; i < 64 && client.Available > 0; ++i)
        {
            try
            {
                IPEndPoint remote = new IPEndPoint(IPAddress.Any, 0);
                byte[] data = client.Receive(ref remote);
                if (!IPAddress.IsLoopback(remote.Address) || remote.Port != port || data.Length > 4096) continue;
                var feedback = JsonUtility.FromJson<Feedback>(Encoding.UTF8.GetString(data));
                if (feedback == null || feedback.schema != "g1.bimanual.unity.sim.state.v1" ||
                    !feedback.simulation_only || feedback.session != packet.session) continue;
                if (feedback.state != "ready" && feedback.state != "tracking" &&
                    feedback.state != "returning" && feedback.state != "blocked") continue;
                if (useExistingScene && !ValidJoints(feedback)) continue;
                bool restarted;
                if (!feedbackGate.Accept(feedback.backend_id, feedback.backend_started_ns,
                    feedback.feedback_sequence, feedback.sequence, packet.sequence, out restarted)) continue;
                if (restarted)
                {
                    // A new backend must receive inactive input before any new
                    // engage. Never carry old calibration across a process restart.
                    active = false;
                    returnPending = false;
                    returnSequence = -1;
                    mustLeaveZones = true;
                    alignmentTime = pinchTime = 0;
                    ResetBinders();
                    Debug.Log("[BIMANUAL SIM] backend restarted; fresh alignment required.");
                }
                if (ValidJoints(feedback)) { LatestJoints = feedback.q_rad; LatestJointNames = feedback.joint_names; }
                ikTargetValid = feedback.ik_target_valid &&
                    ValidDelta(feedback.left_ik_target_operator_delta) &&
                    ValidDelta(feedback.right_ik_target_operator_delta);
                worldTargetValid = feedback.input_frame == "omni_world_v1" && feedback.ik_target_valid
                    && ValidRotation(feedback.right_ik_target_world_wxyz) && ValidDelta(feedback.left_ik_target_world_m)
                    && ValidDelta(feedback.right_ik_target_world_m);
                if (worldTargetValid)
                {
                    var l = feedback.left_ik_target_world_m;
                    var r = feedback.right_ik_target_world_m;
                    leftWorldTarget = new Vector3(l[0], l[1], l[2]);
                    rightWorldTarget = new Vector3(r[0], r[1], r[2]);
                    var q = feedback.right_ik_target_world_wxyz;
                    rightWorldRotation = new Quaternion(q[1], q[2], q[3], q[0]);
                    ikTargetValid = true;
                }
                if (ikTargetValid && ValidDelta(feedback.left_ik_target_operator_delta) && ValidDelta(feedback.right_ik_target_operator_delta))
                {
                    var l = feedback.left_ik_target_operator_delta;
                    var r = feedback.right_ik_target_operator_delta;
                    leftIkDelta = new Vector3(l[0], l[1], l[2]);
                    rightIkDelta = new Vector3(r[0], r[1], r[2]);
                }
                backendState = feedback.state;
                feedbackSequence = feedback.sequence;
                lastFeedback = now;
                if (backendState == "returning" || backendState == "blocked")
                {
                    active = false;
                    mustLeaveZones = true;
                    returnPending = false;
                    returnSequence = -1;
                    ResetBinders();
                }
                // If already at home Python may acknowledge ready in one tick,
                // without an observable returning frame.
                if (backendState == "ready" && returnPending && returnSequence >= 0 &&
                    feedback.sequence >= returnSequence)
                {
                    returnPending = false;
                    returnSequence = -1;
                }
            }
            catch (SocketException) { break; }
            catch (ArgumentException) { /* Ignore malformed feedback. */ }
        }
        Transform leftWrist = Wrist(leftSkeleton), rightWrist = Wrist(rightSkeleton);
        if (!frameSet)
        {
            origin = head.position;
            heading = Quaternion.Euler(0, head.eulerAngles.y, 0);
            frameSet = leftWrist != null && rightWrist != null && leftHand.IsTracked && rightHand.IsTracked;
        }
        // Fixed headset-heading frame; no live head motion injected into wrist goals.
        Vector3 leftZone = origin + heading * new Vector3(-.22f, -.24f, .38f);
        Vector3 rightZone = origin + heading * new Vector3(.22f, -.24f, .38f);
        if (useExistingScene && leftBinder != null)
        {
            Vector3 ikPosition;
            bool available = TryGetIkTarget(true, out ikPosition);
            leftMarker.SetActive(!active || available);
            leftMarker.transform.position = active && available ? ikPosition : leftBinder.EngagementTargetPosition;
        }
        else leftMarker.transform.position = leftZone;
        if (rightMarker != null) rightMarker.transform.position = rightZone;
        bool tracked = useExistingScene ? ReadBinder(leftBinder, packet.left) : ReadHand(leftHand, leftWrist, packet.left);
        tracked = (useExistingScene ? ReadBinder(rightBinder, packet.right) : ReadHand(rightHand, rightWrist, packet.right)) && tracked;
        if (leftTrackedMarker != null)
        {
            leftTrackedMarker.SetActive(packet.left.tracked);
            if (packet.left.tracked) leftTrackedMarker.transform.SetPositionAndRotation(
                leftBinder.DisplayedWristPosition, leftBinder.DisplayedWristRotation);
        }
        bool omniReady = Omni != null && Omni.IsReady;
        packet.schema = useExistingScene ? "g1.bimanual.unity.sim.v2" : "g1.bimanual.unity.sim.v1";
        packet.input_frame = useExistingScene ? "omni_world_v1" : "legacy_relative";
        packet.base_yaw_rad = Omni == null ? 0 : -(float)Omni.OperatorBodyYawDegrees * Mathf.Deg2Rad;
        if (useExistingScene && !omniReady)
        {
            packet.left.tracked = packet.right.tracked = tracked = false;
            if (active) { active = false; returnPending = true; mustLeaveZones = true; ResetBinders(); }
        }
        bool inZones = useExistingScene
            ? tracked && leftBinder.IsAlignmentReady && rightBinder.IsAlignmentReady
            : tracked && Vector3.Distance(leftWrist.position, leftZone) < .07f && Vector3.Distance(rightWrist.position, rightZone) < .07f;
        bool pinch = (packet.left.tracked && leftHand.GetFingerIsPinching(OVRHand.HandFinger.Index))
            || (packet.right.tracked && rightHand.GetFingerIsPinching(OVRHand.HandFinger.Index));
        bool fresh = now - lastFeedback < .75;
        if (!fresh && active)
        {
            active = false;
            returnPending = true;
            mustLeaveZones = true;
            ResetBinders();
        }
        if (mustLeaveZones && CanClearMustLeave(backendState == "ready", tracked, inZones, pinch))
            mustLeaveZones = false;
        if (useExistingScene && !active)
        {
            bool eligible = fresh && backendState == "ready" && !pinch && !mustLeaveZones;
            leftReadyUntil = RememberReady(now, leftReadyUntil, eligible && packet.left.tracked,
                leftBinder.EngagementProgress);
            rightReadyUntil = RememberReady(now, rightReadyUntil, eligible && packet.right.tracked,
                rightBinder.EngagementProgress);
        }
        if (!active)
        {
            alignmentTime = fresh && backendState == "ready" && inZones && !pinch && !mustLeaveZones
                ? alignmentTime + Time.unscaledDeltaTime : 0;
            // Binders already enforce the configured stable hold. Do not add
            // another simultaneous dwell gate on top of the two hand timers.
            bool engageReady = useExistingScene
                ? CanEngage(fresh, backendState == "ready", tracked, inZones, pinch, mustLeaveZones,
                    now < leftReadyUntil ? 1 : 0, now < rightReadyUntil ? 1 : 0)
                : alignmentTime >= .35f;
            if (engageReady)
            {
                if (useExistingScene)
                {
                    leftBinder.Calibrate();
                    rightBinder.Calibrate();
                    ReadBinder(leftBinder, packet.left);
                    ReadBinder(rightBinder, packet.right);
                }
                active = true;
                returnPending = false;
                returnSequence = -1;
                pinchTime = 0;
            }
        }
        else
        {
            pinchTime = pinch ? pinchTime + Time.unscaledDeltaTime : 0;
            if (pinchTime >= .5f)
            {
                active = false;
                returnPending = true;
                mustLeaveZones = true;
                ResetBinders();
            }
        }
        if (useExistingScene)
        {
            leftMarker.transform.localScale = Vector3.one * TargetMarkerDiameter;
            leftMarker.GetComponent<Renderer>().material.color = AlignmentColor(active, leftBinder.IsAlignmentReady);
            if (now-lastDiagnostic >= 1)
            {
                Debug.Log(string.Format("[BIMANUAL ENGAGE] backend={0} fresh={1} active={2} pinch={3} leave={4} L={5}/{6:F1}cm/{7:P0} R={8}/{9:F1}cm/{10:P0}",
                    backendState, fresh, active, pinch, mustLeaveZones,
                    leftBinder.EngagementState, leftBinder.AlignmentPositionError*100, leftBinder.EngagementProgress,
                    rightBinder.EngagementState, rightBinder.AlignmentPositionError*100, rightBinder.EngagementProgress));
                lastDiagnostic = now;
                LogTargetOffset(true);
                LogTargetOffset(false);
            }
        }
        packet.engage = active;
        packet.return_home = returnPending;
        if (now-lastSend >= 1.0/60)
        {
            if (returnPending && returnSequence < 0) returnSequence = packet.sequence;
            packet.sender_time_s = now;
            byte[] data = Encoding.UTF8.GetBytes(JsonUtility.ToJson(packet));
            try { client.Send(data, data.Length, new IPEndPoint(IPAddress.Loopback, port)); }
            catch (SocketException) { /* Missing receiver is shown as WAIT. */ }
            ++packet.sequence;
            lastSend = now;
        }
        Status = !fresh ? "WAIT: start IK backend" : backendState == "blocked"
            ? "BLOCKED: restart IK backend" : backendState == "returning" || returnPending
            ? "RETURNING: wait" : active ? "TRACKING | pinch 0.5s to return"
            : mustLeaveZones ? "READY: move out of zones, release pinch"
            : pinch ? "READY: release pinch before engage"
            : "READY: align one hand, then the other; readiness remembered 4s";
        if (useExistingScene && !active && backendState == "ready" && fresh)
            Status += string.Format("\nL: {0} {1:F1}cm {2:P0} | R: {3} {4:F1}cm {5:P0}",
                leftBinder.EngagementState, leftBinder.AlignmentPositionError*100, leftBinder.EngagementProgress,
                rightBinder.EngagementState, rightBinder.AlignmentPositionError*100, rightBinder.EngagementProgress);
        if (useExistingScene && !omniReady)
            Status = Omni == null ? "WAIT: Omni alignment" : Omni.Status;
        else if (useExistingScene && !active) Status = "ALIGNED: release external hold\n" + Status;
        UpdateStatusBar(fresh, pinch);
    }

    private void CreateStatusBar()
    {
        statusBar = new GameObject("Bimanual camera status bar", typeof(RectTransform),
            typeof(Canvas), typeof(CanvasScaler), typeof(Image)).GetComponent<RectTransform>();
        var canvas = statusBar.GetComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.overrideSorting = true;
        canvas.sortingOrder = 101; // Camera canvas uses 100; UI remains above the video.
        canvas.worldCamera = head.GetComponent<Camera>();
        statusBar.GetComponent<CanvasScaler>().dynamicPixelsPerUnit = 10;
        var background = statusBar.GetComponent<Image>();
        background.color = new Color(.025f, .03f, .04f, .97f);
        background.raycastTarget = false;
        statusFont = Font.CreateDynamicFontFromOSFont(new[] { "Malgun Gothic", "Arial" }, 28);
        leftStatus = CreateStatusText("Left", new Vector2(0, .45f), new Vector2(.5f, 1), 15);
        rightStatus = CreateStatusText("Right", new Vector2(.5f, .45f), new Vector2(1, 1), 15);
        cycleStatus = CreateStatusText("Cycle", Vector2.zero, new Vector2(1, .45f), 12);
        nextCameraSearch = 0;
    }

    private Text CreateStatusText(string name, Vector2 minimum, Vector2 maximum, int size)
    {
        var text = new GameObject(name, typeof(RectTransform), typeof(Text)).GetComponent<Text>();
        text.transform.SetParent(statusBar, false);
        text.rectTransform.anchorMin = minimum;
        text.rectTransform.anchorMax = maximum;
        text.rectTransform.offsetMin = new Vector2(4, 1);
        text.rectTransform.offsetMax = new Vector2(-4, -1);
        text.font = statusFont;
        text.fontSize = size;
        text.alignment = TextAnchor.MiddleCenter;
        text.raycastTarget = false;
        text.supportRichText = false;
        return text;
    }

    private void UpdateHandStatus(Text text, string side, G1ExistingHandTargetBinder binder, bool tracked, double readyUntil)
    {
        bool aligned = binder != null && binder.IsAlignmentReady;
        bool ready = tracked && Time.realtimeSinceStartupAsDouble < readyUntil;
        string state = !tracked ? "추적 없음" : active ? "조작 중" : ready ? (aligned ? "준비 완료" : "목표 안으로")
            : aligned ? string.Format("정렬 {0:P0}", binder.EngagementProgress) : "위치 맞추기";
        text.text = side + " | " + state;
        text.color = !tracked ? new Color(1, .65f, .3f) : active || ready ? Color.green
            : aligned ? Color.yellow : Color.white;
    }

    private void UpdateStatusBar(bool fresh, bool pinch)
    {
        // Search after the camera's Start has created the PiP. Never create a
        // camera receiver as a side effect of showing engagement instructions.
        if (statusCamera == null && Time.realtimeSinceStartupAsDouble >= nextCameraSearch)
        {
            statusCamera = head.GetComponentInChildren<G1HeadCameraPiP>();
            nextCameraSearch = Time.realtimeSinceStartupAsDouble + 1;
        }
        var cameraRect = statusCamera == null ? null : statusCamera.transform as RectTransform;
        if (cameraRect != null)
        {
            if (statusBar.parent != cameraRect) statusBar.SetParent(cameraRect, false);
            statusBar.anchorMin = new Vector2(0, 0);
            statusBar.anchorMax = new Vector2(1, 0);
            statusBar.pivot = new Vector2(.5f, 1);
            statusBar.sizeDelta = new Vector2(0, 48);
            statusBar.anchoredPosition3D = new Vector3(0, -6, -1);
            statusBar.localRotation = Quaternion.identity;
            statusBar.localScale = Vector3.one;
            statusBar.GetComponent<Canvas>().sortingOrder = statusCamera.GetComponent<Canvas>().sortingOrder + 1;
        }
        else
        {
            // Same placement when video is disabled/unavailable; no central text.
            if (statusBar.parent != head) statusBar.SetParent(head, false);
            statusBar.anchorMin = statusBar.anchorMax = new Vector2(.5f, .5f);
            statusBar.pivot = new Vector2(.5f, 1);
            statusBar.sizeDelta = new Vector2(320, 48);
            statusBar.localScale = Vector3.one * G1HeadCameraPiP.DefaultCanvasScale;
            statusBar.localRotation = Quaternion.identity;
            statusBar.localPosition = new Vector3(0, G1HeadCameraPiP.DefaultCanvasVerticalOffset
                - 126 * G1HeadCameraPiP.DefaultCanvasScale, .7982f);
        }
        UpdateHandStatus(leftStatus, "왼손", leftBinder, packet.left.tracked, leftReadyUntil);
        UpdateHandStatus(rightStatus, "오른손", rightBinder, packet.right.tracked, rightReadyUntil);
        if (useExistingScene && (Omni == null || !Omni.IsReady))
        {
            cycleStatus.text = Omni == null ? "Omni 수신 대기" : Omni.Status;
            return;
        }
        cycleStatus.text = !fresh ? "시뮬레이션 수신 대기" : backendState == "blocked" ? "중단: PC 로그 확인"
            : backendState == "returning" || returnPending ? "초기자세 복귀 중"
            : active ? "양팔 조작 중 · pinch로 복귀" : mustLeaveZones ? "손을 목표 밖으로 옮겨 재준비"
            : pinch ? "pinch를 풀어 주세요" : "정렬 완료 · 외부 고정 해제 후 한 손씩 목표에 정렬";
    }

    private void OnGUI() { GUI.Label(new Rect(20, 20, 900, 50), "BIMANUAL IK INPUT | " + Status); }

    private void OnDisable()
    {
        if (client != null)
        {
            if (packet != null)
            {
                packet.engage = false;
                packet.return_home = true;
                packet.sender_time_s = Time.realtimeSinceStartupAsDouble;
                byte[] data = Encoding.UTF8.GetBytes(JsonUtility.ToJson(packet));
                try { client.Send(data, data.Length, new IPEndPoint(IPAddress.Loopback, port)); }
                catch (SocketException) { }
            }
            client.Close();
            client = null;
        }
        if (leftMarker != null) Destroy(leftMarker);
        if (leftTrackedMarker != null) Destroy(leftTrackedMarker);
        if (rightMarker != null) Destroy(rightMarker);
        if (statusBar != null) Destroy(statusBar.gameObject);
        if (statusFont != null) Destroy(statusFont);
    }
}
