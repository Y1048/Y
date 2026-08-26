using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class G1RobotStateUdpReceiver : MonoBehaviour
{
    [Serializable]
    private class RightArmState
    {
        public float[] joints;
        public bool active;
        public float[] wrist_delta;
        public float[] target_delta;
        public float[] wrist_position;
        public float[] target_position;
        public float position_error;
        public float orientation_error_deg;
        public float orientation_assist_gain;
        public float orientation_cost_scale;
        public float min_wrist_limit_margin_deg;
        public bool workspace_limited;
        public bool collision_limited;
    }

    [Serializable]
    private class RobotStatePacket
    {
        public RightArmState right_arm;
        public InspectionState inspection;
        public double timestamp;
    }

    [Serializable]
    private class InspectionState
    {
        public string state;
        public string target_source;
        public float[] target_position;
        public float[] tool_tip_position;
        public float[] panel_position;
        public float[] panel_half_size;
        public float distance_m;
        public float hold_progress;
        public float elapsed_s;
        public float minimum_distance_m;
        public bool complete;
    }

    public int udp_port = 5006;
    public float state_timeout = 0.5f;

    public bool HasRecentState
    {
        get
        {
            return latest_right_arm_joints != null
                && Time.realtimeSinceStartup - latest_packet_time <= state_timeout;
        }
    }

    public bool IsTeleoperationActive { get; private set; }
    public float[] LatestRightArmJoints => latest_right_arm_joints;
    public Vector3 LatestWristOperatorDelta { get; private set; }
    public Vector3 LatestTargetOperatorDelta { get; private set; }
    public Vector3 LatestWristRobotPosition { get; private set; }
    public Vector3 LatestTargetRobotPosition { get; private set; }
    public float LatestPositionError { get; private set; }
    public float LatestOrientationErrorDegrees { get; private set; }
    public float LatestOrientationAssistGain { get; private set; }
    public float LatestOrientationCostScale { get; private set; }
    public float LatestWristLimitMarginDegrees { get; private set; }
    public bool IsWorkspaceLimited { get; private set; }
    public bool IsCollisionLimited { get; private set; }
    public bool HasMotionDiagnostics { get; private set; }
    public bool HasAbsoluteMinkPositions { get; private set; }
    public bool HasInspectionState { get; private set; }
    public string LatestInspectionState { get; private set; } = "waiting";
    public string LatestInspectionTargetSource { get; private set; } = "";
    public Vector3 LatestInspectionTargetRobotPosition { get; private set; }
    public Vector3 LatestInspectionToolTipRobotPosition { get; private set; }
    public Vector3 LatestInspectionPanelRobotPosition { get; private set; }
    public Vector3 LatestInspectionPanelHalfSize { get; private set; }
    public float LatestInspectionDistance { get; private set; }
    public float LatestInspectionHoldProgress { get; private set; }
    public float LatestInspectionElapsedSeconds { get; private set; }
    public bool IsInspectionComplete { get; private set; }
    public ulong StateRevision { get; private set; }

    private UdpClient udp_client;
    private IPEndPoint receive_endpoint;
    private float[] latest_right_arm_joints;
    private float latest_packet_time = float.NegativeInfinity;
    private bool state_timed_out = true;

    private void OnEnable()
    {
        OpenSocket();
    }

    private void Update()
    {
        if (udp_client == null)
        {
            return;
        }

        try
        {
            while (udp_client.Available > 0)
            {
                byte[] packet_data = udp_client.Receive(ref receive_endpoint);
                RobotStatePacket packet_value = JsonUtility.FromJson<RobotStatePacket>(
                    Encoding.UTF8.GetString(packet_data));
                if (packet_value == null
                    || packet_value.right_arm == null
                    || packet_value.right_arm.joints == null
                    || packet_value.right_arm.joints.Length < 7)
                {
                    continue;
                }

                latest_right_arm_joints = packet_value.right_arm.joints;
                IsTeleoperationActive = packet_value.right_arm.active;
                LatestPositionError = packet_value.right_arm.position_error;
                LatestOrientationErrorDegrees = packet_value.right_arm.orientation_error_deg;
                LatestOrientationAssistGain = packet_value.right_arm.orientation_assist_gain;
                LatestOrientationCostScale = packet_value.right_arm.orientation_cost_scale;
                LatestWristLimitMarginDegrees = packet_value.right_arm.min_wrist_limit_margin_deg;
                IsWorkspaceLimited = packet_value.right_arm.workspace_limited;
                IsCollisionLimited = packet_value.right_arm.collision_limited;

                HasMotionDiagnostics = HasVector(packet_value.right_arm.wrist_delta)
                    && HasVector(packet_value.right_arm.target_delta);
                if (HasMotionDiagnostics)
                {
                    LatestWristOperatorDelta = RobotToOperatorDelta(
                        packet_value.right_arm.wrist_delta);
                    LatestTargetOperatorDelta = RobotToOperatorDelta(
                        packet_value.right_arm.target_delta);
                }
                else
                {
                    LatestWristOperatorDelta = Vector3.zero;
                    LatestTargetOperatorDelta = Vector3.zero;
                }

                HasAbsoluteMinkPositions = HasVector(packet_value.right_arm.wrist_position)
                    && HasVector(packet_value.right_arm.target_position);
                if (HasAbsoluteMinkPositions)
                {
                    LatestWristRobotPosition = ToVector3(packet_value.right_arm.wrist_position);
                    LatestTargetRobotPosition = ToVector3(packet_value.right_arm.target_position);
                }
                else
                {
                    LatestWristRobotPosition = Vector3.zero;
                    LatestTargetRobotPosition = Vector3.zero;
                }

                HasInspectionState = packet_value.inspection != null
                    && HasVector(packet_value.inspection.target_position)
                    && HasVector(packet_value.inspection.tool_tip_position)
                    && HasVector(packet_value.inspection.panel_position)
                    && HasVector(packet_value.inspection.panel_half_size);
                if (HasInspectionState)
                {
                    LatestInspectionState = packet_value.inspection.state;
                    LatestInspectionTargetSource = packet_value.inspection.target_source;
                    LatestInspectionTargetRobotPosition = ToVector3(
                        packet_value.inspection.target_position);
                    LatestInspectionToolTipRobotPosition = ToVector3(
                        packet_value.inspection.tool_tip_position);
                    LatestInspectionPanelRobotPosition = ToVector3(
                        packet_value.inspection.panel_position);
                    LatestInspectionPanelHalfSize = ToVector3(
                        packet_value.inspection.panel_half_size);
                    LatestInspectionDistance = packet_value.inspection.distance_m;
                    LatestInspectionHoldProgress = Mathf.Clamp01(
                        packet_value.inspection.hold_progress);
                    LatestInspectionElapsedSeconds = packet_value.inspection.elapsed_s;
                    IsInspectionComplete = packet_value.inspection.complete;
                }
                else
                {
                    ResetInspectionState();
                }

                latest_packet_time = Time.realtimeSinceStartup;
                state_timed_out = false;
                StateRevision++;
            }
        }
        catch (SocketException exception_value)
        {
            if (exception_value.SocketErrorCode != SocketError.WouldBlock)
            {
                Debug.LogWarning("G1 robot-state UDP receive failed: " + exception_value.Message);
            }
        }
        catch (ObjectDisposedException)
        {
        }

        if (!state_timed_out
            && Time.realtimeSinceStartup - latest_packet_time > state_timeout)
        {
            ResetRuntimeState(false);
            state_timed_out = true;
        }
    }

    private void OnDisable()
    {
        CloseSocket();
    }

    private void OnDestroy()
    {
        CloseSocket();
    }

    private void OpenSocket()
    {
        CloseSocket();

        try
        {
            udp_client = new UdpClient();
            udp_client.Client.SetSocketOption(
                SocketOptionLevel.Socket,
                SocketOptionName.ReuseAddress,
                true);
            udp_client.Client.Bind(new IPEndPoint(IPAddress.Any, udp_port));
            udp_client.Client.Blocking = false;
            receive_endpoint = new IPEndPoint(IPAddress.Any, 0);
            Debug.Log("G1 robot-state UDP listening on port " + udp_port + ".");
        }
        catch (SocketException exception_value)
        {
            Debug.LogError("Could not open G1 robot-state UDP port "
                + udp_port + ": " + exception_value.Message);
            CloseSocket();
        }
    }

    private void CloseSocket()
    {
        if (udp_client != null)
        {
            udp_client.Close();
            udp_client = null;
        }

        ResetRuntimeState(true);
        StateRevision = 0;
        state_timed_out = true;
    }

    private void ResetRuntimeState(bool clear_joint_state)
    {
        IsTeleoperationActive = false;
        LatestWristOperatorDelta = Vector3.zero;
        LatestTargetOperatorDelta = Vector3.zero;
        LatestWristRobotPosition = Vector3.zero;
        LatestTargetRobotPosition = Vector3.zero;
        LatestPositionError = 0.0f;
        LatestOrientationErrorDegrees = 0.0f;
        LatestOrientationAssistGain = 0.0f;
        LatestOrientationCostScale = 1.0f;
        LatestWristLimitMarginDegrees = 0.0f;
        IsWorkspaceLimited = false;
        IsCollisionLimited = false;
        HasMotionDiagnostics = false;
        HasAbsoluteMinkPositions = false;
        ResetInspectionState();

        if (clear_joint_state)
        {
            latest_right_arm_joints = null;
            latest_packet_time = float.NegativeInfinity;
        }
    }

    private void ResetInspectionState()
    {
        HasInspectionState = false;
        LatestInspectionState = "waiting";
        LatestInspectionTargetSource = "";
        LatestInspectionTargetRobotPosition = Vector3.zero;
        LatestInspectionToolTipRobotPosition = Vector3.zero;
        LatestInspectionPanelRobotPosition = Vector3.zero;
        LatestInspectionPanelHalfSize = Vector3.zero;
        LatestInspectionDistance = 0.0f;
        LatestInspectionHoldProgress = 0.0f;
        LatestInspectionElapsedSeconds = 0.0f;
        IsInspectionComplete = false;
    }

    private static bool HasVector(float[] vector_value)
    {
        return vector_value != null && vector_value.Length >= 3;
    }

    private static Vector3 ToVector3(float[] value)
    {
        return new Vector3(value[0], value[1], value[2]);
    }

    private static Vector3 RobotToOperatorDelta(float[] robot_delta)
    {
        // MuJoCo G1: +X forward, +Y left, +Z up.
        // Unity operator: +X right, +Y up, +Z forward.
        return new Vector3(
            -robot_delta[1],
            robot_delta[2],
            robot_delta[0]);
    }
}
