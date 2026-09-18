using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

/// <summary>Opt-in paired wrist input. Fixed loopback destination, simulation schema only.</summary>
[DefaultExecutionOrder(-20000)]
public class G1BimanualSimulationSender : MonoBehaviour
{
    public enum ArmMode { RightArm, BimanualSimulation }
    public bool useExistingScene;
    public ArmMode armMode = ArmMode.BimanualSimulation;
    public G1ExistingHandTargetBinder rightBinder;
    public G1ExistingHandTargetBinder leftBinder;
    public G1ExistingTargetUdpSender existingSender;
    public bool UsesExistingScene => useExistingScene && armMode == ArmMode.BimanualSimulation;
    public bool IsTracking => active && backendState == "tracking";
    public float[] LatestJoints { get; private set; }
    public string[] LatestJointNames { get; private set; }
    public bool HasFreshJoints => LatestJoints != null && Time.realtimeSinceStartupAsDouble-lastFeedback < .75;

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
    public string Status { get; private set; } = "WAIT: start Python simulation";

    [Serializable] private class HandPacket
    {
        public bool tracked;
        public float[] position_m = new float[3];
        public float[] quaternion_wxyz = new float[] { 1, 0, 0, 0 };
    }
    [Serializable] private class Packet
    {
        public string schema = "g1.bimanual.unity.sim.v1";
        public bool simulation_only = true;
        public string session;
        public long sequence;
        public double sender_time_s;
        public bool engage;
        public bool return_home;
        public HandPacket left = new HandPacket();
        public HandPacket right = new HandPacket();
    }
    [Serializable] private class Feedback
    {
        public string schema;
        public bool simulation_only;
        public string session;
        public long sequence;
        public string state;
        public string reason;
        public string[] joint_names;
        public float[] q_rad;
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
    private float alignmentTime;
    private float pinchTime;
    private string backendState = "waiting";
    private GameObject leftMarker, rightMarker;
    private GameObject leftTrackedMarker;
    private TextMesh label;

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
            Debug.LogError("Bimanual simulation requires headset and both OVR hand/skeleton references.");
            enabled = false;
            return;
        }
        packet = new Packet { session = Guid.NewGuid().ToString("N") };
        frameSet = active = returnPending = mustLeaveZones = false;
        alignmentTime = pinchTime = 0;
        backendState = "waiting";
        lastFeedback = double.NegativeInfinity;
        feedbackSequence = -1;
        returnSequence = -1;
        client = new UdpClient(new IPEndPoint(IPAddress.Loopback, 0));
        client.Client.Blocking = false;
        // Suppress Windows UDP ICMP reset when Python is not running yet.
        if (Application.platform == RuntimePlatform.WindowsEditor || Application.platform == RuntimePlatform.WindowsPlayer)
            client.Client.IOControl((IOControlCode)(-1744830452), new byte[] { 0 }, null);
        leftMarker = MakeMarker("Left engage / raw target");
        leftMarker.GetComponent<Renderer>().material.color = Color.green;
        if (useExistingScene)
        {
            leftTrackedMarker = MakeMarker("Left tracked wrist");
            leftTrackedMarker.GetComponent<Renderer>().material.color = Color.cyan;
            leftTrackedMarker.transform.localScale = Vector3.one * .025f;
        }
        if (!useExistingScene) rightMarker = MakeMarker("Right engage zone");
        label = new GameObject("Bimanual simulation status").AddComponent<TextMesh>();
        label.fontSize = 48;
        label.characterSize = .006f;
        label.anchor = TextAnchor.MiddleCenter;
    }

    private GameObject MakeMarker(string name)
    {
        var marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        marker.name = name;
        marker.transform.localScale = Vector3.one * .045f;
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
        Vector3 p = binder.OperatorTargetDelta;
        Quaternion q = Quaternion.Inverse(binder.OperatorHeading) * binder.TrackedWristRotation;
        output.position_m = new[] { p.x, p.y, p.z };
        output.quaternion_wxyz = new[] { q.w, q.x, q.y, q.z };
        return true;
    }

    private void ResetBinders()
    {
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
                    !feedback.simulation_only || feedback.session != packet.session ||
                    feedback.sequence < feedbackSequence || feedback.sequence >= packet.sequence) continue;
                if (useExistingScene && !ValidJoints(feedback)) continue;
                if (ValidJoints(feedback)) { LatestJoints = feedback.q_rad; LatestJointNames = feedback.joint_names; }
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
        leftMarker.transform.position = useExistingScene && leftBinder != null
            ? (active ? leftBinder.target_transform.position : leftBinder.EngagementTargetPosition) : leftZone;
        if (rightMarker != null) rightMarker.transform.position = rightZone;
        bool tracked = useExistingScene ? ReadBinder(leftBinder, packet.left) : ReadHand(leftHand, leftWrist, packet.left);
        tracked = (useExistingScene ? ReadBinder(rightBinder, packet.right) : ReadHand(rightHand, rightWrist, packet.right)) && tracked;
        if (leftTrackedMarker != null)
        {
            leftTrackedMarker.SetActive(packet.left.tracked);
            if (packet.left.tracked) leftTrackedMarker.transform.SetPositionAndRotation(
                leftBinder.TrackedWristPosition, leftBinder.TrackedWristRotation);
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
        if (mustLeaveZones && backendState == "ready" && tracked && !inZones && !pinch)
            mustLeaveZones = false;
        if (!active)
        {
            alignmentTime = fresh && backendState == "ready" && inZones && !pinch && !mustLeaveZones
                ? alignmentTime + Time.unscaledDeltaTime : 0;
            if (alignmentTime >= .35f && (!useExistingScene ||
                (leftBinder.EngagementProgress >= 1 && rightBinder.EngagementProgress >= 1)))
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
        Status = !fresh ? "WAIT: start Python simulation" : backendState == "blocked"
            ? "BLOCKED: restart simulation" : backendState == "returning" || returnPending
            ? "RETURNING: wait" : active ? "TRACKING | pinch 0.5s to return"
            : mustLeaveZones ? "READY: move out of zones, release pinch"
            : "READY: align both wrists with spheres";
        if (useExistingScene && !active && backendState == "ready" && fresh)
            Status += string.Format("\nL: {0} {1:F1}cm {2:P0} | R: {3} {4:F1}cm {5:P0}",
                leftBinder.EngagementState, leftBinder.AlignmentPositionError*100, leftBinder.EngagementProgress,
                rightBinder.EngagementState, rightBinder.AlignmentPositionError*100, rightBinder.EngagementProgress);
        label.text = "BIMANUAL SIMULATION ONLY\n" + Status;
        label.transform.position = head.position + head.forward * .8f + Vector3.down * .1f;
        label.transform.rotation = head.rotation;
    }

    private void OnGUI() { GUI.Label(new Rect(20, 20, 900, 50), "BIMANUAL SIMULATION ONLY | " + Status); }

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
        if (label != null) Destroy(label.gameObject);
    }
}
