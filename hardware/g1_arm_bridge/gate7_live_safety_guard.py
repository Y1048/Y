#!/usr/bin/env python3
"""SDK-neutral safety guards for the supported Gate 7 physical entrypoint.

The helpers in this module do not import Unitree SDK, create DDS entities, or
send robot commands. They enforce collision evidence on ACTIVE Mink samples and
validate the final shaped dual-arm command segment against the latest full-body
measured pose before a caller is allowed to publish it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Sequence

from arm_sdk_hold_contract import DUAL_ARM_INDICES, dual_arm_from_all_joints
from arm_sdk_teleop_contract import Gate7ContractError, MinkArmSample


@dataclass(frozen=True)
class ArmSegmentPoint:
    q_rad: tuple[float, ...]


@dataclass(frozen=True)
class LinearDualArmSegment:
    start_q_rad: tuple[float, ...]
    goal_q_rad: tuple[float, ...]
    segments: int

    def discrete_samples(self) -> tuple[ArmSegmentPoint, ...]:
        return tuple(
            ArmSegmentPoint(
                tuple(
                    start + (goal - start) * (index / self.segments)
                    for start, goal in zip(self.start_q_rad, self.goal_q_rad)
                )
            )
            for index in range(self.segments + 1)
        )


def require_active_collision_evidence(sample: MinkArmSample) -> MinkArmSample:
    """Require a finite numerical clearance for every ACTIVE command sample."""

    if sample.active:
        clearance = sample.minimum_clearance_m
        if clearance is None or not math.isfinite(float(clearance)):
            raise Gate7ContractError(
                "active Mink state requires finite minimum_clearance_m"
            )
    return sample


def _finite_all_joints(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != 29:
        raise Gate7ContractError("measured_all_q_rad must contain exactly 29 values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise Gate7ContractError("measured_all_q_rad contains a non-finite value")
    return result


def build_final_command_segment(
    frame: Any,
    measured_all_q_rad: Sequence[float],
    *,
    maximum_joint_sample_step_rad: float = math.radians(0.25),
    maximum_segments: int = 64,
) -> tuple[LinearDualArmSegment, tuple[float, ...]]:
    """Build a bounded swept segment from measured pose to the final frame target."""

    measured = _finite_all_joints(measured_all_q_rad)
    if not math.isfinite(maximum_joint_sample_step_rad) or maximum_joint_sample_step_rad <= 0.0:
        raise Gate7ContractError("maximum_joint_sample_step_rad must be positive")
    if not isinstance(maximum_segments, int) or isinstance(maximum_segments, bool):
        raise Gate7ContractError("maximum_segments must be an integer")
    if maximum_segments < 2:
        raise Gate7ContractError("maximum_segments must be at least 2")

    motor_q = getattr(frame, "motor_q_rad", None)
    if motor_q is None or len(motor_q) <= max(DUAL_ARM_INDICES):
        raise Gate7ContractError("final Arm SDK frame is missing dual-arm q slots")
    goal = tuple(float(motor_q[index]) for index in DUAL_ARM_INDICES)
    if not all(math.isfinite(value) for value in goal):
        raise Gate7ContractError("final Arm SDK frame contains non-finite arm q")
    start = dual_arm_from_all_joints(measured)
    maximum_delta = max(
        (abs(goal_value - start_value) for start_value, goal_value in zip(start, goal)),
        default=0.0,
    )
    required_segments = max(
        2,
        int(math.ceil(maximum_delta / maximum_joint_sample_step_rad)),
    )
    if required_segments > maximum_segments:
        raise Gate7ContractError(
            "final command segment exceeds bounded collision sampling: "
            f"segments={required_segments}>{maximum_segments}"
        )
    return LinearDualArmSegment(start, goal, required_segments), measured


def validate_final_command_segment(
    frame: Any,
    measured_all_q_rad: Sequence[float],
    validator: Callable[[Any, tuple[float, ...]], tuple[bool, str]] | None,
) -> tuple[bool, str]:
    """Validate the exact post-shaping Arm SDK frame and swept segment."""

    if validator is None:
        return False, "final_command_collision_validator_missing"
    try:
        segment, measured = build_final_command_segment(frame, measured_all_q_rad)
        allowed, reason = validator(segment, measured)
    except Exception as exc:
        return False, f"final_command_collision_error:{type(exc).__name__}:{exc}"
    if not isinstance(allowed, bool):
        return False, "final_command_collision_validator_returned_nonboolean"
    return allowed, str(reason)
