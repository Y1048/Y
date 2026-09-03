#!/usr/bin/env python3
"""SDK-neutral tests for Gate 7 acquisition guards (R33/R40)."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from gate7_acquisition_guard import (
    ActiveAcquisitionGuard,
    validate_full_body_snapshot_matches_precheck,
)


def sample(
    sequence: int,
    *,
    session_id: str = "session-a",
    active: bool = True,
    packet_age_s: float = 0.0,
):
    return SimpleNamespace(
        sequence=sequence,
        session_id=session_id,
        active=active,
        input_command_mode="active" if active else "idle",
        controller_state="active" if active else "idle",
        input_packet_age_s=packet_age_s,
    )


class Gate7AcquisitionGuardTests(unittest.TestCase):
    def test_continuous_ordered_active_stream_stays_fresh(self) -> None:
        guard = ActiveAcquisitionGuard(0.25)
        guard.seed(sample(10), now_s=1.0)
        guard.observe(sample(11), now_s=1.10)
        self.assertAlmostEqual(0.10, guard.require_fresh(now_s=1.20))

    def test_stream_stall_fails_before_weight_can_continue(self) -> None:
        guard = ActiveAcquisitionGuard(0.25)
        guard.seed(sample(10), now_s=1.0)
        with self.assertRaisesRegex(RuntimeError, "stale"):
            guard.require_fresh(now_s=1.251)

    def test_session_change_and_nonactive_packet_fail(self) -> None:
        guard = ActiveAcquisitionGuard(0.25)
        guard.seed(sample(10), now_s=1.0)
        with self.assertRaisesRegex(RuntimeError, "session changed"):
            guard.observe(sample(1, session_id="session-b"), now_s=1.05)

        guard = ActiveAcquisitionGuard(0.25)
        guard.seed(sample(10), now_s=1.0)
        with self.assertRaisesRegex(RuntimeError, "left ACTIVE"):
            guard.observe(sample(11, active=False), now_s=1.05)

    def test_embedded_stale_active_packet_fails(self) -> None:
        guard = ActiveAcquisitionGuard(0.25)
        with self.assertRaisesRegex(RuntimeError, "embedded Mink input age"):
            guard.seed(sample(10, packet_age_s=0.30), now_s=1.0)

    def test_nonincreasing_sequence_fails(self) -> None:
        guard = ActiveAcquisitionGuard(0.25)
        guard.seed(sample(10), now_s=1.0)
        with self.assertRaisesRegex(RuntimeError, "did not increase"):
            guard.observe(sample(10), now_s=1.05)

    def test_full_body_precheck_detects_waist_or_leg_change(self) -> None:
        expected = [0.0] * 29
        precheck = {"latest_all_joint_q_rad": expected}
        actual = list(expected)
        actual[12] = 0.03
        snapshot = SimpleNamespace(all_q_rad=tuple(actual))
        with self.assertRaisesRegex(RuntimeError, "full-body pose changed"):
            validate_full_body_snapshot_matches_precheck(
                snapshot,
                precheck,
                0.01,
            )

    def test_full_body_exact_match_passes(self) -> None:
        expected = [float(index) / 1000.0 for index in range(29)]
        precheck = {"latest_all_joint_q_rad": expected}
        snapshot = SimpleNamespace(all_q_rad=tuple(expected))
        self.assertEqual(
            0.0,
            validate_full_body_snapshot_matches_precheck(
                snapshot,
                precheck,
                0.01,
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
