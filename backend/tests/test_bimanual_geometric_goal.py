"""Synthetic geometric IK checks; not measured Quest or G1 validation."""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mink
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_geometric_goal as geometric
from g1_bimanual_sim import BimanualSimulation


class GeometricGoalTests(unittest.TestCase):
    def setUp(self):
        self.sim = BimanualSimulation()

    def translated(self, distance):
        return {side: mink.SE3.from_rotation_and_translation(
            pose.rotation(), pose.translation() + np.array([distance, 0., .02]))
            for side, pose in self.sim.home_targets.items()}

    def assert_witness(self, result):
        self.assertTrue(result['valid'])
        self.assertTrue(np.isfinite(result['q']).all())
        self.assertGreaterEqual(result['minimum_clearance_m'], self.sim.clearance_m)
        self.assertGreaterEqual(self.sim.clearance(result['q']), self.sim.clearance_m)
        q = result['q'][self.sim.qids]
        lower, upper = geometric._ranges(self.sim)
        self.assertTrue(np.all(q >= lower - 1e-9))
        self.assertTrue(np.all(q <= upper + 1e-9))
        self.sim.config.update(result['q'])
        for side in ('left', 'right'):
            expected = self.sim.config.get_transform_frame_to_world(side + '_wrist_yaw_link', 'body')
            np.testing.assert_allclose(result['poses'][side].as_matrix(), expected.as_matrix(), atol=1e-12)

    def test_known_reachable_joint_witness_goals_converge(self):
        # Goals come from valid joint configurations, so reachability is known
        # independently of this solver's residual or a guessed Cartesian box.
        for arm_delta in ([0., 0., 0., 0., .4, .2, -.3],
                          [-.5, .1, -.1, -.2, .15, .1, -.1]):
            with self.subTest(arm_delta=arm_delta):
                witness = self.sim.home.copy()
                witness[self.sim.qids] += np.tile(arm_delta, 2)
                self.assertGreater(self.sim.clearance(witness), self.sim.clearance_m)
                self.sim.config.update(witness)
                goals = geometric._poses(self.sim)
                self.sim.config.update(self.sim.home)
                result = geometric.solve_geometric_goal(self.sim, goals)
                self.assert_witness(result)
                self.assertEqual(result['status'], 'geometric_goal_converged')
                self.assertLessEqual(max(result['position_error_m'].values()), geometric.POSITION_TOLERANCE_M)
                self.assertLessEqual(max(result['orientation_error_rad'].values()), geometric.ORIENTATION_TOLERANCE_RAD)

    def test_reachable_goal_does_not_stay_at_initial_command_wrist(self):
        goals = self.translated(.08)
        result = geometric.solve_geometric_goal(self.sim, goals)
        self.assert_witness(result)
        self.assertEqual(result['status'], 'geometric_goal_converged')
        for side in ('left', 'right'):
            self.assertLess(np.linalg.norm(result['poses'][side].translation() - goals[side].translation()), .001)
            self.assertGreater(np.linalg.norm(result['poses'][side].translation() - self.sim.home_targets[side].translation()), .075)

    def test_unreachable_goal_returns_checked_partial_not_raw_request(self):
        goals = self.translated(.7)
        result = geometric.solve_geometric_goal(self.sim, goals)
        self.assert_witness(result)
        self.assertEqual(result['status'], 'geometric_goal_partial')
        self.assertGreater(min(result['position_error_m'].values()), .2)
        self.assertLessEqual(result['iterations'], geometric.MAX_ITERATIONS)

    def test_torso_and_overlapping_hand_targets_keep_coupled_clearance(self):
        for position in ([0., 0., .9], [.3, 0., .9]):
            with self.subTest(position=position):
                self.sim.config.update(self.sim.home)
                goals = {side: mink.SE3.from_rotation_and_translation(
                    pose.rotation(), np.array(position)) for side, pose in self.sim.home_targets.items()}
                result = geometric.solve_geometric_goal(self.sim, goals)
                self.assert_witness(result)
                self.assertEqual(result['status'], 'geometric_goal_partial')
                self.assertGreater(min(result['position_error_m'].values()), .01)

    def test_rotation_conflict_preserves_reachable_position_and_reports_residual(self):
        goals = {side: mink.SE3.from_rotation_and_translation(
            pose.rotation() @ mink.SO3.exp(np.array([0., np.pi, 0.])),
            pose.translation()) for side, pose in self.sim.home_targets.items()}
        result = geometric.solve_geometric_goal(self.sim, goals)
        self.assert_witness(result)
        self.assertEqual(result['status'], 'geometric_goal_partial')
        self.assertLess(max(result['position_error_m'].values()), .001)
        self.assertGreater(min(result['orientation_error_rad'].values()), .1)

    def test_velocity_acceleration_history_does_not_define_geometric_target(self):
        goals = self.translated(.08)
        expected = geometric.solve_geometric_goal(self.sim, goals)
        other = BimanualSimulation()
        other.velocity[other.dofs] = np.linspace(-1., 1., 14)
        other.acceleration[other.dofs] = np.linspace(-2., 2., 14)
        other.brake_plan = [(other.home.copy(), other.velocity.copy())]
        result = geometric.solve_geometric_goal(other, goals)
        np.testing.assert_allclose(result['q'], expected['q'], atol=1e-12, rtol=0.)

    def test_private_model_preserves_parent_and_input_goals(self):
        goals = self.translated(.08)
        original = {side: goal.as_matrix().copy() for side, goal in goals.items()}
        q, velocity = self.sim.config.q.copy(), self.sim.velocity.copy()
        ranges = self.sim.model.jnt_range.copy()
        preferences = {side: policy.posture_reference.copy() for side, policy in self.sim.motion.items()}
        private = copy.deepcopy(self.sim, {id(self.sim.model): self.sim.model})
        result = geometric.solve_geometric_goal(private, goals)
        self.assertTrue(result['valid'])
        np.testing.assert_array_equal(self.sim.config.q, q)
        np.testing.assert_array_equal(self.sim.velocity, velocity)
        np.testing.assert_array_equal(self.sim.model.jnt_range, ranges)
        for side in ('left', 'right'):
            np.testing.assert_array_equal(goals[side].as_matrix(), original[side])
            np.testing.assert_array_equal(self.sim.motion[side].posture_reference, preferences[side])

    def test_common_base_yaw_rotates_result_without_changing_joints(self):
        goals = self.translated(.08)
        first = geometric.solve_geometric_goal(self.sim, goals)
        rotated = BimanualSimulation()
        rotated.set_base_yaw(.8)
        rotation = mink.SO3.from_matrix(rotated.base_rotation)
        rotated_goals = {side: mink.SE3.from_rotation_and_translation(
            rotation @ goal.rotation(), rotated.base_rotation @ goal.translation())
            for side, goal in goals.items()}
        second = geometric.solve_geometric_goal(rotated, rotated_goals)
        np.testing.assert_allclose(first['q'][self.sim.qids], second['q'][rotated.qids], atol=1e-8, rtol=0.)
        for side in ('left', 'right'):
            np.testing.assert_allclose(rotated.base_rotation @ first['poses'][side].translation(),
                                       second['poses'][side].translation(), atol=1e-9, rtol=0.)

    def test_small_budget_is_partial_and_never_claims_convergence(self):
        result = geometric.solve_geometric_goal(self.sim, self.translated(.08), max_iterations=1)
        self.assert_witness(result)
        self.assertEqual(result['status'], 'geometric_goal_partial')
        self.assertEqual(result['iterations'], 1)

    def test_invalid_inputs_and_start_are_rejected(self):
        with self.assertRaises(ValueError):
            geometric.solve_geometric_goal(self.sim, {}, max_iterations=1)
        with self.assertRaises(ValueError):
            geometric.solve_geometric_goal(self.sim, self.translated(.08), max_iterations=0)
        goals = self.translated(.08)
        goals['left'] = mink.SE3.from_rotation_and_translation(mink.SO3.identity(), np.full(3, np.nan))
        with self.assertRaises(ValueError):
            geometric.solve_geometric_goal(self.sim, goals)
        goals['left'] = mink.SE3.from_rotation_and_translation(mink.SO3(np.zeros(4)), np.zeros(3))
        with self.assertRaises(ValueError):
            geometric.solve_geometric_goal(self.sim, goals)
        q = self.sim.home.copy()
        q[self.sim.qids[0]] = self.sim.ranges[0, 1] + .01
        self.sim.config.update(q)
        self.assertFalse(geometric.solve_geometric_goal(self.sim, self.translated(.08))['valid'])

    def test_interior_collision_rejects_clear_endpoints(self):
        start = self.sim.home.copy()
        displacement = np.zeros(14)
        displacement[0] = .1
        def clearance(q, threshold=None):
            travelled = abs(q[self.sim.qids[0]] - start[self.sim.qids[0]])
            return .004 if .03 < travelled < .07 else .02
        with patch.object(self.sim, 'clearance', side_effect=clearance):
            candidate, distance = geometric._checked_segment(self.sim, start, displacement)
        self.assertIsNone(candidate)
        self.assertIsNone(distance)

    def test_solver_failure_keeps_valid_start_with_explicit_partial_status(self):
        with patch.object(geometric.qpsolvers, 'solve_problem', return_value=None):
            result = geometric.solve_geometric_goal(self.sim, self.translated(.08))
        self.assert_witness(result)
        self.assertEqual(result['status'], 'geometric_goal_partial')
        self.assertEqual(result['termination'], 'qp_unavailable')
        np.testing.assert_array_equal(result['q'], self.sim.home)

    def position_tasks_for_native_result_check(self):
        tasks = []
        for side, goal in self.translated(.08).items():
            task = mink.FrameTask(side + '_wrist_yaw_link', 'body',
                                  1., 0., gain=.8, lm_damping=0.)
            task.set_target(goal)
            tasks.append(task)
        return tasks

    def test_native_success_rejects_nonfinite_and_wrong_shape_steps(self):
        # A successful native status is not proof that a usable joint vector
        # was returned. Keep the real Mink objective and mock only that result.
        tasks = self.position_tasks_for_native_result_check()
        bounds = (np.vstack((np.eye(14), -np.eye(14))), np.full(28, .1))
        bad_steps = [np.full(14, np.nan), np.full(14, np.inf),
                     np.zeros(13), np.zeros((14, 1))]
        for index, step in enumerate(bad_steps):
            with self.subTest(index=index), patch.object(
                    geometric.qpsolvers, 'solve_problem',
                    return_value=SimpleNamespace(found=True, x=step)):
                self.assertIsNone(geometric._solve(tasks, self.sim, bounds))

    def test_native_success_rejects_inequality_violation(self):
        tasks = self.position_tasks_for_native_result_check()
        bounds = (np.vstack((np.eye(14), -np.eye(14))), np.full(28, .1))
        for sign in (-1., 1.):
            step = np.zeros(14)
            step[0] = sign * (.1 + 2e-7)
            with self.subTest(sign=sign), patch.object(
                    geometric.qpsolvers, 'solve_problem',
                    return_value=SimpleNamespace(found=True, x=step)):
                self.assertIsNone(geometric._solve(tasks, self.sim, bounds))

    def test_native_success_rejects_original_equality_violation(self):
        tasks = self.position_tasks_for_native_result_check()
        bounds = (np.vstack((np.eye(14), -np.eye(14))), np.full(28, .1))
        # Non-unit rows ensure this protects the original physical equality,
        # including if the native solver later receives normalized rows.
        a = np.eye(14)[:2] * np.array([[.25], [4.]])
        valid = np.zeros(14)
        valid[:2] = [.02, -.03]
        b = a @ valid
        for joint in (0, 1):
            for sign in (-1., 1.):
                step = valid.copy()
                step[joint] += sign * 2e-7 / a[joint, joint]
                with self.subTest(joint=joint, sign=sign), patch.object(
                        geometric.qpsolvers, 'solve_problem',
                        return_value=SimpleNamespace(found=True, x=step)):
                    self.assertIsNone(geometric._solve(
                        tasks, self.sim, bounds, equality=(a, b)))

    def test_valid_equality_result_preserves_task_config_and_bounds(self):
        tasks = self.position_tasks_for_native_result_check()
        bounds = (np.vstack((np.eye(14), -np.eye(14))), np.full(28, .1))
        step = np.linspace(-.03, .03, 14)
        a = np.eye(14)[:2] * np.array([[.25], [4.]])
        b = a @ step
        original_q = self.sim.config.q.copy()
        original_arrays = [value.copy() for value in (*bounds, a, b, step)]
        original_tasks = [(task.transform_target_to_world.as_matrix().copy(),
                           task.compute_error(self.sim.config).copy(),
                           task.compute_jacobian(self.sim.config).copy())
                          for task in tasks]
        with patch.object(geometric.qpsolvers, 'solve_problem',
                          return_value=SimpleNamespace(found=True, x=step)):
            result = geometric._solve(tasks, self.sim, bounds, equality=(a, b))
        np.testing.assert_array_equal(result, step)
        np.testing.assert_array_equal(self.sim.config.q, original_q)
        for actual, expected in zip((*bounds, a, b, step), original_arrays):
            np.testing.assert_array_equal(actual, expected)
        for task, (target, error, jacobian) in zip(tasks, original_tasks):
            np.testing.assert_array_equal(task.transform_target_to_world.as_matrix(), target)
            np.testing.assert_array_equal(task.compute_error(self.sim.config), error)
            np.testing.assert_array_equal(task.compute_jacobian(self.sim.config), jacobian)

    def test_clearance_pruning_preserves_exact_sampled_minimum(self):
        origin = self.sim.home.copy()
        displacement = np.tile([-.1, .02, -.01, -.02, .02, .02, -.01], 2)
        expected_clearance = self.sim.clearance
        fast_q, fast_minimum = geometric._checked_segment(
            self.sim, origin, displacement, expected_clearance(origin))
        with patch.object(self.sim, 'clearance',
                          side_effect=lambda q, threshold=None: expected_clearance(q)):
            full_q, full_minimum = geometric._checked_segment(
                self.sim, origin, displacement, expected_clearance(origin))
        np.testing.assert_array_equal(fast_q, full_q)
        self.assertAlmostEqual(fast_minimum, full_minimum, places=12)

    def test_geometric_warm_start_is_stable_while_live_seed_changes(self):
        goals = self.translated(.7)
        previous = None
        samples = []
        for frame in range(10):
            # A different valid live command seed must not select a fresh
            # redundant local branch on every display calculation.
            live = self.sim.home.copy()
            live[self.sim.qids] += np.tile([-.01 * frame, 0., 0., 0., 0., 0., 0.], 2)
            self.sim.config.update(live)
            result = geometric.solve_geometric_goal(self.sim, goals, initial_q=previous)
            self.assert_witness(result)
            previous = result['q'].copy()
            samples.append(np.stack([result['poses'][side].translation() for side in ('left', 'right')]))
        self.assertLess(np.max(np.linalg.norm(np.ptp(np.array(samples)[-6:], axis=0), axis=1)), .002)
        # Warm starts must also follow a changed, reachable request instead of
        # becoming a held marker unrelated to the new goals.
        near = self.translated(.08)
        for _ in range(6):
            self.sim.config.update(self.sim.home)
            result = geometric.solve_geometric_goal(self.sim, near, initial_q=previous)
            self.assert_witness(result)
            previous = result['q'].copy()
        self.assertLess(max(result['position_error_m'].values()), .001)

    def test_invalid_warm_start_is_explicit_and_preserves_current_configuration(self):
        for kind in ('nonfinite', 'range', 'frozen', 'shape'):
            warm = self.sim.home.copy()
            if kind == 'nonfinite': warm[self.sim.qids[0]] = np.nan
            elif kind == 'range': warm[self.sim.qids[0]] = self.sim.ranges[0, 1] + .1
            elif kind == 'frozen': warm[self.sim.base_qadr] += .01
            else: warm = warm[:-1]
            result = geometric.solve_geometric_goal(self.sim, self.translated(.08), initial_q=warm)
            self.assertFalse(result['valid'])
            self.assertEqual(result['status'], 'invalid_warm_start')
            np.testing.assert_array_equal(self.sim.config.q, self.sim.home)
        self.assertTrue(geometric.solve_geometric_goal(self.sim, self.translated(.08))['valid'])

    def test_time_budget_preserves_only_last_fully_checked_witness(self):
        # Time expires during the first segment, after a QP succeeds. This must
        # not return the unchecked endpoint or partially sampled candidate.
        values = iter([0., .001, .002, .003, .004, .005, .05, .06])
        with patch.object(geometric.time, 'perf_counter', side_effect=lambda: next(values, .1)):
            result = geometric.solve_geometric_goal(
                self.sim, self.translated(.08), max_duration_s=.04)
        self.assert_witness(result)
        self.assertEqual(result['termination'], 'time_budget')
        self.assertEqual(result['status'], 'geometric_goal_partial')
        self.assertEqual(result['iterations'], 0)
        np.testing.assert_array_equal(result['q'], self.sim.home)

    def test_time_budget_expiration_retains_prior_accepted_progress(self):
        calls = [0]
        def clock():
            calls[0] += 1
            return calls[0] * .001
        with patch.object(geometric.time, 'perf_counter', side_effect=clock):
            result = geometric.solve_geometric_goal(
                self.sim, self.translated(.7), max_duration_s=.08)
        self.assert_witness(result)
        self.assertEqual(result['termination'], 'time_budget')
        self.assertGreater(result['iterations'], 0)
        self.assertGreater(np.linalg.norm(result['q'] - self.sim.home), 0.)

    def test_invalid_time_budgets_are_rejected(self):
        for value in (0., -.1, float('nan'), float('inf'), True, '.04'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                geometric.solve_geometric_goal(self.sim, self.translated(.08), max_duration_s=value)


if __name__ == '__main__':
    unittest.main()
