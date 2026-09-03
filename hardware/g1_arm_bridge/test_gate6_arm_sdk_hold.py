#!/usr/bin/env python3
"""Offline tests for Gate 6 authorization and SDK-message adaptation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from arm_sdk_hold_contract import build_measured_hold_frame, dual_arm_from_all_joints
from gate6_arm_sdk_hold import (
    DEFAULT_CONFIG_PATH,
    _apply_frame,
    load_runtime_config,
    validate_output_authorization,
    validate_precheck,
)

HERE = Path(__file__).resolve().parent
GATE6_PROGRAM = HERE / "gate6_arm_sdk_hold.py"


class _FakeMotorCommand:
    def __init__(self) -> None:
        self.mode = 0
        self.q = 0.0
        self.dq = 0.0
        self.tau = 0.0
        self.kp = 0.0
        self.kd = 0.0


class _FakeLowCmd:
    def __init__(self) -> None:
        self.mode_pr = 0
        self.mode_machine = 0
        self.motor_cmd = [_FakeMotorCommand() for _ in range(35)]


class Gate6ArmSdkHoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_runtime_config(DEFAULT_CONFIG_PATH)

    def test_repository_config_blocks_hardware_output(self) -> None:
        self.assertFalse(self.config.hardware_output_authorized)
        with self.assertRaisesRegex(PermissionError, "hardware_output_authorized"):
            validate_output_authorization(
                self.config,
                enable_hardware_output=True,
                confirmation=self.config.hardware_confirmation_phrase,
                grounded_regular_confirmation=(
                    self.config.grounded_regular_confirmation_phrase
                ),
            )

    def test_blocked_hardware_process_creates_no_publisher_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            event_path = Path(temp_dir) / "events.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(GATE6_PROGRAM),
                    "no-network-interface-needed",
                    "--enable-hardware-output",
                    "--confirm",
                    self.config.hardware_confirmation_phrase,
                    "--status-json",
                    str(status_path),
                    "--event-log",
                    str(event_path),
                ],
                cwd=HERE,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            self.assertEqual(10, result.returncode, result.stdout + result.stderr)
            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("OUTPUT_NOT_AUTHORIZED", status["fault"]["code"])
            self.assertFalse(status["publisher_present"])
            self.assertFalse(status["command_output_enabled"])

    def test_authorized_config_still_requires_exact_phrase(self) -> None:
        config = replace(self.config, hardware_output_authorized=True)
        with self.assertRaisesRegex(PermissionError, "confirmation phrase"):
            validate_output_authorization(
                config,
                enable_hardware_output=True,
                confirmation="wrong",
                grounded_regular_confirmation=(
                    config.grounded_regular_confirmation_phrase
                ),
            )
        with self.assertRaisesRegex(PermissionError, "grounded Regular"):
            validate_output_authorization(
                config,
                enable_hardware_output=True,
                confirmation=config.hardware_confirmation_phrase,
                grounded_regular_confirmation="",
            )
        validate_output_authorization(
            config,
            enable_hardware_output=True,
            confirmation=config.hardware_confirmation_phrase,
            grounded_regular_confirmation=(
                config.grounded_regular_confirmation_phrase
            ),
        )

    def test_dry_run_needs_no_hardware_authorization(self) -> None:
        validate_output_authorization(
            self.config,
            enable_hardware_output=False,
            confirmation="",
            grounded_regular_confirmation="",
        )

    def test_precheck_must_be_recent_and_direct_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "precheck.json"
            payload = {
                "schema": "g1.startup_precheck.result.v1",
                "checked_at_unix_ns": time.time_ns(),
                "decision": "DIRECT_TELEOP_READY",
                "recovery_bypass_allowed": True,
                "command_output_enabled": False,
                "publisher_present": False,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(payload, validate_precheck(path, 60.0))
            payload["decision"] = "RECOVERY_REQUIRED"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RECOVERY_REQUIRED"):
                validate_precheck(path, 60.0)

    def test_sdk_adapter_copies_all_contract_slots(self) -> None:
        measured = [0.0] * 29
        measured[15:22] = [0.1, 0.2, 0.0, 0.8, 0.0, 0.0, 0.0]
        measured[22:29] = [0.1, -0.2, 0.0, 0.8, 0.0, 0.0, 0.0]
        frame = build_measured_hold_frame(
            measured,
            dual_arm_from_all_joints(measured),
            mode_pr=0,
            mode_machine=5,
            weight=0.2,
        )
        message = _FakeLowCmd()
        _apply_frame(message, frame)
        self.assertEqual(5, message.mode_machine)
        self.assertEqual(0.2, message.motor_cmd[29].q)
        self.assertEqual(1, message.motor_cmd[22].mode)
        self.assertEqual(0, message.motor_cmd[12].mode)
        self.assertEqual(0.0, message.motor_cmd[12].kp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
