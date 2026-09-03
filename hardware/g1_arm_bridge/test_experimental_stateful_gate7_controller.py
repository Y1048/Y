#!/usr/bin/env python3
"""Offline contract tests for the replacement-style experimental Gate 7."""

from __future__ import annotations

import unittest

from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose
from experimental_stateful_gate7_controller import (
    ExperimentalStatefulGate7TeleopController,
)
from gate7_capture_quality import CONFIG_PATH, REGULAR_PATH, _replace_dual
from gate7_hardware_virtual_e2e import _packet
from arm_sdk_teleop_contract import parse_mink_arm_sample


class ExperimentalStatefulGate7ControllerTests(unittest.TestCase):
    def test_active_target_uses_stateful_limiter_without_physical_authority(self):
        config = load_gate7_config(CONFIG_PATH)
        regular = load_regular_arm_pose(REGULAR_PATH)
        controller = ExperimentalStatefulGate7TeleopController(
            regular,
            config,
            return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
        )
        measured = _replace_dual(
            regular.reference_all_joint_q_rad,
            regular.dual_arm_q_rad,
        )
        first = parse_mink_arm_sample(_packet(regular, 0))
        second = parse_mink_arm_sample(_packet(regular, 1))
        controller.step(first, measured, 0.004)
        decision = controller.step(second, measured, 0.004)
        self.assertEqual("TRACK_MINK_RIGHT", decision.state)
        self.assertIsNotNone(controller.motion_limiter)
        continued = controller.step(None, measured, 0.004)
        self.assertEqual("TRACK_MINK_RIGHT", continued.state)
        self.assertTrue(continued.command_candidate_valid)
        self.assertFalse(config.hardware_output_authorized)


if __name__ == "__main__":
    unittest.main()
