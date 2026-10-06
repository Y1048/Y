"""Split objective contract; no hardware, sockets or user-input prediction."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_sim import BimanualSimulation, mink
from g1_bimanual_profile import TRACKING, RETURN


class SplitTrackingTests(unittest.TestCase):
    def test_two_frame_tasks_share_target_but_not_cost_or_rate(self):
        sim = BimanualSimulation()
        for side, policy in sim.motion.items():
            with self.subTest(side=side):
                goal = sim.home_targets[side]
                tasks = policy.prepare(goal, .2)
                frames = [task for task in tasks if isinstance(task, mink.FrameTask)]
                self.assertEqual(frames, [policy.position_task, policy.orientation_task])
                self.assertIs(policy.configuration, sim.config)
                self.assertTrue(np.all(np.asarray(policy.position_task.position_cost) > 0))
                self.assertTrue(np.all(np.asarray(policy.position_task.orientation_cost) == 0))
                self.assertTrue(np.all(np.asarray(policy.orientation_task.position_cost) == 0))
                self.assertTrue(np.all(np.asarray(policy.orientation_task.orientation_cost) > 0))
                self.assertAlmostEqual(policy.position_task.gain, sim.dt * 12.)
                self.assertAlmostEqual(policy.orientation_task.gain, sim.dt * 1.5)
                np.testing.assert_array_equal(policy.effective_target_position, goal.translation())
                np.testing.assert_allclose(policy.position_task.compute_error(sim.config), 0., atol=1e-12)
                np.testing.assert_allclose(policy.orientation_task.compute_error(sim.config), 0., atol=1e-12)
        self.assertIsNot(sim.motion['left'].position_task, sim.motion['right'].position_task)

    def test_reset_disables_both_diagnostic_rates(self):
        sim = BimanualSimulation()
        for side, policy in sim.motion.items():
            policy.prepare(sim.home_targets[side], .2)
            self.assertEqual(policy.diagnostics()['position_approach_rate_s'], 12.)
            self.assertEqual(policy.diagnostics()['orientation_approach_rate_s'], 1.5)
            policy.reset(sim.home)
            self.assertEqual(policy.diagnostics()['position_approach_rate_s'], 0.)
            self.assertEqual(policy.diagnostics()['orientation_approach_rate_s'], 0.)

    def test_return_and_tracking_numeric_contracts_are_explicit(self):
        self.assertAlmostEqual(np.rad2deg(TRACKING.joint_acceleration_limit_rad_s2), 300.)
        self.assertAlmostEqual(np.rad2deg(RETURN.joint_acceleration_limit_rad_s2), 90.)
        np.testing.assert_allclose(np.rad2deg(TRACKING.joint_velocity_limits_rad_s),
                                   ([150.] * 4 + [180.] * 3) * 2)
        np.testing.assert_allclose(np.rad2deg(RETURN.joint_velocity_limits_rad_s),
                                   ([90.] * 4 + [180.] * 3) * 2)
        self.assertEqual(TRACKING.hard_clearance_m, .005)
        self.assertEqual(TRACKING.wrist_priority_proximal_damping_scale, 14.)


if __name__ == '__main__':
    unittest.main()
