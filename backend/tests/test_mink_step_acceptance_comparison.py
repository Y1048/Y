"""Ensure the offline ablation matches production before changing its merit gate."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_mink_step_acceptance import (
    EvaluateStep, EvaluateLookahead, InspectMerit, InspectEndpointSolutions, BuildPlanner, IncrementCollisionLimit, ResolvedCollisionLimit,
    WristPositionTask, FullOrientationErrorTask, CenterRedundancy, GetLimitAvoidanceStep,
    GetWristOnlySegments, probe,
)


class MinkStepAcceptanceComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        probe.base._apply_operational_joint_limits(cls.model)
        cls.initial = probe.base._initial_configuration(cls.model)
        cls.addresses = [int(cls.model.jnt_qposadr[probe.base._joint_id(cls.model, name)])
                         for name in probe.base.g1.RIGHT_ARM_JOINTS]
        cls.initial[cls.addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])

    def Goal(self, q):
        configuration = probe.mink.Configuration(self.model)
        configuration.update(q)
        return configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

    def test_first_step_matches_actual_production_planner(self):
        for delta in ([0, 0, 0], [0.1, 0, 0.05], [0.4, 0.25, 0.3]):
            production = BuildPlanner(self.model, self.initial)
            audit = BuildPlanner(self.model, self.initial)
            pose = self.Goal(self.initial)
            goal = probe.base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation() + delta)
            q = self.initial.copy()
            for _ in range(12):
                expected = production.Plan(q, goal)
                candidate, decision = EvaluateStep(audit, q, goal)
                np.testing.assert_allclose(candidate, expected.next_q, atol=1e-10)
                q = candidate

    def test_geometry_only_still_rejects_unsafe_and_invalid_velocity(self):
        planner = BuildPlanner(self.model, self.initial)
        goal_q = self.initial.copy()
        goal_q[self.addresses[0]] -= 0.2
        with patch.object(planner, "CheckConfiguration", side_effect=lambda q: np.array_equal(q, self.initial)):
            q, decision = EvaluateStep(planner, self.initial, self.Goal(goal_q), False)
        np.testing.assert_array_equal(q, self.initial)
        self.assertEqual("geometry_hold", decision["status"])
        with patch.object(probe.mink, "solve_ik", return_value=np.full(self.model.nv, np.nan)):
            q, decision = EvaluateStep(planner, self.initial, self.Goal(goal_q), False)
        self.assertEqual("invalid_velocity", decision["status"])
        np.testing.assert_array_equal(q, self.initial)

    def test_merit_only_hold_is_distinguished_from_collision(self):
        planner = BuildPlanner(self.model, self.initial)
        goal_q = self.initial.copy()
        goal_q[self.addresses[0]] -= 0.2
        with patch.object(planner, "GetMerit", return_value=1.0):
            q, decision = EvaluateStep(planner, self.initial, self.Goal(goal_q), True)
            self.assertEqual("merit_hold", decision["status"])
            np.testing.assert_array_equal(q, self.initial)
            q, decision = EvaluateStep(planner, self.initial, self.Goal(goal_q), False)
        self.assertEqual("accepted", decision["status"])
        self.assertGreater(np.max(np.abs(q - self.initial)), 1e-5)
        self.assertTrue(planner.CheckConfiguration(q))

    def test_merit_audit_preserves_configuration_and_directional_derivative(self):
        planner = BuildPlanner(self.model, self.initial)
        pose = self.Goal(self.initial)
        goal = probe.base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation() + [0.03, 0.01, 0.02])
        EvaluateStep(planner, self.initial, goal)
        audit = InspectMerit(planner, self.initial, goal)
        np.testing.assert_array_equal(planner.configuration.q, self.initial)
        velocity = np.zeros(self.model.nv)
        velocity[planner.right_dofs] = audit["velocity_right_rad_s"]
        values = []
        for sign in (-1, 1):
            q = self.initial.copy()
            probe.mujoco.mj_integratePos(self.model, q, velocity, sign * 1e-6)
            planner.configuration.update(q)
            values.append(planner.GetMerit(goal, audit["orientation_scale"]))
        self.assertAlmostEqual(audit["actual_directional_derivative"],
            (values[1] - values[0]) / 2e-6, delta=1e-6)

    def test_cartesian_position_jacobian_matches_all_seven_joint_derivatives(self):
        configuration = probe.mink.Configuration(self.model)
        task = WristPositionTask()
        task.set_target(self.Goal(self.initial))
        for offset in (0, 0.1, -0.15):
            q = self.initial.copy()
            q[self.addresses] += offset
            configuration.update(q)
            jacobian = task.compute_jacobian(configuration)
            for dof in probe.base._right_arm_dof_indices(self.model):
                axis = np.zeros(self.model.nv)
                axis[dof] = 1
                values = []
                for sign in (-1, 1):
                    candidate = q.copy()
                    probe.mujoco.mj_integratePos(self.model, candidate, axis, sign * 1e-6)
                    configuration.update(candidate)
                    values.append(task.compute_error(configuration))
                np.testing.assert_allclose(jacobian[:, dof], (values[1] - values[0]) / 2e-6,
                    atol=1e-8, rtol=1e-6)

    def test_consistent_task_gradient_matches_merit_near_wrist_limit(self):
        planner = BuildPlanner(self.model, self.initial)
        q = self.initial.copy()
        joint = probe.base._joint_id(self.model, probe.base.g1.RIGHT_ARM_JOINTS[4])
        q[self.addresses[4]] = self.model.jnt_range[joint, 0] + 0.01
        goal = self.Goal(self.initial)
        planner.position_task = WristPositionTask()
        planner.orientation_task = FullOrientationErrorTask(self.model)
        planner.tasks[:2] = [planner.position_task, planner.orientation_task]
        planner.position_task.set_target(goal)
        planner.orientation_task.set_target(goal)
        audit = InspectMerit(planner, q, goal)
        gradient = np.sum([t["gradient_right"] for t in audit["tasks"][:2]], axis=0)
        np.testing.assert_allclose(gradient, audit["actual_gradient_right"], atol=1e-7, rtol=1e-6)

    def test_endpoint_audit_accepts_known_safe_goal_without_changing_input(self):
        planner = BuildPlanner(self.model, self.initial)
        planner.configuration.update(self.initial)
        result = InspectEndpointSolutions(planner, self.initial, self.Goal(self.initial))
        self.assertEqual(len(result["endpoints"]), 12)
        self.assertTrue(result["endpoints"][0]["pose_match"])
        self.assertFalse(result["robot_command"])
        np.testing.assert_array_equal(planner.configuration.q, self.initial)
        for endpoint in result["endpoints"]:
            if endpoint["pose_match"]:
                self.assertTrue(endpoint["configuration_valid"])
                self.assertGreaterEqual(endpoint["clearance_mm"], 19.9999)

    def test_increment_bound_reserves_linear_sphere_clearance_at_both_rates(self):
        model = probe.mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <body><joint name="slide" type="slide" axis="1 0 0"/>
            <geom name="moving" type="sphere" size="0.05" mass="1"/></body>
          <body pos="0.13 0 0"><joint name="other" type="slide" axis="1 0 0"/>
            <geom name="fixed" type="sphere" size="0.05" mass="1"/></body>
        </worldbody></mujoco>''')
        configuration = probe.mink.Configuration(model)
        limit = IncrementCollisionLimit(model, [(["moving"], ["fixed"])],
            minimum_distance_from_collisions=0.02, collision_detection_distance=0.1)
        for dt in (1 / 60, 1 / 200):
            inequality = limit.compute_qp_inequalities(configuration, dt)
            np.testing.assert_allclose(inequality.G, [[1, -1]], atol=1e-12)
            np.testing.assert_allclose(inequality.h, [0.0085], atol=1e-12)
            # QP variable is delta-q, not velocity: leave 1.5 mm of the 10 mm gap.
            q = configuration.q.copy()
            probe.mujoco.mj_integratePos(model, q, np.array([inequality.h[0] / dt, 0]), dt)
            data = probe.mujoco.MjData(model)
            data.qpos[:] = q
            probe.mujoco.mj_forward(model, data)
            distance = probe.mujoco.mj_geomDistance(model, data, 0, 1, 0.1, None)
            self.assertAlmostEqual(distance, 0.0215, places=10)

    def test_zero_mesh_witness_normal_matches_finite_difference(self):
        # 녹화 3번 구간 5.65초의 멈춤 자세. 원래 witness 방향과 실제 거리 변화가 반대였다.
        q = np.array([
            4.392805439439132e-14, -7.666026903226974e-16, 0.7799999999999954,
            1, -5.852966459865408e-15, -8.92788069130186e-15, 9.770285958805481e-16,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            3.1101961023921527e-15, -1.2477916415929996e-14, 9.505038416421948e-15,
            0.2908451557159424, 0.214829221367836, -0.02931341528892517,
            0.978631854057312, 0.14132997393608093, 0.016765931621193886, -0.00814927276223898,
            -0.29405185962582764, -0.12498445845308812, 0.957827198473354,
            0.0872664625997166, -0.038627630321619894, 0.1868308441438968, 0.5949817306519907])
        configuration = probe.mink.Configuration(self.model)
        configuration.update(q)
        pair = tuple(probe.mujoco.mj_name2id(self.model, probe.mujoco.mjtObj.mjOBJ_GEOM, name)
            for name in ("mink_collision_torso_link_0_19", "mink_collision_right_shoulder_yaw_link_0_32"))
        limit = ResolvedCollisionLimit(self.model, [([pair[0]], [pair[1]])],
            minimum_distance_from_collisions=0.0205, collision_detection_distance=0.04)
        distance, jacobian = limit.ResolveWitness(configuration, pair)
        velocity = np.zeros(self.model.nv)
        velocity[probe.base._right_arm_dof_indices(self.model)] = [
            -0.16455216798082373, 0.6981317007977389, 0.6981317007977039, 0,
            0.35551624215509836, 0.7051399385750551, -0.2345496542472314]
        values = []
        data = probe.mujoco.MjData(self.model)
        epsilon = 1e-5
        for sign in (-1, 1):
            candidate = q.copy()
            probe.mujoco.mj_integratePos(self.model, candidate, velocity, sign * epsilon)
            data.qpos[:] = candidate
            probe.mujoco.mj_forward(self.model, data)
            values.append(probe.mujoco.mj_geomDistance(self.model, data, *pair, 0.2, None))
        numeric = (values[1] - values[0]) / (2 * epsilon)
        self.assertLess(numeric, -0.09)
        self.assertAlmostEqual(float(jacobian @ velocity), numeric, delta=1e-5)
        self.assertAlmostEqual(distance, 0.020039020210652946, delta=1e-8)
        np.testing.assert_array_equal(configuration.q, q)
        inequality = limit.compute_qp_inequalities(configuration, probe.base.DT)
        self.assertGreater((inequality.G @ (velocity * probe.base.DT) - inequality.h).item(), 0.001)
        tangent = ResolvedCollisionLimit(self.model, [([pair[0]], [pair[1]])],
            minimum_distance_from_collisions=0.0205, collision_detection_distance=0.04,
            recover_reserve=False)
        tangent_inequality = tangent.compute_qp_inequalities(configuration, probe.base.DT)
        np.testing.assert_allclose(tangent_inequality.G, inequality.G)
        np.testing.assert_allclose(tangent_inequality.h, 0)
        self.assertLess(inequality.h.item(), 0)

    def test_unresolved_zero_witness_fails_closed(self):
        limit = ResolvedCollisionLimit(self.model, probe.base._build_collision_pairs(self.model)[0])
        configuration = probe.mink.Configuration(self.model)
        configuration.update(self.initial)
        with patch.object(probe.mujoco, "mj_geomDistance", return_value=0.0):
            with self.assertRaisesRegex(RuntimeError, "Unresolved collision witness"):
                limit.ResolveWitness(configuration, limit.geom_id_pairs[0])
        np.testing.assert_array_equal(configuration.q, self.initial)

    def test_centering_preserves_wrist_twist_limits_and_frozen_dofs(self):
        planner = BuildPlanner(self.model, self.initial)
        planner.configuration.update(self.initial)
        primary = np.zeros(self.model.nv)
        centered, result = CenterRedundancy(planner, primary)
        self.assertEqual(result["status"], "centered")
        self.assertGreater(np.linalg.norm(centered), 1e-4)
        jacobian = planner.configuration.get_frame_jacobian("right_wrist_yaw_link", "body")
        np.testing.assert_allclose(jacobian @ centered, 0, atol=1e-12)
        np.testing.assert_array_equal(centered[planner.frozen_dofs], 0)
        self.assertLessEqual(result["normalized_cost_after"], result["normalized_cost_before"])
        for limit in planner.limits:
            inequality = limit.compute_qp_inequalities(planner.configuration, probe.base.DT)
            if inequality.G is not None:
                self.assertTrue(np.all(inequality.G @ (centered * probe.base.DT) <= inequality.h + 1e-10))
        np.testing.assert_array_equal(planner.configuration.q, self.initial)

    def test_centering_rank_deficiency_retains_primary(self):
        planner = BuildPlanner(self.model, self.initial)
        primary = np.zeros(self.model.nv)
        with patch.object(planner.configuration, "get_frame_jacobian", return_value=np.zeros((6, self.model.nv))):
            centered, result = CenterRedundancy(planner, primary)
        self.assertEqual(result["status"], "rank_deficient")
        np.testing.assert_array_equal(centered, primary)

    def test_centering_invalid_constraint_retains_primary(self):
        planner = BuildPlanner(self.model, self.initial)
        primary = np.zeros(self.model.nv)
        for bound in (np.nan, -np.inf):
            inequality = SimpleNamespace(G=np.zeros((1, self.model.nv)), h=np.array([bound]))
            planner.limits = [SimpleNamespace(compute_qp_inequalities=lambda *args: inequality)]
            centered, result = CenterRedundancy(planner, primary)
            self.assertEqual(result["status"], "invalid_constraint")
            np.testing.assert_array_equal(centered, primary)

    def test_centering_invalid_candidate_falls_back_to_valid_primary(self):
        goal_q = self.initial.copy()
        goal_q[self.addresses[0]] -= 0.2
        goal = self.Goal(goal_q)
        expected, _ = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal)
        for invalid in (np.full(self.model.nv, np.nan), np.full(self.model.nv, 100)):
            with patch("compare_mink_step_acceptance.CenterRedundancy", return_value=(invalid, {"status": "test"})):
                actual, result = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal,
                                              center_redundancy=True)
            self.assertTrue(result["redundancy_fallback"])
            np.testing.assert_allclose(actual, expected, atol=1e-10)

    def test_centering_rejected_finite_step_falls_back_to_primary(self):
        goal_q = self.initial.copy()
        goal_q[self.addresses[0]] -= 0.2
        goal = self.Goal(goal_q)
        expected, _ = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal)
        with patch("compare_mink_step_acceptance.CenterRedundancy",
                   return_value=(np.zeros(self.model.nv), {"status": "test"})):
            actual, result = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal,
                                          center_redundancy=True)
        self.assertTrue(result["redundancy_fallback"])
        np.testing.assert_allclose(actual, expected, atol=1e-10)

    def test_wrist_cycles_use_fk_targets_and_return_to_initial_pose(self):
        cycles = list(GetWristOnlySegments(self.model))
        self.assertEqual(len(cycles), 3)
        for index, (_, packets) in enumerate(cycles, 4):
            self.assertEqual(len(packets), 721)
            for sample, degrees in ((0, 0), (180, 25), (540, -25), (720, 0)):
                q = self.initial.copy()
                q[self.addresses[index]] += np.deg2rad(degrees)
                goal = self.Goal(q)
                arm = packets[sample]["value"]["right_arm"]
                np.testing.assert_allclose(arm["target_position"], goal.translation(), atol=1e-12)
                np.testing.assert_allclose(arm["target_rotation_matrix_robot"],
                                           goal.rotation().as_matrix(), atol=1e-12)

    def test_limit_avoidance_uses_nearest_boundary_not_midpoint(self):
        for point, expected in ((0.0, 0.0), (0.8, 0.0), (0.800001, -0.000001),
                                (0.95, -0.15), (-0.95, 0.15)):
            step, result = GetLimitAvoidanceStep(np.array([point]), np.array([1.0]),
                np.array([-1.0]), np.array([1.0]), -0.4, 0.4, 0.2)
            self.assertAlmostEqual(step, expected, delta=1e-12)
            self.assertLessEqual(result["limit_cost_after_rad2"], result["limit_cost_before_rad2"] + 1e-12)
        step, _ = GetLimitAvoidanceStep(np.array([0.95]), np.array([1.0]),
            np.array([-1.0]), np.array([1.0]), -0.05, 0.4, 0.2)
        self.assertAlmostEqual(step, -0.05, delta=1e-12)
        # QP 허용오차로 0이 구간 바깥에 있어도 실제 허용구간 안에서 푼다.
        for low, high, expected in ((1e-10, 0.1, 1e-10), (-0.1, -1e-10, -1e-10)):
            step, _ = GetLimitAvoidanceStep(np.array([0.0]), np.array([1.0]),
                np.array([-1.0]), np.array([1.0]), low, high, 0.2)
            self.assertEqual(step, expected)

    def test_limit_avoidance_conflicting_boundaries_and_invalid_intervals(self):
        step, _ = GetLimitAvoidanceStep(np.array([0.95, 0.95]), np.array([1.0, -1.0]),
            np.array([-1.0, -1.0]), np.array([1.0, 1.0]), -0.4, 0.4, 0.2)
        self.assertEqual(step, 0.0)
        for margin in (0, -1, np.nan):
            with self.assertRaises(ValueError):
                GetLimitAvoidanceStep(np.array([0.0]), np.array([1.0]),
                    np.array([-1.0]), np.array([1.0]), -0.4, 0.4, margin)

    def test_limit_avoidance_retains_primary_away_from_limits(self):
        goal_q = self.initial.copy()
        goal_q[self.addresses[4]] += np.deg2rad(1)
        goal = self.Goal(goal_q)
        expected, _ = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal)
        actual, result = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal,
            center_redundancy=True, limit_margin_rad=np.deg2rad(18))
        np.testing.assert_allclose(actual, expected, atol=1e-12)
        self.assertEqual(result["redundancy"]["active_joint_indices"], [])
        self.assertEqual(result["redundancy"]["step_rad"], 0.0)

    def test_limit_avoidance_near_wrist_boundary_preserves_linear_constraints(self):
        planner = BuildPlanner(self.model, self.initial)
        q = self.initial.copy()
        q[self.addresses[4]] = np.deg2rad(-105)
        planner.configuration.update(q)
        centered, result = CenterRedundancy(planner, np.zeros(self.model.nv), np.deg2rad(18))
        self.assertEqual(result["active_joint_indices"], [4])
        self.assertLess(result["limit_cost_after_rad2"], result["limit_cost_before_rad2"])
        jacobian = planner.configuration.get_frame_jacobian("right_wrist_yaw_link", "body")
        np.testing.assert_allclose(jacobian @ centered, 0, atol=1e-12)
        np.testing.assert_array_equal(centered[planner.frozen_dofs], 0)
        for limit in planner.limits:
            inequality = limit.compute_qp_inequalities(planner.configuration, probe.base.DT)
            if inequality.G is not None:
                self.assertTrue(np.all(inequality.G @ (centered * probe.base.DT) <= inequality.h + 1e-10))
        np.testing.assert_array_equal(planner.configuration.q, q)

    def test_lookahead_executes_only_first_step_with_checked_preview(self):
        goal_q = self.initial.copy()
        goal_q[self.addresses] += np.deg2rad([-15, 5, 10, 10, 15, 5, -10])
        goal = self.Goal(goal_q)
        planner = BuildPlanner(self.model, self.initial)
        expected, _ = EvaluateStep(BuildPlanner(self.model, self.initial), self.initial, goal)
        actual, result = EvaluateLookahead(planner, self.initial, goal)
        np.testing.assert_allclose(actual, expected, atol=1e-10)
        self.assertEqual(result["lookahead_steps"], 3)
        preview = actual.copy()
        preview[self.addresses] = result["lookahead_target_right_q_rad"]
        self.assertTrue(planner.CheckConfiguration(preview))
        self.assertGreater(np.linalg.norm(preview - actual), 1e-6)
        np.testing.assert_allclose(self.Goal(preview).translation(), result["lookahead_target_position"], atol=1e-12)
        np.testing.assert_array_equal(planner.configuration.q, actual)
        np.testing.assert_allclose(actual[0:self.addresses[0]], self.initial[0:self.addresses[0]], atol=1e-10)

    def test_lookahead_baseline_matches_production_plan_contract(self):
        production = BuildPlanner(self.model, self.initial)
        audit = BuildPlanner(self.model, self.initial)
        goal_q = self.initial.copy()
        goal_q[self.addresses] += np.deg2rad([-15, 5, 10, 10, 15, 5, -10])
        goal = self.Goal(goal_q)
        q = self.initial.copy()
        for _ in range(10):
            expected = production.Plan(q, goal)
            actual, result = EvaluateLookahead(audit, q, goal)
            np.testing.assert_allclose(actual, expected.next_q, atol=1e-10)
            np.testing.assert_allclose(result["lookahead_target_right_q_rad"],
                                       expected.target_q[self.addresses], atol=1e-10)
            np.testing.assert_allclose(result["lookahead_target_position"], expected.target_position, atol=1e-10)
            self.assertEqual(result["lookahead_steps"], expected.accepted_steps)
            q = actual

    def test_lookahead_preserves_actual_policy_even_for_subclass(self):
        planner = BuildPlanner(self.model, self.initial)
        planner.orientation_task = FullOrientationErrorTask(self.model)
        owner = probe.live.VirtualCenterOrientationTask
        calls = []
        goal = self.Goal(self.initial)

        def Step(unused, q, supplied_goal, *args):
            calls.append(q.copy())
            self.assertIs(supplied_goal, goal)
            owner.assist_latched = len(calls) > 1
            owner.last_min_wrist_margin_deg = 30 if len(calls) == 1 else 1
            planner.orientation_task.cost[:] = len(calls)
            candidate = q.copy()
            candidate[self.addresses[4]] += 0.001
            return candidate, {"status": "accepted", "minimum_path_clearance_mm": 25.0}

        with patch("compare_mink_step_acceptance.EvaluateStep", side_effect=Step):
            actual, result = EvaluateLookahead(planner, self.initial, goal)
        self.assertFalse(owner.assist_latched)
        self.assertEqual(owner.last_min_wrist_margin_deg, 30)
        np.testing.assert_array_equal(planner.orientation_task.cost, np.ones(6))
        self.assertEqual(len(calls), 3)
        self.assertAlmostEqual(actual[self.addresses[4]], self.initial[self.addresses[4]] + 0.001)
        self.assertEqual(result["lookahead_steps"], 3)

    def test_blocked_prediction_never_advances_preview(self):
        planner = BuildPlanner(self.model, self.initial)
        first = self.initial.copy()
        first[self.addresses[4]] += 0.001
        with patch("compare_mink_step_acceptance.EvaluateStep", side_effect=[
                (first, {"status": "accepted", "minimum_path_clearance_mm": 25.0}),
                (first, {"status": "geometry_hold", "minimum_path_clearance_mm": None})]):
            actual, result = EvaluateLookahead(planner, self.initial, self.Goal(self.initial))
        np.testing.assert_array_equal(actual, first)
        np.testing.assert_array_equal(result["lookahead_target_right_q_rad"], first[self.addresses])
        self.assertEqual(result["lookahead_steps"], 1)
        self.assertEqual(result["lookahead_final_status"], "geometry_hold")

    def test_lookahead_restores_policy_after_prediction_error(self):
        planner = BuildPlanner(self.model, self.initial)
        owner = probe.live.VirtualCenterOrientationTask
        calls = []

        def Step(*args):
            calls.append(True)
            owner.assist_latched = len(calls) > 1
            if len(calls) > 1:
                raise RuntimeError("prediction failed")
            return self.initial.copy(), {"status": "accepted", "minimum_path_clearance_mm": 25.0}

        with patch("compare_mink_step_acceptance.EvaluateStep", side_effect=Step):
            with self.assertRaisesRegex(RuntimeError, "prediction failed"):
                EvaluateLookahead(planner, self.initial, self.Goal(self.initial))
        self.assertFalse(owner.assist_latched)
        np.testing.assert_array_equal(planner.configuration.q, self.initial)


if __name__ == "__main__":
    unittest.main()
