"""Offline endpoint and sampled-path diagnostic invariants."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diagnose_mink_collision_feasibility import EndpointProblem, InspectDirectPath, InspectWaypointRoute, InspectShortcuts, BuildPlanner, probe


class CollisionFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        probe.base._apply_operational_joint_limits(cls.model)
        cls.q = probe.base._initial_configuration(cls.model)
        cls.addresses = [int(cls.model.jnt_qposadr[probe.base._joint_id(cls.model, name)])
            for name in probe.base.g1.RIGHT_ARM_JOINTS]
        cls.q[cls.addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
        configuration = probe.mink.Configuration(cls.model)
        configuration.update(cls.q)
        cls.goal = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

    def setUp(self):
        self.planner = BuildPlanner(self.model, self.q)
        self.problem = EndpointProblem(self.planner, self.q, self.goal)

    def test_exact_pose_constraint_jacobian(self):
        joints = self.q[self.addresses].copy() + 0.1
        analytic = self.problem.GetJacobian(joints)
        for index in range(7):
            offset = np.zeros(7)
            offset[index] = 1e-6
            numeric = (self.problem.GetResidual(joints + offset) - self.problem.GetResidual(joints - offset)) / 2e-6
            np.testing.assert_allclose(analytic[:, index], numeric, atol=1e-8, rtol=1e-6)

    def test_known_safe_endpoint_and_short_path(self):
        result = self.problem.InspectEndpoint(self.q[self.addresses])
        self.assertTrue(result["pose_match"])
        end = self.q.copy()
        end[self.addresses[3]] += np.deg2rad(1)
        path = InspectDirectPath(self.planner, self.q, end, spacing_deg=0.05, goal=self.goal)
        self.assertTrue(path["sampled_valid"])
        self.assertGreaterEqual(path["checked_samples"], 21)
        self.assertAlmostEqual(path["velocity_only_minimum_duration_s"], 1 / 40)
        self.assertEqual(path["goal_error"]["merit_increasing_intervals"], path["checked_samples"] - 1)

    def test_path_rejects_unsafe_middle_even_with_valid_endpoints(self):
        end = self.q.copy()
        end[self.addresses[0]] += 0.04

        def GetClearance(q):
            fraction = (q[self.addresses[0]] - self.q[self.addresses[0]]) / 0.04
            return 0.01 if 0.4 < fraction < 0.6 else 0.03

        with patch.object(self.planner, "GetClearance", side_effect=GetClearance), patch.object(
                self.planner, "CheckConfiguration", side_effect=lambda q: GetClearance(q) >= 0.02):
            path = InspectDirectPath(self.planner, self.q, end)
        self.assertFalse(path["sampled_valid"])
        self.assertGreater(path["first_invalid_fraction"], 0.39)
        self.assertLess(path["first_invalid_fraction"], 0.61)

    def test_path_rejects_frozen_change_and_invalid_input(self):
        end = self.q.copy()
        end[0] += 0.01
        with self.assertRaisesRegex(ValueError, "frozen"):
            InspectDirectPath(self.planner, self.q, end)
        for spacing in (0, -1, np.nan, np.inf):
            with self.assertRaises(ValueError):
                InspectDirectPath(self.planner, self.q, self.q, spacing)
        end[self.addresses[0]] = np.nan
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            InspectDirectPath(self.planner, self.q, end)

    def test_problem_freezes_all_other_coordinates_and_input(self):
        joints = self.q[self.addresses] + 0.02
        before = self.q.copy()
        candidate = self.problem.GetConfiguration(joints)
        mask = np.ones(self.model.nq, dtype=bool)
        mask[self.addresses] = False
        np.testing.assert_array_equal(candidate[mask], self.q[mask])
        self.problem.GetResidual(joints)
        self.problem.GetNegativeClearance(joints)
        np.testing.assert_array_equal(self.q, before)

    def test_joint_distance_gradient_and_clearance_constraint(self):
        joints = self.q[self.addresses] + 0.05
        analytic = self.problem.GetJointDistanceJacobian(joints)
        for index in range(7):
            offset = np.zeros(7)
            offset[index] = 1e-6
            numeric = (self.problem.GetJointDistance(joints + offset) -
                self.problem.GetJointDistance(joints - offset)) / 2e-6
            self.assertAlmostEqual(analytic[index], numeric, places=8)
        self.assertEqual(self.problem.GetJointDistance(self.q[self.addresses]), 0)
        with patch.object(self.planner, "GetClearance", return_value=0.019):
            self.assertAlmostEqual(self.problem.GetClearanceResidual(joints), -0.001)

    def test_waypoint_route_metrics_cover_all_legs(self):
        via, end = self.q.copy(), self.q.copy()
        via[self.addresses[3]] += np.deg2rad(0.5)
        end[self.addresses[3]] += np.deg2rad(1)
        route = InspectWaypointRoute(self.planner, [self.q, via, end], self.goal, 0.05, 0.5)
        self.assertTrue(route["sampled_valid"])
        self.assertEqual(len(route["legs"]), 2)
        self.assertAlmostEqual(route["joint_path_length_deg"], 1)
        self.assertAlmostEqual(route["maximum_joint_excursion_deg"], 1)
        self.assertAlmostEqual(route["velocity_only_minimum_duration_s"], 1 / 40)

    def test_shortcut_rechecks_saved_pose_match_flag(self):
        end = self.q.copy()
        end[self.addresses[3]] += 0.2
        baseline = {"results": [{"q": self.q.tolist(), "direct_path": {"sampled_valid": True}}]}
        endpoints = {"results": [{"q": end.tolist(), "pose_match": True}]}
        with self.assertRaisesRegex(ValueError, "No endpoint passes"):
            InspectShortcuts(self.planner, self.q, self.goal, baseline, endpoints, 0.5)


if __name__ == "__main__":
    unittest.main()
