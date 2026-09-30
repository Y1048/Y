"""Read-only effective tuning profile for the current bilateral upper body.

Keep historical/reference controllers out of this file. The current
unity_display_world_v1 path should expose its behavior-shaping numbers here so
an operator can inspect the controller without hunting through solver code.
"""

from dataclasses import dataclass
import math

import g1_mink_shared as base
from g1_bimanual_limits import (
    IK_TRACKING_RATE_S,
    JOINT_ACCELERATION_LIMIT_RAD_S2,
    JOINT_JERK_LIMIT_RAD_S3,
    JOINT_VELOCITY_LIMITS_RAD_S,
    RETURN_RIGHT_WAYPOINT_RAD,
)


@dataclass(frozen=True)
class TrackingProfile:
    control_hz: float = 60.0
    hard_clearance_m: float = .005
    elbow_operational_min_rad: float = math.radians(5.0)
    elbow_operational_max_rad: float = math.radians(120.0)

    position_cost: float = base.POSITION_COST
    orientation_cost: float = base.ORIENTATION_COST
    posture_cost: float = base.POSTURE_COST
    frame_gain: float = base.FRAME_GAIN
    lm_damping: float = base.LM_DAMPING
    build_ik_damping: float = 1e-6
    proximal_damping_cost: float = base.PROXIMAL_DAMPING_COST
    wrist_damping_cost: float = base.WRIST_DAMPING_COST

    shoulder_comfort_cost: float = .6
    shoulder_comfort_roll_band_rad: float = math.radians(20.0)
    shoulder_comfort_yaw_band_rad: float = math.radians(45.0)
    shoulder_yaw_envelope_rad: float = math.radians(90.0)
    shoulder_yaw_stop_scale: float = .8

    elbow_clearance_cost: float = 8.0
    elbow_gain_per_second: float = .6
    elbow_reference_release_m: float = .025
    elbow_assist_error_m: float = .02
    elbow_assist_start_max_rad: float = math.radians(20.0)
    elbow_lift_m: float = .08
    elbow_below_shoulder_m: float = .04
    elbow_min_lift_m: float = .005
    torso_front_inner_m: float = .015
    torso_front_outer_m: float = .06
    torso_front_lateral_margin_m: float = .03

    orientation_position_priority_scale: float = .5
    orientation_collision_clearance_m: float = .012
    orientation_joint_margin_rad: float = math.radians(5.0)
    orientation_elbow_margin_rad: float = math.radians(5.0)
    orientation_error_elbow_m: float = .025
    orientation_error_constrained_m: float = .08
    orientation_release_error_m: float = .01
    orientation_release_clearance_m: float = .025
    orientation_release_joint_margin_rad: float = math.radians(8.0)
    orientation_priority_dwell_s: float = .3
    orientation_scale_slew_per_second: float = 1.0

    wrist_priority_position_full_m: float = .002
    wrist_priority_position_zero_m: float = .008
    wrist_priority_rotation_full_rad: float = math.radians(3.0)
    wrist_priority_margin_min_rad: float = math.radians(5.0)
    wrist_priority_margin_full_rad: float = math.radians(28.0)
    wrist_priority_clearance_min_m: float = .005
    wrist_priority_clearance_full_m: float = .025
    wrist_priority_proximal_damping_scale: float = 5.0

    collision_minimum_m: float = .006
    collision_detection_distance_m: float = .15
    collision_gain: float = .85
    collision_stopping_acceleration_scale: float = .25
    joint_limit_stopping_speed_scale: float = .8
    checked_stop_substep_rad: float = math.radians(.25)

    ik_tracking_rate_s: float = IK_TRACKING_RATE_S
    joint_acceleration_limit_rad_s2: float = JOINT_ACCELERATION_LIMIT_RAD_S2
    joint_velocity_limits_rad_s: tuple = JOINT_VELOCITY_LIMITS_RAD_S


@dataclass(frozen=True)
class ReturnProfile:
    settle_s: float = .5
    maximum_duration_s: float = 30.0
    maximum_replans: int = 2
    near_hands_threshold_m: float = .012
    separation_probe_maximum_s: float = 10.0
    joint_acceleration_limit_rad_s2: float = JOINT_ACCELERATION_LIMIT_RAD_S2
    joint_jerk_limit_rad_s3: float = JOINT_JERK_LIMIT_RAD_S3
    right_waypoint_rad: tuple = tuple(float(value) for value in RETURN_RIGHT_WAYPOINT_RAD)


TRACKING = TrackingProfile()
RETURN = ReturnProfile()
