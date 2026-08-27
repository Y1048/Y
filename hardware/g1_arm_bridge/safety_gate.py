#!/usr/bin/env python3
"""Unitree G1 오른팔용 순수 함수형 하드웨어 안전 게이트.

DDS에 의존하지 않고 로봇 명령도 보내지 않는다. 향후 publisher가 사용할 수 있는
유일한 7관절 명령을 반환하기 전에 LowState 신선도, 관절 범위, 현재 자세와의 차이,
주기당 속도 제한을 순서대로 검사한다.
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

# Unitree 공식 MuJoCo G1 29-DoF 범위를 사용한다. 팔꿈치 하한만 Mink와 동일한
# 텔레오퍼레이션 운용 정책에 맞춰 의도적으로 더 보수적으로 제한한다.
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
    """목표를 검증하고 publisher가 사용할 수 있는 유일한 관절 벡터를 반환한다.

    거부된 결과는 항상 command_q_rad=None이다. 실제 출력 코드는 이를 hard
    stop으로 취급해야 하며 자체 목표를 대신 넣어 우회하면 안 된다.
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
