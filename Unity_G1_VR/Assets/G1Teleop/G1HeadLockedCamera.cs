using UnityEngine;

/// <summary>
/// 시작할 때 XR TrackingSpace를 한 번 이동해 카메라를 G1 머리 마운트에 맞춘다.
/// 이후에는 Quest의 위치와 회전을 모두 그대로 따라 시각-전정 불일치를 피한다.
/// 사용자의 몸 전체 이동은 binder의 머리 상대 좌표 계산에서 상쇄한다.
/// </summary>
[DefaultExecutionOrder(10000)]
public sealed class G1HeadLockedCamera : MonoBehaviour
{
    public Transform xr_center_eye;
    public Transform xr_tracking_space;
    public G1UnityRightArmPreview robot_preview;
    public bool align_position_once = true;
    public bool lock_position = false;

    public bool IsPositionLocked { get; private set; }
    public bool IsInitialAlignmentApplied { get; private set; }
    public Vector3 LastPositionCorrection { get; private set; }
    public Transform TrackingSpace => xr_tracking_space != null
        ? xr_tracking_space
        : xr_center_eye == null
            ? null
            : xr_center_eye.parent;

    private void OnEnable()
    {
        IsInitialAlignmentApplied = false;
        Application.onBeforeRender += ApplyPositionLock;
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
    }

    private void ApplyPositionLock()
    {
        ApplyPositionLockNow();
    }

    public bool ApplyPositionLockNow()
    {
        IsPositionLocked = false;
        LastPositionCorrection = Vector3.zero;
        bool initial_alignment_needed = align_position_once
            && !IsInitialAlignmentApplied;
        if (!Application.isPlaying
            || (!initial_alignment_needed && !lock_position)
            || xr_center_eye == null
            || robot_preview == null
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

        LastPositionCorrection = LockTrackingSpacePosition(
            tracking_space,
            xr_center_eye,
            robot_preview.HeadCameraMount.position);
        IsInitialAlignmentApplied = true;
        IsPositionLocked = lock_position;
        return true;
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
