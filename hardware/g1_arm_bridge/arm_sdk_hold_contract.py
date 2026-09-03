#!/usr/bin/env python3
"""G1 ``rt/arm_sdk`` measured-pose HOLD command contract.

This module intentionally has no Unitree SDK or network dependency.  It defines
the only command frame that Gate 6 may hand to the Linux publisher and validates
both arms because the Arm SDK weight blends the dual-arm command as one unit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Sequence

LOWSTATE_TOPIC: Final[str] = "rt/lowstate"
ARM_SDK_TOPIC: Final[str] = "rt/arm_sdk"
BODY_JOINT_COUNT: Final[int] = 29
MOTOR_COMMAND_COUNT: Final[int] = 35
ARM_SDK_WEIGHT_INDEX: Final[int] = 29

LEFT_ARM_INDICES: Final[tuple[int, ...]] = tuple(range(15, 22))
RIGHT_ARM_INDICES: Final[tuple[int, ...]] = tuple(range(22, 29))
DUAL_ARM_INDICES: Final[tuple[int, ...]] = LEFT_ARM_INDICES + RIGHT_ARM_INDICES
WAIST_INDICES: Final[tuple[int, ...]] = (12, 13, 14)

LEFT_ARM_JOINT_NAMES: Final[tuple[str, ...]] = (
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
)
RIGHT_ARM_JOINT_NAMES: Final[tuple[str, ...]] = (
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
)

# Unitree's G1 29-DoF MuJoCo limits.  These are physical model limits, not the
# more restrictive right-elbow teleoperation policy in safety_gate.py.
LEFT_ARM_LIMITS_RAD: Final[tuple[tuple[float, float], ...]] = (
    (-3.0892, 2.6704),
    (-1.5882, 2.2515),
    (-2.6180, 2.6180),
    (-1.0472, 2.0944),
    (-1.97222, 1.97222),
    (-1.61443, 1.61443),
    (-1.61443, 1.61443),
)
RIGHT_ARM_LIMITS_RAD: Final[tuple[tuple[float, float], ...]] = (
    (-3.0892, 2.6704),
    (-2.2515, 1.5882),
    (-2.6180, 2.6180),
    (-1.0472, 2.0944),
    (-1.97222, 1.97222),
    (-1.61443, 1.61443),
    (-1.61443, 1.61443),
)


@dataclass(frozen=True)
class ArmSdkHoldConfig:
    """Parameters that affect command construction and runtime validation."""

    lowstate_timeout_s: float = 0.25
    joint_limit_margin_rad: float = math.radians(2.0)
    maximum_target_error_rad: float = math.radians(10.0)
    proximal_kp: float = 80.0
    proximal_kd: float = 3.0
    wrist_kp: float = 40.0
    wrist_kd: float = 1.5
    non_arm_kp: float = 0.0
    non_arm_kd: float = 0.0


@dataclass(frozen=True)
class HoldValidation:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class ArmSdkCommandFrame:
    """SDK-neutral representation of one 35-slot HG LowCmd message."""

    mode_pr: int
    mode_machine: int
    weight: float
    motor_mode: tuple[int, ...]
    motor_q_rad: tuple[float, ...]
    motor_dq_rad_s: tuple[float, ...]
    motor_tau_nm: tuple[float, ...]
    motor_kp: tuple[float, ...]
    motor_kd: tuple[float, ...]


def _finite_vector(
    values: Sequence[float],
    *,
    expected_length: int,
    name: str,
) -> tuple[float, ...]:
    if len(values) != expected_length:
        raise ValueError(f"{name} must contain exactly {expected_length} values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} contains a non-finite value")
    return result


def _uint8(value: int, name: str) -> int:
    result = int(value)
    if result < 0 or result > 255:
        raise ValueError(f"{name} must be in [0, 255]")
    return result


def _validate_arm_limits(
    values: Sequence[float],
    names: Sequence[str],
    limits: Sequence[tuple[float, float]],
    margin_rad: float,
    side: str,
) -> HoldValidation:
    for value, name, (lower, upper) in zip(values, names, limits):
        safe_lower = lower + margin_rad
        safe_upper = upper - margin_rad
        if value < safe_lower or value > safe_upper:
            return HoldValidation(
                False,
                (
                    f"{side}_joint_limit:{name} "
                    f"value={math.degrees(value):.2f}deg "
                    f"safe=[{math.degrees(safe_lower):.2f},"
                    f"{math.degrees(safe_upper):.2f}]deg"
                ),
            )
    return HoldValidation(True, "ok")


def validate_measured_hold(
    measured_all_q_rad: Sequence[float],
    target_dual_arm_q_rad: Sequence[float],
    lowstate_age_s: float,
    config: ArmSdkHoldConfig = ArmSdkHoldConfig(),
) -> HoldValidation:
    """Validate fresh measured state and a dual-arm HOLD target."""

    if not math.isfinite(lowstate_age_s) or lowstate_age_s < 0.0:
        return HoldValidation(False, "invalid_lowstate_age")
    if lowstate_age_s > config.lowstate_timeout_s:
        return HoldValidation(False, "lowstate_stale")
    if not math.isfinite(config.joint_limit_margin_rad) or config.joint_limit_margin_rad < 0.0:
        return HoldValidation(False, "invalid_joint_limit_margin")

    try:
        measured = _finite_vector(
            measured_all_q_rad,
            expected_length=BODY_JOINT_COUNT,
            name="measured_all_q_rad",
        )
        target = _finite_vector(
            target_dual_arm_q_rad,
            expected_length=len(DUAL_ARM_INDICES),
            name="target_dual_arm_q_rad",
        )
    except ValueError as exc:
        return HoldValidation(False, str(exc))

    measured_dual_arm = tuple(measured[index] for index in DUAL_ARM_INDICES)
    left_result = _validate_arm_limits(
        measured_dual_arm[:7],
        LEFT_ARM_JOINT_NAMES,
        LEFT_ARM_LIMITS_RAD,
        config.joint_limit_margin_rad,
        "measured_left",
    )
    if not left_result.allowed:
        return left_result
    right_result = _validate_arm_limits(
        measured_dual_arm[7:],
        RIGHT_ARM_JOINT_NAMES,
        RIGHT_ARM_LIMITS_RAD,
        config.joint_limit_margin_rad,
        "measured_right",
    )
    if not right_result.allowed:
        return right_result
    target_left_result = _validate_arm_limits(
        target[:7],
        LEFT_ARM_JOINT_NAMES,
        LEFT_ARM_LIMITS_RAD,
        config.joint_limit_margin_rad,
        "target_left",
    )
    if not target_left_result.allowed:
        return target_left_result
    target_right_result = _validate_arm_limits(
        target[7:],
        RIGHT_ARM_JOINT_NAMES,
        RIGHT_ARM_LIMITS_RAD,
        config.joint_limit_margin_rad,
        "target_right",
    )
    if not target_right_result.allowed:
        return target_right_result

    maximum_error = max(
        abs(target_value - measured_value)
        for target_value, measured_value in zip(target, measured_dual_arm)
    )
    if maximum_error > config.maximum_target_error_rad:
        return HoldValidation(
            False,
            f"dual_arm_target_error:{math.degrees(maximum_error):.2f}deg",
        )
    return HoldValidation(True, "ok")


def build_measured_hold_frame(
    measured_all_q_rad: Sequence[float],
    target_dual_arm_q_rad: Sequence[float],
    *,
    mode_pr: int,
    mode_machine: int,
    weight: float,
    config: ArmSdkHoldConfig = ArmSdkHoldConfig(),
) -> ArmSdkCommandFrame:
    """Build one frame while preserving all non-arm positions at measured q.

    Only indices 15..28 receive dynamic dual-arm targets.  Waist indices
    12..14 and every leg joint remain at their measured values in the payload;
    they are not part of the Arm SDK target update set.
    """

    measured = _finite_vector(
        measured_all_q_rad,
        expected_length=BODY_JOINT_COUNT,
        name="measured_all_q_rad",
    )
    target = _finite_vector(
        target_dual_arm_q_rad,
        expected_length=len(DUAL_ARM_INDICES),
        name="target_dual_arm_q_rad",
    )
    if not math.isfinite(weight) or weight < 0.0 or weight > 1.0:
        raise ValueError("weight must be finite and in [0, 1]")

    motor_mode = [0] * MOTOR_COMMAND_COUNT
    motor_q = [0.0] * MOTOR_COMMAND_COUNT
    motor_dq = [0.0] * MOTOR_COMMAND_COUNT
    motor_tau = [0.0] * MOTOR_COMMAND_COUNT
    motor_kp = [0.0] * MOTOR_COMMAND_COUNT
    motor_kd = [0.0] * MOTOR_COMMAND_COUNT

    for index, value in enumerate(measured):
        motor_q[index] = value

    for command_index, joint_index in enumerate(DUAL_ARM_INDICES):
        motor_mode[joint_index] = 1
        motor_q[joint_index] = target[command_index]
        if joint_index in (19, 20, 21, 26, 27, 28):
            motor_kp[joint_index] = config.wrist_kp
            motor_kd[joint_index] = config.wrist_kd
        else:
            motor_kp[joint_index] = config.proximal_kp
            motor_kd[joint_index] = config.proximal_kd

    # The firmware interprets motor_cmd[29].q as the dual-arm blend weight.
    motor_q[ARM_SDK_WEIGHT_INDEX] = float(weight)

    frame = ArmSdkCommandFrame(
        mode_pr=_uint8(mode_pr, "mode_pr"),
        mode_machine=_uint8(mode_machine, "mode_machine"),
        weight=float(weight),
        motor_mode=tuple(motor_mode),
        motor_q_rad=tuple(motor_q),
        motor_dq_rad_s=tuple(motor_dq),
        motor_tau_nm=tuple(motor_tau),
        motor_kp=tuple(motor_kp),
        motor_kd=tuple(motor_kd),
    )
    validate_command_frame(frame)
    return frame


def validate_command_frame(frame: ArmSdkCommandFrame) -> None:
    """Raise ValueError when a frame can affect anything outside both arms."""

    vectors = (
        (frame.motor_mode, "motor_mode"),
        (frame.motor_q_rad, "motor_q_rad"),
        (frame.motor_dq_rad_s, "motor_dq_rad_s"),
        (frame.motor_tau_nm, "motor_tau_nm"),
        (frame.motor_kp, "motor_kp"),
        (frame.motor_kd, "motor_kd"),
    )
    for values, name in vectors:
        if len(values) != MOTOR_COMMAND_COUNT:
            raise ValueError(f"{name} must contain {MOTOR_COMMAND_COUNT} slots")
    for name, values in (
        ("motor_q_rad", frame.motor_q_rad),
        ("motor_dq_rad_s", frame.motor_dq_rad_s),
        ("motor_tau_nm", frame.motor_tau_nm),
        ("motor_kp", frame.motor_kp),
        ("motor_kd", frame.motor_kd),
    ):
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError(f"{name} contains a non-finite value")
    if frame.motor_q_rad[ARM_SDK_WEIGHT_INDEX] != frame.weight:
        raise ValueError("weight slot does not match frame.weight")
    for index in range(BODY_JOINT_COUNT):
        if index not in DUAL_ARM_INDICES:
            if frame.motor_mode[index] != 0:
                raise ValueError(f"non-arm motor {index} must remain disabled")
            if frame.motor_kp[index] != 0.0 or frame.motor_kd[index] != 0.0:
                raise ValueError(f"non-arm motor {index} must have zero gains")
            if frame.motor_dq_rad_s[index] != 0.0 or frame.motor_tau_nm[index] != 0.0:
                raise ValueError(f"non-arm motor {index} must have zero dq/tau")


def blend_weight(
    elapsed_s: float,
    *,
    ramp_up_s: float,
    hold_s: float,
    ramp_down_s: float,
    maximum_weight: float,
) -> tuple[str, float, bool]:
    """Return ``(phase, weight, done)`` for a bounded acquire/hold/release run."""

    values = (elapsed_s, ramp_up_s, hold_s, ramp_down_s, maximum_weight)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("weight schedule values must be finite")
    if elapsed_s < 0.0 or ramp_up_s <= 0.0 or hold_s < 0.0 or ramp_down_s <= 0.0:
        raise ValueError("invalid weight schedule duration")
    if maximum_weight <= 0.0 or maximum_weight > 1.0:
        raise ValueError("maximum_weight must be in (0, 1]")

    if elapsed_s < ramp_up_s:
        return "ACQUIRE", maximum_weight * elapsed_s / ramp_up_s, False
    hold_end = ramp_up_s + hold_s
    if elapsed_s < hold_end:
        return "HOLD", maximum_weight, False
    release_end = hold_end + ramp_down_s
    if elapsed_s < release_end:
        ratio = (elapsed_s - hold_end) / ramp_down_s
        return "RELEASE", maximum_weight * (1.0 - ratio), False
    return "COMPLETE", 0.0, True


def dual_arm_from_all_joints(all_joint_q_rad: Sequence[float]) -> tuple[float, ...]:
    measured = _finite_vector(
        all_joint_q_rad,
        expected_length=BODY_JOINT_COUNT,
        name="all_joint_q_rad",
    )
    return tuple(measured[index] for index in DUAL_ARM_INDICES)
