"""PC output must satisfy the unchanged, pinned G1 C++ arm receiver guard."""
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import mink
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_sim as simulator
from g1_bimanual_limits import (
    ONBOARD_ARM_NUMERICAL_RESERVE_RAD,
    onboard_compatible_joint_ranges,
)

CONTRACT = json.loads((Path(__file__).parent/'fixtures'
    /'g1_onboard_arm_joint_ranges_20261007.json').read_text(encoding='utf-8'))
NAMES = CONTRACT['joint_names']
LOWER = np.asarray(CONTRACT['accepted_lower_rad'])
UPPER = np.asarray(CONTRACT['accepted_upper_rad'])


class OnboardJointRangeTests(unittest.TestCase):
    def test_pinned_receiver_float_arithmetic_is_preserved(self):
        margin = np.float32(CONTRACT['margin_rad'])
        np.testing.assert_array_equal(
            (np.asarray(CONTRACT['raw_lower_rad'], dtype=np.float32)
             + margin).astype(float), LOWER)
        np.testing.assert_array_equal(
            (np.asarray(CONTRACT['raw_upper_rad'], dtype=np.float32)
             - margin).astype(float), UPPER)
        actual = onboard_compatible_joint_ranges(
            NAMES, np.tile([-10., 10.], (14, 1)))
        expected = np.column_stack((
            LOWER + ONBOARD_ARM_NUMERICAL_RESERVE_RAD,
            UPPER - ONBOARD_ARM_NUMERICAL_RESERVE_RAD))
        np.testing.assert_array_equal(actual, expected)

    def test_model_operational_limit_and_receiver_limit_are_intersected(self):
        model = np.tile([-.1, .1], (14, 1))
        original = model.copy()
        result = onboard_compatible_joint_ranges(NAMES, model)
        np.testing.assert_array_equal(result, original)
        np.testing.assert_array_equal(model, original)
        self.assertFalse(np.shares_memory(result, model))

    def test_limits_follow_joint_names_not_input_order_or_left_right_mirroring(self):
        ranges = np.tile([-10., 10.], (14, 1))
        forward = onboard_compatible_joint_ranges(NAMES, ranges)
        reverse = onboard_compatible_joint_ranges(NAMES[::-1], ranges)
        np.testing.assert_array_equal(reverse, forward[::-1])
        self.assertNotEqual(forward[1, 0], forward[8, 0])

    def test_unknown_duplicate_or_missing_joint_fails_closed(self):
        for names in (NAMES[:-1], ['unknown'] + NAMES[1:],
                      [NAMES[1]] + NAMES[1:]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                onboard_compatible_joint_ranges(names, np.tile([-10., 10.], (14, 1)))

    def test_nonfinite_invalid_or_empty_ranges_fail_closed(self):
        for ranges in (np.zeros((13, 2)), np.zeros((14, 2)),
                       np.full((14, 2), np.nan), np.tile([-np.inf, np.inf], (14, 1)),
                       np.tile([4., 5.], (14, 1))):
            with self.subTest(shape=ranges.shape), self.assertRaises(ValueError):
                onboard_compatible_joint_ranges(NAMES, ranges)

    def test_mink_cache_safety_and_posture_see_the_same_reconciled_model(self):
        s = simulator.BimanualSimulation()
        ids = [s.model.joint(n).id for n in s.names]
        np.testing.assert_array_equal(s.model.jnt_range[ids], s.ranges)
        limit = next(x for x in s.limits if isinstance(x, mink.ConfigurationLimit))
        np.testing.assert_array_equal(limit.lower[s.qids], s.ranges[:, 0])
        np.testing.assert_array_equal(limit.upper[s.qids], s.ranges[:, 1])
        self.assertTrue(np.all(s.ranges[:, 0] > LOWER))
        self.assertTrue(np.all(s.ranges[:, 1] < UPPER))
        for p in s.motion.values():
            indices = [NAMES.index(n) for n in s.names if n.startswith(p.side+'_')]
            np.testing.assert_array_equal(s.model.jnt_range[p.joint_ids], s.ranges[indices])
        # Preserve the existing more restrictive elbow minimum; hardware caps max.
        self.assertEqual(s.ranges[3, 0], math.radians(5.))
        self.assertLess(s.ranges[3, 1], math.radians(120.))

    def test_home_and_return_waypoint_remain_inside_receiver_guard(self):
        s = simulator.BimanualSimulation()
        for q in (s.home[s.qids], s.return_motion.waypoint):
            self.assertTrue(np.all(q >= s.ranges[:, 0]))
            self.assertTrue(np.all(q <= s.ranges[:, 1]))
            self.assertTrue(np.all(q >= LOWER))
            self.assertTrue(np.all(q <= UPPER))

    def test_checked_stops_reject_outward_boundary_steps_for_every_arm_joint(self):
        s = simulator.BimanualSimulation()
        # Isolate numeric limits; collision constraints are checked separately.
        with patch.object(s, 'clearance', return_value=.2):
            for returning in (False, True):
                for j in range(14):
                    for direction, column in ((-1., 0), (1., 1)):
                        with self.subTest(returning=returning, joint=j, direction=direction):
                            q = s.home.copy()
                            q[s.qids[j]] = s.ranges[j, column]
                            s.config.update(q)
                            s.velocity[:] = 0.
                            outward = np.zeros(s.model.nv)
                            outward[s.dofs[j]] = direction * .001
                            self.assertEqual(
                                s.checked_stop_plan(outward, returning=returning),
                                (None, 'joint_range'))
                            plan, reason = s.checked_stop_plan(
                                np.zeros(s.model.nv), returning=returning)
                            self.assertIsNotNone(plan, reason)
                            for candidate, _ in plan:
                                self.assertTrue(np.all(candidate[s.qids] >= LOWER))
                                self.assertTrue(np.all(candidate[s.qids] <= UPPER))

    def test_recorded_rejected_wrist_pitch_is_outside_new_model(self):
        s = simulator.BimanualSimulation()
        recorded_first_rejected_left_pitch = -1.56872587186673
        self.assertLess(recorded_first_rejected_left_pitch, LOWER[5])
        self.assertLess(recorded_first_rejected_left_pitch, s.ranges[5, 0])
        # Even the old checked-stop numeric tolerance remains inside RX bounds.
        self.assertTrue(np.all(s.ranges[:, 0] - 1e-8 > LOWER))
        self.assertTrue(np.all(s.ranges[:, 1] + 1e-8 < UPPER))

    def test_out_of_range_pose_uses_bounded_ik_and_returns_without_output_clip(self):
        s = simulator.BimanualSimulation()
        probe = mink.Configuration(s.model)
        q = s.home.copy()
        q[s.qids[[5, 12]]] = -1.7
        probe.update(q)
        targets = {side: probe.get_transform_frame_to_world(
            side+'_wrist_yaw_link', 'body') for side in ('left', 'right')}
        for _ in range(240):
            self.assertTrue(s.step(targets), s.reason)
            self.assertTrue(np.all(s.config.q[s.qids] >= LOWER))
            self.assertTrue(np.all(s.config.q[s.qids] <= UPPER))
            for candidate, _ in s.brake_plan:
                self.assertTrue(np.all(candidate[s.qids] >= LOWER))
                self.assertTrue(np.all(candidate[s.qids] <= UPPER))
        for _ in range(1800):
            self.assertTrue(s.step(returning=True), s.reason)
            self.assertTrue(np.all(s.config.q[s.qids] >= LOWER))
            self.assertTrue(np.all(s.config.q[s.qids] <= UPPER))
            if s.return_motion.stage == 'complete':
                break
        self.assertEqual(s.return_motion.stage, 'complete')
        np.testing.assert_allclose(s.config.q[s.qids], s.home[s.qids], atol=1e-5)


if __name__ == '__main__':
    unittest.main()
