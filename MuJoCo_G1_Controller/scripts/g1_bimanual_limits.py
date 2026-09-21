"""Joint-space limits for all 14 simulation/observation IK outputs.

These are target-trajectory limits, not hardware gains or actuator ratings.
Tracking, checked stopping and return share the same values.
"""

JOINT_VELOCITY_LIMIT_RAD_S = 3.0
JOINT_ACCELERATION_LIMIT_RAD_S2 = 3.0
