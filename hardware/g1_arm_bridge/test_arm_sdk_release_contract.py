#!/usr/bin/env python3
"""Offline tests for the shared Arm SDK release finalizer."""

from __future__ import annotations

import unittest

from arm_sdk_release_contract import execute_release_sequence


class FakeClock:
    def __init__(self) -> None:
        self.now = 10.0
        self.unix_ns = 1_000

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def time_ns(self) -> int:
        self.unix_ns += 1
        return self.unix_ns


class ReleaseContractTests(unittest.TestCase):
    def test_normal_release_completes_zero_tail(self) -> None:
        clock = FakeClock()
        published: list[float] = []

        evidence = execute_release_sequence(
            start_weight=0.2,
            ramp_s=0.02,
            zero_cycles=3,
            publish_hz=100.0,
            build_ramp_frame=lambda weight: weight,
            build_zero_frame=lambda: 0.0,
            publish_frame=published.append,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            unix_time_ns=clock.time_ns,
        )

        self.assertTrue(evidence.release_ramp_completed)
        self.assertTrue(evidence.zero_release_completed)
        self.assertFalse(evidence.output_state_unknown)
        self.assertIsNone(evidence.release_fault)
        self.assertEqual(3, evidence.release_zero_frames_sent)
        self.assertEqual(0.0, evidence.last_successful_weight)
        self.assertFalse(evidence.external_authority_handoff_confirmed)
        self.assertGreaterEqual(len(published), 6)
        self.assertTrue(all(a >= b for a, b in zip(published[:3], published[1:3])))

    def test_first_ramp_write_failure_still_attempts_all_zero_frames(self) -> None:
        clock = FakeClock()
        calls = 0
        published: list[float] = []

        def publish(frame: float) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("ramp write failed")
            published.append(frame)

        evidence = execute_release_sequence(
            start_weight=0.2,
            ramp_s=0.02,
            zero_cycles=4,
            publish_hz=100.0,
            build_ramp_frame=lambda weight: weight,
            build_zero_frame=lambda: 0.0,
            publish_frame=publish,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            unix_time_ns=clock.time_ns,
        )

        self.assertFalse(evidence.release_ramp_completed)
        self.assertTrue(evidence.zero_release_completed)
        self.assertFalse(evidence.output_state_unknown)
        self.assertEqual(4, evidence.release_zero_frames_sent)
        self.assertIn("ramp:OSError", evidence.release_fault)
        self.assertEqual([0.0, 0.0, 0.0, 0.0], published)

    def test_partial_zero_tail_keeps_output_state_unknown(self) -> None:
        clock = FakeClock()
        zero_calls = 0

        def build_zero() -> float:
            nonlocal zero_calls
            zero_calls += 1
            if zero_calls == 2:
                raise RuntimeError("zero build failed")
            return 0.0

        evidence = execute_release_sequence(
            start_weight=0.1,
            ramp_s=0.01,
            zero_cycles=3,
            publish_hz=100.0,
            build_ramp_frame=lambda weight: weight,
            build_zero_frame=build_zero,
            publish_frame=lambda _frame: None,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
            unix_time_ns=clock.time_ns,
        )

        self.assertTrue(evidence.release_ramp_completed)
        self.assertFalse(evidence.zero_release_completed)
        self.assertTrue(evidence.output_state_unknown)
        self.assertEqual(1, evidence.release_zero_frames_sent)
        self.assertIn("zero_tail:RuntimeError", evidence.release_fault)

    def test_invalid_arguments_fail_before_any_publish(self) -> None:
        called = False

        def publish(_frame: float) -> None:
            nonlocal called
            called = True

        with self.assertRaises(ValueError):
            execute_release_sequence(
                start_weight=-0.1,
                ramp_s=1.0,
                zero_cycles=1,
                publish_hz=100.0,
                build_ramp_frame=lambda weight: weight,
                build_zero_frame=lambda: 0.0,
                publish_frame=publish,
            )
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
