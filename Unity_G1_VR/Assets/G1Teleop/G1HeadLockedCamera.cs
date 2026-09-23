using UnityEngine;

/// <summary>
/// 시작할 때 XR TrackingSpace의 수평 방향과 위치를 G1 머리 마운트에 맞춘다.
/// 이후에는 Quest tracking space를 고정하고 손과 머리의 원본 이동을 유지한다.
/// 로봇만 Omni yaw로 회전하며 카메라 위치를 다시 로봇에 붙이지 않는다.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1HeadLockedCamera : MonoBehaviour
{
    public Transform xr_center_eye;
    public Transform xr_tracking_space;
    public G1UnityRightArmPreview robot_preview;
    public bool align_position_once = true;
    public bool lock_position = true;
    [Min(0.0f)]
    public float head_tracking_stable_duration = 0.15f;
    [Min(0.0f)]
    public float minimum_floor_head_height = 0.4f;
    public bool show_head_camera_pip = true;
    public int head_camera_tcp_port = G1HeadCameraPiP.DefaultTcpPort;
    public bool show_ambient_operator_environment = true;
    public bool follow_omni_body_heading = true;
    [Min(0.0f)]
    public float operator_height_above_shoulders_m = 0.30f;
    [Min(0.0f)]
    public float operator_forward_offset_m = 0.05f;

    public bool IsPositionLocked { get; private set; }
    public bool IsInitialAlignmentApplied { get; private set; }
    public bool IsHeadTrackingReady { get; private set; }
    public Vector3 LastPositionCorrection { get; private set; }
    public float LastYawCorrectionDegrees { get; private set; }
    public G1OmniBodyHeading OmniBodyHeading { get; private set; }
    public Transform TrackingSpace => xr_tracking_space != null
        ? xr_tracking_space
        : xr_center_eye == null
            ? null
            : xr_center_eye.parent;

    private Vector3 stableHeadPosition;
    private Quaternion stableHeadRotation;
    private float head_tracking_valid_since = -1.0f;
    private G1HeadCameraPiP head_camera_pip;
    private G1AmbientOperatorEnvironment ambient_operator_environment;

    private void OnEnable()
    {
        IsInitialAlignmentApplied = false;
        lock_position = false; // Keep the aligned Quest world fixed after startup.
        head_tracking_stable_duration = Mathf.Max(1.0f, head_tracking_stable_duration);
        ResetHeadTrackingReadiness();
        if (head_camera_pip != null)
        {
            head_camera_pip.gameObject.SetActive(true);
        }
        if (ambient_operator_environment != null)
        {
            ambient_operator_environment.gameObject.SetActive(true);
        }
        Application.onBeforeRender += ApplyPositionLock;
    }

    private void Start()
    {
        if (show_ambient_operator_environment)
        {
            ambient_operator_environment =
                G1AmbientOperatorEnvironment.Create();
        }
        if (show_head_camera_pip && xr_center_eye != null)
        {
            head_camera_pip = G1HeadCameraPiP.Create(
                xr_center_eye,
                robot_preview == null ? null : robot_preview.RobotRoot,
                head_camera_tcp_port);
        }
        if (follow_omni_body_heading && xr_center_eye != null)
        {
            OmniBodyHeading = gameObject.AddComponent<G1OmniBodyHeading>();
            OmniBodyHeading.Initialize(this);
        }
    }

    private void LateUpdate()
    {
        ApplyPositionLock();
    }

    private void OnDisable()
    {
        Application.onBeforeRender -= ApplyPositionLock;
        IsPositionLocked = false;
        IsInitialAlignmentApplied = false;
        ResetHeadTrackingReadiness();
        if (head_camera_pip != null)
        {
            head_camera_pip.gameObject.SetActive(false);
        }
        if (ambient_operator_environment != null)
        {
            ambient_operator_environment.gameObject.SetActive(false);
        }
    }

    private void ApplyPositionLock()
    {
        ApplyPositionLockNow();
    }

    public bool ApplyPositionLockNow()
    {
        IsPositionLocked = false;
        LastPositionCorrection = Vector3.zero;
        LastYawCorrectionDegrees = 0.0f;
        bool initial_alignment_needed = align_position_once
            && !IsInitialAlignmentApplied;
        if (!Application.isPlaying
            || xr_center_eye == null
            || (!initial_alignment_needed && !lock_position))
        {
            return false;
        }

        if (initial_alignment_needed && !UpdateHeadTrackingReadiness())
        {
            return false;
        }

        if (robot_preview == null
            || !robot_preview.IsRobotAnchored
            || robot_preview.HeadCameraMount == null)
        {
            return false;
        }

        if (!robot_preview.TryGetBimanualWorldFrame(
            out _, out _, out Vector3 shoulder_center, out _, out _))
        {
            return false;
        }
        Vector3 desired_camera_position = GetOperatorAnchorPosition(
            shoulder_center,
            robot_preview.HeadCameraMount.forward,
            operator_height_above_shoulders_m,
            operator_forward_offset_m);

        Transform tracking_space = TrackingSpace;
        if (tracking_space == null)
        {
            return false;
        }

        if (initial_alignment_needed)
        {
            LastYawCorrectionDegrees = AlignTrackingSpaceToHeadMount(
                tracking_space,
                xr_center_eye,
                robot_preview.HeadCameraMount,
                out Vector3 position_correction,
                desired_camera_position);
            LastPositionCorrection = position_correction;
            IsInitialAlignmentApplied = true;
            Debug.Log(
                $"G1 head camera initial alignment applied after stable XR tracking. "
                + $"correction={LastPositionCorrection} "
                + $"yaw_correction={LastYawCorrectionDegrees:F1} deg "
                + $"camera={xr_center_eye.position} "
                + $"shoulders={shoulder_center} "
                + $"operator_offset=up {operator_height_above_shoulders_m:F2}m, "
                + $"forward {operator_forward_offset_m:F2}m");
        }
        else
        {
            LastPositionCorrection = LockTrackingSpacePosition(
                tracking_space,
                xr_center_eye,
                desired_camera_position);
        }

        IsPositionLocked = lock_position;
        return true;
    }

    private bool UpdateHeadTrackingReadiness()
    {
        bool tracking_valid = IsTrackedHeadPoseValid(
            OVRPlugin.GetNodePositionTracked(OVRPlugin.Node.EyeCenter),
            OVRPlugin.GetNodeOrientationTracked(OVRPlugin.Node.EyeCenter),
            OVRPlugin.GetNodePositionValid(OVRPlugin.Node.EyeCenter),
            OVRPlugin.GetNodeOrientationValid(OVRPlugin.Node.EyeCenter))
            && IsTrackedHeadTransformReady(
                xr_center_eye.localPosition,
                minimum_floor_head_height);
        if (!tracking_valid)
        {
            ResetHeadTrackingReadiness();
            return false;
        }

        float current_time = Time.unscaledTime;
        if (head_tracking_valid_since < 0.0f ||
            Vector3.Distance(stableHeadPosition, xr_center_eye.localPosition) > .02f ||
            Quaternion.Angle(stableHeadRotation, xr_center_eye.localRotation) > 2f)
        {
            head_tracking_valid_since = current_time;
            stableHeadPosition = xr_center_eye.localPosition;
            stableHeadRotation = xr_center_eye.localRotation;
        }

        IsHeadTrackingReady = current_time - head_tracking_valid_since
            >= Mathf.Max(1.0f, head_tracking_stable_duration);
        return IsHeadTrackingReady;
    }

    private void ResetHeadTrackingReadiness()
    {
        head_tracking_valid_since = -1.0f;
        IsHeadTrackingReady = false;
    }

    public static bool IsTrackedHeadPoseValid(
        bool position_tracked,
        bool orientation_tracked,
        bool position_valid,
        bool orientation_valid)
    {
        return position_tracked
            && orientation_tracked
            && position_valid
            && orientation_valid;
    }

    public static bool IsTrackedHeadTransformReady(
        Vector3 center_eye_local_position,
        float minimum_head_height)
    {
        return IsFinite(center_eye_local_position)
            && center_eye_local_position.y >= Mathf.Max(0.0f, minimum_head_height);
    }

    private static bool IsFinite(Vector3 value)
    {
        return !float.IsNaN(value.x)
            && !float.IsInfinity(value.x)
            && !float.IsNaN(value.y)
            && !float.IsInfinity(value.y)
            && !float.IsNaN(value.z)
            && !float.IsInfinity(value.z);
    }

    public static Vector3 LockTrackingSpacePosition(
        Transform tracking_space,
        Transform camera_transform,
        Vector3 desired_camera_position)
    {
        if (tracking_space == null || camera_transform == null)
        {
            return Vector3.zero;
        }

        Vector3 correction = desired_camera_position - camera_transform.position;
        tracking_space.position += correction;
        return correction;
    }

    public static float AlignTrackingSpaceToHeadMount(
        Transform tracking_space,
        Transform camera_transform,
        Transform head_mount,
        out Vector3 position_correction)
        => AlignTrackingSpaceToHeadMount(
            tracking_space,
            camera_transform,
            head_mount,
            out position_correction,
            head_mount == null ? Vector3.zero : head_mount.position);

    public static float AlignTrackingSpaceToHeadMount(
        Transform tracking_space,
        Transform camera_transform,
        Transform head_mount,
        out Vector3 position_correction,
        Vector3 desired_camera_position)
    {
        position_correction = Vector3.zero;
        if (tracking_space == null
            || camera_transform == null
            || head_mount == null)
        {
            return 0.0f;
        }

        Vector3 camera_forward = Vector3.ProjectOnPlane(
            camera_transform.forward,
            Vector3.up);
        Vector3 robot_forward = Vector3.ProjectOnPlane(
            head_mount.forward,
            Vector3.up);
        float yaw_correction = 0.0f;
        if (camera_forward.sqrMagnitude >= 0.0001f
            && robot_forward.sqrMagnitude >= 0.0001f)
        {
            yaw_correction = Vector3.SignedAngle(
                camera_forward.normalized,
                robot_forward.normalized,
                Vector3.up);
            tracking_space.rotation = Quaternion.AngleAxis(
                yaw_correction,
                Vector3.up) * tracking_space.rotation;
        }

        position_correction = desired_camera_position - camera_transform.position;
        tracking_space.position += position_correction;
        return yaw_correction;
    }

    public static Vector3 GetOperatorAnchorPosition(
        Vector3 shoulder_center,
        Vector3 robot_forward,
        float height_above_shoulders_m,
        float forward_offset_m)
    {
        Vector3 forward = Vector3.ProjectOnPlane(robot_forward, Vector3.up);
        if (forward.sqrMagnitude < 0.0001f)
        {
            forward = Vector3.forward;
        }
        return shoulder_center
            + Vector3.up * Mathf.Max(0.0f, height_above_shoulders_m)
            + forward.normalized * Mathf.Max(0.0f, forward_offset_m);
    }

    public static void LockWorldPosition(
        Transform camera_transform,
        Vector3 desired_camera_position)
    {
        if (camera_transform != null)
        {
            camera_transform.position = desired_camera_position;
        }
    }
}
