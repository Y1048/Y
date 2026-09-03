#!/usr/bin/env python3
"""SDK-neutral tests for Gate 7 supported-path collision guards (R2/R41)."""

from __future__ import annotations

from types import SimpleNamespace
import math
import unittest

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import Gate7ContractError
from gate7_live_safety_guard import (
    build_final_command_segment,
    require_active_collision_evidence,
    validate_final_command_segment,
)


class Gate7LiveSafetyGuardTests(unittest.TestCase):
    def test_active_sample_requires_numeric_clearance(self) -> None:
        sample = SimpleNamespace(active=True, minimum_clearance_m=None)
        with self.assertRaisesRegex(Gate7ContractError, "minimum_clearance_m"):
            require_active_collision_evidence(sample)

    def test_inactive_sample_may_omit_clearance(self) -> None:
        sample = SimpleNamespace(active=False, minimum_clearance_m=None)
        self.assertIs(sample, require_active_collision_evidence(sample))

    def test_final_segment_uses_latest_full_body_pose_and_exact_frame_target(self) -> None:
        measured = tuple(float(index) / 1000.0 for index in range(29))
        motor_q = [0.0] * 35
        for index in range(29):
            motor_q[index] = measured[index]
        motor_q[22] += math.radians(0.40)
        frame = SimpleNamespace(motor_q_rad=tuple(motor_q))

        segment, canonical_measured = build_final_command_segment(frame, measured)
        points = segment.discrete_samples()

        self.assertEqual(measured, canonical_measured)
        self.assertGreaterEqual(len(points), 3)
        self.assertEqual(
            tuple(measured[index] for index in DUAL_ARM_INDICES),
            points[0].q_rad,
        )
        self.assertEqual(
            tuple(motor_q[index] for index in DUAL_ARM_INDICES),
            points[-1].q_rad,
        )

    def test_rejected_final_segment_blocks_frame(self) -> None:
        measured = tuple(0.0 for _ in range(29))
        motor_q = [0.0] * 35
        motor_q[22] = math.radians(0.2)
        frame = SimpleNamespace(motor_q_rad=tuple(motor_q))
        calls = []

        def validator(segment, full_body):
            calls.append((segment, full_body))
            return False, "collision_clearance:5.00mm"

        allowed, reason = validate_final_command_segment(
            frame,
            measured,
            validator,
        )
        self.assertFalse(allowed)
        self.assertIn("collision_clearance", reason)
        self.assertEqual(1, len(calls))
        self.assertEqual(measured, calls[0][1])

    def test_missing_validator_fails_closed(self) -> None:
        measured = tuple(0.0 for _ in range(29))
        frame = SimpleNamespace(motor_q_rad=tuple(0.0 for _ in range(35)))
        allowed, reason = validate_final_command_segment(frame, measured, None)
        self.assertFalse(allowed)
        self.assertEqual("final_command_collision_validator_missing", reason)

    def test_unexpected_large_one_cycle_segment_is_rejected(self) -> None:
        measured = tuple(0.0 for _ in range(29))
        motor_q = [0.0] * 35
        motor_q[22] = math.radians(20.0)
        frame = SimpleNamespace(motor_q_rad=tuple(motor_q))
        with self.assertRaisesRegex(Gate7ContractError, "bounded collision sampling"):
            build_final_command_segment(frame, measured)


if __name__ == "__main__":
    unittest.main(verbosity=2)
