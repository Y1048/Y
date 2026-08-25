#!/usr/bin/env python3
"""Pure right-arm hardware safety gate for Unitree G1 teleoperation.

This module has NO DDS dependency and sends NO robot command. It validates and
rate-limits a proposed seven-joint right-arm target before a future command
publisher is allowed to use it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Sequence

JOINT_NAMES: Final[tuple[str, ...]] = (
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
)

# Official Unitree MuJoCo G1 29-DoF ranges. Elbow lower bound is intentionally
# tightened to the teleoperation operational policy already used by Mink.
JOINT_LIMITS_RAD: Final[tuple[tuple[float, float], ...]] = (
    (-3.0892, 2.6704),
    (-2.2515, 1.5882),
    (-2.6180, 2.6180),
    (math.radians(5.0), 2.0944),
    (-1.97222, 1.97222),
    (-1.61443, 1.61443),
    (-1.61443, 1.61443),
)


@dataclass(frozen=True)
class SafetyConfig:
    lowstate_timeout_s: float = 0.25
    max_target_error_rad: float = math.radians(10.0)
    max_command_velocity_rad_s: float = math.radians(15.0)
    joint_limit_margin_rad: float = math.radians(2.0)


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str
    command_q_rad: tuple[float, ...] | None
    rate_limited: bool = False


def _vector(values: Sequence[float], name: str) -> tuple[float, ...]:
    if len(values) != 7:
        raise ValueError(f"{name} must contain exactly 7 joints")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} contains a non-finite value")
    return result


def _within_joint_limits(values: Sequence[float], margin: float) -> tuple[bool, str]:
    for index, (value, limits) in enumerate(zip(values, JOINT_LIMITS_RAD)):
        low, high = limits
        safe_low = low + margin
        safe_high = high - margin
        if value < safe_low or value > safe_high:
            return False, (
                f"joint_limit:{JOINT_NAMES[index]} value={math.degrees(value):.2f}deg "
                f"safe=[{math.degrees(safe_low):.2f},{math.degrees(safe_high):.2f}]deg"
            )
    return True, "ok"


def evaluate_target(
    measured_q_rad: Sequence[float],
    requested_q_rad: Sequence[float],
    previous_command_q_rad: Sequence[float] | None,
    lowstate_age_s: float,
    dt_s: float,
    config: SafetyConfig = SafetyConfig(),
) -> SafetyDecision:
    """Validate a target and return the only joint vector a publisher may use.

    A denied decision always returns command_q_rad=None. Future hardware output
    code must treat that as a hard stop and must not substitute its own target.
    """

    if not math.isfinite(lowstate_age_s) or lowstate_age_s < 0.0:
        return SafetyDecision(False, "invalid_lowstate_age", None)
    if lowstate_age_s > config.lowstate_timeout_s:
        return SafetyDecision(False, "lowstate_stale", None)
    if not math.isfinite(dt_s) or dt_s <= 0.0:
        return SafetyDecision(False, "invalid_dt", None)

    try:
        measured = _vector(measured_q_rad, "measured_q_rad")
        requested = _vector(requested_q_rad, "requested_q_rad")
    except ValueError as exc:
        return SafetyDecision(False, str(exc), None)

    measured_ok, measured_reason = _within_joint_limits(
        measured, config.joint_limit_margin_rad
    )
    if not measured_ok:
        return SafetyDecision(False, "measured_" + measured_reason, None)

    requested_ok, requested_reason = _within_joint_limits(
        requested, config.joint_limit_margin_rad
    )
    if not requested_ok:
        return SafetyDecision(False, "requested_" + requested_reason, None)

    maximum_error = max(abs(target - actual) for target, actual in zip(requested, measured))
    if maximum_error > config.max_target_error_rad:
        return SafetyDecision(
            False,
            f"target_error:{math.degrees(maximum_error):.2f}deg",
            None,
        )

    if previous_command_q_rad is None:
        previous = measured
    else:
        try:
            previous = _vector(previous_command_q_rad, "previous_command_q_rad")
        except ValueError as exc:
            return SafetyDecision(False, str(exc), None)

    max_step = config.max_command_velocity_rad_s * dt_s
    command = []
    rate_limited = False
    for previous_value, requested_value in zip(previous, requested):
        delta = requested_value - previous_value
        if delta > max_step:
            delta = max_step
            rate_limited = True
        elif delta < -max_step:
            delta = -max_step
            rate_limited = True
        command.append(previous_value + delta)

    command_ok, command_reason = _within_joint_limits(
        command, config.joint_limit_margin_rad
    )
    if not command_ok:
        return SafetyDecision(False, "command_" + command_reason, None)

    return SafetyDecision(True, "ok", tuple(command), rate_limited)
