#!/usr/bin/env python3
"""Offline tests for the Gate 7 fault-injection matrix."""

from __future__ import annotations

import unittest

from gate7_fault_injection_matrix import BuildFaultMatrix


class Gate7FaultInjectionMatrixTests(unittest.TestCase):
    def test_all_synthetic_fault_scenarios_fail_closed(self):
        result = BuildFaultMatrix()
        self.assertTrue(result["passed"], result["scenarios"])
        self.assertEqual(8, result["scenario_count"])
        self.assertFalse(result["publisher_present"])
        self.assertFalse(result["command_output_enabled"])
        self.assertFalse(result["hardware_output_authorized"])

        stale = result["scenarios"]["stale_packet_recovery"]
        self.assertTrue(stale["target_frozen"])
        self.assertEqual("TRACK_MINK_RIGHT", stale["recovered_state"])

        persistent = result["scenarios"]["persistent_packet_loss"]
        self.assertEqual("REGULAR_HOLD", persistent["final_state"])
        transition_states = [item["state"] for item in persistent["transitions"]]
        self.assertIn("SAFETY_HOLD", transition_states)
        self.assertIn("REGULAR_RETURN", transition_states)


if __name__ == "__main__":
    unittest.main()
