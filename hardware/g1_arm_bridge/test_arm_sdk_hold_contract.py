#!/usr/bin/env python3
"""Offline tests for the Gate 6 Arm SDK command contract."""

from __future__ import annotations

import math
import unittest

from arm_sdk_hold_contract import (
    ARM_SDK_WEIGHT_INDEX,
    BODY_JOINT_COUNT,
    DUAL_ARM_INDICES,
    MOTOR_COMMAND_COUNT,
    WAIST_INDICES,
    ArmSdkHoldConfig,
    blend_weight,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
    validate_measured_hold,
)


def _safe_all_q() -> tuple[float, ...]:
    values = [0.0] * BODY_JOINT_COUNT
    left_deg = (16.0, 12.0, -2.0, 56.0, 8.0, -1.0, 2.0)
    right_deg = (16.0, -12.0, 2.0, 56.0, -8.0, 1.0, -2.0)
    for index, value in zip(range(15, 22), left_deg):
        values[index] = math.radians(value)
    for index, value in zip(range(22, 29), right_deg):
        values[index] = math.radians(value)
    values[12] = math.radians(3.0)
    values[13] = math.radians(-1.0)
    values[14] = math.radians(2.0)
    return tuple(values)


class ArmSdkHoldContractTests(unittest.TestCase):
    def test_measured_dual_arm_hold_is_accepted(self) -> None:
        measured = _safe_all_q()
        target = dual_arm_from_all_joints(measured)
        result = validate_measured_hold(measured, target, 0.01)
        self.assertTrue(result.allowed, result.reason)

    def test_stale_lowstate_is_rejected(self) -> None:
        measured = _safe_all_q()
        result = validate_measured_hold(
            measured,
            dual_arm_from_all_joints(measured),
            ArmSdkHoldConfig().lowstate_timeout_s + 0.001,
        )
        self.assertFalse(result.allowed)
        self.assertEqual("lowstate_stale", result.reason)

    def test_dual_arm_target_error_is_rejected(self) -> None:
        measured = _safe_all_q()
        target = list(dual_arm_from_all_joints(measured))
        target[8] += math.radians(10.1)
        result = validate_measured_hold(measured, target, 0.01)
        self.assertFalse(result.allowed)
        self.assertTrue(result.reason.startswith("dual_arm_target_error:"))

    def test_left_arm_limit_is_not_skipped(self) -> None:
        measured = list(_safe_all_q())
        measured[16] = math.radians(140.0)
        result = validate_measured_hold(
            measured,
            dual_arm_from_all_joints(measured),
            0.01,
        )
        self.assertFalse(result.allowed)
        self.assertTrue(result.reason.startswith("measured_left_joint_limit:"))

    def test_frame_updates_only_dual_arm_and_weight(self) -> None:
        measured = _safe_all_q()
        target = dual_arm_from_all_joints(measured)
        frame = build_measured_hold_frame(
            measured,
            target,
            mode_pr=0,
            mode_machine=5,
            weight=0.2,
        )
        self.assertEqual(MOTOR_COMMAND_COUNT, len(frame.motor_q_rad))
        self.assertEqual(0.2, frame.motor_q_rad[ARM_SDK_WEIGHT_INDEX])
        for index in range(BODY_JOINT_COUNT):
            if index in DUAL_ARM_INDICES:
                self.assertEqual(1, frame.motor_mode[index])
                self.assertGreater(frame.motor_kp[index], 0.0)
                self.assertGreater(frame.motor_kd[index], 0.0)
            else:
                self.assertEqual(0, frame.motor_mode[index])
                self.assertEqual(0.0, frame.motor_kp[index])
                self.assertEqual(0.0, frame.motor_kd[index])
                self.assertEqual(measured[index], frame.motor_q_rad[index])
        for index in WAIST_INDICES:
            self.assertEqual(0, frame.motor_mode[index])
            self.assertEqual(measured[index], frame.motor_q_rad[index])

    def test_weight_schedule_is_bounded_and_returns_to_zero(self) -> None:
        acquire = blend_weight(
            1.5,
            ramp_up_s=3.0,
            hold_s=2.0,
            ramp_down_s=3.0,
            maximum_weight=0.2,
        )
        hold = blend_weight(
            3.5,
            ramp_up_s=3.0,
            hold_s=2.0,
            ramp_down_s=3.0,
            maximum_weight=0.2,
        )
        release = blend_weight(
            6.5,
            ramp_up_s=3.0,
            hold_s=2.0,
            ramp_down_s=3.0,
            maximum_weight=0.2,
        )
        complete = blend_weight(
            8.0,
            ramp_up_s=3.0,
            hold_s=2.0,
            ramp_down_s=3.0,
            maximum_weight=0.2,
        )
        self.assertEqual("ACQUIRE", acquire[0])
        self.assertAlmostEqual(0.1, acquire[1])
        self.assertFalse(acquire[2])
        self.assertEqual(("HOLD", 0.2, False), hold)
        self.assertAlmostEqual(0.1, release[1])
        self.assertEqual("RELEASE", release[0])
        self.assertEqual(("COMPLETE", 0.0, True), complete)


if __name__ == "__main__":
    unittest.main(verbosity=2)
