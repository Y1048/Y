import sys
import json
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/twist2_right_arm_manual'))
from replay_upstream_mink import build, base


class UpstreamTrackingTests(unittest.TestCase):
    def test_position_priority_recovers_original_orientation_on_return(self):
        rows = json.loads((Path(__file__).parent / 'fixtures/mink_wrist_priority_20260909.json').read_text())
        for row in rows:
            model, planner, trajectory = build()
            q = np.asarray(row['current_q']);origin = q.copy()
            planner.configuration.update(q);trajectory.Reset(q)
            reachable = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
            difficult = base._matrix_to_se3(np.asarray(row['goal_rotation']), np.asarray(row['goal_position']))
            previous = np.zeros(7);scale = 1.
            frozen = np.ones(len(q), dtype=bool);frozen[planner.qpos_ids] = False
            for goal, ticks in ((difficult, 600), (reachable, 900)):
                for _ in range(ticks):
                    step = trajectory.Track(q, goal)
                    self.assertTrue(step.applied, step.status)
                    velocity = np.asarray(step.velocity_rad_s)
                    self.assertTrue(np.all(np.abs(velocity-previous)/trajectory.dt_s <= np.asarray(trajectory.acceleration_limits)+1e-6))
                    self.assertTrue(np.all(np.abs(velocity) <= np.asarray(trajectory.velocity_limits)+1e-6))
                    self.assertLessEqual(abs(trajectory.orientation_priority_scale-scale), trajectory.dt_s+1e-9)
                    q, previous, scale = step.q, velocity, trajectory.orientation_priority_scale
                    self.assertTrue(planner.CheckConfiguration(q))
                    np.testing.assert_allclose(q[frozen], origin[frozen], atol=1e-10)
                planner.configuration.update(q)
                pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
                if goal is difficult:
                    self.assertTrue(trajectory.position_priority_active)
                    self.assertAlmostEqual(scale, .25)
                    self.assertLess(np.linalg.norm(pose.translation()-goal.translation()), .065)
                else:
                    self.assertFalse(trajectory.position_priority_active)
                    self.assertEqual(scale, 1.)
                    self.assertLess(np.linalg.norm(pose.translation()-goal.translation()), .003)
                    self.assertLess(np.degrees(base._rotation_error_radians(goal.rotation().as_matrix(),pose.rotation().as_matrix())), .2)

    def test_priority_hysteresis_and_pinch_reset(self):
        row = json.loads((Path(__file__).parent / 'fixtures/mink_wrist_priority_20260909.json').read_text())[0]
        model, planner, trajectory = build()
        q = np.asarray(row['current_q']);planner.configuration.update(q);trajectory.Reset(q)
        pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        outside = base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation()+[.09,0,0])
        for _ in range(10):trajectory._update_orientation_priority(q, outside, .006)
        self.assertFalse(trajectory.position_priority_active)
        trajectory._update_orientation_priority(q, pose, .006)
        for _ in range(10):trajectory._update_orientation_priority(q, outside, .006)
        self.assertFalse(trajectory.position_priority_active)
        for _ in range(60):trajectory._update_orientation_priority(q, outside, .006)
        self.assertTrue(trajectory.position_priority_active)
        self.assertAlmostEqual(trajectory.orientation_priority_scale, .25)
        trajectory.BeginReturn(q)
        self.assertFalse(trajectory.position_priority_active)
        self.assertEqual(trajectory.orientation_priority_scale, 1.)
        np.testing.assert_allclose(planner.wrist_task.orientation_cost, 2.)

    def test_recorded_boundary_lifts_elbow_without_stopping(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/mink_elbow_boundary_20260909.json').read_text())
        model, planner, trajectory = build()
        q = np.asarray(fixture['current_q'])
        original = q.copy()
        planner.configuration.update(q)
        trajectory.Reset(q)
        goal = base._matrix_to_se3(np.array(fixture['goal_rotation']), np.array(fixture['goal_position']))
        elbow_z = planner.configuration.get_transform_frame_to_world('right_elbow_link', 'body').translation()[2]
        previous = np.zeros(7)
        frozen = np.ones(len(q), dtype=bool)
        frozen[planner.qpos_ids] = False
        for _ in range(300):
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            velocity = np.array(step.velocity_rad_s)
            self.assertTrue(np.all(np.abs((velocity-previous)/trajectory.dt_s)
                <= np.array(trajectory.acceleration_limits)+1e-6))
            self.assertTrue(np.all(np.abs(velocity) <= np.array(trajectory.velocity_limits)+1e-6))
            q, previous = step.q, velocity
            self.assertTrue(planner.CheckConfiguration(q))
            np.testing.assert_allclose(q[frozen], original[frozen], atol=1e-10)
        planner.configuration.update(q)
        raised = planner.configuration.get_transform_frame_to_world('right_elbow_link', 'body').translation()[2]
        wrist = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body').translation()
        self.assertGreater(raised-elbow_z, .05)
        self.assertLess(np.linalg.norm(wrist-goal.translation()), .06)
        trajectory.Reset(q)
        self.assertFalse(trajectory.elbow_assist_active)

    def test_fixed_cartesian_goals_do_not_overshoot_at_sixty_degree_acceleration(self):
        for distance in (.02, .05):
            with self.subTest(distance=distance):
                model, planner, trajectory = build()
                np.testing.assert_allclose(trajectory.acceleration_limits, np.deg2rad([60.]*7))
                q = base._initial_configuration(model)
                original = q.copy()
                planner.configuration.update(q)
                trajectory.Reset(q)
                pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
                target = pose.translation().copy() + [distance, 0, 0]
                goal = base._matrix_to_se3(pose.rotation().as_matrix(), target)
                previous = np.zeros(7)
                frozen = np.ones(len(q), dtype=bool)
                frozen[planner.qpos_ids] = False
                for _ in range(600):
                    step = trajectory.Track(q, goal)
                    self.assertTrue(step.applied, step.status)
                    velocity = np.asarray(step.velocity_rad_s)
                    self.assertTrue(np.all(np.abs((velocity-previous)/trajectory.dt_s)
                        <= np.asarray(trajectory.acceleration_limits)+1e-6))
                    q, previous = step.q, velocity
                    np.testing.assert_allclose(q[frozen], original[frozen], atol=1e-10)
                    planner.configuration.update(q)
                    position = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body').translation()
                    self.assertLessEqual(position[0]-target[0], 1e-4)
                self.assertLess(np.linalg.norm(position-target), .003)

    def test_free_motion_has_no_velocity_reset_jumps(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        goal = base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation() + [.02, 0, 0])
        previous = np.zeros(7)
        for _ in range(120):
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            velocity = np.asarray(step.velocity_rad_s)
            observed = (velocity - previous) / trajectory.dt_s
            self.assertTrue(np.all(np.abs(observed) <= np.asarray(trajectory.acceleration_limits)+1e-6))
            q, previous = step.q, velocity

    def test_solver_failure_brakes_instead_of_resetting(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        trajectory.acceleration_bound.previous[0] = .1
        trajectory._solve_velocity = lambda: None
        goal = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        step = trajectory.Track(q, goal)
        self.assertTrue(step.applied, step.status)
        self.assertEqual(step.status, 'upstream_braking')
        self.assertGreater(step.velocity_rad_s[0], 0.)
        self.assertAlmostEqual(step.velocity_rad_s[0], .1-np.deg2rad(60)*trajectory.dt_s)

    def test_tracking_and_return_seed_preserve_other_joints(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        goal = base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation() + [.02, 0, 0])
        step = trajectory.Track(q, goal)
        self.assertTrue(step.applied, step.status)
        mask = np.ones(len(q), dtype=bool)
        mask[planner.qpos_ids] = False
        np.testing.assert_allclose(step.q[mask], q[mask], atol=1e-10)
        self.assertTrue(planner.CheckConfiguration(step.q))
        trajectory.BeginReturn(step.q)
        returned = trajectory.Step(step.q, q)
        self.assertTrue(returned.applied, returned.status)
        self.assertLessEqual(max(abs(x) for x in returned.acceleration_rad_s2), np.deg2rad(60) + 1e-6)

    def test_exact_collision_rejection_keeps_pose(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        goal = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        planner.CheckConfiguration = lambda _: False
        step = trajectory.Track(q, goal)
        self.assertFalse(step.applied)
        self.assertEqual(step.status, 'upstream_collision_hold')
        np.testing.assert_array_equal(step.q, q)
        self.assertIsNotNone(trajectory.rejected_sample)


if __name__ == '__main__':
    unittest.main()
