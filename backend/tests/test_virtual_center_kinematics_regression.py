"""Offline numerical checks: no viewer, network, SDK, or physical output."""

import json
import math
import sys
import unittest
from pathlib import Path

import mink
import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_virtual_center_kinematics as probe


class VirtualCenterKinematicsRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probe.base._prepare_mink_xml()
        cls.model = mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        probe.base._apply_operational_joint_limits(cls.model)
        cls.initial_q = probe.base._initial_configuration(cls.model)
        cls.qpos = [int(cls.model.jnt_qposadr[probe.base._joint_id(cls.model, name)])
                    for name in probe.base.g1.RIGHT_ARM_JOINTS]
        cls.initial_q[cls.qpos] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])

    def CheckLimits(self, result):
        self.assertGreaterEqual(result["sampled_minimum_clearance_mm"], 19.5)
        self.assertLessEqual(result["maximum_joint_limit_violation_rad"], 1e-8)
        self.assertLessEqual(result["maximum_frozen_joint_drift_rad"], 1e-8)
        velocity = result["maximum_joint_velocity_deg_s"]
        self.assertLessEqual(max(velocity[:4]), 40.0 + 1e-6)
        self.assertLessEqual(max(velocity[4:]), 100.0 + 1e-6)

    def test_orientation_jacobian_matches_finite_difference(self):
        result = probe.CheckJacobian(self.model, self.initial_q)
        self.assertGreater(result["legacy_max_derivative_error"], 0.5)
        self.assertLess(result["current_max_derivative_error"], 1e-6)

    def test_pose_diagnostics_roundtrip_through_gate7_contract(self):
        configuration = mink.Configuration(self.model)
        configuration.update(self.initial_q)
        pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        all_qpos = [int(self.model.jnt_qposadr[probe.base._joint_id(self.model, name)])
                    for name in probe.base.g1.G1_29_JOINTS]
        packet = probe.base._state_packet(configuration, self.qpos, all_qpos, False,
                                         pose.translation(), None, False)
        packet["right_arm"].update(probe.live.orientation_diagnostics(
            np.eye(3), pose.rotation().as_matrix()))
        payload = json.dumps(packet, allow_nan=False).encode("utf-8")
        from arm_sdk_teleop_contract import parse_mink_arm_sample
        parse_mink_arm_sample(payload)
        restored = json.loads(payload)
        np.testing.assert_array_equal(restored["right_arm"]["target_rotation_matrix_robot"], np.eye(3))
        np.testing.assert_allclose(restored["right_arm"]["wrist_rotation_matrix_robot"], pose.rotation().as_matrix())

    def test_wrist_only_motion_does_not_swing_proximal_joints(self):
        for index in (4, 5, 6):
            with self.subTest(wrist_index=index):
                target_configuration = mink.Configuration(self.model)

                def TargetAt(seconds):
                    q = self.initial_q.copy()
                    q[self.qpos[index]] += math.radians(25) * math.sin(2 * math.pi * seconds / 12)
                    target_configuration.update(q)
                    return target_configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

                result = probe.RunCase(self.model, self.initial_q, TargetAt(0), "exact_posture", 12,
                                       TargetAt, clearance_stride=1)
                self.assertLess(result["maximum_proximal_excursion_deg"], 0.5)
                self.assertLess(result["orientation_error_p95_deg"], 0.5)
                self.assertLess(result["position_error_p95_cm"], 0.1)
                self.CheckLimits(result)

    def test_mixed_known_reachable_target_converges(self):
        target_configuration = mink.Configuration(self.model)
        q = self.initial_q.copy()
        q[self.qpos] += np.deg2rad([-20, 5, 15, 10, 20, 15, -20])
        target_configuration.update(q)
        target = target_configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        result = probe.RunCase(self.model, self.initial_q, target, "exact_posture", 6, clearance_stride=1)
        self.assertLess(result["position_error_cm"], 0.5)
        self.assertLess(result["orientation_error_deg"], 0.1)
        self.CheckLimits(result)


if __name__ == "__main__":
    unittest.main()
