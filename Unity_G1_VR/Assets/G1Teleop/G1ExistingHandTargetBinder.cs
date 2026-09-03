using UnityEngine;
using UnityEngine.Serialization;

/// <summary>
/// Quest 오른손 추적 자세를 G1 텔레오퍼레이션의 상대 손목 목표로 변환한다.
/// 손목 소스 선택, 머리 yaw 기준 좌표계, engage 정렬/유지, 중립 자세 보정을
/// 담당하며 UDP 송신, IK 계산, 관절 명령 생성은 담당하지 않는다.
/// </summary>
public class G1ExistingHandTargetBinder : MonoBehaviour
{
    public Transform source_hand;
    public Transform target_transform;
    public Transform reference_transform;
    public G1HeadLockedCamera head_camera_alignment;
    public OVRHand ovr_hand;
    public OVRSkeleton ovr_skeleton;
    public bool prefer_skeleton_wrist = true;
    public bool use_anatomical_hand_frame = true;
    public bool use_palm_center = false;
    public bool require_tracked_hand = true;
    public bool apply_position = true;
    public bool apply_rotation = true;
    public bool auto_calibrate_on_first_track = true;
    public bool require_alignment_to_engage = true;
    public bool require_orientation_alignment_to_engage = false;
    public bool use_reference_yaw = true;
    [FormerlySerializedAs("neutral_target_position")]
    public Vector3 preview_neutral_offset = new Vector3(0.22f, -0.24f, 0.48f);
    public Vector3 movement_scale = Vector3.one;
    public Vector3 position_offset = Vector3.zero;
    [Range(0.01f, 1.0f)]
    public float position_smoothing = 1.00f;
    public float auto_calibration_delay = 0.35f;
    public float engagement_distance = 0.10f;
    public float engagement_orientation_tolerance_degrees = 30.0f;
    public float engagement_hold_duration = 0.55f;
    public float engagement_position_stability = 0.025f;
    public float engagement_rotation_stability_degrees = 16.0f;
    public float engagement_frame_initialization_delay = 0.25f;
    public float tracked_wrist_max_speed_mps = 1.10f;
    public float tracked_wrist_min_step_allowance = 0.020f;
    public float body_translation_minimum_step = 0.0005f;
    public float body_translation_direction_cosine = 0.85f;
    public float body_translation_magnitude_ratio_minimum = 0.55f;
    public float body_translation_residual_tolerance = 0.012f;

    public bool IsTrackingValid { get; private set; }
    public bool IsCalibrated { get; private set; }
    public Vector3 OperatorTargetDelta { get; private set; }
    public Quaternion OperatorHandRotation { get; private set; } = Quaternion.identity;
    public Quaternion MappedHandRotation { get; private set; } = Quaternion.identity;
    public Vector3 OperatorOrigin { get; private set; }
    public Quaternion OperatorHeading { get; private set; } = Quaternion.identity;
    public Vector3 TrackedWristPosition { get; private set; }
    public Vector3 TrackedHandPosition { get; private set; }
    public Quaternion TrackedWristRotation { get; private set; } = Quaternion.identity;
    public Vector3 CalibratedWristPosition { get; private set; }
    public Quaternion CalibratedWristRotation { get; private set; } = Quaternion.identity;
    public bool IsUsingSkeletonWrist { get; private set; }
    public bool IsAnatomicalFrameValid { get; private set; }
    public bool IsAlignmentReady { get; private set; }
    public float AlignmentPositionError { get; private set; }
    public float AlignmentOrientationErrorDegrees { get; private set; }
    public bool IsEngagementFrameLocked { get; private set; }
    public float EngagementProgress { get; private set; }
    public Vector3 EngagementTargetPosition { get; private set; }
    public Quaternion EngagementTargetRotation { get; private set; } = Quaternion.identity;
    public string EngagementState { get; private set; } = "initializing";
    public Vector3 BodyCompensatedTrackingDelta { get; private set; }
    public Vector3 EstimatedBodyTranslation { get; private set; }
    public bool HasBodyTranslationCompensation { get; private set; }
    public Vector3 TrackedHeadPosition { get; private set; }
    public Quaternion TrackedHeadRotation { get; private set; } = Quaternion.identity;
    public float TrackedHeadAngularSpeedDegrees { get; private set; }
    public bool IsHeadMotionHold { get; private set; }
    public Vector3 CalibratedHeadPosition { get; private set; }
    public bool IsTrackedPosePlausible { get; private set; } = true;
    public float TrackedWristSpeedMPS { get; private set; }

    private float log_timer;
    private float tracked_duration;
    private float engagement_frame_initialization_duration;
    private Vector3 neutral_wrist_position;
    private Quaternion neutral_hand_rotation = Quaternion.identity;
    private Quaternion neutral_target_rotation = Quaternion.identity;
    private Vector3 alignment_reference_position;
    private Quaternion alignment_reference_rotation = Quaternion.identity;
    private bool alignment_reference_initialized;
    private Quaternion engagement_target_local_rotation = Quaternion.identity;
    private Transform tracked_wrist_transform;
    private Transform middle_finger_base_transform;
    private Transform index_finger_base_transform;
    private Transform pinky_finger_base_transform;
    private Vector3 neutral_head_position;
    private Vector3 previous_body_tracking_wrist_position;
    private Vector3 previous_body_tracking_head_position;
    private bool body_tracking_initialized;
    private Vector3 last_accepted_wrist_position;
    private bool accepted_wrist_position_initialized;
    private bool tracked_pose_outlier_latched;
    private Quaternion previous_tracked_head_rotation = Quaternion.identity;
    private bool tracked_head_rotation_initialized;

    private void Awake()
    {
        if (target_transform == null)
        {
            target_transform = transform;
        }
    }

    private void LateUpdate()
    {
        if (source_hand == null || target_transform == null)
        {
            IsTrackingValid = false;
            EngagementState = "missing-reference";
            return;
        }

        UpdateTrackedHead();
        UpdateTrackedWrist();

        UpdateEngagementFrame();

        if (!IsCalibrated)
        {
            UpdateEngagementTargetPose();
        }

        IsTrackingValid = GetHandTracked();
        UpdateHeadMotionDiagnostics();
        if (IsTrackingValid)
        {
            IsTrackingValid = UpdateTrackedPosePlausibility();
        }
        else
        {
            IsTrackedPosePlausible = false;
            TrackedWristSpeedMPS = 0.0f;
        }
        if (!IsTrackingValid)
        {
            if (IsCalibrated)
            {
                // 순간적인 손 추적 손실 동안에는 마지막 유효 목표를 유지한다.
                // 손실이 계속되면 UDP sender가 캘리브레이션을 해제하며 기준점은 바꾸지 않는다.
                IsAlignmentReady = true;
                EngagementProgress = 1.0f;
                EngagementState = "active-hold-tracking-unavailable";
            }
            else
            {
                tracked_duration = 0.0f;
                IsAlignmentReady = false;
                AlignmentPositionError = float.PositiveInfinity;
                AlignmentOrientationErrorDegrees = float.PositiveInfinity;
                EngagementProgress = 0.0f;
                EngagementState = "tracking-unavailable";
                alignment_reference_initialized = false;
            }

            LogStatus(false);
            return;
        }

        if (!IsCalibrated)
        {
            UpdateEngagementState();
        }

        if (!IsCalibrated)
        {
            LogStatus(false);
            return;
        }

        UpdateOperatorTarget();

        if (apply_position)
        {
            Vector3 local_target = preview_neutral_offset + position_offset + OperatorTargetDelta;
            target_transform.position = OperatorOrigin + OperatorHeading * local_target;
        }

        if (apply_rotation)
        {
            target_transform.rotation = MappedHandRotation;
        }

        LogStatus(true);
    }

    public void Calibrate()
    {
        if (tracked_wrist_transform == null || !IsTrackingValid)
        {
            return;
        }

        if (!IsEngagementFrameLocked)
        {
            CaptureEngagementFrame();
        }

        // engage 순간의 실제 손목과 로봇 목표를 각각 중립점으로 저장한다.
        // 이후에는 두 절대 위치가 아니라 중립점에서의 상대 이동량만 사용한다.
        neutral_wrist_position = TrackedWristPosition;
        neutral_head_position = TrackedHeadPosition;
        neutral_hand_rotation = TrackedWristRotation;
        CalibratedWristPosition = neutral_wrist_position;
        CalibratedHeadPosition = neutral_head_position;
        CalibratedWristRotation = neutral_hand_rotation;
        OperatorTargetDelta = Vector3.zero;
        BodyCompensatedTrackingDelta = Vector3.zero;
        EstimatedBodyTranslation = Vector3.zero;
        HasBodyTranslationCompensation = reference_transform != null;
        previous_body_tracking_wrist_position = TrackedWristPosition;
        previous_body_tracking_head_position = TrackedHeadPosition;
        body_tracking_initialized = reference_transform != null;
        ResetHeadMotionDiagnostics();
        OperatorHandRotation = Quaternion.identity;
        neutral_target_rotation = EngagementTargetRotation;
        MappedHandRotation = neutral_target_rotation;
        IsCalibrated = true;
        AcceptCurrentTrackedPose();
        IsAlignmentReady = true;
        AlignmentPositionError = 0.0f;
        AlignmentOrientationErrorDegrees = 0.0f;
        EngagementProgress = 1.0f;
        EngagementState = "active";

        Vector3 local_target = preview_neutral_offset + position_offset;
        target_transform.position = OperatorOrigin + OperatorHeading * local_target;
        target_transform.rotation = EngagementTargetRotation;
        Debug.Log("G1 right hand calibrated to the headset forward frame.");
    }

    public void ResetCalibration()
    {
        IsCalibrated = false;
        tracked_duration = 0.0f;
        OperatorTargetDelta = Vector3.zero;
        BodyCompensatedTrackingDelta = Vector3.zero;
        EstimatedBodyTranslation = Vector3.zero;
        HasBodyTranslationCompensation = false;
        CalibratedHeadPosition = Vector3.zero;
        OperatorHandRotation = Quaternion.identity;
        MappedHandRotation = EngagementTargetRotation;
        neutral_target_rotation = EngagementTargetRotation;
        IsAlignmentReady = false;
        AlignmentPositionError = float.PositiveInfinity;
        AlignmentOrientationErrorDegrees = float.PositiveInfinity;
        EngagementProgress = 0.0f;
        EngagementState = "waiting-position";
        alignment_reference_initialized = false;
        body_tracking_initialized = false;
        accepted_wrist_position_initialized = false;
        tracked_pose_outlier_latched = false;
        ResetHeadMotionDiagnostics();
        IsTrackedPosePlausible = true;
        TrackedWristSpeedMPS = 0.0f;
    }

    public void RecenterEngagementFrame()
    {
        ResetCalibration();
        IsEngagementFrameLocked = false;
        engagement_frame_initialization_duration = 0.0f;
    }

    public void SetEngagementTargetPosition(Vector3 world_position)
    {
        SetEngagementTargetPose(world_position, EngagementTargetRotation);
    }

    public void SetEngagementTargetPose(
        Vector3 world_position,
        Quaternion world_rotation)
    {
        if (!IsEngagementFrameLocked || IsCalibrated)
        {
            return;
        }

        preview_neutral_offset = Quaternion.Inverse(OperatorHeading)
            * (world_position - OperatorOrigin)
            - position_offset;
        engagement_target_local_rotation = Quaternion.Inverse(OperatorHeading)
            * world_rotation;
        UpdateEngagementTargetPose();
    }

    private void UpdateEngagementTargetPose()
    {
        if (!IsEngagementFrameLocked)
        {
            return;
        }

        Vector3 local_target = preview_neutral_offset + position_offset;
        EngagementTargetPosition = OperatorOrigin + OperatorHeading * local_target;
        EngagementTargetRotation = OperatorHeading
            * engagement_target_local_rotation;
        target_transform.position = EngagementTargetPosition;
        target_transform.rotation = EngagementTargetRotation;
    }

    private void UpdateEngagementFrame()
    {
        if (IsEngagementFrameLocked)
        {
            return;
        }

        if (head_camera_alignment == null
            || !head_camera_alignment.IsHeadTrackingReady)
        {
            engagement_frame_initialization_duration = 0.0f;
            EngagementState = "waiting-for-head-tracking";
            return;
        }

        engagement_frame_initialization_duration += Time.deltaTime;
        if (engagement_frame_initialization_duration < engagement_frame_initialization_delay)
        {
            return;
        }

        CaptureEngagementFrame();
    }

    private void CaptureEngagementFrame()
    {
        // 방 안의 절대 좌표가 아니라 캡처 시점의 머리 위치와 yaw를 기준으로 고정한다.
        // 고개를 돌려도 이미 engage된 팔 목표가 같이 회전하지 않도록 하는 기준 프레임이다.
        OperatorOrigin = reference_transform == null ? Vector3.zero : reference_transform.position;
        OperatorHeading = GetReferenceYawRotation();
        IsEngagementFrameLocked = true;
        UpdateEngagementTargetPose();
        Debug.Log("G1 engagement frame locked in world coordinates.");
    }

    private void UpdateEngagementState()
    {
        AlignmentPositionError = Vector3.Distance(
            TrackedWristPosition,
            EngagementTargetPosition);
        AlignmentOrientationErrorDegrees = Quaternion.Angle(
            TrackedWristRotation,
            EngagementTargetRotation);
        bool position_aligned = AlignmentPositionError <= engagement_distance;
        bool orientation_aligned = !require_orientation_alignment_to_engage
            || AlignmentOrientationErrorDegrees
                <= engagement_orientation_tolerance_degrees;
        IsAlignmentReady = GetAlignmentReady(
            require_alignment_to_engage,
            require_orientation_alignment_to_engage,
            AlignmentPositionError,
            engagement_distance,
            AlignmentOrientationErrorDegrees,
            engagement_orientation_tolerance_degrees);

        if (!position_aligned)
        {
            EngagementState = "waiting-position";
        }
        else if (!orientation_aligned)
        {
            EngagementState = "waiting-orientation";
        }
        else
        {
            EngagementState = "hold-still";
        }

        if (IsAlignmentReady)
        {
            // 목표 근처에 있는 것만으로 engage하지 않고, 손이 안정적으로 유지된 시간까지
            // 확인해 우연한 교차나 추적 노이즈로 인한 오작동을 줄인다.
            if (!alignment_reference_initialized)
            {
                alignment_reference_position = TrackedWristPosition;
                alignment_reference_rotation = TrackedWristRotation;
                alignment_reference_initialized = true;
                tracked_duration = 0.0f;
            }

            float position_change = Vector3.Distance(
                alignment_reference_position,
                TrackedWristPosition);
            float rotation_change = Quaternion.Angle(
                alignment_reference_rotation,
                TrackedWristRotation);
            bool hand_is_stable = position_change <= engagement_position_stability
                && rotation_change <= engagement_rotation_stability_degrees;
            if (hand_is_stable)
            {
                tracked_duration += Time.deltaTime;
            }
            else
            {
                alignment_reference_position = TrackedWristPosition;
                alignment_reference_rotation = TrackedWristRotation;
                tracked_duration = 0.0f;
            }
        }
        else
        {
            tracked_duration = 0.0f;
            alignment_reference_initialized = false;
        }

        float hold_duration = require_alignment_to_engage
            ? engagement_hold_duration
            : auto_calibration_delay;
        EngagementProgress = Mathf.Clamp01(
            tracked_duration / Mathf.Max(0.01f, hold_duration));

        if (auto_calibrate_on_first_track && EngagementProgress >= 1.0f)
        {
            Calibrate();
        }
    }

    public static bool GetAlignmentReady(
        bool require_alignment_value,
        bool require_orientation_value,
        float position_error_value,
        float position_tolerance_value,
        float orientation_error_value,
        float orientation_tolerance_value)
    {
        if (!require_alignment_value)
        {
            return true;
        }

        bool position_aligned = position_error_value <= position_tolerance_value;
        bool orientation_aligned = !require_orientation_value
            || orientation_error_value <= orientation_tolerance_value;
        return position_aligned && orientation_aligned;
    }

    private void UpdateOperatorTarget()
    {
        // 머리 이동을 무조건 빼면 고개만 움직여도 반대 방향의 팔 명령이 생긴다.
        // 손목과 머리가 같은 방향과 비슷한 거리로 움직인 프레임만 몸 이동으로 누적한다.
        Vector3 hand_delta;
        if (reference_transform != null)
        {
            if (!body_tracking_initialized)
            {
                previous_body_tracking_wrist_position = TrackedWristPosition;
                previous_body_tracking_head_position = TrackedHeadPosition;
                body_tracking_initialized = true;
            }

            Vector3 wrist_step = TrackedWristPosition
                - previous_body_tracking_wrist_position;
            Vector3 head_step = TrackedHeadPosition
                - previous_body_tracking_head_position;
            EstimatedBodyTranslation += GetCommonBodyTranslationStep(
                wrist_step,
                head_step,
                body_translation_minimum_step,
                body_translation_direction_cosine,
                body_translation_magnitude_ratio_minimum,
                body_translation_residual_tolerance);
            previous_body_tracking_wrist_position = TrackedWristPosition;
            previous_body_tracking_head_position = TrackedHeadPosition;

            hand_delta = CalculateBodyCompensatedTrackingDelta(
                TrackedWristPosition,
                neutral_wrist_position,
                EstimatedBodyTranslation);
            BodyCompensatedTrackingDelta = hand_delta;
            HasBodyTranslationCompensation = true;
        }
        else
        {
            hand_delta = TrackedWristPosition - neutral_wrist_position;
            BodyCompensatedTrackingDelta = hand_delta;
            HasBodyTranslationCompensation = false;
        }

        Vector3 local_delta = Quaternion.Inverse(OperatorHeading) * hand_delta;
        Vector3 scaled_delta = Vector3.Scale(local_delta, movement_scale);
        OperatorTargetDelta = Vector3.Lerp(
            OperatorTargetDelta,
            scaled_delta,
            Mathf.Clamp01(position_smoothing));

        Quaternion hand_rotation_delta = TrackedWristRotation
            * Quaternion.Inverse(neutral_hand_rotation);
        OperatorHandRotation = hand_rotation_delta;
        MappedHandRotation = hand_rotation_delta * neutral_target_rotation;
    }

    private void UpdateTrackedWrist()
    {
        IsAnatomicalFrameValid = false;
        Transform resolved_transform = GetSkeletonWristTransform();
        if (resolved_transform == null)
        {
            resolved_transform = source_hand;
        }

        if (tracked_wrist_transform == null
            || (!IsCalibrated && tracked_wrist_transform != resolved_transform))
        {
            tracked_wrist_transform = resolved_transform;
            IsUsingSkeletonWrist = tracked_wrist_transform != null
                && tracked_wrist_transform != source_hand;
        }

        if (tracked_wrist_transform == null)
        {
            return;
        }

        Vector3 current_wrist_position = tracked_wrist_transform.position;
        TrackedWristPosition = current_wrist_position;
        Quaternion current_wrist_rotation = GetAnatomicalHandRotation(
            tracked_wrist_transform.rotation);
        TrackedWristRotation = current_wrist_rotation;
        TrackedHandPosition = GetPalmCenterPosition();
    }

    private void UpdateTrackedHead()
    {
        TrackedHeadPosition = reference_transform == null
            ? Vector3.zero
            : reference_transform.position;
        TrackedHeadRotation = reference_transform == null
            ? Quaternion.identity
            : reference_transform.rotation;
    }

    private void UpdateHeadMotionDiagnostics()
    {
        float safe_delta_time = Mathf.Max(Time.unscaledDeltaTime, 1.0f / 120.0f);
        if (!tracked_head_rotation_initialized)
        {
            previous_tracked_head_rotation = TrackedHeadRotation;
            tracked_head_rotation_initialized = true;
            TrackedHeadAngularSpeedDegrees = 0.0f;
            IsHeadMotionHold = false;
            return;
        }

        TrackedHeadAngularSpeedDegrees = Quaternion.Angle(
            previous_tracked_head_rotation,
            TrackedHeadRotation) / safe_delta_time;
        previous_tracked_head_rotation = TrackedHeadRotation;
        // 머리 각속도는 원인 분석용으로만 기록한다. Quest의 작은 HMD 회전을
        // 손 추적 손실로 취급하면 정상 IK 명령이 반복해서 차단된다.
        IsHeadMotionHold = false;
    }

    private void ResetHeadMotionDiagnostics()
    {
        IsHeadMotionHold = false;
        TrackedHeadAngularSpeedDegrees = 0.0f;
        previous_tracked_head_rotation = TrackedHeadRotation;
        tracked_head_rotation_initialized = reference_transform != null;
    }

    public static Vector3 CalculateBodyCompensatedTrackingDelta(
        Vector3 current_wrist_position,
        Vector3 neutral_wrist_position_value,
        Vector3 estimated_body_translation)
    {
        return current_wrist_position
            - neutral_wrist_position_value
            - estimated_body_translation;
    }

    public static Vector3 GetCommonBodyTranslationStep(
        Vector3 wrist_step,
        Vector3 head_step,
        float minimum_step,
        float direction_cosine_threshold,
        float magnitude_ratio_minimum,
        float residual_tolerance)
    {
        float wrist_distance = wrist_step.magnitude;
        float head_distance = head_step.magnitude;
        float safe_minimum_step = Mathf.Max(0.0f, minimum_step);
        if (wrist_distance < safe_minimum_step
            || head_distance < safe_minimum_step)
        {
            return Vector3.zero;
        }

        float magnitude_ratio = Mathf.Min(wrist_distance, head_distance)
            / Mathf.Max(wrist_distance, head_distance);
        if (magnitude_ratio < Mathf.Clamp01(magnitude_ratio_minimum))
        {
            return Vector3.zero;
        }

        float direction_cosine = Vector3.Dot(wrist_step, head_step)
            / (wrist_distance * head_distance);
        if (direction_cosine < Mathf.Clamp(direction_cosine_threshold, -1.0f, 1.0f)
            || Vector3.Distance(wrist_step, head_step)
                > Mathf.Max(0.0f, residual_tolerance))
        {
            return Vector3.zero;
        }

        return head_step;
    }

    public static bool IsTrackedWristStepPlausible(
        Vector3 current_head_relative_wrist_position,
        Vector3 previous_head_relative_wrist_position,
        float delta_time,
        float maximum_speed_mps,
        float minimum_step_allowance)
    {
        float safe_delta_time = Mathf.Max(delta_time, 1.0f / 120.0f);
        float allowed_step = Mathf.Max(
            Mathf.Max(0.0f, minimum_step_allowance),
            Mathf.Max(0.0f, maximum_speed_mps) * safe_delta_time);
        return Vector3.Distance(
            current_head_relative_wrist_position,
            previous_head_relative_wrist_position) <= allowed_step;
    }

    private bool UpdateTrackedPosePlausibility()
    {
        Vector3 current_wrist_position = TrackedWristPosition;
        if (!accepted_wrist_position_initialized || !IsCalibrated)
        {
            last_accepted_wrist_position = current_wrist_position;
            accepted_wrist_position_initialized = true;
            tracked_pose_outlier_latched = false;
            IsTrackedPosePlausible = true;
            TrackedWristSpeedMPS = 0.0f;
            return true;
        }

        float safe_delta_time = Mathf.Max(Time.unscaledDeltaTime, 1.0f / 120.0f);
        float position_step = Vector3.Distance(
            current_wrist_position,
            last_accepted_wrist_position);
        TrackedWristSpeedMPS = position_step / safe_delta_time;

        if (tracked_pose_outlier_latched)
        {
            IsTrackedPosePlausible = false;
            return false;
        }

        if (!IsTrackedWristStepPlausible(
            current_wrist_position,
            last_accepted_wrist_position,
            safe_delta_time,
            tracked_wrist_max_speed_mps,
            tracked_wrist_min_step_allowance))
        {
            tracked_pose_outlier_latched = true;
            IsTrackedPosePlausible = false;
            Debug.LogWarning(
                "G1 hand pose outlier rejected: wrist speed="
                + TrackedWristSpeedMPS.ToString("F2")
                + " m/s. Holding the last valid robot target.");
            return false;
        }

        last_accepted_wrist_position = current_wrist_position;
        IsTrackedPosePlausible = true;
        return true;
    }

    private void AcceptCurrentTrackedPose()
    {
        last_accepted_wrist_position = TrackedWristPosition;
        accepted_wrist_position_initialized = true;
        tracked_pose_outlier_latched = false;
        IsTrackedPosePlausible = true;
        TrackedWristSpeedMPS = 0.0f;
    }

    private bool GetRawTrackingAvailable()
    {
        if (!require_tracked_hand)
        {
            return true;
        }

        return ovr_hand != null
            ? ovr_hand.IsTracked && ovr_hand.IsDataHighConfidence
            : OVRInput.GetControllerPositionTracked(OVRInput.Controller.RHand);
    }

    private Quaternion GetAnatomicalHandRotation(Quaternion fallback_rotation)
    {
        if (!use_anatomical_hand_frame)
        {
            IsAnatomicalFrameValid = true;
            return fallback_rotation;
        }

        if (ovr_skeleton == null)
        {
            return fallback_rotation;
        }

        ResolveAnatomicalHandTransforms();
        if (middle_finger_base_transform == null
            || index_finger_base_transform == null
            || pinky_finger_base_transform == null)
        {
            return fallback_rotation;
        }

        Vector3 finger_direction =
            middle_finger_base_transform.position - TrackedWristPosition;
        Vector3 palm_across =
            index_finger_base_transform.position - pinky_finger_base_transform.position;
        if (finger_direction.sqrMagnitude < 0.000001f
            || palm_across.sqrMagnitude < 0.000001f)
        {
            return fallback_rotation;
        }

        finger_direction.Normalize();
        palm_across = Vector3.ProjectOnPlane(
            palm_across,
            finger_direction).normalized;
        Vector3 palm_normal = Vector3.Cross(
            finger_direction,
            palm_across).normalized;
        if (palm_normal.sqrMagnitude < 0.000001f)
        {
            return fallback_rotation;
        }

        // Semantic hand frame: +Z follows the fingers and +Y is the palm normal.
        IsAnatomicalFrameValid = true;
        return Quaternion.LookRotation(finger_direction, palm_normal);
    }

    private void ResolveAnatomicalHandTransforms()
    {
        if (middle_finger_base_transform != null
            && index_finger_base_transform != null
            && pinky_finger_base_transform != null)
        {
            return;
        }

        if (ovr_skeleton.Bones == null)
        {
            return;
        }

        foreach (OVRBone bone_value in ovr_skeleton.Bones)
        {
            if (bone_value == null)
            {
                continue;
            }

            if (bone_value.Id == OVRSkeleton.BoneId.Hand_Middle1)
            {
                middle_finger_base_transform = bone_value.Transform;
            }
            else if (bone_value.Id == OVRSkeleton.BoneId.Hand_Index1)
            {
                index_finger_base_transform = bone_value.Transform;
            }
            else if (bone_value.Id == OVRSkeleton.BoneId.Hand_Pinky1)
            {
                pinky_finger_base_transform = bone_value.Transform;
            }
        }
    }

    private Vector3 GetPalmCenterPosition()
    {
        if (!use_palm_center || ovr_skeleton == null || ovr_skeleton.Bones == null)
        {
            return TrackedWristPosition;
        }

        foreach (OVRBone bone_value in ovr_skeleton.Bones)
        {
            if (bone_value != null && bone_value.Id == OVRSkeleton.BoneId.Hand_Middle1)
            {
                return Vector3.Lerp(
                    TrackedWristPosition,
                    bone_value.Transform.position,
                    0.50f);
            }
        }

        return TrackedWristPosition;
    }

    private Transform GetSkeletonWristTransform()
    {
        if (!prefer_skeleton_wrist || ovr_skeleton == null || ovr_skeleton.Bones == null)
        {
            return null;
        }

        foreach (OVRBone bone_value in ovr_skeleton.Bones)
        {
            if (bone_value != null && bone_value.Id == OVRSkeleton.BoneId.Hand_WristRoot)
            {
                return bone_value.Transform;
            }
        }

        return null;
    }

    private bool GetHandTracked()
    {
        bool tracking_available;
        if (!require_tracked_hand)
        {
            tracking_available = true;
        }
        else if (ovr_hand != null)
        {
            // Meta는 손을 완전히 잃기 전에도 낮은 신뢰도의 추정 자세를 잠시
            // 제공할 수 있다. 이 전이 프레임은 고개 회전 때 손목이 끌려가는
            // 원인이 되므로 새 목표로 사용하지 않고 마지막 정상 목표를 유지한다.
            tracking_available = ovr_hand.IsTracked
                && ovr_hand.IsDataHighConfidence;
        }
        else
        {
            tracking_available = OVRInput.GetControllerPositionTracked(
                OVRInput.Controller.RHand);
        }

        bool semantic_frame_available = !use_anatomical_hand_frame
            || IsAnatomicalFrameValid;
        return tracking_available && semantic_frame_available;
    }

    private Quaternion GetReferenceYawRotation()
    {
        if (!use_reference_yaw || reference_transform == null)
        {
            return Quaternion.identity;
        }

        Vector3 forward_value = Vector3.ProjectOnPlane(reference_transform.forward, Vector3.up);
        if (forward_value.sqrMagnitude < 0.0001f)
        {
            return Quaternion.identity;
        }

        return Quaternion.LookRotation(forward_value.normalized, Vector3.up);
    }

    private void LogStatus(bool active_value)
    {
        log_timer += Time.deltaTime;
        if (log_timer < 2.0f)
        {
            return;
        }

        log_timer = 0.0f;
        string tracked_text = ovr_hand == null
            ? "OVRInput.RHand"
            : ovr_hand.IsTracked.ToString();
        string confidence_text = ovr_hand == null
            ? "unknown"
            : ovr_hand.IsDataHighConfidence.ToString();
        Debug.Log(
            "G1 hand binder active=" + active_value
            + " tracked=" + tracked_text
            + " high_confidence=" + confidence_text
            + " pose_plausible=" + IsTrackedPosePlausible
            + " wrist_speed_mps=" + TrackedWristSpeedMPS.ToString("F2")
            + " hand_frame=" + (IsAnatomicalFrameValid ? "valid" : "invalid")
            + " align_position_cm="
            + (AlignmentPositionError * 100.0f).ToString("F1")
            + " align_rotation_deg="
            + AlignmentOrientationErrorDegrees.ToString("F1")
            + " engage_state=" + EngagementState
            + " hold=" + (EngagementProgress * 100.0f).ToString("F0") + "%"
            + " operator_delta=" + OperatorTargetDelta.ToString("F3"));
    }
}
