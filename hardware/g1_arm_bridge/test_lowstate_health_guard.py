#!/usr/bin/env python3
"""SDK-neutral tests for supported LowState health supervision (R50)."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from lowstate_health_guard import validate_lowstate_health_message


class _Motor:
    def __init__(self, *, tau_est=0.0, temperature=30, motorstate=0):
        self.tau_est = tau_est
        self.temperature = [temperature, temperature]
        self.motorstate = motorstate


class _Message:
    def __init__(
        self,
        *,
        roll=0.0,
        pitch=0.0,
        temperature=30,
        motorstate=0,
        tau_est=0.0,
    ):
        self.imu_state = SimpleNamespace(rpy=[roll, pitch, 0.0])
        self.motor_state = [
            _Motor(
                tau_est=tau_est,
                temperature=temperature,
                motorstate=motorstate,
            )
            for _ in range(29)
        ]


class LowStateHealthGuardTests(unittest.TestCase):
    def test_nominal_state_passes(self) -> None:
        validate_lowstate_health_message(_Message())

    def test_roll_pitch_limit_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "roll/pitch limit"):
            validate_lowstate_health_message(_Message(roll=0.36))

    def test_motor_temperature_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "temperature"):
            validate_lowstate_health_message(_Message(temperature=76))

    def test_motor_fault_state_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "fault state"):
            validate_lowstate_health_message(_Message(motorstate=1))

    def test_nonfinite_torque_is_fail_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "tau_est"):
            validate_lowstate_health_message(_Message(tau_est=float("nan")))

    def test_supported_wsl_starters_use_health_guarded_entries(self) -> None:
        here = Path(__file__).resolve().parent
        expectations = {
            "start_gate6_hold_wsl.sh": "gate6_arm_sdk_hold_entry.py",
            "start_gate7_live_arm_sdk_wsl.sh": "gate7_live_arm_sdk_entry.py",
            "start_right_arm_jog_wsl.sh": "g1_right_arm_jog_entry.py",
        }
        for filename, entrypoint in expectations.items():
            text = (here / filename).read_text(encoding="utf-8")
            self.assertIn(entrypoint, text)

    def test_supported_entries_reference_health_guard(self) -> None:
        here = Path(__file__).resolve().parent
        for filename in (
            "gate6_arm_sdk_hold_entry.py",
            "gate7_live_arm_sdk_entry.py",
            "g1_right_arm_jog_entry.py",
        ):
            text = (here / filename).read_text(encoding="utf-8")
            self.assertIn("lowstate_health_guard", text)
            self.assertIn("require_latest_lowstate_health", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
