using System;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class G1ExistingTargetUdpSender : MonoBehaviour
{
    public G1ExistingHandTargetBinder hand_binder;
    public G1RobotStateUdpReceiver state_receiver;
    public Transform right_hand_target;
    public string udp_host = "127.0.0.1";
    public int udp_port = 5005;
    public float send_hz = 60.0f;
    public Vector3 robot_center = new Vector3(0.42f, -0.16f, 1.05f);
    public Vector3 position_offset = Vector3.zero;
    public Vector3 robot_min = new Vector3(0.22f, -0.50f, 0.70f);
    public Vector3 robot_max = new Vector3(0.70f, 0.30f, 1.50f);
    public bool disengage_on_workspace_exit = true;
    public float workspace_exit_confirm_seconds = 0.80f;
    public float workspace_exit_margin = 0.02f;

    // Live Quest hand tracking is noisier than the deterministic fake sender.
    // Keep the backend's 0.08 m/s reference limiter authoritative, but remove
    // small frame-to-frame tracking noise before it becomes an IK target.
    public float live_position_filter_time_constant_s = 0.060f;
    public float live_rotation_filter_time_constant_s = 0.050f;

    // Forward hand travel is reduced slightly so normal operator reach does not
    // immediately drive the G1 elbow toward full extension. Lateral/vertical
    // travel remain 1:1.
    public float operator_forward_scale = 0.75f;

    public Vector3 LastRobotTarget { get; private set; }
    public Vector3 UnclampedRobotTarget { get; private set; }
    public Vector3 LastOperatorTargetDelta { get; private set; }
    public bool IsWorkspaceLimited { get; private set; }
    public bool IsCommandValid { get; private set; }

    private UdpClient udp_client;
    private IPEndPoint udp_endpoint;
    private float send_interval;
    private float send_timer;
    private int packet_count;
    private bool workspace_exit_latched;
    private bool previous_calibrated;
    private bool backend_workspace_rearm_pending;
    private ulong backend_workspace_rearm_revision;
    private string session_id;
    private long sequence;
    private bool shutdown_complete;
    private float workspace_exit_duration;
    private bool workspace_violation_hold_active;
    private bool live_filter_initialized;
    private Vector3 filtered_operator_delta;
    private Quaternion filtered_operator_rotation = Quaternion.identity;

    private void Awake()
    {
        if (state_receiver == null)
        {
            state_receiver = GetComponent<G1RobotStateUdpReceiver>();
        }
        workspace_exit_margin = Mathf.Max(0.0f, workspace_exit_margin);
        live_position_filter_time_constant_s = Mathf.Max(0.001f, live_position_filter_time_constant_s);
        live_rotation_filter_time_constant_s = Mathf.Max(0.001f, live_rotation_filter_time_constant_s);
        operator_forward_scale = Mathf.Clamp(operator_forward_scale, 0.10f, 1.0f);
        send_interval = 1.0f / Mathf.Max(1.0f, send_hz);
        LastRobotTarget = robot_center + position_offset;
        UnclampedRobotTarget = LastRobotTarget;
        LastOperatorTargetDelta = Vector3.zero;
    }

    private void OnEnable() { OpenSocket(); }

    private void Update()
    {
        if (!Application.isPlaying || shutdown_complete) return;
        if (hand_binder == null && right_hand_target == null) return;
        send_timer += Time.deltaTime;
        if (send_timer < send_interval) return;
        send_timer = 0.0f;
        SendTarget();
    }

    private void SendTarget()
    {
        bool calibrated = hand_binder == null || hand_binder.IsCalibrated;
        bool calibration_started = calibrated && !previous_calibrated;
        previous_calibrated = calibrated;

        if (calibration_started)
        {
            bool stale_backend_limit = state_receiver != null
                && state_receiver.HasRecentState
                && state_receiver.IsWorkspaceLimited;
            backend_workspace_rearm_pending = stale_backend_limit;
            backend_workspace_rearm_revision = state_receiver == null ? 0 : state_receiver.StateRevision;
            workspace_exit_latched = false;
            workspace_exit_duration = 0.0f;
            IsWorkspaceLimited = false;
            workspace_violation_hold_active = false;
            live_filter_initialized = false;
            Debug.Log("G1 teleoperation engagement accepted; stale workspace feedback is being rearmed.");
        }

        bool tracking_valid = hand_binder == null || hand_binder.IsTrackingValid;
        bool command_valid = GetCommandValidity(calibrated, tracking_valid);

        Vector3 raw_operator_delta = hand_binder == null
            ? Vector3.zero
            : hand_binder.OperatorTargetDelta;
        raw_operator_delta.z *= operator_forward_scale;

        // Position deltas are already expressed in the headset-heading frame by
        // the binder. Express absolute wrist orientation in that SAME frame.
        // Sending Unity world rotation directly made live Quest rotation depend
        // on the room/world yaw while the position command did not.
        Quaternion raw_operator_rotation;
        if (hand_binder == null)
        {
            raw_operator_rotation = right_hand_target.rotation;
        }
        else
        {
            raw_operator_rotation = Quaternion.Inverse(hand_binder.OperatorHeading)
                * hand_binder.TrackedWristRotation;
        }

        if (!live_filter_initialized)
        {
            filtered_operator_delta = raw_operator_delta;
            filtered_operator_rotation = raw_operator_rotation;
            live_filter_initialized = true;
        }
        else
        {
            float position_alpha = ExponentialFilterAlpha(
                send_interval,
                live_position_filter_time_constant_s);
            float rotation_alpha = ExponentialFilterAlpha(
                send_interval,
                live_rotation_filter_time_constant_s);
            filtered_operator_delta = Vector3.Lerp(
                filtered_operator_delta,
                raw_operator_delta,
                position_alpha);
            filtered_operator_rotation = Quaternion.Slerp(
                filtered_operator_rotation,
                raw_operator_rotation,
                rotation_alpha);
        }

        Vector3 operator_delta = filtered_operator_delta;
        Quaternion target_rotation = filtered_operator_rotation;

        UnclampedRobotTarget = OperatorToRobot(operator_delta);
        Vector3 clamped_robot_target = ClampToRobotWorkspace(UnclampedRobotTarget);
        bool local_workspace_exit = command_valid && IsOutsideRobotWorkspace(UnclampedRobotTarget);
        bool backend_workspace_exit = command_valid
            && state_receiver != null
            && state_receiver.HasRecentState
            && state_receiver.IsWorkspaceLimited;
        bool backend_feedback_armed = !workspace_exit_latched && !backend_workspace_rearm_pending;

        bool workspace_exit_candidate = disengage_on_workspace_exit
            && ShouldDisengageForWorkspace(local_workspace_exit, backend_workspace_exit, backend_feedback_armed);
        workspace_exit_duration = UpdateWorkspaceExitDuration(workspace_exit_candidate, workspace_exit_duration, send_interval);
        bool workspace_exit_confirmed = IsWorkspaceExitConfirmed(workspace_exit_duration, workspace_exit_confirm_seconds);

        if (workspace_exit_confirmed)
        {
            bool first_exit = !workspace_exit_latched;
            workspace_exit_latched = true;
            backend_workspace_rearm_pending = false;
            IsWorkspaceLimited = true;
            command_valid = false;
            workspace_violation_hold_active = false;
            live_filter_initialized = false;
            if (hand_binder != null && hand_binder.IsCalibrated) hand_binder.ResetCalibration();
            if (first_exit)
            {
                string exit_source = local_workspace_exit ? "Unity workspace boundary" : "MuJoCo workspace boundary";
                Debug.LogWarning("G1 teleoperation disengaged at " + exit_source
                    + ". Return the hand to the engagement target to reconnect.");
            }
        }
        else
        {
            if (workspace_exit_candidate && !workspace_violation_hold_active)
            {
                workspace_violation_hold_active = true;
                Debug.Log("G1 workspace excursion detected; continuing with workspace-clipped targets and will rebase on recovery.");
            }

            if (!workspace_exit_candidate && workspace_violation_hold_active)
            {
                workspace_violation_hold_active = false;
                Debug.Log("G1 workspace excursion cleared; re-centering hand-to-robot mapping.");
                if (hand_binder != null && hand_binder.IsTrackingValid && hand_binder.IsCalibrated)
                {
                    hand_binder.ResetCalibration();
                    hand_binder.Calibrate();
                    live_filter_initialized = false;
                    raw_operator_rotation = Quaternion.Inverse(hand_binder.OperatorHeading)
                        * hand_binder.TrackedWristRotation;
                    target_rotation = raw_operator_rotation;
                }
            }

            bool received_fresh_backend_clear = backend_workspace_rearm_pending
                && state_receiver != null
                && state_receiver.StateRevision > backend_workspace_rearm_revision
                && !state_receiver.IsWorkspaceLimited;
            if (received_fresh_backend_clear)
            {
                Debug.Log("G1 teleoperation re-engaged inside the workspace.");
                backend_workspace_rearm_pending = false;
                workspace_exit_latched = false;
                workspace_exit_duration = 0.0f;
            }

            if (command_valid)
            {
                LastRobotTarget = clamped_robot_target;
                LastOperatorTargetDelta = operator_delta;
            }
            IsWorkspaceLimited = workspace_exit_latched;
        }

        IsCommandValid = command_valid;
        Vector3 send_position = command_valid ? clamped_robot_target : LastRobotTarget;
        Quaternion send_rotation = target_rotation;
        string command_state = workspace_exit_latched ? "workspace_exit" : (command_valid ? "active" : "idle");
        string json_text = BuildPacket(send_position, send_rotation, command_valid, command_state);
        if (!SendPacket(json_text)) return;
        packet_count++;
        if (packet_count % 120 == 0) Debug.Log("G1 Quest hand UDP #" + packet_count + ": " + json_text);
    }

    public static float ExponentialFilterAlpha(float delta_time, float time_constant)
    {
        float safe_dt = Mathf.Max(0.0f, delta_time);
        float safe_tau = Mathf.Max(0.001f, time_constant);
        return 1.0f - Mathf.Exp(-safe_dt / safe_tau);
    }

    public Vector3 OperatorToRobot(Vector3 operator_delta)
    {
        Vector3 robot_delta = new Vector3(operator_delta.z, -operator_delta.x, operator_delta.y);
        return robot_center + position_offset + robot_delta;
    }

    public Vector3 RobotToOperatorDelta(Vector3 robot_target)
    {
        Vector3 robot_delta = robot_target - robot_center - position_offset;
        return new Vector3(-robot_delta.y, robot_delta.z, robot_delta.x);
    }

    public static bool ShouldDisengageForWorkspace(bool local_workspace_exit, bool backend_workspace_exit, bool backend_feedback_armed)
    {
        return local_workspace_exit || (backend_feedback_armed && backend_workspace_exit);
    }

    public static bool GetCommandValidity(bool calibrated, bool tracking_valid)
    {
        return calibrated && tracking_valid;
    }

    public static float UpdateWorkspaceExitDuration(bool workspace_exit, float current_duration, float delta_time)
    {
        if (!workspace_exit) return 0.0f;
        return Mathf.Max(0.0f, current_duration) + Mathf.Max(0.0f, delta_time);
    }

    public static bool IsWorkspaceExitConfirmed(float workspace_exit_duration, float confirm_seconds)
    {
        return workspace_exit_duration >= Mathf.Max(0.01f, confirm_seconds);
    }

    private bool IsOutsideRobotWorkspace(Vector3 robot_target)
    {
        return robot_target.x < robot_min.x - workspace_exit_margin
            || robot_target.x > robot_max.x + workspace_exit_margin
            || robot_target.y < robot_min.y - workspace_exit_margin
            || robot_target.y > robot_max.y + workspace_exit_margin
            || robot_target.z < robot_min.z - workspace_exit_margin
            || robot_target.z > robot_max.z + workspace_exit_margin;
    }

    private Vector3 ClampToRobotWorkspace(Vector3 robot_target)
    {
        return new Vector3(
            Mathf.Clamp(robot_target.x, robot_min.x, robot_max.x),
            Mathf.Clamp(robot_target.y, robot_min.y, robot_max.y),
            Mathf.Clamp(robot_target.z, robot_min.z, robot_max.z));
    }

    private void OpenSocket()
    {
        CloseSocket();
        udp_client = new UdpClient();
        udp_endpoint = new IPEndPoint(IPAddress.Parse(udp_host), udp_port);
        session_id = Guid.NewGuid().ToString("N");
        sequence = 0;
        send_timer = 0.0f;
        packet_count = 0;
        workspace_exit_latched = false;
        workspace_exit_duration = 0.0f;
        previous_calibrated = hand_binder != null && hand_binder.IsCalibrated;
        backend_workspace_rearm_pending = false;
        backend_workspace_rearm_revision = 0;
        IsWorkspaceLimited = false;
        IsCommandValid = false;
        shutdown_complete = false;
        workspace_violation_hold_active = false;
        live_filter_initialized = false;
        filtered_operator_delta = Vector3.zero;
        filtered_operator_rotation = Quaternion.identity;
    }

    private string BuildPacket(Vector3 target_position, Quaternion target_rotation, bool tracking_valid, string command_state)
    {
        long packet_sequence = sequence;
        sequence++;
        return string.Format(
            CultureInfo.InvariantCulture,
            "{{\"session_id\":\"{0}\",\"sequence\":{1},\"command_state\":\"{2}\",\"right\":{{\"pos\":[{3:F5},{4:F5},{5:F5}],\"rot\":[{6:F5},{7:F5},{8:F5},{9:F5}],\"valid\":{10}}},\"timestamp\":{11:F6},\"source\":\"quest3s_head_relative\"}}",
            session_id, packet_sequence, command_state,
            target_position.x, target_position.y, target_position.z,
            target_rotation.x, target_rotation.y, target_rotation.z, target_rotation.w,
            tracking_valid ? "true" : "false",
            Time.realtimeSinceStartupAsDouble);
    }

    private bool SendPacket(string json_text)
    {
        if (udp_client == null || udp_endpoint == null) return false;
        try
        {
            byte[] packet_data = Encoding.UTF8.GetBytes(json_text);
            udp_client.Send(packet_data, packet_data.Length, udp_endpoint);
            return true;
        }
        catch (SocketException exception_value)
        {
            Debug.LogWarning("G1 target UDP send failed: " + exception_value.Message);
            return false;
        }
        catch (ObjectDisposedException) { return false; }
    }

    private void ShutdownSocket()
    {
        if (shutdown_complete) return;
        shutdown_complete = true;
        IsCommandValid = false;
        if (udp_client == null) return;
        CloseSocket();
    }

    private void CloseSocket()
    {
        if (udp_client != null)
        {
            udp_client.Close();
            udp_client = null;
        }
        udp_endpoint = null;
        IsCommandValid = false;
    }

    private void OnDisable() { ShutdownSocket(); }
    private void OnApplicationQuit() { ShutdownSocket(); }
    private void OnDestroy() { ShutdownSocket(); }
}
