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
                self.assertAlmostEqual(policy.orientation_task.gain, sim.dt * 3.)
                self.assertAlmostEqual(policy.posture_task.gain, sim.dt * 1.5 / TRACKING.frame_gain)
                self.assertAlmostEqual(policy.shoulder_comfort_task.gain, sim.dt * 1.5)
                np.testing.assert_array_equal(policy.effective_target_position, goal.translation())
                np.testing.assert_allclose(policy.position_task.compute_error(sim.config), 0., atol=1e-12)
                np.testing.assert_allclose(policy.orientation_task.compute_error(sim.config), 0., atol=1e-12)
        self.assertIsNot(sim.motion['left'].position_task, sim.motion['right'].position_task)

    def test_reset_disables_both_diagnostic_rates(self):
        sim = BimanualSimulation()
        for side, policy in sim.motion.items():
            policy.prepare(sim.home_targets[side], .2)
            self.assertEqual(policy.diagnostics()['position_approach_rate_s'], 12.)
            self.assertEqual(policy.diagnostics()['orientation_approach_rate_s'], 3.)
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

    def test_wrist_rotation_converges_without_large_proximal_excursion(self):
        # Synthetic 45-degree roll/yaw step: verifies response, not only constants.
        # Pitch changes wrist-origin position geometrically and has a separate
        # position/orientation tradeoff; do not assert the same bound for pitch.
        for side in ('left', 'right'):
            for axis in (0, 2):
                with self.subTest(side=side, axis=axis):
                    sim = BimanualSimulation()
                    home = sim.home_targets[side]
                    goal = mink.SE3.from_rotation_and_translation(
                        home.rotation() @ mink.SO3.exp(np.eye(3)[axis]*np.pi/4),
                        home.translation())
                    goals = dict(sim.home_targets, **{side: goal})
                    policy = sim.motion[side]
                    for _ in range(66):
                        previous = sim.velocity.copy()
                        self.assertTrue(sim.step(goals), sim.reason)
                        self.assertLessEqual(np.max(np.abs(sim.velocity-previous)),
                            TRACKING.joint_acceleration_limit_rad_s2*sim.dt+1e-6)
                        self.assertTrue(np.all(np.abs(sim.velocity[sim.dofs]) <= sim.caps+1e-6))
                        self.assertGreaterEqual(sim.clearance(sim.config.q), .005)
                        pose = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link', 'body')
                        self.assertLess(np.linalg.norm(pose.translation()-goal.translation()), .003)
                        excursion = np.abs(sim.config.q[policy.qpos_ids]-sim.home[policy.qpos_ids])
                        self.assertLess(np.rad2deg(max(excursion[:4])), 10.)
                        self.assertLess(np.rad2deg(excursion[3]), 1.5)
                    self.assertLess(np.rad2deg(np.linalg.norm(
                        (pose.rotation().inverse() @ goal.rotation()).log())), 5.)

    def test_aligned_held_wrist_keeps_priority_but_translation_releases_it(self):
        sim = BimanualSimulation()
        for side, policy in sim.motion.items():
            with self.subTest(side=side):
                q = sim.home.copy()
                q[policy.qpos_ids[4]] += .4
                sim.config.update(q)
                pose = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link', 'body')
                policy.prepare(pose, .2)
                self.assertGreater(policy.wrist_priority_weight, .9)
                moving = mink.SE3.from_rotation_and_translation(pose.rotation(), pose.translation()+[.02, 0, 0])
                policy.prepare(moving, .2)
                self.assertEqual(policy.wrist_priority_weight, 0.)
                policy.prepare(pose, .005)
                self.assertEqual(policy.wrist_priority_weight, 0.)
                policy.reset(q)
                policy.prepare(pose, .2)
                self.assertLess(policy.wrist_priority_weight, 1e-6)

    def test_common_base_rotation_is_not_a_new_wrist_rotation(self):
        sim = BimanualSimulation()
        references = {s: p.wrist_reference_rotation.copy() for s,p in sim.motion.items()}
        sim.set_base_yaw(.8)
        rotation = mink.SO3.exp(np.array([0.,0.,.8])).as_matrix()
        for side, policy in sim.motion.items():
            np.testing.assert_allclose(policy.wrist_reference_rotation, rotation @ references[side], atol=1e-12)
            pose = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link','body')
            policy.prepare(pose, .2)
            self.assertLess(policy.wrist_priority_weight, 1e-6)


if __name__ == '__main__':
    unittest.main()
