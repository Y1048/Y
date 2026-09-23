"""Shared bilateral target limits; independent from measured-state visualization."""
import math

# Fixed-base simulation / IK tuning profile. These are controller-side motion
# bounds, not physical G1 authorization or gain settings.
PROXIMAL_VELOCITY_LIMIT_DEG_S = 90.0
WRIST_VELOCITY_LIMIT_DEG_S = 180.0
JOINT_ACCELERATION_LIMIT_DEG_S2 = 90.0
IK_TRACKING_RATE_S = 1.0

ARM_VELOCITY_LIMITS_RAD_S = (
    math.radians(PROXIMAL_VELOCITY_LIMIT_DEG_S),
) * 4 + (
    math.radians(WRIST_VELOCITY_LIMIT_DEG_S),
) * 3
JOINT_VELOCITY_LIMITS_RAD_S = ARM_VELOCITY_LIMITS_RAD_S * 2
# Maximum across joints, retained for scalar summary consumers.
JOINT_VELOCITY_LIMIT_RAD_S = max(JOINT_VELOCITY_LIMITS_RAD_S)
JOINT_ACCELERATION_LIMIT_RAD_S2 = math.radians(
    JOINT_ACCELERATION_LIMIT_DEG_S2)
