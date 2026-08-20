using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class G1HandPoseUdpSender : MonoBehaviour
{
    public static G1HandPoseUdpSender Active { get; private set; }

    public enum InputMode
    {
        ManualKeyboard,
        AutoMotion,
        TransformSources
    }

    public enum MappingAxis
    {
        X,
        Y,
        Z
    }

    [Header("UDP")]
    public string host = "127.0.0.1";
    public int port = 5005;
    public float sendRateHz = 60.0f;

    [Header("Input")]
    public InputMode inputMode = InputMode.ManualKeyboard;
    public Transform rightHandSource;
    public Transform leftHandSource;
    public G1Quest3SXRHandsInput questHandsInput;
    public bool sendLeftHand = false;

    [Header("Robot target mapping")]
    public Vector3 rightRobotCenter = new Vector3(0.42f, -0.16f, 1.05f);
    public Vector3 leftRobotCenter = new Vector3(0.42f, 0.16f, 1.05f);
    public Vector3 minTarget = new Vector3(0.22f, -0.50f, 0.70f);
    public Vector3 maxTarget = new Vector3(0.70f, 0.30f, 1.50f);
    public Vector3 handToRobotScale = new Vector3(1.00f, 0.80f, 1.10f);
    public MappingAxis forwardAxis = MappingAxis.Z;
    public MappingAxis rightAxis = MappingAxis.X;
    public MappingAxis upAxis = MappingAxis.Y;
    public bool invertForward = false;
    public bool invertRight = true;
    public bool invertUp = false;

    [Header("Manual / fake input")]
    public float moveSpeed = 0.85f;
    public float fastMoveMultiplier = 2.5f;
    public Vector3 autoAmplitude = new Vector3(0.0f, 0.13f, 0.10f);
    public float autoSpeed = 1.0f;

    [Header("Smoothing")]
    [Range(0.01f, 1.0f)] public float positionAlpha = 0.30f;
    [Range(0.01f, 1.0f)] public float rotationAlpha = 0.30f;
    // Slower, smoother movement for teleoperation stability.
    public float maxTargetSpeed = 0.30f;
    // Keep a packet valid slightly longer to avoid false dropouts.
    public float trackingTimeoutSeconds = 0.60f;
    public float workspaceExitConfirmSeconds = 0.80f;
    public float trackingHoldSeconds = 0.80f;

    public Vector3 RightTarget { get; private set; }
    public Vector3 LeftTarget { get; private set; }
    public Vector3 RightHandDelta { get; private set; }
    public Vector3 RightRobotDelta { get; private set; }
    public bool RightWorkspaceLimited { get; private set; }
    public bool LeftWorkspaceLimited { get; private set; }
    public bool RightSpeedLimited { get; private set; }
    public bool LeftSpeedLimited { get; private set; }
    public bool RightTrackingHeld { get; private set; }
    public bool LeftTrackingHeld { get; private set; }
    public bool RightValid { get; private set; }
    public bool LeftValid { get; private set; }
    public int SentCount => sentCount;
    public string SessionId => sessionId;
    public long Sequence => sequence;

    UdpClient udp;
    IPEndPoint endpoint;
    float nextSendTime;
    int sentCount;
    string sessionId = System.Guid.NewGuid().ToString("N");
    long sequence = 0;
    Vector3 rightHandOrigin;
    Vector3 leftHandOrigin;
    bool calibrated;
    Quaternion rightRotation = Quaternion.identity;
    Quaternion leftRotation = Quaternion.identity;
    float lastRightSourceTime;
    float lastLeftSourceTime;
    bool workspaceExitLatched;
    float workspaceExitDuration;
    bool workspaceExitPreviouslyConfirmed;
    bool workspaceViolationHoldActive;
    Vector3 rightUnclampedRobotTarget;

    void OnEnable()
    {
        Active = this;
        Application.runInBackground = true;
        udp = new UdpClient();
        endpoint = new IPEndPoint(IPAddress.Parse(host), port);
        RightTarget = rightRobotCenter;
        LeftTarget = leftRobotCenter;
        RightHandDelta = Vector3.zero;
        RightRobotDelta = Vector3.zero;
        RightWorkspaceLimited = false;
        LeftWorkspaceLimited = false;
        RightSpeedLimited = false;
        LeftSpeedLimited = false;
        RightTrackingHeld = false;
        LeftTrackingHeld = false;
        RightValid = true;
        LeftValid = false;
        nextSendTime = 0.0f;
        sentCount = 0;
        sequence = 0;
        workspaceExitLatched = false;
        workspaceExitDuration = 0.0f;
        workspaceViolationHoldActive = false;
        workspaceExitPreviouslyConfirmed = false;
        calibrated = false;
        Debug.Log($"G1HandPoseUdpSender enabled. Sending G1 hand target UDP to {host}:{port}");
        if (sessionId == null || sessionId.Length == 0)
            sessionId = System.Guid.NewGuid().ToString("N");
    }

    void OnDisable()
    {
        if (Active == this)
            Active = null;

        udp?.Close();
        udp = null;
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.C))
            Calibrate();

        if (Input.GetKeyDown(KeyCode.Alpha1))
            inputMode = InputMode.ManualKeyboard;
        if (Input.GetKeyDown(KeyCode.Alpha2))
            inputMode = InputMode.AutoMotion;
        if (Input.GetKeyDown(KeyCode.Alpha3))
            inputMode = InputMode.TransformSources;
        if (Input.GetKeyDown(KeyCode.U))
            CycleUpAxis();
        if (Input.GetKeyDown(KeyCode.I))
            invertUp = !invertUp;
        if (Input.GetKeyDown(KeyCode.O))
            invertForward = !invertForward;
        if (Input.GetKeyDown(KeyCode.P))
            invertRight = !invertRight;
        if (Input.GetKeyDown(KeyCode.LeftBracket))
            AddVerticalSensitivity(-0.05f);
        if (Input.GetKeyDown(KeyCode.RightBracket))
            AddVerticalSensitivity(0.05f);
        if (Input.GetKeyDown(KeyCode.Comma))
            AddHorizontalSensitivity(-0.05f);
        if (Input.GetKeyDown(KeyCode.Period))
            AddHorizontalSensitivity(0.05f);
        if (Input.GetKeyDown(KeyCode.Minus))
            AddForwardSensitivity(-0.05f);
        if (Input.GetKeyDown(KeyCode.Equals))
            AddForwardSensitivity(0.05f);
        if (Input.GetKeyDown(KeyCode.Semicolon))
            AddSmoothing(-0.02f);
        if (Input.GetKeyDown(KeyCode.Quote))
            AddSmoothing(0.02f);

        UpdateTargets();

        if (udp == null || Time.time < nextSendTime)
            return;

        nextSendTime = Time.time + 1.0f / Mathf.Max(1.0f, sendRateHz);
        SendMessage();
    }

    public void Calibrate()
    {
        rightHandOrigin = rightHandSource != null ? rightHandSource.position : Vector3.zero;
        leftHandOrigin = leftHandSource != null ? leftHandSource.position : Vector3.zero;
        calibrated = true;
        Debug.Log("G1 teleop hand calibration updated.");
    }

    public void ResetTargets()
    {
        RightTarget = rightRobotCenter;
        LeftTarget = leftRobotCenter;
    }

    public void AddHorizontalSensitivity(float amount)
    {
        handToRobotScale.y = Mathf.Clamp(handToRobotScale.y + amount, 0.05f, 3.0f);
    }

    public void AddVerticalSensitivity(float amount)
    {
        handToRobotScale.z = Mathf.Clamp(handToRobotScale.z + amount, 0.05f, 3.0f);
    }

    public void AddForwardSensitivity(float amount)
    {
        handToRobotScale.x = Mathf.Clamp(handToRobotScale.x + amount, 0.05f, 3.0f);
    }

    public void AddSmoothing(float amount)
    {
        positionAlpha = Mathf.Clamp(positionAlpha + amount, 0.02f, 0.80f);
        rotationAlpha = Mathf.Clamp(rotationAlpha + amount, 0.02f, 0.80f);
    }

    public void CycleUpAxis()
    {
        if (upAxis == MappingAxis.X)
            upAxis = MappingAxis.Y;
        else if (upAxis == MappingAxis.Y)
            upAxis = MappingAxis.Z;
        else
            upAxis = MappingAxis.X;
    }

    void UpdateTargets()
    {
        switch (inputMode)
        {
            case InputMode.AutoMotion:
                UpdateAutoTargets();
                break;
            case InputMode.TransformSources:
                UpdateTransformTargets();
                break;
            default:
                UpdateManualTargets();
                break;
        }
    }

    void UpdateAutoTargets()
    {
        float t = Time.time * autoSpeed;
        Vector3 target = new Vector3(
            rightRobotCenter.x + autoAmplitude.x * Mathf.Sin(0.6f * t),
            rightRobotCenter.y + autoAmplitude.y * Mathf.Sin(0.8f * t),
            rightRobotCenter.z + autoAmplitude.z * Mathf.Sin(1.1f * t)
        );
        Vector3 mapped = ClampTarget(target, out bool limited);
        RightTarget = MoveTarget(RightTarget, mapped, out bool speed_limited);
        RightWorkspaceLimited = limited;
        RightSpeedLimited = speed_limited;
        rightRotation = Quaternion.identity;
        RightValid = true;
    }

    void UpdateManualTargets()
    {
        Vector3 delta = Vector3.zero;

        if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow))
            delta.z += 1.0f;
        if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow))
            delta.z -= 1.0f;
        if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow))
            delta.y += 1.0f;
        if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow))
            delta.y -= 1.0f;
        if (Input.GetKey(KeyCode.E))
            delta.x += 1.0f;
        if (Input.GetKey(KeyCode.Q))
            delta.x -= 1.0f;
        if (Input.GetKeyDown(KeyCode.R))
            ResetTargets();

        if (delta.sqrMagnitude > 1e-6f)
        {
            float speed = moveSpeed;
            if (Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift))
                speed *= fastMoveMultiplier;
            Vector3 mapped = ClampTarget(RightTarget + delta.normalized * speed * Time.deltaTime, out bool limited);
            RightTarget = MoveTarget(RightTarget, mapped, out bool speed_limited);
            RightWorkspaceLimited = limited;
            RightSpeedLimited = speed_limited;
        }

        RightValid = true;
    }

    void UpdateTransformTargets()
    {
        if (!calibrated && rightHandSource != null && rightHandSource.position.sqrMagnitude > 1e-6f)
            Calibrate();
        if (!calibrated)
        {
            RightValid = false;
            LeftValid = false;
            RightTrackingHeld = false;
            LeftTrackingHeld = false;
            RightSpeedLimited = false;
            LeftSpeedLimited = false;
            return;
        }

        Vector3 rightTarget = RightTarget;
        Quaternion nextRightRotation = rightRotation;
        bool right_tracked = questHandsInput == null || questHandsInput.RightTracked;
        float right_last_tracked_time = questHandsInput != null ? questHandsInput.LastRightTrackedTime : Time.time;
        RightValid = UpdateOneTransformTarget(
            rightHandSource,
            rightHandOrigin,
            rightRobotCenter,
            right_tracked,
            right_last_tracked_time,
            ref rightTarget,
            ref nextRightRotation,
            ref rightUnclampedRobotTarget,
            ref lastRightSourceTime,
            out bool right_limited,
            out bool right_speed_limited,
            out bool right_held);

        bool right_workspace_exit = !workspaceExitLatched && ShouldDisengageForWorkspace(rightUnclampedRobotTarget);
        bool confirmed_workspace_exit = UpdateWorkspaceExitState(
            right_workspace_exit && RightValid,
            RightValid,
            Time.deltaTime);
        if (confirmed_workspace_exit)
        {
            workspaceExitLatched = true;
            workspaceExitPreviouslyConfirmed = true;
            workspaceExitDuration = workspaceExitConfirmSeconds;
            workspaceViolationHoldActive = false;
            RightTarget = rightRobotCenter;
            RightValid = false;
            Debug.Log("G1 workspace exit confirmed. Teleop disengaged.");
        }
        else if (workspaceExitLatched && !right_workspace_exit && RightValid)
        {
            workspaceExitLatched = false;
            workspaceExitDuration = 0.0f;
            workspaceExitPreviouslyConfirmed = false;
            RightValid = true;
            Calibrate();
            Debug.Log("G1 workspace re-entered. Teleop re-engaged.");
        }

        RightTarget = rightTarget;
        rightRotation = nextRightRotation;
        RightWorkspaceLimited = right_limited;
        RightSpeedLimited = right_speed_limited;
        RightTrackingHeld = right_held;

        if (sendLeftHand)
        {
            Vector3 leftTarget = LeftTarget;
            Quaternion nextLeftRotation = leftRotation;
            bool left_tracked = questHandsInput == null || questHandsInput.LeftTracked;
            float left_last_tracked_time = questHandsInput != null ? questHandsInput.LastLeftTrackedTime : Time.time;
            Vector3 leftUnclampedRobotTarget = Vector3.zero;
            LeftValid = UpdateOneTransformTarget(
                leftHandSource,
                leftHandOrigin,
                leftRobotCenter,
                left_tracked,
                left_last_tracked_time,
                ref leftTarget,
                ref nextLeftRotation,
                ref leftUnclampedRobotTarget,
                ref lastLeftSourceTime,
                out bool left_limited,
                out bool left_speed_limited,
                out bool left_held);
            LeftTarget = leftTarget;
            leftRotation = nextLeftRotation;
            LeftWorkspaceLimited = left_limited;
            LeftSpeedLimited = left_speed_limited;
            LeftTrackingHeld = left_held;
        }
        else
        {
            LeftValid = false;
            LeftWorkspaceLimited = false;
            LeftSpeedLimited = false;
            LeftTrackingHeld = false;
        }
    }

    bool UpdateOneTransformTarget(
        Transform source,
        Vector3 origin,
        Vector3 robotCenter,
        bool sourceTracked,
        float lastTrackedTime,
        ref Vector3 currentTarget,
        ref Quaternion currentRotation,
        ref Vector3 unclampedRobotTarget,
        ref float lastSourceTime,
        out bool workspaceLimited,
        out bool speedLimited,
        out bool trackingHeld)
    {
        workspaceLimited = false;
        speedLimited = false;
        trackingHeld = false;
        unclampedRobotTarget = robotCenter;

        if (source == null)
            return false;

        if (!sourceTracked)
        {
            float lost_time = Time.time - lastTrackedTime;
            trackingHeld = lost_time <= trackingHoldSeconds;
            return trackingHeld;
        }

        lastSourceTime = Time.time;
        Vector3 handDelta = source.position - origin;
        Vector3 robotDelta = HandDeltaToRobotDelta(handDelta);
        unclampedRobotTarget = robotCenter + robotDelta;
        if (source == rightHandSource)
        {
            RightHandDelta = handDelta;
            RightRobotDelta = robotDelta;
        }
        Vector3 mapped = ClampTarget(unclampedRobotTarget, out workspaceLimited);
        currentTarget = MoveTarget(currentTarget, mapped, out speedLimited);
        currentRotation = Quaternion.Slerp(currentRotation, source.rotation, rotationAlpha);
        return Time.time - lastSourceTime <= trackingTimeoutSeconds;
    }

    Vector3 HandDeltaToRobotDelta(Vector3 handDelta)
    {
        float forward = GetAxisValue(handDelta, forwardAxis);
        float right = GetAxisValue(handDelta, rightAxis);
        float up = GetAxisValue(handDelta, upAxis);

        if (invertForward)
            forward = -forward;
        if (invertRight)
            right = -right;
        if (invertUp)
            up = -up;

        return new Vector3(
            forward * handToRobotScale.x,
            right * handToRobotScale.y,
            up * handToRobotScale.z
        );
    }

    float GetAxisValue(Vector3 value, MappingAxis axis)
    {
        switch (axis)
        {
            case MappingAxis.X:
                return value.x;
            case MappingAxis.Y:
                return value.y;
            default:
                return value.z;
        }
    }

    Vector3 ClampTarget(Vector3 target, out bool limited)
    {
        Vector3 clamped = new Vector3(
            Mathf.Clamp(target.x, minTarget.x, maxTarget.x),
            Mathf.Clamp(target.y, minTarget.y, maxTarget.y),
            Mathf.Clamp(target.z, minTarget.z, maxTarget.z)
        );
        limited = (clamped - target).sqrMagnitude > 1e-8f;
        return clamped;
    }

    Vector3 MoveTarget(Vector3 currentTarget, Vector3 mappedTarget, out bool speedLimited)
    {
        Vector3 smoothedTarget = Vector3.Lerp(currentTarget, mappedTarget, positionAlpha);
        float maxDistance = Mathf.Max(0.0f, maxTargetSpeed) * Time.deltaTime;
        Vector3 delta = smoothedTarget - currentTarget;

        if (maxDistance <= 1e-6f || delta.magnitude <= maxDistance)
        {
            speedLimited = false;
            return smoothedTarget;
        }

        speedLimited = true;
        return currentTarget + delta.normalized * maxDistance;
    }

    void SendMessage()
    {
        string commandState = workspaceExitLatched ? "workspace_exit" : (RightValid ? "active" : "idle");
        string json = BuildPacket(commandState);

        byte[] bytes = Encoding.UTF8.GetBytes(json);
        udp.Send(bytes, bytes.Length, endpoint);
        sentCount++;

        if (sentCount % 120 == 0)
            Debug.Log($"G1 UDP hand target #{sentCount}: {json}");
    }

    string BuildPacket(string commandState)
    {
        long packetSequence = sequence;
        sequence++;
        if (!sendLeftHand)
        {
            return string.Format(
                CultureInfo.InvariantCulture,
                "{{\"session_id\":\"{0}\",\"sequence\":{1},\"command_state\":\"{2}\",\"right\":{{\"pos\":[{3:F5},{4:F5},{5:F5}],\"rot\":[{6:F5},{7:F5},{8:F5},{9:F5}],\"valid\":{10}}},\"timestamp\":{11:F6},\"source\":\"unity_quest3s_head_relative\"}}",
                sessionId,
                packetSequence,
                commandState,
                RightTarget.x, RightTarget.y, RightTarget.z,
                rightRotation.x, rightRotation.y, rightRotation.z, rightRotation.w,
                RightValid ? "true" : "false",
                Time.realtimeSinceStartupAsDouble
            );
        }

        return string.Format(
            CultureInfo.InvariantCulture,
            "{{\"session_id\":\"{0}\",\"sequence\":{1},\"command_state\":\"{2}\",\"right\":{{\"pos\":[{3:F5},{4:F5},{5:F5}],\"rot\":[{6:F5},{7:F5},{8:F5},{9:F5}],\"valid\":{10}}},\"left\":{{\"pos\":[{11:F5},{12:F5},{13:F5}],\"rot\":[{14:F5},{15:F5},{16:F5},{17:F5}],\"valid\":{18}}},\"timestamp\":{19:F6},\"source\":\"unity_quest3s_head_relative\"}}",
            sessionId,
            packetSequence,
            commandState,
            RightTarget.x, RightTarget.y, RightTarget.z,
            rightRotation.x, rightRotation.y, rightRotation.z, rightRotation.w,
            RightValid ? "true" : "false",
            LeftTarget.x, LeftTarget.y, LeftTarget.z,
            leftRotation.x, leftRotation.y, leftRotation.z, leftRotation.w,
            LeftValid ? "true" : "false",
            Time.realtimeSinceStartupAsDouble
        );
    }

    bool ShouldDisengageForWorkspace(Vector3 unclampedTarget)
    {
        return unclampedTarget.x < minTarget.x || unclampedTarget.x > maxTarget.x
            || unclampedTarget.y < minTarget.y || unclampedTarget.y > maxTarget.y
            || unclampedTarget.z < minTarget.z || unclampedTarget.z > maxTarget.z;
    }

    bool UpdateWorkspaceExitState(
        bool workspaceViolation,
        bool sourceValid,
        float deltaTime)
    {
        if (!workspaceViolation)
        {
            workspaceExitDuration = 0.0f;
            workspaceViolationHoldActive = false;
            return false;
        }

        if (!sourceValid)
            return false;

        if (!workspaceViolationHoldActive)
        {
            workspaceViolationHoldActive = true;
            Debug.Log("G1 workspace excursion detected; waiting for confirmation before disengage.");
        }

        workspaceExitDuration += deltaTime;
        if (workspaceExitDuration >= workspaceExitConfirmSeconds && !workspaceExitPreviouslyConfirmed)
        {
            workspaceExitPreviouslyConfirmed = true;
            return true;
        }
        return false;
    }
}
