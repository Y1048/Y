#!/usr/bin/env python3
"""SDK-neutral LowState health checks for supported Arm SDK entrypoints (R50).

This module creates no DDS entity. It inspects LowState messages already received
by the existing subscribers and tracks IMU tilt plus motor temperature/fault and
torque finiteness. Base odometry, remote deadman and CRC supervision remain
separate open items.
"""

from __future__ import annotations

import math
from typing import Any


DEFAULT_ROLL_PITCH_LIMIT_RAD = 0.35
DEFAULT_MOTOR_TEMPERATURE_LIMIT_C = 75.0
BODY_JOINT_COUNT = 29


def _value(obj: Any, name: str) -> Any:
    value = getattr(obj, name)
    return value() if callable(value) else value


def _temperature_max_c(motor: Any) -> float:
    value = _value(motor, "temperature")
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError("empty motor temperature")
        temperatures = tuple(float(item) for item in value)
    else:
        try:
            temperatures = tuple(float(item) for item in value)
        except TypeError:
            temperatures = (float(value),)
    if not all(math.isfinite(item) for item in temperatures):
        raise ValueError("non-finite motor temperature")
    return max(temperatures)


def validate_lowstate_health_message(
    message: Any,
    *,
    roll_pitch_limit_rad: float = DEFAULT_ROLL_PITCH_LIMIT_RAD,
    motor_temperature_limit_c: float = DEFAULT_MOTOR_TEMPERATURE_LIMIT_C,
) -> None:
    """Raise when a standing Arm SDK run should stop and release authority."""

    if not math.isfinite(roll_pitch_limit_rad) or roll_pitch_limit_rad <= 0.0:
        raise ValueError("roll_pitch_limit_rad must be finite and positive")
    if not math.isfinite(motor_temperature_limit_c):
        raise ValueError("motor_temperature_limit_c must be finite")

    imu_state = _value(message, "imu_state")
    rpy = _value(imu_state, "rpy")
    if len(rpy) < 2:
        raise ValueError("LowState IMU rpy is incomplete")
    roll = float(rpy[0])
    pitch = float(rpy[1])
    if not all(math.isfinite(value) for value in (roll, pitch)):
        raise ValueError("LowState IMU roll/pitch is non-finite")
    if abs(roll) > roll_pitch_limit_rad or abs(pitch) > roll_pitch_limit_rad:
        raise RuntimeError(
            "LowState IMU roll/pitch limit: "
            f"roll={roll:.3f} pitch={pitch:.3f} rad"
        )

    motor_state = _value(message, "motor_state")
    if len(motor_state) < BODY_JOINT_COUNT:
        raise ValueError("LowState motor_state is shorter than 29 joints")
    for index in range(BODY_JOINT_COUNT):
        motor = motor_state[index]
        tau_est = float(_value(motor, "tau_est"))
        if not math.isfinite(tau_est):
            raise RuntimeError(f"motor {index} tau_est is non-finite")
        temperature = _temperature_max_c(motor)
        if temperature > motor_temperature_limit_c:
            raise RuntimeError(
                f"motor {index} temperature {temperature:.1f}C exceeds "
                f"{motor_temperature_limit_c:.1f}C"
            )
        motorstate = int(_value(motor, "motorstate"))
        if motorstate != 0:
            raise RuntimeError(f"motor {index} fault state is {motorstate}")


def install_lowstate_health_tracking(buffer_type: type) -> None:
    """Track the latest health result while preserving the original snapshot."""

    if getattr(buffer_type, "_supported_health_tracking_installed", False):
        return
    original_callback = buffer_type.callback
    buffer_type._supported_latest_health_error = "no LowState health sample"

    def guarded_callback(self, message: Any) -> None:
        try:
            validate_lowstate_health_message(message)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        else:
            error = None
        # Preserve the full q/dq snapshot even when a new health condition is
        # unsafe so the existing release path still has a measured pose.
        original_callback(self, message)
        buffer_type._supported_latest_health_error = error

    buffer_type.callback = guarded_callback
    buffer_type._supported_health_tracking_installed = True


def require_latest_lowstate_health(buffer_type: type) -> None:
    error = getattr(
        buffer_type,
        "_supported_latest_health_error",
        "LowState health tracking is not installed",
    )
    if error is not None:
        raise RuntimeError("LowState health fault: " + str(error))
