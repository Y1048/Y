#!/usr/bin/env python3
"""SDK-neutral tests for the supported Jog result guard (R46)."""

from __future__ import annotations

import unittest

from g1_right_arm_jog_entry import apply_release_result_guard


class RightArmJogReleaseGuardTests(unittest.TestCase):
    def test_no_publisher_remains_disabled_without_unknown_state(self) -> None:
        payload = {
            "passed": False,
            "publisher_created": False,
            "command_output_enabled": False,
            "release_zero_frames": 0,
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertFalse(result["release_attempted"])
        self.assertFalse(result["zero_release_completed"])
        self.assertFalse(result["output_state_unknown"])
        self.assertFalse(result["command_output_enabled"])

    def test_incomplete_zero_tail_is_fail_closed(self) -> None:
        payload = {
            "passed": False,
            "publisher_created": True,
            "command_output_enabled": False,
            "release_zero_frames": 4,
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertTrue(result["release_attempted"])
        self.assertFalse(result["zero_release_completed"])
        self.assertTrue(result["output_state_unknown"])
        self.assertTrue(result["command_output_enabled"])
        self.assertFalse(result["passed"])
        self.assertIn("zero_tail_incomplete", result["release_fault"])

    def test_release_error_keeps_output_unknown_even_with_full_count(self) -> None:
        payload = {
            "passed": False,
            "publisher_created": True,
            "command_output_enabled": False,
            "release_zero_frames": 25,
            "emergency_zero_release_error": "OSError: write failed",
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertFalse(result["zero_release_completed"])
        self.assertTrue(result["output_state_unknown"])
        self.assertTrue(result["command_output_enabled"])
        self.assertIn("write failed", result["release_fault"])

    def test_fault_with_complete_zero_tail_reports_safe_output_but_not_pass(self) -> None:
        payload = {
            "passed": False,
            "publisher_created": True,
            "command_output_enabled": True,
            "release_zero_frames": 25,
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertTrue(result["zero_release_completed"])
        self.assertFalse(result["output_state_unknown"])
        self.assertFalse(result["command_output_enabled"])
        self.assertFalse(result["passed"])
        self.assertEqual(0.0, result["last_successful_weight"])

    def test_nominal_pass_requires_complete_zero_tail(self) -> None:
        payload = {
            "passed": True,
            "publisher_created": True,
            "command_output_enabled": False,
            "release_zero_frames": 25,
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertTrue(result["passed"])
        self.assertTrue(result["release_ramp_completed"])
        self.assertTrue(result["zero_release_completed"])
        self.assertFalse(result["command_output_enabled"])

    def test_nominal_pass_is_revoked_if_zero_tail_is_short(self) -> None:
        payload = {
            "passed": True,
            "publisher_created": True,
            "command_output_enabled": False,
            "release_zero_frames": 24,
        }
        result = apply_release_result_guard(payload, release_zero_cycles=25)
        self.assertFalse(result["passed"])
        self.assertTrue(result["output_state_unknown"])
        self.assertTrue(result["command_output_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
