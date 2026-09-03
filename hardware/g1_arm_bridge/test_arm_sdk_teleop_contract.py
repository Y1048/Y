#!/usr/bin/env python3
"""Offline unit tests for the locked Gate 7 command-intent contract."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import (
    Gate7ContractError,
    Gate7TeleopController,
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
    plan_minimum_jerk_return,
)
from g1_joint_contract import G1_29_JOINT_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"


def _replace_dual(all_q, dual_q):
    values = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        values[index] = value
    return tuple(values)


def _sample(
    regular,
    sequence,
    mode,
    *,
    right_offset_deg=0.0,
    age_s=0.0,
    workspace=False,
    collision=False,
    session="session-a",
):
    dual = list(regular.dual_arm_q_rad)
    dual[7] += math.radians(right_offset_deg)
    all_q = _replace_dual(regular.reference_all_joint_q_rad, dual)
    active = mode == "active"
    value = {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": sequence,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": list(all_q),
        "right_arm": {
            "joints": list(all_q[22:29]),
            "active": active,
            "workspace_limited": workspace,
            "collision_limited": collision,
            "minimum_clearance_m": 0.011 if collision else 0.040,
            "command_state": "active" if active else "idle",
        },
        "input_command_mode": mode,
        "session_id": session,
        "input_packet_age_s": age_s,
        "timestamp": 1.0,
    }
    return parse_mink_arm_sample(json.dumps(value))


class ArmSdkTeleopContractTests(unittest.TestCase):
    def setUp(self):
        self.config = load_gate7_config(CONFIG_PATH)
        self.regular = load_regular_arm_pose(REGULAR_PATH)
        self.measured = _replace_dual(
            self.regular.reference_all_joint_q_rad,
            self.regular.dual_arm_q_rad,
        )

    def _controller(self, validator=lambda _trajectory, _all_q: (True, "ok")):
        return Gate7TeleopController(
            self.regular,
            self.config,
            return_path_validator=validator,
        )

    def _engage(self, controller):
        controller.step(_sample(self.regular, 0, "active"), self.measured, 0.01)
        return controller.step(
            _sample(self.regular, 1, "active", right_offset_deg=1.0),
            self.measured,
            0.01,
        )

    def test_repository_config_is_locked(self):
        self.assertFalse(self.config.hardware_output_authorized)
        self.assertEqual(
            10.0,
            self.config.unintended_hold_before_regular_return_s,
        )

    def test_packet_rejects_mismatched_right_arm_vector(self):
        sample = _sample(self.regular, 0, "active")
        value = {
            "schema": "g1.mink.right_arm.state.v1",
            "sequence": sample.sequence,
            "state_source": "mink_simulation",
            "all_joint_names": list(G1_29_JOINT_NAMES),
            "all_joint_q_rad": list(sample.all_joint_q_rad),
            "right_arm": {
                "joints": [0.0] * 7,
                "active": True,
                "workspace_limited": False,
                "collision_limited": False,
                "minimum_clearance_m": 0.040,
                "command_state": "active",
            },
            "input_command_mode": "active",
            "session_id": "session-a",
            "input_packet_age_s": 0.0,
            "timestamp": 1.0,
        }
        with self.assertRaisesRegex(Gate7ContractError, "does not match"):
            parse_mink_arm_sample(json.dumps(value))

    def test_missing_disengage_reason_is_rejected_not_inferred(self):
        sample = _sample(self.regular, 0, "idle")
        value = {
            "schema": "g1.mink.right_arm.state.v1",
            "sequence": sample.sequence,
            "state_source": "mink_simulation",
            "all_joint_names": list(G1_29_JOINT_NAMES),
            "all_joint_q_rad": list(sample.all_joint_q_rad),
            "right_arm": {
                "joints": list(sample.right_arm_q_rad),
                "active": False,
                "workspace_limited": False,
                "collision_limited": False,
                "minimum_clearance_m": 0.040,
                "command_state": "idle",
            },
            "session_id": "session-a",
            "input_packet_age_s": 0.0,
            "timestamp": 1.0,
        }
        with self.assertRaisesRegex(Gate7ContractError, "input_command_mode"):
            parse_mink_arm_sample(json.dumps(value))

    def test_collision_nearby_above_minimum_does_not_block_tracking(self):
        controller = self._controller()
        controller.step(_sample(self.regular, 0, "active"), self.measured, 0.01)
        sample = _sample(self.regular, 1, "active", right_offset_deg=1.0)
        value = {
            "schema": "g1.mink.right_arm.state.v1",
            "sequence": sample.sequence,
            "state_source": "mink_simulation",
            "all_joint_names": list(G1_29_JOINT_NAMES),
            "all_joint_q_rad": list(sample.all_joint_q_rad),
            "right_arm": {
                "joints": list(sample.right_arm_q_rad),
                "active": True,
                "workspace_limited": False,
                "collision_limited": True,
                "minimum_clearance_m": 0.027,
                "command_state": "active",
            },
            "input_command_mode": "active",
            "session_id": "session-a",
            "input_packet_age_s": 0.0,
            "timestamp": 1.0,
        }
        decision = controller.step(
            parse_mink_arm_sample(json.dumps(value)), self.measured, 0.01
        )
        self.assertEqual("TRACK_MINK_RIGHT", decision.state)

    def test_active_tracking_preserves_left_arm(self):
        controller = self._controller()
        decision = self._engage(controller)
        self.assertEqual("TRACK_MINK_RIGHT", decision.state)
        self.assertEqual(
            self.regular.dual_arm_q_rad[:7],
            decision.target_dual_arm_q_rad[:7],
        )

    def test_only_active_to_pinch_starts_return(self):
        controller = self._controller()
        controller.step(
            _sample(self.regular, 0, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        decision = controller.step(
            _sample(self.regular, 1, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("HOLD_CURRENT", decision.state)

        controller = self._controller()
        self._engage(controller)
        decision = controller.step(
            _sample(self.regular, 2, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("REGULAR_RETURN", decision.state)
        self.assertEqual("intentional_pinch_return", decision.reason)

    def test_pinch_uses_validated_return_when_current_sample_reports_collision(self):
        controller = self._controller()
        self._engage(controller)
        decision = controller.step(
            _sample(
                self.regular,
                2,
                "pinch_disengaged",
                collision=True,
            ),
            self.measured,
            0.01,
        )
        self.assertEqual("REGULAR_RETURN", decision.state)
        self.assertEqual("intentional_pinch_return", decision.reason)

    def test_faults_enter_safety_hold_before_timeout(self):
        cases = (
            (_sample(self.regular, 2, "tracking_disengaged"), "tracking_loss_hold"),
            (_sample(self.regular, 2, "workspace_exit", workspace=True), "workspace_hold"),
            (_sample(self.regular, 2, "idle", collision=True), "collision_hold"),
            (
                _sample(
                    self.regular,
                    2,
                    "idle",
                    age_s=self.config.input_timeout_s + 0.001,
                ),
                "input_stale",
            ),
        )
        for sample, reason in cases:
            with self.subTest(reason=reason):
                controller = self._controller()
                self._engage(controller)
                decision = controller.step(sample, self.measured, 0.01)
                self.assertEqual("SAFETY_HOLD", decision.state)
                self.assertEqual(reason, decision.reason)

    def test_fault_recovery_before_timeout_resumes_tracking(self):
        controller = self._controller()
        self._engage(controller)
        decision = controller.step(
            _sample(self.regular, 2, "tracking_disengaged"),
            self.measured,
            9.0,
        )
        self.assertEqual("SAFETY_HOLD", decision.state)

        decision = controller.step(
            _sample(self.regular, 3, "active", right_offset_deg=1.0),
            self.measured,
            0.01,
        )
        self.assertEqual("TRACK_MINK_RIGHT", decision.state)

        decision = controller.step(
            _sample(self.regular, 4, "tracking_disengaged"),
            self.measured,
            1.1,
        )
        self.assertEqual("SAFETY_HOLD", decision.state)

    def test_persistent_fault_returns_after_ten_seconds(self):
        controller = self._controller()
        self._engage(controller)
        decision = controller.step(
            _sample(self.regular, 2, "tracking_disengaged"),
            self.measured,
            5.0,
        )
        self.assertEqual("SAFETY_HOLD", decision.state)

        decision = controller.step(None, self.measured, 5.0)
        self.assertEqual("REGULAR_RETURN", decision.state)
        self.assertEqual("unintended_hold_timeout_return", decision.reason)

    def test_idle_before_first_active_never_starts_timeout_return(self):
        controller = self._controller()
        controller.step(_sample(self.regular, 0, "idle"), self.measured, 0.01)
        decision = controller.step(
            _sample(self.regular, 1, "idle"),
            self.measured,
            11.0,
        )
        self.assertEqual("HOLD_CURRENT", decision.state)
        self.assertEqual("inactive_hold", decision.reason)

    def test_unvalidated_return_is_denied(self):
        controller = self._controller(validator=None)
        self._engage(controller)
        decision = controller.step(
            _sample(self.regular, 2, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("HOLD_CURRENT", decision.state)
        self.assertEqual("return_path_unvalidated", decision.reason)

    def test_rejected_return_path_is_denied(self):
        controller = self._controller(
            validator=lambda _trajectory, _all_q: (False, "collision_sample")
        )
        self._engage(controller)
        decision = controller.step(
            _sample(self.regular, 2, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("HOLD_CURRENT", decision.state)
        self.assertEqual(
            "return_path_rejected:collision_sample",
            decision.reason,
        )

    def test_tracking_loss_during_intentional_return_does_not_cancel_it(self):
        controller = self._controller()
        self._engage(controller)
        returning = controller.step(
            _sample(self.regular, 2, "pinch_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("REGULAR_RETURN", returning.state)

        decision = controller.step(
            _sample(self.regular, 3, "tracking_disengaged"),
            self.measured,
            0.01,
        )
        self.assertEqual("REGULAR_RETURN", decision.state)
        self.assertEqual("intentional_pinch_return", decision.reason)
        self.assertGreater(decision.return_progress, returning.return_progress)

    def test_minimum_jerk_trajectory_has_exact_endpoints_and_limits(self):
        start = list(self.regular.dual_arm_q_rad)
        start[0] += math.radians(20.0)
        start[4] -= math.radians(30.0)
        trajectory = plan_minimum_jerk_return(
            start,
            self.regular.dual_arm_q_rad,
            self.config,
        )
        samples = trajectory.discrete_samples()
        self.assertEqual(tuple(start), samples[0].q_rad)
        for actual, expected in zip(
            samples[-1].q_rad, self.regular.dual_arm_q_rad
        ):
            self.assertAlmostEqual(expected, actual, places=12)
        for point in samples:
            for value, limit in zip(
                point.dq_rad_s, self.config.velocity_limits_rad_s
            ):
                self.assertLessEqual(abs(value), limit + 1e-9)
            for value, limit in zip(
                point.ddq_rad_s2, self.config.acceleration_limits_rad_s2
            ):
                self.assertLessEqual(abs(value), limit + 1e-9)
            for value, limit in zip(
                point.jerk_rad_s3, self.config.jerk_limits_rad_s3
            ):
                self.assertLessEqual(abs(value), limit + 1e-9)
        for joint in range(14):
            low = min(start[joint], self.regular.dual_arm_q_rad[joint]) - 1e-12
            high = max(start[joint], self.regular.dual_arm_q_rad[joint]) + 1e-12
            self.assertTrue(all(low <= point.q_rad[joint] <= high for point in samples))

    def test_non_increasing_sequence_is_rejected(self):
        controller = self._controller()
        controller.step(_sample(self.regular, 1, "active"), self.measured, 0.01)
        with self.assertRaisesRegex(Gate7ContractError, "non-increasing"):
            controller.step(
                _sample(self.regular, 1, "active"), self.measured, 0.01
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
