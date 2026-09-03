#!/usr/bin/env python3
"""Offline checks for the locked ten-degree Gate 7 motion profile."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from arm_sdk_teleop_contract import load_gate7_config
from gate7_live_arm_sdk import LoadLiveHardwareConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE7_CONFIG = PROJECT_ROOT / "config" / "g1_gate7_visible_motion_mink_arm_sdk.json"
HARDWARE_CONFIG = (
    PROJECT_ROOT / "config" / "g1_gate7_visible_motion_hardware_output.json"
)


class Gate7VisibleMotionProfileTests(unittest.TestCase):
    def test_profile_is_locked_and_bounded(self) -> None:
        gate7 = load_gate7_config(GATE7_CONFIG)
        hardware = LoadLiveHardwareConfig(HARDWARE_CONFIG)

        self.assertFalse(gate7.hardware_output_authorized)
        self.assertFalse(hardware.hardware_output_authorized)
        self.assertEqual(1.0, gate7.command_weight)
        self.assertAlmostEqual(math.radians(10.0), gate7.proximal_max_velocity_rad_s)
        self.assertAlmostEqual(math.radians(25.0), gate7.wrist_max_velocity_rad_s)
        self.assertEqual(30.0, hardware.maximum_active_duration_s)
        self.assertAlmostEqual(
            math.radians(10.0), hardware.maximum_start_pose_excursion_rad
        )
        self.assertEqual(25, hardware.release_zero_cycles)


if __name__ == "__main__":
    unittest.main(verbosity=2)
