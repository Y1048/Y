#!/usr/bin/env python3
"""Ruckig-backed online joint motion limiter for offline Gate 7 experiments."""

from __future__ import annotations

import math
from typing import Sequence

from ruckig import InputParameter, OutputParameter, Result, Ruckig, Synchronization


def _finite_vector(values: Sequence[float], size: int, name: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) != size:
        raise ValueError(f"{name} must contain exactly {size} values")
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} contains a non-finite value")
    return result


class RuckigJointMotionLimiter:
    """Generate one jerk-constrained online trajectory step per control tick."""

    def __init__(
        self,
        initial_q_rad: Sequence[float],
        velocity_limits_rad_s: Sequence[float],
        acceleration_limits_rad_s2: Sequence[float],
        jerk_limits_rad_s3: Sequence[float],
        dt_s: float,
    ) -> None:
        initial = tuple(float(value) for value in initial_q_rad)
        self.size = len(initial)
        if self.size == 0:
            raise ValueError("initial_q_rad must not be empty")
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")
        self.dt_s = float(dt_s)
        velocity_limits = _finite_vector(
            velocity_limits_rad_s, self.size, "velocity_limits_rad_s"
        )
        acceleration_limits = _finite_vector(
            acceleration_limits_rad_s2, self.size, "acceleration_limits_rad_s2"
        )
        jerk_limits = _finite_vector(
            jerk_limits_rad_s3, self.size, "jerk_limits_rad_s3"
        )
        if any(
            value <= 0.0
            for limits in (velocity_limits, acceleration_limits, jerk_limits)
            for value in limits
        ):
            raise ValueError("motion limits must be positive")

        self._ruckig = Ruckig(self.size, self.dt_s)
        self._input = InputParameter(self.size)
        self._output = OutputParameter(self.size)
        self._input.current_position = list(
            _finite_vector(initial, self.size, "initial_q_rad")
        )
        self._input.current_velocity = [0.0] * self.size
        self._input.current_acceleration = [0.0] * self.size
        self._input.target_position = list(initial)
        self._input.target_velocity = [0.0] * self.size
        self._input.target_acceleration = [0.0] * self.size
        self._input.max_velocity = list(velocity_limits)
        self._input.max_acceleration = list(acceleration_limits)
        self._input.max_jerk = list(jerk_limits)
        # Each arm joint follows its own feasible trajectory. Global time
        # synchronization lets one slow joint delay every other joint.
        self._input.synchronization = Synchronization.No
        self.q_rad = tuple(initial)
        self.velocity_rad_s = (0.0,) * self.size
        self.acceleration_rad_s2 = (0.0,) * self.size

    def Step(self, target_q_rad: Sequence[float], dt_s: float) -> tuple[float, ...]:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("dt_s must be finite and positive")
        if not math.isclose(dt_s, self.dt_s, rel_tol=0.0, abs_tol=1.0e-12):
            self.dt_s = float(dt_s)
            self._ruckig = Ruckig(self.size, self.dt_s)
        target = _finite_vector(target_q_rad, self.size, "target_q_rad")
        self._input.target_position = list(target)
        result = self._ruckig.update(self._input, self._output)
        if int(result) < 0:
            raise RuntimeError(f"Ruckig update failed with {result}")
        self._output.pass_to_input(self._input)
        self.q_rad = tuple(float(value) for value in self._output.new_position)
        self.velocity_rad_s = tuple(
            float(value) for value in self._output.new_velocity
        )
        self.acceleration_rad_s2 = tuple(
            float(value) for value in self._output.new_acceleration
        )
        return self.q_rad
