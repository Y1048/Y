#!/usr/bin/env python3
"""Offline tests for the shared G1 hardware runtime state schema."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hardware_state import FaultCode, HardwarePhase, build_status, write_status


class HardwareStateTests(unittest.TestCase):
    def test_read_only_status_is_fail_closed(self) -> None:
        status = build_status(
            phase=HardwarePhase.READ_ONLY_ACTIVE,
            component="test",
            command_output_enabled=False,
            publisher_present=False,
        )
        self.assertTrue(status["fail_closed"])
        self.assertFalse(status["fault"]["active"])
        self.assertEqual(status["fault"]["code"], "NONE")

    def test_fault_requires_fault_phase(self) -> None:
        with self.assertRaises(ValueError):
            build_status(
                phase=HardwarePhase.READ_ONLY_ACTIVE,
                component="test",
                command_output_enabled=False,
                publisher_present=False,
                fault_code=FaultCode.LOWSTATE_TIMEOUT,
            )

    def test_fault_phase_requires_fault_code(self) -> None:
        with self.assertRaises(ValueError):
            build_status(
                phase=HardwarePhase.FAULT,
                component="test",
                command_output_enabled=False,
                publisher_present=False,
            )

    def test_command_output_requires_publisher(self) -> None:
        with self.assertRaises(ValueError):
            build_status(
                phase=HardwarePhase.HOLD_ACTIVE,
                component="test",
                command_output_enabled=True,
                publisher_present=False,
            )

    def test_atomic_json_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "status.json"
            status = build_status(
                phase=HardwarePhase.READ_ONLY_WAIT,
                component="test",
                command_output_enabled=False,
                publisher_present=False,
                details={"packets": 0},
            )
            write_status(path, status)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["phase"], "READ_ONLY_WAIT")
            self.assertEqual(loaded["details"]["packets"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
