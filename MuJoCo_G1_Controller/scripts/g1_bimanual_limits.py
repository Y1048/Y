"""Shared bilateral motion limits; measured-state visualization is independent."""
import math
import numpy as np

# Live tracking can move aggressively, but staged return/recovery keeps the
# previously validated conservative limits.
TRACKING_PROXIMAL_VELOCITY_LIMIT_DEG_S = 150.0
TRACKING_WRIST_VELOCITY_LIMIT_DEG_S = 180.0
TRACKING_JOINT_ACCELERATION_LIMIT_DEG_S2 = 300.0
POSITION_TRACKING_RATE_S = 12.0
ORIENTATION_TRACKING_RATE_S = 1.5

RETURN_PROXIMAL_VELOCITY_LIMIT_DEG_S = 90.0
RETURN_WRIST_VELOCITY_LIMIT_DEG_S = 180.0
RETURN_JOINT_ACCELERATION_LIMIT_DEG_S2 = 90.0
JOINT_JERK_LIMIT_RAD_S3 = 1.28
RETURN_RIGHT_WAYPOINT_RAD = np.deg2rad(
    [10.0, -35.0, 0.0, 70.0, 0.0, 0.0, 0.0])

TRACKING_ARM_VELOCITY_LIMITS_RAD_S = (
    math.radians(TRACKING_PROXIMAL_VELOCITY_LIMIT_DEG_S),
) * 4 + (
    math.radians(TRACKING_WRIST_VELOCITY_LIMIT_DEG_S),
) * 3
TRACKING_JOINT_VELOCITY_LIMITS_RAD_S = (
    TRACKING_ARM_VELOCITY_LIMITS_RAD_S * 2)
TRACKING_JOINT_VELOCITY_LIMIT_RAD_S = max(
    TRACKING_JOINT_VELOCITY_LIMITS_RAD_S)
TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2 = math.radians(
    TRACKING_JOINT_ACCELERATION_LIMIT_DEG_S2)

RETURN_ARM_VELOCITY_LIMITS_RAD_S = (
    math.radians(RETURN_PROXIMAL_VELOCITY_LIMIT_DEG_S),
) * 4 + (
    math.radians(RETURN_WRIST_VELOCITY_LIMIT_DEG_S),
) * 3
RETURN_JOINT_VELOCITY_LIMITS_RAD_S = (
    RETURN_ARM_VELOCITY_LIMITS_RAD_S * 2)
RETURN_JOINT_VELOCITY_LIMIT_RAD_S = max(
    RETURN_JOINT_VELOCITY_LIMITS_RAD_S)
RETURN_JOINT_ACCELERATION_LIMIT_RAD_S2 = math.radians(
    RETURN_JOINT_ACCELERATION_LIMIT_DEG_S2)


# Pinned from the deployed G1 include/twist2_common.hpp, 2026-10-07.
# external_controller_bridge.cpp accepts kLower + 0.05F .. kUpper - 0.05F.
# Left/right shoulder-roll limits are asymmetric; bind by name, never mirror.
_ONBOARD_ARM_RAW_JOINT_RANGES_RAD = {
    'left_shoulder_pitch_joint': (-3.0892, 2.6704),
    'left_shoulder_roll_joint': (-1.5882, 2.2515),
    'left_shoulder_yaw_joint': (-2.618, 2.618),
    'left_elbow_joint': (-1.0472, 2.0944),
    'left_wrist_roll_joint': (-1.972222054, 1.972222054),
    'left_wrist_pitch_joint': (-1.614429558, 1.614429558),
    'left_wrist_yaw_joint': (-1.614429558, 1.614429558),
    'right_shoulder_pitch_joint': (-3.0892, 2.6704),
    'right_shoulder_roll_joint': (-2.2515, 1.5882),
    'right_shoulder_yaw_joint': (-2.618, 2.618),
    'right_elbow_joint': (-1.0472, 2.0944),
    'right_wrist_roll_joint': (-1.972222054, 1.972222054),
    'right_wrist_pitch_joint': (-1.614429558, 1.614429558),
    'right_wrist_yaw_joint': (-1.614429558, 1.614429558),
}
ONBOARD_ARM_JOINT_MARGIN_RAD = 0.05
# Larger than the checked-stop 1e-8 tolerance and float32 roundoff. This is
# numerical headroom, not an additional physical clearance guarantee.
ONBOARD_ARM_NUMERICAL_RESERVE_RAD = 1e-6


def onboard_compatible_joint_ranges(
        joint_names: list[str] | tuple[str, ...],
        model_ranges: np.ndarray) -> np.ndarray:
    """Intersect all 14 operational ranges with the unchanged G1 RX guard.

    Apply at model construction, before Mink caches its ConfigurationLimit.
    IK, posture allocation, checked stopping and staged return then see one
    boundary. This function never clips a computed joint command.
    """
    if (len(joint_names) != 14
            or set(joint_names) != set(_ONBOARD_ARM_RAW_JOINT_RANGES_RAD)):
        raise ValueError('Expected exactly the 14 named bilateral arm joints')
    ranges = np.asarray(model_ranges, dtype=float)
    if (ranges.shape != (14, 2) or not np.isfinite(ranges).all()
            or np.any(ranges[:, 0] >= ranges[:, 1])):
        raise ValueError('Invalid bilateral model joint ranges')
    # Match C++ float-literal arithmetic before promotion to JSON/double.
    raw = np.asarray([
        _ONBOARD_ARM_RAW_JOINT_RANGES_RAD[name] for name in joint_names
    ], dtype=np.float32)
    margin = np.float32(ONBOARD_ARM_JOINT_MARGIN_RAD)
    lower = (raw[:, 0] + margin).astype(float)
    upper = (raw[:, 1] - margin).astype(float)
    result = np.column_stack((
        np.maximum(ranges[:, 0], lower + ONBOARD_ARM_NUMERICAL_RESERVE_RAD),
        np.minimum(ranges[:, 1], upper - ONBOARD_ARM_NUMERICAL_RESERVE_RAD),
    ))
    if np.any(result[:, 0] >= result[:, 1]):
        raise ValueError('Model and onboard arm joint ranges do not intersect')
    return result
