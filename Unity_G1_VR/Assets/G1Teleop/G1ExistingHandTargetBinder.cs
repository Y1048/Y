using UnityEngine;
using UnityEngine.Serialization;

public class G1ExistingHandTargetBinder : MonoBehaviour
{
    public Transform source_hand;
    public Transform target_transform;
    public Transform reference_transform;
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

        UpdateTrackedWrist();

        UpdateEngagementFrame();

        if (!IsCalibrated)
        {
            UpdateEngagementTargetPose();
        }

        IsTrackingValid = GetHandTracked();
        if (!IsTrackingValid)
        {
            if (IsCalibrated)
            {
                // Hold the last valid target during temporary hand-tracking loss.
                // Workspace exit is the only automatic disengagement condition.
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

        neutral_wrist_position = TrackedWristPosition;
        neutral_hand_rotation = TrackedWristRotation;
        CalibratedWristPosition = neutral_wrist_position;
        CalibratedWristRotation = neutral_hand_rotation;
        OperatorTargetDelta = Vector3.zero;
        OperatorHandRotation = Quaternion.identity;
        neutral_target_rotation = EngagementTargetRotation;
        MappedHandRotation = neutral_target_rotation;
        IsCalibrated = true;
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
        OperatorHandRotation = Quaternion.identity;
        MappedHandRotation = EngagementTargetRotation;
        neutral_target_rotation = EngagementTargetRotation;
        IsAlignmentReady = false;
        AlignmentPositionError = float.PositiveInfinity;
        AlignmentOrientationErrorDegrees = float.PositiveInfinity;
        EngagementProgress = 0.0f;
        EngagementState = "waiting-position";
        alignment_reference_initialized = false;
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

        engagement_frame_initialization_duration += Time.deltaTime;
        if (engagement_frame_initialization_duration < engagement_frame_initialization_delay)
        {
            return;
        }

        CaptureEngagementFrame();
    }

    private void CaptureEngagementFrame()
    {
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
        Vector3 hand_delta = TrackedWristPosition - neutral_wrist_position;
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

        TrackedWristPosition = tracked_wrist_transform.position;
        TrackedWristRotation = GetAnatomicalHandRotation(
            tracked_wrist_transform.rotation);
        TrackedHandPosition = GetPalmCenterPosition();
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
            palm_across,
            finger_direction).normalized;
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
            tracking_available = ovr_hand.IsTracked;
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
        string tracked_text = ovr_hand == null ? "OVRInput.RHand" : ovr_hand.IsTracked.ToString();
        Debug.Log(
            "G1 hand binder active=" + active_value
            + " tracked=" + tracked_text
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
