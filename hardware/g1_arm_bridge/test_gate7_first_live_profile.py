#!/usr/bin/env python3
"""Offline checks for the locked first physical Gate 7 VR profile."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from arm_sdk_hold_contract import build_measured_hold_frame
from arm_sdk_teleop_contract import load_gate7_config
from gate7_live_arm_sdk import (
    LoadLiveHardwareConfig,
    ValidateStartPoseExcursion,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIRST_GATE7_CONFIG = (
    PROJECT_ROOT / "config" / "g1_gate7_first_live_mink_arm_sdk.json"
)
FIRST_HARDWARE_CONFIG = (
    PROJECT_ROOT / "config" / "g1_gate7_first_live_hardware_output.json"
)
NORMAL_GATE7_CONFIG = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
NORMAL_HARDWARE_CONFIG = (
    PROJECT_ROOT / "config" / "g1_gate7_live_hardware_output.json"
)


class Gate7FirstLiveProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate7 = load_gate7_config(FIRST_GATE7_CONFIG)
        self.hardware = LoadLiveHardwareConfig(FIRST_HARDWARE_CONFIG)

    def test_first_live_profile_is_locked_and_bounded(self) -> None:
        self.assertFalse(self.gate7.hardware_output_authorized)
        self.assertFalse(self.hardware.hardware_output_authorized)
        self.assertEqual(1.0, self.gate7.command_weight)
        self.assertAlmostEqual(
            math.radians(10.0), self.gate7.proximal_max_velocity_rad_s
        )
        self.assertAlmostEqual(
            math.radians(25.0), self.gate7.wrist_max_velocity_rad_s
        )
        self.assertEqual(20.0, self.hardware.maximum_active_duration_s)
        self.assertAlmostEqual(
            math.radians(5.0), self.hardware.maximum_initial_arm_velocity_rad_s
        )
        self.assertAlmostEqual(
            math.radians(3.0), self.hardware.maximum_start_pose_excursion_rad
        )
        self.assertEqual(25, self.hardware.release_zero_cycles)

    def test_excursion_gate_accepts_boundary_and_rejects_beyond_it(self) -> None:
        measured = [0.0] * 29
        acquisition = tuple(measured[15:29])
        target = list(acquisition)
        target[7] = math.radians(3.0)
        boundary_frame = build_measured_hold_frame(
            measured,
            target,
            mode_pr=0,
            mode_machine=5,
            weight=1.0,
        )
        self.assertAlmostEqual(
            math.radians(3.0),
            ValidateStartPoseExcursion(
                boundary_frame,
                acquisition,
                self.hardware.maximum_start_pose_excursion_rad,
            ),
        )

        target[7] = math.radians(3.01)
        outside_frame = build_measured_hold_frame(
            measured,
            target,
            mode_pr=0,
            mode_machine=5,
            weight=1.0,
        )
        with self.assertRaisesRegex(RuntimeError, "start_pose_excursion_limit"):
            ValidateStartPoseExcursion(
                outside_frame,
                acquisition,
                self.hardware.maximum_start_pose_excursion_rad,
            )

    def test_existing_gate7_profile_remains_locked_and_unchanged(self) -> None:
        normal_gate7 = load_gate7_config(NORMAL_GATE7_CONFIG)
        normal_hardware = LoadLiveHardwareConfig(NORMAL_HARDWARE_CONFIG)
        self.assertFalse(normal_gate7.hardware_output_authorized)
        self.assertFalse(normal_hardware.hardware_output_authorized)
        self.assertEqual(0.2, normal_gate7.command_weight)
        self.assertEqual(60.0, normal_hardware.maximum_active_duration_s)
        self.assertAlmostEqual(
            math.pi, normal_hardware.maximum_start_pose_excursion_rad
        )

    def test_excursion_check_precedes_physical_write(self) -> None:
        source = (
            PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "gate7_live_arm_sdk.py"
        ).read_text(encoding="utf-8")
        loop = source.index("while not stop_requested.is_set()")
        validation = source.index("ValidateStartPoseExcursion(", loop)
        write = source.index("publisher.Write(command_message)", loop)
        self.assertLess(validation, write)


if __name__ == "__main__":
    unittest.main(verbosity=2)
