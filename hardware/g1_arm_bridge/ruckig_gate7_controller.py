#!/usr/bin/env python3
"""Ruckig trajectory shaping for Gate 7 decisions without robot I/O."""

from __future__ import annotations

import math
from dataclasses import replace

from arm_sdk_hold_contract import LEFT_ARM_LIMITS_RAD, RIGHT_ARM_LIMITS_RAD
from arm_sdk_teleop_contract import (
    Gate7Decision,
    Gate7TeleopController,
    _validate_dual_arm_joint_limits,
    dual_arm_from_all_joints,
)
from ruckig_joint_motion_limiter import RuckigJointMotionLimiter


class RuckigGate7TeleopController:
    """Apply one persistent Ruckig trajectory to every Gate 7 command state."""

    def __init__(
        self,
        regular_pose,
        config,
        *,
        return_path_validator,
        velocity_scale: float = 1.0,
        acceleration_scale: float = 1.0,
        jerk_scale: float = 1.0,
    ) -> None:
        if config.hardware_output_authorized:
            raise ValueError("Gate 7 algorithm config must remain hardware locked")
        scales = (
            float(velocity_scale),
            float(acceleration_scale),
            float(jerk_scale),
        )
        if not all(math.isfinite(value) and value >= 1.0 for value in scales):
            raise ValueError("Ruckig limit scales must be finite and at least 1")

        # Gate7TeleopController keeps state, watchdog, collision and return
        # semantics. Ruckig is the only motion-rate layer after those decisions.
        planning_config = replace(
            config,
            proximal_max_velocity_rad_s=1.0e6,
            wrist_max_velocity_rad_s=1.0e6,
            maximum_target_error_rad=math.radians(360.0),
        )
        self.config = config
        self.velocity_scale = scales[0]
        self.acceleration_scale = scales[1]
        self.jerk_scale = scales[2]
        self.velocity_limits_rad_s = tuple(
            value * self.velocity_scale for value in config.velocity_limits_rad_s
        )
        self.acceleration_limits_rad_s2 = tuple(
            value * self.acceleration_scale
            for value in config.acceleration_limits_rad_s2
        )
        self.jerk_limits_rad_s3 = tuple(
            value * self.jerk_scale for value in config.jerk_limits_rad_s3
        )
        self.controller = Gate7TeleopController(
            regular_pose,
            planning_config,
            return_path_validator=return_path_validator,
        )
        self.motion_limiter: RuckigJointMotionLimiter | None = None
        self.joint_limit_margin_rad = math.radians(3.0)

    @property
    def state(self) -> str:
        return self.controller.state

    def _safe_target(self, target_dual_arm_q_rad) -> tuple[float, ...]:
        limits = LEFT_ARM_LIMITS_RAD + RIGHT_ARM_LIMITS_RAD
        return tuple(
            max(
                lower + self.joint_limit_margin_rad,
                min(upper - self.joint_limit_margin_rad, float(target)),
            )
            for target, (lower, upper) in zip(target_dual_arm_q_rad, limits)
        )

    def step(self, sample, measured_all_q_rad, dt_s: float) -> Gate7Decision:
        measured_dual = dual_arm_from_all_joints(measured_all_q_rad)
        decision = self.controller.step(sample, measured_all_q_rad, dt_s)
        if self.motion_limiter is None:
            self.motion_limiter = RuckigJointMotionLimiter(
                measured_dual,
                self.velocity_limits_rad_s,
                self.acceleration_limits_rad_s2,
                self.jerk_limits_rad_s3,
                dt_s,
            )
        safe_target = self._safe_target(decision.target_dual_arm_q_rad)
        shaped_target = self.motion_limiter.Step(safe_target, dt_s)
        _validate_dual_arm_joint_limits(
            shaped_target,
            "ruckig_target_dual_arm_q_rad",
        )
        maximum_error = max(
            abs(target - measured)
            for target, measured in zip(shaped_target, measured_dual)
        )
        if maximum_error > self.config.maximum_target_error_rad:
            return Gate7Decision(
                state="SAFETY_HOLD",
                reason=f"ruckig_target_error:{math.degrees(maximum_error):.2f}deg",
                target_dual_arm_q_rad=measured_dual,
                return_progress=decision.return_progress,
                command_candidate_valid=False,
            )
        return Gate7Decision(
            state=decision.state,
            reason=decision.reason,
            target_dual_arm_q_rad=tuple(shaped_target),
            return_progress=decision.return_progress,
            command_candidate_valid=decision.command_candidate_valid,
        )
