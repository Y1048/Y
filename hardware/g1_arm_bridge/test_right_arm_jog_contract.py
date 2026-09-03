#!/usr/bin/env python3

from __future__ import annotations

import math
import unittest

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    RIGHT_ARM_INDICES,
    RIGHT_ARM_JOINT_NAMES,
    ArmSdkHoldConfig,
)
from right_arm_jog_contract import ArmJointJogController, ArmJointJogLimits


def measured_pose() -> tuple[float, ...]:
    values = [0.0] * 29
    values[25] = math.radians(55.0)
    return tuple(values)


class RightArmJogContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = ArmJointJogLimits(
            step_rad=math.radians(1.0),
            minimum_offset_rad=math.radians(-20.0),
            maximum_offset_rad=math.radians(20.0),
            maximum_velocity_rad_s=math.radians(5.0),
            joint_limit_margin_rad=math.radians(5.0),
        )
        self.hold = ArmSdkHoldConfig(
            maximum_target_error_rad=math.radians(12.0),
            joint_limit_margin_rad=math.radians(5.0),
        )

    def test_each_joint_changes_only_its_selected_target(self) -> None:
        measured = measured_pose()
        for joint_name, joint_index in zip(
            RIGHT_ARM_JOINT_NAMES,
            RIGHT_ARM_INDICES,
        ):
            controller = ArmJointJogController(measured, joint_name, self.limits)
            controller.request_step(1)
            tick = controller.advance(
                measured,
                0.1,
                mode_pr=0,
                mode_machine=5,
                weight=0.1,
                hold_config=self.hold,
            )
            expected = measured[joint_index] + math.radians(0.5)
            self.assertAlmostEqual(expected, tick.commanded_joint_rad)
            for frame_joint_index in DUAL_ARM_INDICES:
                expected_q = (
                    expected
                    if frame_joint_index == joint_index
                    else measured[frame_joint_index]
                )
                self.assertAlmostEqual(
                    expected_q,
                    tick.frame.motor_q_rad[frame_joint_index],
                    msg=f"{joint_name} unexpectedly changed {frame_joint_index}",
                )

    def test_request_is_clamped_to_directional_range_from_start(self) -> None:
        controller = ArmJointJogController(
            measured_pose(),
            "right_elbow",
            self.limits,
        )
        for _ in range(30):
            controller.request_step(1)
        self.assertAlmostEqual(
            math.radians(75.0),
            controller.requested_joint_rad,
        )

        for _ in range(50):
            controller.request_step(-1)
        self.assertAlmostEqual(
            math.radians(35.0),
            controller.requested_joint_rad,
        )

    def test_request_home_returns_requested_target_to_start(self) -> None:
        controller = ArmJointJogController(
            measured_pose(),
            "right_elbow",
            self.limits,
        )
        controller.request_step(1)
        self.assertFalse(controller.home_requested)
        self.assertAlmostEqual(math.radians(55.0), controller.request_home())
        self.assertTrue(controller.home_requested)

    def test_preview_step_does_not_mutate_requested_target(self) -> None:
        controller = ArmJointJogController(
            measured_pose(),
            "right_elbow",
            self.limits,
        )
        preview = controller.preview_step(1)
        self.assertAlmostEqual(math.radians(56.0), preview)
        self.assertAlmostEqual(math.radians(55.0), controller.requested_joint_rad)

    def test_down_step_is_rate_limited(self) -> None:
        measured = measured_pose()
        controller = ArmJointJogController(
            measured,
            "right_elbow",
            self.limits,
        )
        controller.request_step(-1)
        tick = controller.advance(
            measured,
            0.02,
            mode_pr=0,
            mode_machine=5,
            weight=0.1,
            hold_config=self.hold,
        )
        self.assertAlmostEqual(math.radians(54.9), tick.commanded_joint_rad)

    def test_non_arm_command_slots_remain_disabled(self) -> None:
        measured = measured_pose()
        controller = ArmJointJogController(
            measured,
            "right_elbow",
            self.limits,
        )
        tick = controller.advance(
            measured,
            0.01,
            mode_pr=0,
            mode_machine=5,
            weight=0.1,
            hold_config=self.hold,
        )
        for index in range(29):
            if index not in DUAL_ARM_INDICES:
                self.assertEqual(0, tick.frame.motor_mode[index])
                self.assertEqual(0.0, tick.frame.motor_kp[index])
                self.assertEqual(0.0, tick.frame.motor_kd[index])

    def test_full_authority_controller_holds_unselected_start_pose(self) -> None:
        measured = list(measured_pose())
        measured[15] = math.radians(3.0)
        measured[22] = math.radians(10.0)
        controller = ArmJointJogController(
            measured,
            "right_shoulder_pitch",
            self.limits,
            hold_unselected_start_pose=True,
        )
        changed = list(measured)
        changed[15] = math.radians(4.0)
        changed[23] = math.radians(-2.0)
        tick = controller.advance(
            changed,
            0.01,
            mode_pr=0,
            mode_machine=5,
            weight=1.0,
            hold_config=self.hold,
        )
        self.assertAlmostEqual(math.radians(3.0), tick.frame.motor_q_rad[15])
        self.assertAlmostEqual(0.0, tick.frame.motor_q_rad[23])
        self.assertAlmostEqual(math.radians(10.0), tick.frame.motor_q_rad[22])

    def test_invalid_direction_is_rejected(self) -> None:
        controller = ArmJointJogController(
            measured_pose(),
            "right_elbow",
            self.limits,
        )
        with self.assertRaises(ValueError):
            controller.request_step(0)

    def test_unknown_joint_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ArmJointJogController(
                measured_pose(),
                "right_gripper",
                self.limits,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
