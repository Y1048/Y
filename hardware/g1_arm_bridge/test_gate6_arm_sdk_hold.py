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

from arm_sdk_hold_contract import blend_weight, build_measured_hold_frame, dual_arm_from_all_joints
from gate6_arm_sdk_hold import (
    DEFAULT_CONFIG_PATH,
    _apply_frame,
    _status_details,
    LowStateSnapshot,
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
    def test_weight_comparison_keeps_all_other_command_fields_identical(self):
        measured = (0.0,) * 29
        target = dual_arm_from_all_joints(measured)
        for tick in range(2276):
            frames = []
            for maximum in (0.2, 0.4):
                phase, weight, done = blend_weight(tick / 250.0,
                    ramp_up_s=3.0, hold_s=3.0, ramp_down_s=3.0,
                    maximum_weight=maximum)
                self.assertGreaterEqual(weight, 0.0)
                self.assertLessEqual(weight, maximum)
                self.assertEqual(done, tick >= 2250)
                frames.append(build_measured_hold_frame(measured, target,
                    mode_pr=0, mode_machine=5, weight=weight, config=self.config.safety))
            self.assertAlmostEqual(frames[1].weight, 2 * frames[0].weight)
            self.assertEqual(frames[0].motor_q_rad[:29], frames[1].motor_q_rad[:29])
            self.assertEqual(frames[0].motor_q_rad[30:], frames[1].motor_q_rad[30:])
            for field in ("motor_mode", "motor_kp", "motor_kd", "motor_dq_rad_s", "motor_tau_nm"):
                self.assertEqual(getattr(frames[0], field), getattr(frames[1], field))
        self.assertEqual(frames[1].weight, 0.0)

    def test_hold_diagnostics_separate_fixed_target_from_measured_waist(self):
        initial_q = tuple([0.0] * 29)
        target = dual_arm_from_all_joints(initial_q)
        measured_q = list(initial_q)
        measured_q[13] = 0.1
        snapshot = LowStateSnapshot(time.monotonic(), 123456, 7, 0, 5,
                                    tuple(measured_q), tuple([0.0] * 29))
        frame = build_measured_hold_frame(snapshot.all_q_rad, target,
                    mode_pr=0, mode_machine=5, weight=0.2, config=self.config.safety)
        details = _status_details(network_interface="offline", snapshot=snapshot,
                    target_dual_arm_q_rad=target, mode_form="0", mode_name="ai",
                    weight=0.2, schedule_phase="HOLD", published_frames=1,
                    reason="offline test", command_frame=frame)
        self.assertEqual(details["lowstate_received_unix_ns"], 123456)
        self.assertEqual(details["measured_all_q_rad"][13], 0.1)
        self.assertEqual(details["target_dual_arm_q_rad"], list(target))
        self.assertEqual(details["sampled_command"]["q_rad"][15:29], list(target))
        self.assertEqual(details["sampled_command"]["waist_kp"], [0.0] * 3)
        self.assertFalse(details["sampled_command"]["firmware_acknowledgement"])
        self.assertEqual(snapshot.all_q_rad[13], 0.1)

    def test_blocked_diagnostics_do_not_invent_state_or_command(self):
        details = _status_details(network_interface="", snapshot=None,
                    target_dual_arm_q_rad=None, mode_form=None, mode_name=None,
                    weight=0.0, schedule_phase="BLOCKED", published_frames=0,
                    reason="offline test")
        self.assertIsNone(details["measured_all_q_rad"])
        self.assertIsNone(details["sampled_command"])

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
