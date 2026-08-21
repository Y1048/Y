using System;
using System.Globalization;
using System.IO;
using UnityEngine;

public class G1LiveTeleopTrace : MonoBehaviour
{
    public G1ExistingHandTargetBinder hand_binder;
    public G1ExistingTargetUdpSender target_sender;
    public G1RobotStateUdpReceiver state_receiver;
    public float sample_hz = 60.0f;

    private StreamWriter writer;
    private float next_sample_time;
    private string trace_path;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Bootstrap()
    {
        if (FindFirstObjectByType<G1LiveTeleopTrace>() != null)
        {
            return;
        }

        G1ExistingTargetUdpSender sender = FindFirstObjectByType<G1ExistingTargetUdpSender>();
        if (sender == null)
        {
            return;
        }

        GameObject trace_object = new GameObject("G1_Live_Teleop_Trace");
        G1LiveTeleopTrace trace = trace_object.AddComponent<G1LiveTeleopTrace>();
        trace.target_sender = sender;
        trace.hand_binder = sender.hand_binder;
        trace.state_receiver = sender.state_receiver;
    }

    private void OnEnable()
    {
        OpenTrace();
    }

    private void Update()
    {
        if (writer == null)
        {
            return;
        }

        float now = Time.realtimeSinceStartup;
        if (now < next_sample_time)
        {
            return;
        }
        next_sample_time = now + 1.0f / Mathf.Max(1.0f, sample_hz);

        bool tracked = hand_binder != null && hand_binder.IsTrackingValid;
        bool calibrated = hand_binder != null && hand_binder.IsCalibrated;
        Vector3 raw_wrist_position = hand_binder == null
            ? Vector3.zero
            : hand_binder.TrackedWristPosition;
        Quaternion raw_wrist_rotation = hand_binder == null
            ? Quaternion.identity
            : hand_binder.TrackedWristRotation;
        Vector3 binder_operator_delta = hand_binder == null
            ? Vector3.zero
            : hand_binder.OperatorTargetDelta;
        Vector3 sender_operator_delta = target_sender == null
            ? Vector3.zero
            : target_sender.LastOperatorTargetDelta;
        Vector3 sender_robot_target = target_sender == null
            ? Vector3.zero
            : target_sender.LastRobotTarget;

        bool backend_recent = state_receiver != null && state_receiver.HasRecentState;
        Vector3 backend_target_delta = backend_recent
            ? state_receiver.LatestTargetOperatorDelta
            : Vector3.zero;
        Vector3 backend_wrist_delta = backend_recent
            ? state_receiver.LatestWristOperatorDelta
            : Vector3.zero;
        float backend_position_error = backend_recent
            ? state_receiver.LatestPositionError
            : 0.0f;
        bool workspace_limited = backend_recent && state_receiver.IsWorkspaceLimited;
        bool collision_limited = backend_recent && state_receiver.IsCollisionLimited;
        float[] joints = backend_recent ? state_receiver.LatestRightArmJoints : null;

        float shoulder_pitch = Joint(joints, 0);
        float shoulder_roll = Joint(joints, 1);
        float shoulder_yaw = Joint(joints, 2);
        float elbow = Joint(joints, 3);
        float wrist_roll = Joint(joints, 4);
        float wrist_pitch = Joint(joints, 5);
        float wrist_yaw = Joint(joints, 6);

        writer.WriteLine(string.Format(
            CultureInfo.InvariantCulture,
            "{0:F6},{1},{2},{3}," +
            "{4:F6},{5:F6},{6:F6}," +
            "{7:F6},{8:F6},{9:F6},{10:F6}," +
            "{11:F6},{12:F6},{13:F6}," +
            "{14:F6},{15:F6},{16:F6}," +
            "{17:F6},{18:F6},{19:F6}," +
            "{20},{21},{22}," +
            "{23:F6},{24:F6},{25:F6},{26:F6},{27:F6},{28:F6},{29:F6}",
            Time.realtimeSinceStartupAsDouble,
            tracked ? 1 : 0,
            calibrated ? 1 : 0,
            target_sender != null && target_sender.IsCommandValid ? 1 : 0,
            raw_wrist_position.x, raw_wrist_position.y, raw_wrist_position.z,
            raw_wrist_rotation.x, raw_wrist_rotation.y,
            raw_wrist_rotation.z, raw_wrist_rotation.w,
            binder_operator_delta.x, binder_operator_delta.y, binder_operator_delta.z,
            sender_operator_delta.x, sender_operator_delta.y, sender_operator_delta.z,
            sender_robot_target.x, sender_robot_target.y, sender_robot_target.z,
            backend_recent ? 1 : 0,
            workspace_limited ? 1 : 0,
            collision_limited ? 1 : 0,
            backend_target_delta.x, backend_target_delta.y, backend_target_delta.z,
            backend_wrist_delta.x, backend_wrist_delta.y, backend_wrist_delta.z,
            backend_position_error,
            shoulder_pitch, shoulder_roll, shoulder_yaw, elbow,
            wrist_roll, wrist_pitch, wrist_yaw));
        writer.Flush();
    }

    private static float Joint(float[] joints, int index)
    {
        return joints != null && joints.Length > index ? joints[index] : float.NaN;
    }

    private void OpenTrace()
    {
        try
        {
            string project_root = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string log_directory = Path.Combine(project_root, "Logs");
            Directory.CreateDirectory(log_directory);
            trace_path = Path.Combine(log_directory, "live_quest_trace.csv");
            writer = new StreamWriter(trace_path, false, System.Text.Encoding.UTF8);
            writer.WriteLine(
                "time_s,tracked,calibrated,command_valid," +
                "raw_wrist_x,raw_wrist_y,raw_wrist_z," +
                "raw_rot_x,raw_rot_y,raw_rot_z,raw_rot_w," +
                "binder_delta_x,binder_delta_y,binder_delta_z," +
                "sender_delta_x,sender_delta_y,sender_delta_z," +
                "sender_robot_x,sender_robot_y,sender_robot_z," +
                "backend_recent,workspace_limited,collision_limited," +
                "backend_target_dx,backend_target_dy,backend_target_dz," +
                "backend_wrist_dx,backend_wrist_dy,backend_wrist_dz," +
                "backend_position_error," +
                "shoulder_pitch,shoulder_roll,shoulder_yaw,elbow," +
                "wrist_roll,wrist_pitch,wrist_yaw");
            writer.Flush();
            next_sample_time = 0.0f;
            Debug.Log("G1 live teleop trace: " + trace_path);
        }
        catch (Exception exception_value)
        {
            Debug.LogWarning("Could not open G1 live teleop trace: " + exception_value.Message);
            CloseTrace();
        }
    }

    private void CloseTrace()
    {
        if (writer != null)
        {
            writer.Flush();
            writer.Dispose();
            writer = null;
        }
    }

    private void OnDisable() { CloseTrace(); }
    private void OnDestroy() { CloseTrace(); }
    private void OnApplicationQuit() { CloseTrace(); }
}
