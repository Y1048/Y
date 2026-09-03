#!/usr/bin/env python3
"""SDK-neutral contract for one active joint in the interactive G1 arm jog."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Sequence

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    RIGHT_ARM_INDICES,
    RIGHT_ARM_JOINT_NAMES,
    RIGHT_ARM_LIMITS_RAD,
    ArmSdkCommandFrame,
    ArmSdkHoldConfig,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
    validate_measured_hold,
)


RIGHT_ARM_JOINT_BY_NAME: Final[dict[str, int]] = dict(
    zip(RIGHT_ARM_JOINT_NAMES, RIGHT_ARM_INDICES)
)


@dataclass(frozen=True)
class ArmJointJogLimits:
    step_rad: float = math.radians(1.0)
    minimum_offset_rad: float = math.radians(-20.0)
    maximum_offset_rad: float = math.radians(20.0)
    maximum_velocity_rad_s: float = math.radians(5.0)
    joint_limit_margin_rad: float = math.radians(5.0)


@dataclass(frozen=True)
class ArmJointJogTick:
    joint_name: str
    requested_joint_rad: float
    commanded_joint_rad: float
    measured_joint_rad: float
    offset_from_start_rad: float
    frame: ArmSdkCommandFrame


def validate_jog_limits(limits: ArmJointJogLimits, arm_index: int) -> None:
    positive_values = (
        limits.step_rad,
        limits.maximum_velocity_rad_s,
        limits.joint_limit_margin_rad,
    )
    if not all(
        math.isfinite(value) and value > 0.0 for value in positive_values
    ):
        raise ValueError("all arm jog limits must be finite and positive")
    if not all(
        math.isfinite(value)
        for value in (limits.minimum_offset_rad, limits.maximum_offset_rad)
    ):
        raise ValueError("arm jog offsets must be finite")
    if limits.minimum_offset_rad > 0.0 or limits.maximum_offset_rad < 0.0:
        raise ValueError("arm jog offsets must include the start pose")
    if arm_index < 0 or arm_index >= len(RIGHT_ARM_INDICES):
        raise ValueError("right-arm joint index is out of range")
    low, high = RIGHT_ARM_LIMITS_RAD[arm_index]
    if 2.0 * limits.joint_limit_margin_rad >= high - low:
        raise ValueError("right-arm joint margin leaves no usable range")


class ArmJointJogController:
    """Rate-limit one selected joint and build the 14-axis Arm SDK target."""

    def __init__(
        self,
        measured_all_q_rad: Sequence[float],
        joint_name: str,
        limits: ArmJointJogLimits = ArmJointJogLimits(),
        *,
        hold_unselected_start_pose: bool = False,
    ) -> None:
        if joint_name not in RIGHT_ARM_JOINT_BY_NAME:
            raise ValueError(f"unsupported right-arm joint: {joint_name}")
        self.joint_name = joint_name
        self.joint_index = RIGHT_ARM_JOINT_BY_NAME[joint_name]
        self.arm_index = RIGHT_ARM_INDICES.index(self.joint_index)
        self.dual_index = DUAL_ARM_INDICES.index(self.joint_index)
        validate_jog_limits(limits, self.arm_index)
        measured_dual = dual_arm_from_all_joints(measured_all_q_rad)
        start_joint = float(measured_dual[self.dual_index])
        if not math.isfinite(start_joint):
            raise ValueError("initial right-arm joint angle must be finite")

        physical_low, physical_high = RIGHT_ARM_LIMITS_RAD[self.arm_index]
        safe_low = physical_low + limits.joint_limit_margin_rad
        safe_high = physical_high - limits.joint_limit_margin_rad
        if start_joint < safe_low or start_joint > safe_high:
            raise ValueError("initial right-arm joint angle is outside the safe range")

        self.limits = limits
        self.hold_unselected_start_pose = bool(hold_unselected_start_pose)
        self.start_dual_q_rad = tuple(float(value) for value in measured_dual)
        self.start_joint_rad = start_joint
        self.requested_joint_rad = start_joint
        self.commanded_joint_rad = start_joint
        self.minimum_joint_rad = max(
            safe_low,
            start_joint + limits.minimum_offset_rad,
        )
        self.maximum_joint_rad = min(
            safe_high,
            start_joint + limits.maximum_offset_rad,
        )

    @property
    def home_requested(self) -> bool:
        return math.isclose(
            self.requested_joint_rad,
            self.start_joint_rad,
            abs_tol=1.0e-12,
        )

    def request_home(self) -> float:
        self.requested_joint_rad = self.start_joint_rad
        return self.requested_joint_rad

    def preview_step(self, direction: int) -> float:
        if direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        requested = self.requested_joint_rad + direction * self.limits.step_rad
        return min(
            self.maximum_joint_rad,
            max(self.minimum_joint_rad, requested),
        )

    def request_step(self, direction: int) -> float:
        self.requested_joint_rad = self.preview_step(direction)
        return self.requested_joint_rad

    def advance(
        self,
        measured_all_q_rad: Sequence[float],
        dt_s: float,
        *,
        mode_pr: int,
        mode_machine: int,
        weight: float,
        hold_config: ArmSdkHoldConfig,
    ) -> ArmJointJogTick:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")

        maximum_step = self.limits.maximum_velocity_rad_s * dt_s
        error = self.requested_joint_rad - self.commanded_joint_rad
        applied_step = min(maximum_step, abs(error))
        if error < 0.0:
            applied_step = -applied_step
        self.commanded_joint_rad += applied_step

        measured_dual = list(dual_arm_from_all_joints(measured_all_q_rad))
        measured_joint = float(measured_dual[self.dual_index])
        target_dual = (
            list(self.start_dual_q_rad)
            if self.hold_unselected_start_pose
            else measured_dual
        )
        target_dual[self.dual_index] = self.commanded_joint_rad
        validation = validate_measured_hold(
            measured_all_q_rad,
            target_dual,
            0.0,
            hold_config,
        )
        if not validation.allowed:
            raise RuntimeError(f"arm jog target rejected: {validation.reason}")

        frame = build_measured_hold_frame(
            measured_all_q_rad,
            target_dual,
            mode_pr=mode_pr,
            mode_machine=mode_machine,
            weight=weight,
            config=hold_config,
        )
        return ArmJointJogTick(
            joint_name=self.joint_name,
            requested_joint_rad=self.requested_joint_rad,
            commanded_joint_rad=self.commanded_joint_rad,
            measured_joint_rad=measured_joint,
            offset_from_start_rad=(
                self.commanded_joint_rad - self.start_joint_rad
            ),
            frame=frame,
        )
