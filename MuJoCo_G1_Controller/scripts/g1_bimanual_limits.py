"""Shared bilateral target limits; independent from measured-state visualization."""
import math

ARM_VELOCITY_LIMITS_RAD_S = (math.pi/2,)*4 + (math.pi,)*3
JOINT_VELOCITY_LIMITS_RAD_S = ARM_VELOCITY_LIMITS_RAD_S * 2
# Maximum across joints, retained for scalar summary consumers.
JOINT_VELOCITY_LIMIT_RAD_S = max(JOINT_VELOCITY_LIMITS_RAD_S)
JOINT_ACCELERATION_LIMIT_RAD_S2 = math.radians(90.0)
