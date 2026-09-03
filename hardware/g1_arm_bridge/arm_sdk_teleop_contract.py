#!/usr/bin/env python3
"""Offline contract between Mink right-arm output and G1 ``rt/arm_sdk``.

This module has no Unitree SDK, DDS, socket, or publisher dependency.  It keeps
the physical-output boundary locked while defining three behaviors:

* active Mink samples update only the right-arm target;
* tracking/network/workspace/collision loss freezes the current dual-arm target
  for a bounded recovery window;
* an intentional pinch returns immediately, while a fault that remains for the
  configured hold time starts the same prevalidated minimum-jerk return of both
  arms to the captured Regular posture.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final, Sequence

from arm_sdk_hold_contract import (
    BODY_JOINT_COUNT,
    DUAL_ARM_INDICES,
    LEFT_ARM_LIMITS_RAD,
    RIGHT_ARM_INDICES,
    RIGHT_ARM_LIMITS_RAD,
    dual_arm_from_all_joints,
)
from g1_joint_contract import G1_29_JOINT_NAMES

MINK_STATE_SCHEMA: Final[str] = "g1.mink.right_arm.state.v1"
REGULAR_POSE_SCHEMA: Final[str] = "g1.regular.dual_arm_pose.v1"
GATE7_CONFIG_SCHEMA: Final[str] = "g1.gate7.mink_arm_sdk.config.v1"

INPUT_COMMAND_MODES: Final[frozenset[str]] = frozenset(
    {
        "active",
        "idle",
        "workspace_exit",
        "pinch_disengaged",
        "tracking_disengaged",
    }
)
CONTROLLER_STATES: Final[frozenset[str]] = frozenset(
    {"active", "hold", "idle", "workspace_fault"}
)
PROXIMAL_DUAL_ARM_OFFSETS: Final[tuple[int, ...]] = (0, 1, 2, 3, 7, 8, 9, 10)
WRIST_DUAL_ARM_OFFSETS: Final[tuple[int, ...]] = (4, 5, 6, 11, 12, 13)


class Gate7ContractError(ValueError):
    """Raised when a packet or configuration violates the locked contract."""


@dataclass(frozen=True)
class RegularArmPose:
    name: str
    dual_arm_q_rad: tuple[float, ...]
    reference_all_joint_q_rad: tuple[float, ...]
    source: str
    captured_at: str


@dataclass(frozen=True)
class Gate7Config:
    input_timeout_s: float
    unintended_hold_before_regular_return_s: float
    command_hz: float
    proximal_max_velocity_rad_s: float
    wrist_max_velocity_rad_s: float
    proximal_max_acceleration_rad_s2: float
    wrist_max_acceleration_rad_s2: float
    proximal_max_jerk_rad_s3: float
    wrist_max_jerk_rad_s3: float
    minimum_return_duration_s: float
    maximum_target_error_rad: float
    minimum_collision_clearance_m: float
    command_weight: float
    hardware_output_authorized: bool

    @property
    def velocity_limits_rad_s(self) -> tuple[float, ...]:
        return _dual_arm_limits(
            self.proximal_max_velocity_rad_s,
            self.wrist_max_velocity_rad_s,
        )

    @property
    def acceleration_limits_rad_s2(self) -> tuple[float, ...]:
        return _dual_arm_limits(
            self.proximal_max_acceleration_rad_s2,
            self.wrist_max_acceleration_rad_s2,
        )

    @property
    def jerk_limits_rad_s3(self) -> tuple[float, ...]:
        return _dual_arm_limits(
            self.proximal_max_jerk_rad_s3,
            self.wrist_max_jerk_rad_s3,
        )


@dataclass(frozen=True)
class MinkArmSample:
    sequence: int
    session_id: str | None
    input_command_mode: str
    controller_state: str
    active: bool
    input_packet_age_s: float | None
    timestamp_s: float
    all_joint_q_rad: tuple[float, ...]
    right_arm_q_rad: tuple[float, ...]
    workspace_limited: bool
    collision_limited: bool
    minimum_clearance_m: float | None
    nearest_collision_geoms: tuple[str, ...]
    nearest_collision_bodies: tuple[str, ...]


@dataclass(frozen=True)
class TrajectorySample:
    time_s: float
    q_rad: tuple[float, ...]
    dq_rad_s: tuple[float, ...]
    ddq_rad_s2: tuple[float, ...]
    jerk_rad_s3: tuple[float, ...]


@dataclass(frozen=True)
class MinimumJerkTrajectory:
    start_q_rad: tuple[float, ...]
    goal_q_rad: tuple[float, ...]
    duration_s: float
    command_hz: float

    def sample(self, time_s: float) -> TrajectorySample:
        if not math.isfinite(time_s):
            raise Gate7ContractError("trajectory time must be finite")
        clamped_time = min(max(float(time_s), 0.0), self.duration_s)
        tau = clamped_time / self.duration_s
        tau2 = tau * tau
        tau3 = tau2 * tau
        tau4 = tau3 * tau
        tau5 = tau4 * tau
        position_scale = 10.0 * tau3 - 15.0 * tau4 + 6.0 * tau5
        velocity_scale = (
            30.0 * tau2 - 60.0 * tau3 + 30.0 * tau4
        ) / self.duration_s
        acceleration_scale = (
            60.0 * tau - 180.0 * tau2 + 120.0 * tau3
        ) / (self.duration_s * self.duration_s)
        jerk_scale = (
            60.0 - 360.0 * tau + 360.0 * tau2
        ) / (self.duration_s**3)
        delta = tuple(
            goal - start
            for start, goal in zip(self.start_q_rad, self.goal_q_rad)
        )
        return TrajectorySample(
            time_s=clamped_time,
            q_rad=tuple(
                start + position_scale * difference
                for start, difference in zip(self.start_q_rad, delta)
            ),
            dq_rad_s=tuple(velocity_scale * difference for difference in delta),
            ddq_rad_s2=tuple(
                acceleration_scale * difference for difference in delta
            ),
            jerk_rad_s3=tuple(jerk_scale * difference for difference in delta),
        )

    def discrete_samples(self) -> tuple[TrajectorySample, ...]:
        steps = max(1, int(round(self.duration_s * self.command_hz)))
        return tuple(
            self.sample(index / self.command_hz)
            for index in range(steps + 1)
        )


@dataclass(frozen=True)
class Gate7Decision:
    state: str
    reason: str
    target_dual_arm_q_rad: tuple[float, ...]
    return_progress: float
    command_candidate_valid: bool
    hardware_output_authorized: bool = False


ReturnPathValidator = Callable[
    [MinimumJerkTrajectory, tuple[float, ...]], tuple[bool, str]
]


def _finite_vector(
    values: Sequence[float], expected_length: int, name: str
) -> tuple[float, ...]:
    if len(values) != expected_length:
        raise Gate7ContractError(
            f"{name} must contain exactly {expected_length} values"
        )
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise Gate7ContractError(f"{name} contains a non-finite value")
    return result


def _finite_number(value: object, name: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise Gate7ContractError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or (positive and result <= 0.0):
        suffix = " and positive" if positive else ""
        raise Gate7ContractError(f"{name} must be finite{suffix}")
    return result


def _dual_arm_limits(proximal: float, wrist: float) -> tuple[float, ...]:
    values = [0.0] * len(DUAL_ARM_INDICES)
    for index in PROXIMAL_DUAL_ARM_OFFSETS:
        values[index] = proximal
    for index in WRIST_DUAL_ARM_OFFSETS:
        values[index] = wrist
    return tuple(values)


def _validate_dual_arm_joint_limits(values: Sequence[float], name: str) -> None:
    vector = _finite_vector(values, len(DUAL_ARM_INDICES), name)
    limits = LEFT_ARM_LIMITS_RAD + RIGHT_ARM_LIMITS_RAD
    for index, (value, (lower, upper)) in enumerate(zip(vector, limits)):
        if value < lower or value > upper:
            raise Gate7ContractError(
                f"{name}[{index}]={math.degrees(value):.2f}deg is outside "
                f"[{math.degrees(lower):.2f},{math.degrees(upper):.2f}]deg"
            )


def load_regular_arm_pose(path: Path) -> RegularArmPose:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != REGULAR_POSE_SCHEMA:
        raise Gate7ContractError("unsupported Regular pose schema")
    indices = tuple(int(index) for index in value.get("joint_indices", []))
    if indices != DUAL_ARM_INDICES:
        raise Gate7ContractError("Regular pose joint_indices must be 15..28")
    authorization = value.get("physical_output_authorized")
    if not isinstance(authorization, bool) or authorization:
        raise Gate7ContractError(
            "Regular pose artifact must explicitly keep physical output locked"
        )
    dual_arm = _finite_vector(
        value.get("dual_arm_q_rad", []),
        len(DUAL_ARM_INDICES),
        "dual_arm_q_rad",
    )
    _validate_dual_arm_joint_limits(dual_arm, "dual_arm_q_rad")
    reference_all_joint = _finite_vector(
        value.get("reference_all_joint_q_rad", []),
        BODY_JOINT_COUNT,
        "reference_all_joint_q_rad",
    )
    return RegularArmPose(
        name=str(value.get("name", "regular")),
        dual_arm_q_rad=dual_arm,
        reference_all_joint_q_rad=reference_all_joint,
        source=str(value.get("source", "unknown")),
        captured_at=str(value.get("captured_at", "unknown")),
    )


def load_gate7_config(path: Path) -> Gate7Config:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if value.get("schema") != GATE7_CONFIG_SCHEMA:
        raise Gate7ContractError("unsupported Gate 7 config schema")
    authorization = value.get("hardware_output_authorized")
    if not isinstance(authorization, bool):
        raise Gate7ContractError("hardware_output_authorized must be boolean")
    config = Gate7Config(
        input_timeout_s=_finite_number(
            value.get("input_timeout_s"), "input_timeout_s", positive=True
        ),
        unintended_hold_before_regular_return_s=_finite_number(
            value.get("unintended_hold_before_regular_return_s"),
            "unintended_hold_before_regular_return_s",
            positive=True,
        ),
        command_hz=_finite_number(
            value.get("command_hz"), "command_hz", positive=True
        ),
        proximal_max_velocity_rad_s=math.radians(
            _finite_number(
                value.get("proximal_max_velocity_deg_s"),
                "proximal_max_velocity_deg_s",
                positive=True,
            )
        ),
        wrist_max_velocity_rad_s=math.radians(
            _finite_number(
                value.get("wrist_max_velocity_deg_s"),
                "wrist_max_velocity_deg_s",
                positive=True,
            )
        ),
        proximal_max_acceleration_rad_s2=math.radians(
            _finite_number(
                value.get("proximal_max_acceleration_deg_s2"),
                "proximal_max_acceleration_deg_s2",
                positive=True,
            )
        ),
        wrist_max_acceleration_rad_s2=math.radians(
            _finite_number(
                value.get("wrist_max_acceleration_deg_s2"),
                "wrist_max_acceleration_deg_s2",
                positive=True,
            )
        ),
        proximal_max_jerk_rad_s3=math.radians(
            _finite_number(
                value.get("proximal_max_jerk_deg_s3"),
                "proximal_max_jerk_deg_s3",
                positive=True,
            )
        ),
        wrist_max_jerk_rad_s3=math.radians(
            _finite_number(
                value.get("wrist_max_jerk_deg_s3"),
                "wrist_max_jerk_deg_s3",
                positive=True,
            )
        ),
        minimum_return_duration_s=_finite_number(
            value.get("minimum_return_duration_s"),
            "minimum_return_duration_s",
            positive=True,
        ),
        maximum_target_error_rad=math.radians(
            _finite_number(
                value.get("maximum_target_error_deg"),
                "maximum_target_error_deg",
                positive=True,
            )
        ),
        minimum_collision_clearance_m=_finite_number(
            value.get("minimum_collision_clearance_m"),
            "minimum_collision_clearance_m",
            positive=True,
        ),
        command_weight=_finite_number(
            value.get("command_weight"), "command_weight", positive=True
        ),
        hardware_output_authorized=authorization,
    )
    if config.command_weight > 1.0:
        raise Gate7ContractError("command_weight must be <= 1")
    if config.hardware_output_authorized:
        raise Gate7ContractError(
            "Gate 7 repository config must keep hardware output locked"
        )
    return config


def parse_mink_arm_sample(payload: bytes | str) -> MinkArmSample:
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate7ContractError("Mink state is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise Gate7ContractError("Mink state root must be an object")
    if value.get("schema") != MINK_STATE_SCHEMA:
        raise Gate7ContractError("unexpected Mink state schema")
    if value.get("state_source") != "mink_simulation":
        raise Gate7ContractError("Mink state source is not mink_simulation")

    sequence = value.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise Gate7ContractError("sequence must be a non-negative integer")
    session_value = value.get("session_id")
    if session_value is not None and (
        not isinstance(session_value, str) or not session_value.strip()
    ):
        raise Gate7ContractError("session_id must be null or a non-empty string")
    session_id = None if session_value is None else session_value.strip()

    input_mode = value.get("input_command_mode")
    if input_mode not in INPUT_COMMAND_MODES:
        raise Gate7ContractError("input_command_mode is invalid")
    names = value.get("all_joint_names")
    if tuple(names or ()) != G1_29_JOINT_NAMES:
        raise Gate7ContractError("all_joint_names does not match G1 motor order")
    all_q = _finite_vector(
        value.get("all_joint_q_rad", []),
        BODY_JOINT_COUNT,
        "all_joint_q_rad",
    )

    right = value.get("right_arm")
    if not isinstance(right, dict):
        raise Gate7ContractError("right_arm must be an object")
    right_q = _finite_vector(right.get("joints", []), 7, "right_arm.joints")
    expected_right = tuple(all_q[index] for index in RIGHT_ARM_INDICES)
    if any(
        abs(actual - expected) > 1e-7
        for actual, expected in zip(right_q, expected_right)
    ):
        raise Gate7ContractError(
            "right_arm.joints does not match all_joint_q_rad[22:29]"
        )
    active = right.get("active")
    if not isinstance(active, bool):
        raise Gate7ContractError("right_arm.active must be boolean")
    controller_state = right.get("command_state")
    if controller_state not in CONTROLLER_STATES:
        raise Gate7ContractError("right_arm.command_state is invalid")
    if active != (controller_state == "active"):
        raise Gate7ContractError("right_arm active/state combination is invalid")

    packet_age_value = value.get("input_packet_age_s")
    packet_age = (
        None
        if packet_age_value is None
        else _finite_number(packet_age_value, "input_packet_age_s")
    )
    if packet_age is not None and packet_age < 0.0:
        raise Gate7ContractError("input_packet_age_s must be non-negative")
    if active and (session_id is None or packet_age is None):
        raise Gate7ContractError(
            "active Mink state requires session_id and input_packet_age_s"
        )

    workspace_limited = right.get("workspace_limited")
    collision_limited = right.get("collision_limited")
    if not isinstance(workspace_limited, bool):
        raise Gate7ContractError("right_arm.workspace_limited must be boolean")
    if not isinstance(collision_limited, bool):
        raise Gate7ContractError("right_arm.collision_limited must be boolean")
    clearance_value = right.get("minimum_clearance_m")
    minimum_clearance = (
        None
        if clearance_value is None
        else _finite_number(clearance_value, "right_arm.minimum_clearance_m")
    )
    nearest_geoms_value = right.get("nearest_collision_geoms", [])
    nearest_bodies_value = right.get("nearest_collision_bodies", [])
    if not isinstance(nearest_geoms_value, list) or not all(
        isinstance(item, str) for item in nearest_geoms_value
    ):
        raise Gate7ContractError(
            "right_arm.nearest_collision_geoms must be a string array"
        )
    if not isinstance(nearest_bodies_value, list) or not all(
        isinstance(item, str) for item in nearest_bodies_value
    ):
        raise Gate7ContractError(
            "right_arm.nearest_collision_bodies must be a string array"
        )

    return MinkArmSample(
        sequence=sequence,
        session_id=session_id,
        input_command_mode=input_mode,
        controller_state=controller_state,
        active=active,
        input_packet_age_s=packet_age,
        timestamp_s=_finite_number(value.get("timestamp"), "timestamp"),
        all_joint_q_rad=all_q,
        right_arm_q_rad=right_q,
        workspace_limited=workspace_limited,
        collision_limited=collision_limited,
        minimum_clearance_m=minimum_clearance,
        nearest_collision_geoms=tuple(nearest_geoms_value),
        nearest_collision_bodies=tuple(nearest_bodies_value),
    )


def plan_minimum_jerk_return(
    start_q_rad: Sequence[float],
    goal_q_rad: Sequence[float],
    config: Gate7Config,
) -> MinimumJerkTrajectory:
    start = _finite_vector(
        start_q_rad, len(DUAL_ARM_INDICES), "return_start_q_rad"
    )
    goal = _finite_vector(
        goal_q_rad, len(DUAL_ARM_INDICES), "return_goal_q_rad"
    )
    _validate_dual_arm_joint_limits(start, "return_start_q_rad")
    _validate_dual_arm_joint_limits(goal, "return_goal_q_rad")

    duration = config.minimum_return_duration_s
    for difference, velocity, acceleration, jerk in zip(
        (abs(goal_value - start_value) for start_value, goal_value in zip(start, goal)),
        config.velocity_limits_rad_s,
        config.acceleration_limits_rad_s2,
        config.jerk_limits_rad_s3,
    ):
        duration = max(
            duration,
            1.875 * difference / velocity,
            math.sqrt(5.7735026919 * difference / acceleration),
            (60.0 * difference / jerk) ** (1.0 / 3.0),
        )
    steps = max(1, math.ceil(duration * config.command_hz))
    rounded_duration = steps / config.command_hz
    return MinimumJerkTrajectory(start, goal, rounded_duration, config.command_hz)


class Gate7TeleopController:
    """Pure fail-closed command-intent controller for the future Gate 7 loop."""

    def __init__(
        self,
        regular_pose: RegularArmPose,
        config: Gate7Config,
        *,
        return_path_validator: ReturnPathValidator | None,
    ) -> None:
        self.regular_pose = regular_pose
        self.config = config
        self.return_path_validator = return_path_validator
        self.state = "HOLD_CURRENT"
        self._session_id: str | None = None
        self._last_sequence: int | None = None
        self._previous_input_mode = "idle"
        self._active_seen = False
        self._latest_sample: MinkArmSample | None = None
        self._input_age_s = float("inf")
        self._target_dual_arm_q_rad: tuple[float, ...] | None = None
        self._return_trajectory: MinimumJerkTrajectory | None = None
        self._return_elapsed_s = 0.0
        self._return_reason = ""
        self._safety_hold_elapsed_s = 0.0

    def _reset_safety_hold(self) -> None:
        self._safety_hold_elapsed_s = 0.0

    def _hold(
        self,
        measured_dual_arm: tuple[float, ...],
        reason: str,
        *,
        cancel_return: bool = True,
    ) -> Gate7Decision:
        if cancel_return:
            self._return_trajectory = None
            self._return_elapsed_s = 0.0
            self._return_reason = ""
        if self._target_dual_arm_q_rad is None:
            self._target_dual_arm_q_rad = measured_dual_arm
        self.state = "HOLD_CURRENT"
        return Gate7Decision(
            state=self.state,
            reason=reason,
            target_dual_arm_q_rad=self._target_dual_arm_q_rad,
            return_progress=0.0,
            command_candidate_valid=True,
        )

    def _begin_regular_return(
        self,
        measured_dual_arm: tuple[float, ...],
        measured_all_q_rad: tuple[float, ...],
        reason: str,
    ) -> Gate7Decision:
        trajectory = plan_minimum_jerk_return(
            measured_dual_arm,
            self.regular_pose.dual_arm_q_rad,
            self.config,
        )
        if self.return_path_validator is None:
            return self._hold(measured_dual_arm, "return_path_unvalidated")
        allowed, validation_reason = self.return_path_validator(
            trajectory,
            measured_all_q_rad,
        )
        if not allowed:
            return self._hold(
                measured_dual_arm,
                "return_path_rejected:" + validation_reason,
            )
        self._return_trajectory = trajectory
        self._return_elapsed_s = 0.0
        self._return_reason = reason
        self._target_dual_arm_q_rad = measured_dual_arm
        self._reset_safety_hold()
        self.state = "REGULAR_RETURN"
        return self._advance_regular_return(0.0, measured_dual_arm)

    def _advance_regular_return(
        self,
        dt_s: float,
        measured_dual_arm: tuple[float, ...],
    ) -> Gate7Decision:
        if self._return_trajectory is None:
            return self._hold(measured_dual_arm, "return_plan_missing")
        self._return_elapsed_s = min(
            self._return_trajectory.duration_s,
            self._return_elapsed_s + dt_s,
        )
        point = self._return_trajectory.sample(self._return_elapsed_s)
        self._target_dual_arm_q_rad = point.q_rad
        progress = self._return_elapsed_s / self._return_trajectory.duration_s
        if progress >= 1.0:
            self.state = "REGULAR_HOLD"
            return Gate7Decision(
                state=self.state,
                reason="regular_return_complete",
                target_dual_arm_q_rad=self.regular_pose.dual_arm_q_rad,
                return_progress=1.0,
                command_candidate_valid=True,
            )
        return Gate7Decision(
            state=self.state,
            reason=self._return_reason,
            target_dual_arm_q_rad=point.q_rad,
            return_progress=progress,
            command_candidate_valid=True,
        )

    def _safety_hold(
        self,
        measured_dual_arm: tuple[float, ...],
        measured_all_q_rad: tuple[float, ...],
        reason: str,
        dt_s: float,
    ) -> Gate7Decision:
        if not self._active_seen:
            return self._hold(measured_dual_arm, reason)
        if self.state != "SAFETY_HOLD":
            self._safety_hold_elapsed_s = 0.0
            self._return_trajectory = None
            self._return_elapsed_s = 0.0
            self._return_reason = ""
            self._target_dual_arm_q_rad = measured_dual_arm
        self.state = "SAFETY_HOLD"
        self._safety_hold_elapsed_s = min(
            self.config.unintended_hold_before_regular_return_s,
            self._safety_hold_elapsed_s + dt_s,
        )
        if (
            self._safety_hold_elapsed_s
            >= self.config.unintended_hold_before_regular_return_s
        ):
            return self._begin_regular_return(
                measured_dual_arm,
                measured_all_q_rad,
                "unintended_hold_timeout_return",
            )
        return Gate7Decision(
            state=self.state,
            reason=reason,
            target_dual_arm_q_rad=self._target_dual_arm_q_rad,
            return_progress=(
                self._safety_hold_elapsed_s
                / self.config.unintended_hold_before_regular_return_s
            ),
            command_candidate_valid=True,
        )

    def _validate_order(self, sample: MinkArmSample) -> bool:
        session_changed = sample.session_id != self._session_id
        if session_changed:
            self._session_id = sample.session_id
            self._last_sequence = sample.sequence
            self._previous_input_mode = "idle"
            self._active_seen = False
            self._reset_safety_hold()
            return False
        if self._last_sequence is not None and sample.sequence <= self._last_sequence:
            raise Gate7ContractError(
                f"non-increasing Mink sequence:{sample.sequence}<={self._last_sequence}"
            )
        self._last_sequence = sample.sequence
        return True

    def _step_right_arm_target(
        self,
        requested_right_q_rad: tuple[float, ...],
        measured_dual_arm: tuple[float, ...],
        dt_s: float,
    ) -> tuple[float, ...]:
        previous = self._target_dual_arm_q_rad or measured_dual_arm
        requested = list(previous)
        requested[7:] = requested_right_q_rad
        stepped = list(previous)
        for index, (current, target, velocity) in enumerate(
            zip(previous, requested, self.config.velocity_limits_rad_s)
        ):
            maximum_step = velocity * dt_s
            delta = target - current
            stepped[index] = current + max(-maximum_step, min(maximum_step, delta))
        result = tuple(stepped)
        _validate_dual_arm_joint_limits(result, "active_target_dual_arm_q_rad")
        maximum_error = max(
            abs(target - measured)
            for target, measured in zip(result, measured_dual_arm)
        )
        if maximum_error > self.config.maximum_target_error_rad:
            raise Gate7ContractError(
                "active target exceeds measured pose by "
                f"{math.degrees(maximum_error):.2f}deg"
            )
        return result

    def step(
        self,
        sample: MinkArmSample | None,
        measured_all_q_rad: Sequence[float],
        dt_s: float,
    ) -> Gate7Decision:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise Gate7ContractError("dt_s must be finite and positive")
        measured_all = _finite_vector(
            measured_all_q_rad, BODY_JOINT_COUNT, "measured_all_q_rad"
        )
        measured_dual = dual_arm_from_all_joints(measured_all)
        if self._target_dual_arm_q_rad is None:
            self._target_dual_arm_q_rad = measured_dual

        new_sample = sample is not None
        pinch_edge = False
        if sample is not None:
            same_session = self._validate_order(sample)
            self._latest_sample = sample
            self._input_age_s = (
                float("inf")
                if sample.input_packet_age_s is None
                else sample.input_packet_age_s
            )
            previous_mode = self._previous_input_mode
            self._previous_input_mode = sample.input_command_mode
            pinch_edge = (
                same_session
                and self._active_seen
                and previous_mode == "active"
                and sample.input_command_mode == "pinch_disengaged"
            )
            if not same_session:
                self._target_dual_arm_q_rad = measured_dual
                return self._hold(measured_dual, "session_sync")
        else:
            self._input_age_s += dt_s

        if self.state == "REGULAR_RETURN":
            return self._advance_regular_return(dt_s, measured_dual)
        if self.state == "REGULAR_HOLD":
            rearm_requested = bool(
                new_sample
                and sample is not None
                and sample.input_command_mode == "active"
                and sample.active
            )
            if rearm_requested:
                self._target_dual_arm_q_rad = measured_dual
                self._reset_safety_hold()
                self.state = "HOLD_CURRENT"
            else:
                self._target_dual_arm_q_rad = self.regular_pose.dual_arm_q_rad
                return Gate7Decision(
                    state=self.state,
                    reason="regular_pose_hold",
                    target_dual_arm_q_rad=self._target_dual_arm_q_rad,
                    return_progress=1.0,
                    command_candidate_valid=True,
                )

        current_sample = self._latest_sample
        if current_sample is None:
            return self._hold(measured_dual, "waiting_for_mink_state")
        mode = current_sample.input_command_mode
        fresh = self._input_age_s <= self.config.input_timeout_s
        if not fresh:
            return self._safety_hold(
                measured_dual, measured_all, "input_stale", dt_s
            )
        # An intentional pinch requests a separately collision-validated path
        # back to Regular. Handle that escape request before the current-pose
        # collision hold; otherwise one collision flag consumes the pinch edge
        # and forces the operator to wait for the unintended-loss timeout.
        if pinch_edge:
            return self._begin_regular_return(
                measured_dual,
                measured_all,
                "intentional_pinch_return",
            )
        if current_sample.workspace_limited or mode == "workspace_exit":
            return self._safety_hold(
                measured_dual, measured_all, "workspace_hold", dt_s
            )
        if current_sample.minimum_clearance_m is None:
            if current_sample.collision_limited:
                return self._safety_hold(
                    measured_dual,
                    measured_all,
                    "collision_state_incomplete_hold",
                    dt_s,
                )
        elif (
            current_sample.minimum_clearance_m
            < self.config.minimum_collision_clearance_m
        ):
            return self._safety_hold(
                measured_dual, measured_all, "collision_hold", dt_s
            )
        if mode == "tracking_disengaged":
            return self._safety_hold(
                measured_dual, measured_all, "tracking_loss_hold", dt_s
            )

        if mode == "active" and current_sample.active and new_sample:
            self._reset_safety_hold()
            try:
                self._target_dual_arm_q_rad = self._step_right_arm_target(
                    current_sample.right_arm_q_rad,
                    measured_dual,
                    dt_s,
                )
            except Gate7ContractError as exc:
                return self._safety_hold(
                    measured_dual,
                    measured_all,
                    "active_target_rejected:" + str(exc),
                    dt_s,
                )
            self._active_seen = True
            self.state = "TRACK_MINK_RIGHT"
            return Gate7Decision(
                state=self.state,
                reason="active_right_arm_tracking",
                target_dual_arm_q_rad=self._target_dual_arm_q_rad,
                return_progress=0.0,
                command_candidate_valid=True,
            )

        if mode == "active" and current_sample.active:
            self._reset_safety_hold()
            self.state = "TRACK_MINK_RIGHT"
            return Gate7Decision(
                state=self.state,
                reason="waiting_for_next_mink_sample",
                target_dual_arm_q_rad=self._target_dual_arm_q_rad,
                return_progress=0.0,
                command_candidate_valid=True,
            )

        return self._safety_hold(
            measured_dual,
            measured_all,
            "inactive_hold",
            dt_s,
        )
