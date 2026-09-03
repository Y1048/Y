using UnityEngine;

/// <summary>
/// 시작할 때 XR TrackingSpace의 수평 방향과 위치를 G1 머리 마운트에 맞춘다.
/// 이후에는 Quest의 회전은 그대로 두고 카메라 위치만 G1 머리 마운트에 고정한다.
/// G1 루트에 base pose가 적용되면 카메라도 머리 마운트와 함께 이동한다.
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

    public bool IsPositionLocked { get; private set; }
    public bool IsInitialAlignmentApplied { get; private set; }
    public bool IsHeadTrackingReady { get; private set; }
    public Vector3 LastPositionCorrection { get; private set; }
    public float LastYawCorrectionDegrees { get; private set; }
    public Transform TrackingSpace => xr_tracking_space != null
        ? xr_tracking_space
        : xr_center_eye == null
            ? null
            : xr_center_eye.parent;

    private float head_tracking_valid_since = -1.0f;
    private G1HeadCameraPiP head_camera_pip;

    private void OnEnable()
    {
        IsInitialAlignmentApplied = false;
        ResetHeadTrackingReadiness();
        if (head_camera_pip != null)
        {
            head_camera_pip.gameObject.SetActive(true);
        }
        Application.onBeforeRender += ApplyPositionLock;
    }

    private void Start()
    {
        if (show_head_camera_pip && xr_center_eye != null)
        {
            head_camera_pip = G1HeadCameraPiP.Create(
                xr_center_eye,
                head_camera_tcp_port);
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
                out Vector3 position_correction);
            LastPositionCorrection = position_correction;
            IsInitialAlignmentApplied = true;
            Debug.Log(
                $"G1 head camera initial alignment applied after stable XR tracking. "
                + $"correction={LastPositionCorrection} "
                + $"yaw_correction={LastYawCorrectionDegrees:F1} deg "
                + $"camera={xr_center_eye.position} "
                + $"mount={robot_preview.HeadCameraMount.position}");
        }
        else
        {
            LastPositionCorrection = LockTrackingSpacePosition(
                tracking_space,
                xr_center_eye,
                robot_preview.HeadCameraMount.position);
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
        if (head_tracking_valid_since < 0.0f)
        {
            head_tracking_valid_since = current_time;
        }

        IsHeadTrackingReady = current_time - head_tracking_valid_since
            >= Mathf.Max(0.0f, head_tracking_stable_duration);
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

        position_correction = head_mount.position - camera_transform.position;
        tracking_space.position += position_correction;
        return yaw_correction;
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
