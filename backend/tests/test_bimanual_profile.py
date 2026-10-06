import math
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))

import g1_mink_shared as base
from g1_bimanual_limits import (
    JOINT_JERK_LIMIT_RAD_S3,
    ORIENTATION_TRACKING_RATE_S,
    POSITION_TRACKING_RATE_S,
    RETURN_JOINT_ACCELERATION_LIMIT_RAD_S2,
    RETURN_JOINT_VELOCITY_LIMITS_RAD_S,
    TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2,
    TRACKING_JOINT_VELOCITY_LIMITS_RAD_S,
)
from g1_bimanual_profile import TRACKING, RETURN


class BimanualProfileTests(unittest.TestCase):
    def test_tracking_profile_preserves_effective_baseline(self):
        self.assertEqual(TRACKING.control_hz, 60.0)
        self.assertEqual(TRACKING.hard_clearance_m, .005)
        self.assertEqual(TRACKING.position_cost, base.POSITION_COST)
        self.assertEqual(TRACKING.orientation_cost, base.ORIENTATION_COST)
        self.assertEqual(TRACKING.posture_cost, base.POSTURE_COST)
        self.assertEqual(TRACKING.frame_gain, base.FRAME_GAIN)
        self.assertEqual(TRACKING.lm_damping, base.LM_DAMPING)
        self.assertEqual(
            TRACKING.position_tracking_rate_s,
            POSITION_TRACKING_RATE_S)
        self.assertEqual(
            TRACKING.orientation_tracking_rate_s,
            ORIENTATION_TRACKING_RATE_S)
        self.assertEqual(
            TRACKING.joint_acceleration_limit_rad_s2,
            TRACKING_JOINT_ACCELERATION_LIMIT_RAD_S2)
        self.assertEqual(
            tuple(TRACKING.joint_velocity_limits_rad_s),
            tuple(TRACKING_JOINT_VELOCITY_LIMITS_RAD_S))
        self.assertEqual(TRACKING.shoulder_comfort_cost, 1.2)
        self.assertEqual(
            TRACKING.shoulder_comfort_yaw_band_rad,
            math.radians(15.0))
        self.assertEqual(
            TRACKING.elbow_operational_min_rad, math.radians(5.0))
        self.assertEqual(
            TRACKING.elbow_operational_max_rad, math.radians(120.0))

    def test_return_profile_preserves_effective_baseline(self):
        self.assertEqual(
            tuple(RETURN.joint_velocity_limits_rad_s),
            tuple(RETURN_JOINT_VELOCITY_LIMITS_RAD_S))
        self.assertEqual(
            RETURN.joint_acceleration_limit_rad_s2,
            RETURN_JOINT_ACCELERATION_LIMIT_RAD_S2)
        self.assertEqual(
            RETURN.joint_jerk_limit_rad_s3,
            JOINT_JERK_LIMIT_RAD_S3)
        self.assertEqual(RETURN.settle_s, .5)
        self.assertEqual(RETURN.maximum_duration_s, 30.0)
        self.assertEqual(RETURN.maximum_replans, 2)
        self.assertEqual(RETURN.near_hands_threshold_m, .012)
        self.assertEqual(RETURN.separation_probe_maximum_s, 10.0)

    def test_profiles_are_read_only(self):
        with self.assertRaises(FrozenInstanceError):
            TRACKING.control_hz = 30.0
        with self.assertRaises(FrozenInstanceError):
            RETURN.settle_s = 1.0


if __name__ == '__main__':
    unittest.main()
