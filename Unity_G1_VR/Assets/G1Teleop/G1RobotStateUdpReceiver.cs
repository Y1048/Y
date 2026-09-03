using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using Newtonsoft.Json;

/// <summary>
/// 지정된 UDP 포트에서 Mink 계산 상태 또는 실제 G1 읽기 전용 상태를 수신한다.
/// 최신 관절값, 손목/목표 오차, 제한 상태, 점검 데모 상태를 읽기 전용 속성으로
/// 제공하며 Unity 프리뷰나 로봇 명령을 직접 변경하지 않는다.
/// 연결: UDP 수신 -> 이 컴포넌트의 속성 -> G1UnityRightArmPreview/G1OfficialRig.
/// 관절각 단위는 rad다. 5006 계산 상태와 5010 실측/재생 상태를 서로 대체하지 않는다.
/// </summary>
public class G1RobotStateUdpReceiver : MonoBehaviour
{
    public const string MinkStateSource = "mink_simulation";
    public const string HardwareStateSource = "g1_lowstate_read_only";

    [Serializable]
    private class RightArmState
    {
        public float[] joints;
        public bool active;
        public float[] wrist_delta;
        public float[] target_delta;
        public float[] wrist_position;
        public float[] target_position;
        public float[] feasible_target_position;
        public float[] feasible_target_delta;
        public bool feasible_target_valid;
        public string feasible_target_status;
        public float position_error;
        public float orientation_error_deg;
        public float orientation_assist_gain;
        public float orientation_cost_scale;
        public float min_wrist_limit_margin_deg;
        public bool workspace_limited;
        public bool collision_limited;
    }

    [Serializable]
    private class BaseStatePacket
    {
        public bool valid;
        public string topic;
        public long received_packets;
        public float last_packet_age_s;
        public float[] position_m;
        public float[] quaternion_xyzw;
        public float[] velocity_mps;
        public float yaw_speed_rad_s;
    }

    [Serializable]
    private class MirrorDiagnosticsPacket
    {
        public float[] source_base_position_m;
        public float[] source_base_quaternion_xyzw;
        public float[] displayed_base_position_m;
        public float[] displayed_base_quaternion_xyzw;
        public float base_position_error_m;
        public float base_orientation_error_deg;
        public float max_joint_position_error_rad;
    }

    [Serializable]
    private class RobotStatePacket
    {
        public string state_source;
        public string session_id;
        public long sequence;
        public string[] all_joint_names;
        public float[] all_joint_q_rad;
        public float[] all_joint_dq_rad_s;
        public BaseStatePacket base_state;
        public MirrorDiagnosticsPacket mirror_diagnostics;
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
    public string expected_state_source = MinkStateSource;
    public bool accept_packets_without_source = true;

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
    public string[] LatestAllJointNames => latest_all_joint_names;
    public float[] LatestAllJointPositions => latest_all_joint_positions;
    public float[] LatestAllJointVelocities => latest_all_joint_velocities;
    public string LatestStateSource { get; private set; } = "";
    public string LatestSessionId { get; private set; } = "";
    public long LatestSequence { get; private set; }
    public bool HasFullBodyJointState
    {
        get
        {
            return latest_all_joint_names != null
                && latest_all_joint_positions != null
                && latest_all_joint_names.Length == 29
                && latest_all_joint_positions.Length == 29;
        }
    }
    public bool HasFullBodyVelocityState
    {
        get
        {
            return latest_all_joint_velocities != null
                && latest_all_joint_velocities.Length == 29;
        }
    }
    public bool HasBasePoseState
    {
        get
        {
            return has_valid_base_pose && HasRecentState;
        }
    }
    public Vector3 LatestBasePositionRobot { get; private set; }
    public Quaternion LatestBaseRotationRobot { get; private set; } = Quaternion.identity;
    public Vector3 LatestBaseVelocityRobot { get; private set; }
    public float LatestBaseYawSpeedRadiansPerSecond { get; private set; }
    public float LatestBasePacketAgeSeconds { get; private set; }
    public string LatestBaseStateTopic { get; private set; } = "";
    public bool HasMirrorDiagnostics { get; private set; }
    public Vector3 LatestSourceBasePositionRobot { get; private set; }
    public Quaternion LatestSourceBaseRotationRobot { get; private set; }
        = Quaternion.identity;
    public Vector3 LatestDisplayedBasePositionRobot { get; private set; }
    public Quaternion LatestDisplayedBaseRotationRobot { get; private set; }
        = Quaternion.identity;
    public float LatestSourceToMuJoCoPositionErrorMeters { get; private set; }
    public float LatestSourceToMuJoCoOrientationErrorDegrees { get; private set; }
    public float LatestSourceToMuJoCoMaxJointErrorRadians { get; private set; }
    public Vector3 LatestWristOperatorDelta { get; private set; }
    public Vector3 LatestTargetOperatorDelta { get; private set; }
    public Vector3 LatestWristRobotPosition { get; private set; }
    public Vector3 LatestTargetRobotPosition { get; private set; }
    public Vector3 LatestFeasibleTargetOperatorDelta { get; private set; }
    public bool HasFeasibleTarget { get; private set; }
    public string LatestFeasibleTargetStatus { get; private set; } = "unavailable";
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
    private string[] latest_all_joint_names;
    private float[] latest_all_joint_positions;
    private float[] latest_all_joint_velocities;
    private float latest_packet_time = float.NegativeInfinity;
    private bool state_timed_out = true;
    private bool full_body_contract_warning_reported;
    private bool base_state_contract_warning_reported;
    private bool mirror_diagnostics_contract_warning_reported;
    private bool source_contract_warning_reported;
    private bool has_valid_base_pose;
    private bool json_contract_warning_reported;

    private static readonly JsonSerializerSettings packet_json_settings = new JsonSerializerSettings
    {
        TypeNameHandling = TypeNameHandling.None,
        MaxDepth = 32
    };

    private static RobotStatePacket ParseStatePacket(string packet_json)
    {
        // 누락된 선택 객체는 null이어야 한다. 빈 몸체 정보로 만들어 검사하면
        // 정상적인 팔 전용 MuJoCo 패킷까지 거부되어 프리뷰가 멈춘다.
        return JsonConvert.DeserializeObject<RobotStatePacket>(packet_json, packet_json_settings);
    }

    private void OnEnable()
    {
        OpenSocket();
    }

    private void Update()
    {
        // 한 프레임에 여러 패킷이 쌓였으면 가장 최신 상태까지 모두 비운다.
        // Unity 오브젝트 갱신은 메인 스레드의 이 메서드에서만 수행한다.
        if (udp_client == null)
        {
            return;
        }

        try
        {
            while (udp_client.Available > 0)
            {
                byte[] packet_data = udp_client.Receive(ref receive_endpoint);
                RobotStatePacket packet_value;
                try
                {
                    packet_value = ParseStatePacket(Encoding.UTF8.GetString(packet_data));
                    json_contract_warning_reported = false;
                }
                catch (JsonException exception_value)
                {
                    if (!json_contract_warning_reported)
                    {
                        Debug.LogWarning("Rejected malformed G1 state JSON on UDP "
                            + udp_port + ": " + exception_value.Message);
                        json_contract_warning_reported = true;
                    }
                    continue;
                }
                if (packet_value == null
                    || packet_value.right_arm == null
                    || packet_value.right_arm.joints == null
                    || packet_value.right_arm.joints.Length < 7)
                {
                    continue;
                }

                bool has_full_body_fields = packet_value.all_joint_names != null
                    || packet_value.all_joint_q_rad != null
                    || packet_value.all_joint_dq_rad_s != null;
                bool has_valid_full_body = HasFullBodyVector(packet_value);
                if (has_full_body_fields && !has_valid_full_body)
                {
                    if (!full_body_contract_warning_reported)
                    {
                        Debug.LogWarning(
                            "Rejected G1 state packet with an invalid 29-joint contract.");
                        full_body_contract_warning_reported = true;
                    }
                    continue;
                }

                bool has_base_state = packet_value.base_state != null;
                bool has_valid_base_contract = HasValidBaseState(
                    packet_value.base_state);
                if (has_base_state && !has_valid_base_contract)
                {
                    if (!base_state_contract_warning_reported)
                    {
                        Debug.LogWarning(
                            "Rejected G1 state packet with an invalid base-state contract on UDP "
                            + udp_port + ".");
                        base_state_contract_warning_reported = true;
                    }
                    continue;
                }

                bool has_mirror_diagnostics = packet_value.mirror_diagnostics != null;
                if (has_mirror_diagnostics
                    && !HasValidMirrorDiagnostics(packet_value.mirror_diagnostics))
                {
                    if (!mirror_diagnostics_contract_warning_reported)
                    {
                        Debug.LogWarning(
                            "Rejected G1 state packet with invalid mirror diagnostics.");
                        mirror_diagnostics_contract_warning_reported = true;
                    }
                    continue;
                }

                if (!MatchesExpectedSource(packet_value))
                {
                    if (!source_contract_warning_reported)
                    {
                        Debug.LogWarning(
                            "Rejected G1 state packet from unexpected source on UDP "
                            + udp_port + ". Expected " + expected_state_source + ".");
                        source_contract_warning_reported = true;
                    }
                    continue;
                }

                latest_right_arm_joints = packet_value.right_arm.joints;
                if (has_valid_full_body)
                {
                    latest_all_joint_names = packet_value.all_joint_names;
                    latest_all_joint_positions = packet_value.all_joint_q_rad;
                    latest_all_joint_velocities = packet_value.all_joint_dq_rad_s;
                    full_body_contract_warning_reported = false;
                }
                else
                {
                    latest_all_joint_names = null;
                    latest_all_joint_positions = null;
                    latest_all_joint_velocities = null;
                    full_body_contract_warning_reported = false;
                }
                if (has_base_state)
                {
                    ApplyBaseState(packet_value.base_state);
                    base_state_contract_warning_reported = false;
                }
                else
                {
                    ResetBaseState();
                }
                if (has_mirror_diagnostics)
                {
                    ApplyMirrorDiagnostics(packet_value.mirror_diagnostics);
                    mirror_diagnostics_contract_warning_reported = false;
                }
                else
                {
                    ResetMirrorDiagnostics();
                }
                LatestStateSource = string.IsNullOrEmpty(packet_value.state_source)
                    ? "legacy_unspecified"
                    : packet_value.state_source;
                LatestSessionId = packet_value.session_id ?? "";
                LatestSequence = packet_value.sequence;
                source_contract_warning_reported = false;
                IsTeleoperationActive = packet_value.right_arm.active;
                LatestPositionError = packet_value.right_arm.position_error;
                LatestOrientationErrorDegrees = packet_value.right_arm.orientation_error_deg;
                LatestOrientationAssistGain = packet_value.right_arm.orientation_assist_gain;
                LatestOrientationCostScale = packet_value.right_arm.orientation_cost_scale;
                LatestWristLimitMarginDegrees = packet_value.right_arm.min_wrist_limit_margin_deg;
                IsWorkspaceLimited = packet_value.right_arm.workspace_limited;
                IsCollisionLimited = packet_value.right_arm.collision_limited;
                HasFeasibleTarget = packet_value.right_arm.feasible_target_valid
                    && HasFiniteVector(packet_value.right_arm.feasible_target_position)
                    && HasFiniteVector(packet_value.right_arm.feasible_target_delta);
                LatestFeasibleTargetOperatorDelta = HasFeasibleTarget
                    ? RobotToOperatorDelta(packet_value.right_arm.feasible_target_delta)
                    : Vector3.zero;
                LatestFeasibleTargetStatus = packet_value.right_arm.feasible_target_status
                    ?? "unavailable";

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
        full_body_contract_warning_reported = false;
        base_state_contract_warning_reported = false;
        mirror_diagnostics_contract_warning_reported = false;
        source_contract_warning_reported = false;
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
        HasFeasibleTarget = false;
        LatestFeasibleTargetOperatorDelta = Vector3.zero;
        LatestFeasibleTargetStatus = "unavailable";
        ResetBaseState();
        ResetMirrorDiagnostics();
        ResetInspectionState();

        if (clear_joint_state)
        {
            latest_right_arm_joints = null;
            latest_all_joint_names = null;
            latest_all_joint_positions = null;
            latest_all_joint_velocities = null;
            latest_packet_time = float.NegativeInfinity;
        }
        LatestStateSource = "";
        LatestSessionId = "";
        LatestSequence = 0;
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

    private void ApplyBaseState(BaseStatePacket base_state)
    {
        has_valid_base_pose = base_state.valid;
        LatestBaseStateTopic = base_state.topic ?? "";
        LatestBasePacketAgeSeconds = base_state.last_packet_age_s;
        LatestBasePositionRobot = ToVector3(base_state.position_m);
        LatestBaseRotationRobot = new Quaternion(
            base_state.quaternion_xyzw[0],
            base_state.quaternion_xyzw[1],
            base_state.quaternion_xyzw[2],
            base_state.quaternion_xyzw[3]).normalized;
        LatestBaseVelocityRobot = ToVector3(base_state.velocity_mps);
        LatestBaseYawSpeedRadiansPerSecond = base_state.yaw_speed_rad_s;
    }

    private void ResetBaseState()
    {
        has_valid_base_pose = false;
        LatestBasePositionRobot = Vector3.zero;
        LatestBaseRotationRobot = Quaternion.identity;
        LatestBaseVelocityRobot = Vector3.zero;
        LatestBaseYawSpeedRadiansPerSecond = 0.0f;
        LatestBasePacketAgeSeconds = 0.0f;
        LatestBaseStateTopic = "";
    }

    private void ApplyMirrorDiagnostics(MirrorDiagnosticsPacket diagnostics)
    {
        HasMirrorDiagnostics = true;
        LatestSourceBasePositionRobot = ToVector3(
            diagnostics.source_base_position_m);
        LatestSourceBaseRotationRobot = ToQuaternion(
            diagnostics.source_base_quaternion_xyzw);
        LatestDisplayedBasePositionRobot = ToVector3(
            diagnostics.displayed_base_position_m);
        LatestDisplayedBaseRotationRobot = ToQuaternion(
            diagnostics.displayed_base_quaternion_xyzw);
        LatestSourceToMuJoCoPositionErrorMeters =
            diagnostics.base_position_error_m;
        LatestSourceToMuJoCoOrientationErrorDegrees =
            diagnostics.base_orientation_error_deg;
        LatestSourceToMuJoCoMaxJointErrorRadians =
            diagnostics.max_joint_position_error_rad;
    }

    private void ResetMirrorDiagnostics()
    {
        HasMirrorDiagnostics = false;
        LatestSourceBasePositionRobot = Vector3.zero;
        LatestSourceBaseRotationRobot = Quaternion.identity;
        LatestDisplayedBasePositionRobot = Vector3.zero;
        LatestDisplayedBaseRotationRobot = Quaternion.identity;
        LatestSourceToMuJoCoPositionErrorMeters = 0.0f;
        LatestSourceToMuJoCoOrientationErrorDegrees = 0.0f;
        LatestSourceToMuJoCoMaxJointErrorRadians = 0.0f;
    }

    private static bool HasVector(float[] vector_value)
    {
        return vector_value != null && vector_value.Length >= 3;
    }

    private static bool HasFiniteVector(float[] vector_value)
    {
        if (!HasVector(vector_value))
        {
            return false;
        }
        for (int component_index = 0; component_index < 3; component_index++)
        {
            if (float.IsNaN(vector_value[component_index])
                || float.IsInfinity(vector_value[component_index]))
            {
                return false;
            }
        }
        return true;
    }

    private static bool HasFullBodyVector(RobotStatePacket packet_value)
    {
        if (packet_value.all_joint_names == null
            || packet_value.all_joint_q_rad == null
            || !G1OfficialRig.MatchesFullBodyJointContract(packet_value.all_joint_names)
            || packet_value.all_joint_q_rad.Length != 29)
        {
            return false;
        }

        for (int joint_index = 0; joint_index < packet_value.all_joint_names.Length;
            joint_index++)
        {
            if (string.IsNullOrEmpty(packet_value.all_joint_names[joint_index])
                || float.IsNaN(packet_value.all_joint_q_rad[joint_index])
                || float.IsInfinity(packet_value.all_joint_q_rad[joint_index]))
            {
                return false;
            }

            if (packet_value.all_joint_dq_rad_s != null
                && (packet_value.all_joint_dq_rad_s.Length != 29
                    || float.IsNaN(packet_value.all_joint_dq_rad_s[joint_index])
                    || float.IsInfinity(packet_value.all_joint_dq_rad_s[joint_index])))
            {
                return false;
            }
        }
        return true;
    }

    private static bool HasValidBaseState(BaseStatePacket base_state)
    {
        if (base_state == null
            || base_state.topic != "rt/odommodestate"
            || base_state.received_packets < 0
            || !HasExactFiniteVector(base_state.position_m, 3)
            || !HasExactFiniteVector(base_state.quaternion_xyzw, 4)
            || !HasExactFiniteVector(base_state.velocity_mps, 3)
            || !IsFinite(base_state.last_packet_age_s)
            || base_state.last_packet_age_s < 0.0f
            || !IsFinite(base_state.yaw_speed_rad_s))
        {
            return false;
        }

        return HasNormalizedQuaternion(base_state.quaternion_xyzw);
    }

    private static bool HasValidMirrorDiagnostics(
        MirrorDiagnosticsPacket diagnostics)
    {
        return diagnostics != null
            && HasExactFiniteVector(diagnostics.source_base_position_m, 3)
            && HasNormalizedQuaternion(
                diagnostics.source_base_quaternion_xyzw)
            && HasExactFiniteVector(diagnostics.displayed_base_position_m, 3)
            && HasNormalizedQuaternion(
                diagnostics.displayed_base_quaternion_xyzw)
            && IsFinite(diagnostics.base_position_error_m)
            && diagnostics.base_position_error_m >= 0.0f
            && IsFinite(diagnostics.base_orientation_error_deg)
            && diagnostics.base_orientation_error_deg >= 0.0f
            && IsFinite(diagnostics.max_joint_position_error_rad)
            && diagnostics.max_joint_position_error_rad >= 0.0f;
    }

    private static bool HasNormalizedQuaternion(float[] quaternion_value)
    {
        if (!HasExactFiniteVector(quaternion_value, 4))
        {
            return false;
        }
        float quaternion_norm = Mathf.Sqrt(
            quaternion_value[0] * quaternion_value[0]
            + quaternion_value[1] * quaternion_value[1]
            + quaternion_value[2] * quaternion_value[2]
            + quaternion_value[3] * quaternion_value[3]);
        return Mathf.Abs(quaternion_norm - 1.0f) <= 0.001f;
    }

    private static bool HasExactFiniteVector(float[] vector_value, int length)
    {
        if (vector_value == null || vector_value.Length != length)
        {
            return false;
        }
        for (int index = 0; index < vector_value.Length; index++)
        {
            if (!IsFinite(vector_value[index]))
            {
                return false;
            }
        }
        return true;
    }

    private static bool IsFinite(float value)
    {
        return !float.IsNaN(value) && !float.IsInfinity(value);
    }

    private bool MatchesExpectedSource(RobotStatePacket packet_value)
    {
        // 실측 전용 포트는 Inspector 설정이 잘못되어도 시뮬레이션을 허용하지 않는다.
        return IsExpectedSource(
            udp_port == 5010 ? HardwareStateSource : expected_state_source,
            udp_port != 5010 && accept_packets_without_source,
            packet_value.state_source);
    }

    public static bool IsExpectedSource(string expected_source, bool legacy_allowed, string packet_source)
    {
        if (string.IsNullOrEmpty(expected_source))
        {
            return true;
        }
        if (packet_source == expected_source)
        {
            return true;
        }
        return legacy_allowed && string.IsNullOrEmpty(packet_source);
    }

    private static Vector3 ToVector3(float[] value)
    {
        return new Vector3(value[0], value[1], value[2]);
    }

    private static Quaternion ToQuaternion(float[] value)
    {
        return new Quaternion(value[0], value[1], value[2], value[3]).normalized;
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
