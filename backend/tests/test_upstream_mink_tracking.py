import sys
import json
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/twist2_right_arm_manual'))
from replay_upstream_mink import build, base


class UpstreamTrackingTests(unittest.TestCase):
    def test_fixed_position_rotations_prefer_wrist_but_allow_pivot_compensation(self):
        from compare_mink_stationary_rotation import run
        from g1_upstream_mink_tracking import UpstreamMinkTracking
        for axis in range(3):
            with self.subTest(axis=axis):
                report = run(UpstreamMinkTracking, axis)
                # Pitch needs proximal compensation for the offset wrist axes;
                # roll/yaw must not recruit the redundant arm unnecessarily.
                limit = 4. if axis == 1 else .5
                self.assertLess(report['proximal_excursion_max_deg'], limit)
                self.assertLess(report['position_error_max_mm'], 6.)
                self.assertLess(report['position_error_final_mm'], 2.)
                self.assertLess(report['rotation_error_final_deg'], .5)

    def test_elbow_reference_initializes_without_explicit_reset(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        goal = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        step = trajectory.Track(q, goal)
        self.assertTrue(step.applied, step.status)
        np.testing.assert_allclose(trajectory._elbow_reference_q, q)
        self.assertFalse(trajectory.elbow_assist_active)

    def test_front_target_lifts_elbow_without_ratchet_or_rotation_loss(self):
        fixture = json.loads((Path(__file__).parent /
            'fixtures/mink_front_elbow_20260917.json').read_text())
        model, planner, trajectory = build()
        reference = np.asarray(fixture['posture_reference'])
        q = np.asarray(fixture['current_q'])
        initial = q.copy()
        planner.configuration.update(q)
        initial_z = planner.configuration.get_transform_frame_to_world(
            'right_elbow_link', 'body').translation()[2]
        trajectory.Reset(q)
        planner.posture_reference = reference.copy()
        planner.posture_task.set_target(reference)
        goal = base._matrix_to_se3(np.asarray(fixture['goal_rotation']),
                                   np.asarray(fixture['goal_position']))
        targets = []
        previous = np.zeros(7)
        frozen = np.ones(len(q), dtype=bool)
        frozen[planner.qpos_ids] = False
        for tick in range(600):
            if tick % 100 == 0:
                trajectory.elbow_assist_active = False  # Repeated re-entry cannot raise the anchor.
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            self.assertTrue(trajectory.elbow_assist_active)
            targets.append(trajectory.elbow_task.target_position[1:3].copy())
            q = step.q
            velocity = np.asarray(step.velocity_rad_s)
            self.assertTrue(np.all(abs(velocity-previous)/trajectory.dt_s <=
                np.asarray(trajectory.acceleration_limits)+1e-5))
            self.assertTrue(np.all(abs(velocity) <= np.asarray(trajectory.velocity_limits)+1e-6))
            previous = velocity
            self.assertTrue(planner.CheckConfiguration(q))
            np.testing.assert_allclose(q[frozen], initial[frozen], atol=1e-10)
        np.testing.assert_allclose(targets, np.broadcast_to(targets[0], (600, 2)), atol=1e-12)
        planner.configuration.update(q)
        elbow_z = planner.configuration.get_transform_frame_to_world('right_elbow_link', 'body').translation()[2]
        self.assertGreater(elbow_z-initial_z, .04)
        self.assertLess(elbow_z-initial_z, .10)
        wrist = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        self.assertLess(np.linalg.norm(wrist.translation()-trajectory.effective_target_position), .08)
        self.assertLess(np.degrees(base._rotation_error_radians(
            goal.rotation().as_matrix(), wrist.rotation().as_matrix())), 5.)
        trajectory.BeginReturn(q)
        self.assertFalse(trajectory.elbow_assist_active)

    def test_elbow_bias_jacobian_is_world_lateral_and_vertical(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        q[planner.qpos_ids[:3]] += [.25, -.2, .4]
        planner.configuration.update(q)
        pose = planner.configuration.get_transform_frame_to_world('right_elbow_link', 'body')
        trajectory.elbow_task.set_target(base._matrix_to_se3(
            pose.rotation().as_matrix(), pose.translation()+[.1, .02, .08]))
        np.testing.assert_allclose(trajectory.elbow_task.compute_error(planner.configuration), [-.02, -.08])
        jacobian = trajectory.elbow_task.compute_jacobian(planner.configuration)
        for dof, address in zip(planner.right_dofs, planner.qpos_ids):
            plus, minus = q.copy(), q.copy()
            plus[address] += 1e-6
            minus[address] -= 1e-6
            planner.configuration.update(plus)
            error_plus = trajectory.elbow_task.compute_error(planner.configuration).copy()
            planner.configuration.update(minus)
            error_minus = trajectory.elbow_task.compute_error(planner.configuration).copy()
            np.testing.assert_allclose((error_plus-error_minus)/2e-6, jacobian[:, dof], atol=1e-7)

    def test_projected_recorded_goal_recovers_wrist_rotation_without_winding(self):
        fixture = json.loads((Path(__file__).parent /
            'fixtures/mink_projected_wrist_rotation_20260917.json').read_text())
        model, planner, trajectory = build()
        q = np.asarray(fixture['current_q'])
        initial = q.copy()
        reference = np.asarray(fixture['posture_reference'])
        planner.configuration.update(q)
        trajectory.Reset(q)
        planner.posture_reference = reference.copy()
        planner.posture_task.set_target(reference)
        goal = base._matrix_to_se3(np.asarray(fixture['goal_rotation']),
                                   np.asarray(fixture['goal_position']))
        original_rotation = planner.configuration.get_transform_frame_to_world(
            'right_wrist_yaw_link', 'body').rotation().as_matrix()
        self.assertGreater(np.degrees(base._rotation_error_radians(
            goal.rotation().as_matrix(), original_rotation)), 90.)
        previous = np.zeros(7)
        frozen = np.ones(len(q), dtype=bool)
        frozen[planner.qpos_ids] = False
        for _ in range(600):
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            self.assertTrue(trajectory.target_projected)
            self.assertFalse(trajectory.collision_orientation_relaxed)
            q = step.q
            velocity = np.asarray(step.velocity_rad_s)
            self.assertTrue(np.all(abs(velocity-previous)/trajectory.dt_s <=
                np.asarray(trajectory.acceleration_limits)+1e-5))
            self.assertTrue(np.all(abs(velocity) <=
                np.asarray(trajectory.velocity_limits)+1e-6))
            previous = velocity
            self.assertTrue(planner.CheckConfiguration(q))
            self.assertLessEqual(abs(q[planner.qpos_ids[2]]-reference[planner.qpos_ids[2]]),
                trajectory.priority_shoulder_yaw_envelope_rad+1e-5)
            np.testing.assert_allclose(q[frozen], initial[frozen], atol=1e-10)
        planner.configuration.update(q)
        pose = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        self.assertLess(np.degrees(base._rotation_error_radians(
            goal.rotation().as_matrix(), pose.rotation().as_matrix())), 5.)

    def test_target_inside_torso_is_projected_without_elbow_assist(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        wrist = planner.configuration.get_transform_frame_to_world(
            'right_wrist_yaw_link', 'body')
        torso_geom = trajectory.torso_geom_ids[0]
        inside = planner.configuration.data.geom_xpos[torso_geom].copy()
        goal = base._matrix_to_se3(wrist.rotation().as_matrix(), inside)
        step = trajectory.Track(q, goal)
        self.assertTrue(step.applied, step.status)
        self.assertTrue(trajectory.target_projected)
        self.assertFalse(trajectory.collision_orientation_relaxed)
        self.assertGreater(trajectory.target_projection_distance_m, 0.)
        self.assertFalse(trajectory.elbow_assist_active)
        self.assertFalse(np.shares_memory(
            trajectory.raw_target_position, trajectory.effective_target_position))
        self.assertGreater(np.linalg.norm(
            trajectory.raw_target_position-trajectory.effective_target_position), .01)

    def test_inside_torso_target_can_slide_along_projected_boundary(self):
        model, planner, trajectory = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        trajectory.Reset(q)
        wrist = planner.configuration.get_transform_frame_to_world(
            'right_wrist_yaw_link', 'body')
        torso_geom = trajectory.torso_geom_ids[0]
        center = planner.configuration.data.geom_xpos[torso_geom].copy()
        rotation = planner.configuration.data.geom_xmat[torso_geom].reshape(3, 3)
        effective = []
        for offset in (-.02, .02):
            inside = center + rotation[:, 2] * offset
            goal = base._matrix_to_se3(wrist.rotation().as_matrix(), inside)
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            self.assertTrue(trajectory.target_projected)
            self.assertFalse(trajectory.collision_orientation_relaxed)
            effective.append(trajectory.effective_target_position.copy())
        self.assertGreater(np.linalg.norm(effective[1]-effective[0]), .02)

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
                    if trajectory.target_projected:
                        self.assertFalse(trajectory.collision_orientation_relaxed)
                        self.assertLess(
                            np.linalg.norm(pose.translation()-trajectory.effective_target_position),
                            np.linalg.norm(pose.translation()-goal.translation()),
                        )
                        self.assertGreater(trajectory.target_projection_distance_m, .01)
                    else:
                        self.assertTrue(trajectory.position_priority_active)
                        self.assertAlmostEqual(scale, .5)
                        self.assertLess(np.linalg.norm(
                            pose.translation()-goal.translation()), .065)
                else:
                    self.assertFalse(trajectory.collision_orientation_relaxed)
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
        for _ in range(10):trajectory._update_orientation_priority(q, outside, .006)
        self.assertAlmostEqual(trajectory.orientation_priority_scale, .5)
        trajectory.BeginReturn(q)
        self.assertFalse(trajectory.position_priority_active)
        self.assertEqual(trajectory.orientation_priority_scale, 1.)
        np.testing.assert_allclose(planner.wrist_task.orientation_cost, 2.)

    def test_position_priority_bounds_shoulder_yaw_without_changing_speed_limits(self):
        row = json.loads((Path(__file__).parent / 'fixtures/mink_wrist_priority_20260909.json').read_text())[0]
        model, planner, trajectory = build()
        q = np.asarray(row['current_q']); planner.configuration.update(q); trajectory.Reset(q)
        goal = base._matrix_to_se3(np.asarray(row['goal_rotation']), np.asarray(row['goal_position']))
        yaw_reference = float(q[planner.qpos_ids[2]])
        max_offset = 0.
        peak_speed = 0.
        for _ in range(900):
            step = trajectory.Track(q, goal)
            self.assertTrue(step.applied, step.status)
            q = step.q
            max_offset = max(max_offset, abs(q[planner.qpos_ids[2]]-yaw_reference))
            peak_speed = max(peak_speed, abs(step.velocity_rad_s[2]))
        self.assertLessEqual(
            max_offset, trajectory.priority_shoulder_yaw_envelope_rad+1e-5)
        self.assertEqual(trajectory.velocity_limits[2], np.deg2rad(90.))
        self.assertGreater(peak_speed, np.deg2rad(10.))

    def test_recorded_inside_body_goal_slides_with_bounded_elbow_lift(self):
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
        self.assertTrue(trajectory.target_projected)
        self.assertFalse(trajectory.collision_orientation_relaxed)
        self.assertLess(raised-elbow_z, .09)
        self.assertLess(np.linalg.norm(
            wrist-trajectory.effective_target_position), .05)
        self.assertGreater(np.linalg.norm(wrist-goal.translation()), .05)
        trajectory.Reset(q)
        self.assertFalse(trajectory.collision_orientation_relaxed)
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
