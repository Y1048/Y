#!/usr/bin/env python3
"""Offline Gate 6 fault-release and interrupted-acquire regression tests."""

from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

from gate6_arm_sdk_hold import (
    DEFAULT_CONFIG_PATH,
    LowStateSnapshot,
    _attempt_fault_release,
    load_runtime_config,
)


HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "gate6_arm_sdk_hold.py"


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
        self.crc = 0
        self.motor_cmd = [_FakeMotorCommand() for _ in range(35)]


class _FakeCRC:
    def Crc(self, _message) -> int:
        return 123


class _FakeBuffer:
    def __init__(self, snapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


class _FakePublisher:
    def __init__(self, fail_calls: set[int] | None = None) -> None:
        self.fail_calls = fail_calls or set()
        self.calls = 0
        self.weights: list[float] = []

    def Write(self, message) -> None:
        self.calls += 1
        if self.calls in self.fail_calls:
            raise OSError(f"write failure {self.calls}")
        self.weights.append(float(message.motor_cmd[29].q))


def safe_snapshot() -> LowStateSnapshot:
    q = [0.0] * 29
    q[15:22] = [0.2, 0.1, 0.0, 0.8, 0.0, 0.0, 0.0]
    q[22:29] = [0.2, -0.1, 0.0, 0.8, 0.0, 0.0, 0.0]
    return LowStateSnapshot(
        received_monotonic_s=1.0,
        received_unix_ns=2,
        sequence=3,
        mode_pr=0,
        mode_machine=5,
        all_q_rad=tuple(q),
        all_dq_rad_s=(0.0,) * 29,
    )


class Gate6FaultReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        base = load_runtime_config(DEFAULT_CONFIG_PATH)
        self.config = replace(
            base,
            ramp_down_s=0.001,
            publish_hz=10_000.0,
            release_zero_cycles=3,
        )
        self.snapshot = safe_snapshot()

    def test_fault_release_completes_zero_tail_without_sdk(self) -> None:
        publisher = _FakePublisher()
        evidence = _attempt_fault_release(
            buffer=_FakeBuffer(self.snapshot),
            fallback_snapshot=self.snapshot,
            publisher=publisher,
            message=_FakeLowCmd(),
            crc=_FakeCRC(),
            config=self.config,
            start_weight=0.12,
        )

        self.assertTrue(evidence.zero_release_completed)
        self.assertFalse(evidence.output_state_unknown)
        self.assertEqual(3, evidence.release_zero_frames_sent)
        self.assertEqual(0.0, evidence.last_successful_weight)
        self.assertGreaterEqual(len(publisher.weights), 3)

    def test_first_fault_release_write_failure_still_attempts_zero_tail(self) -> None:
        publisher = _FakePublisher({1})
        evidence = _attempt_fault_release(
            buffer=_FakeBuffer(self.snapshot),
            fallback_snapshot=self.snapshot,
            publisher=publisher,
            message=_FakeLowCmd(),
            crc=_FakeCRC(),
            config=self.config,
            start_weight=0.12,
        )

        self.assertFalse(evidence.release_ramp_completed)
        self.assertTrue(evidence.zero_release_completed)
        self.assertFalse(evidence.output_state_unknown)
        self.assertEqual(3, evidence.release_zero_frames_sent)
        self.assertIn("ramp:OSError", evidence.release_fault)

    def test_interrupt_release_starts_from_last_successful_weight(self) -> None:
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        main = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        text = ast.unparse(main)
        self.assertIn(
            "interrupt_release_start_weight = min(float(weight), float(last_successful_weight))",
            text,
        )
        self.assertNotIn(
            "started_s = now_s - config.ramp_up_s - config.hold_s",
            text,
        )

    def test_fault_status_distinguishes_unknown_output(self) -> None:
        tree = ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        text = ast.unparse(tree)
        self.assertIn("output_state_unknown", text)
        self.assertIn("zero_release_completed", text)
        self.assertIn("external_authority_handoff_confirmed", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
