#!/usr/bin/env python3
"""SDK-neutral guards for Gate 7 acquisition and publisher-boundary binding.

These helpers create no DDS entities and send no robot command. They keep the
supported physical entrypoint fail-closed while authority is ramping up.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Sequence

from arm_sdk_hold_contract import validate_measured_hold
from arm_sdk_teleop_contract import Gate7ContractError, MinkArmSample


@dataclass
class ActiveAcquisitionGuard:
    """Require one ordered, continuously fresh ACTIVE Mink session during acquire."""

    timeout_s: float
    session_id: str | None = None
    last_sequence: int | None = None
    last_receive_monotonic_s: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0.0:
            raise ValueError("timeout_s must be finite and positive")

    def seed(self, sample: MinkArmSample, *, now_s: float | None = None) -> None:
        self._validate_active_sample(sample)
        self.session_id = sample.session_id
        self.last_sequence = sample.sequence
        self.last_receive_monotonic_s = time.monotonic() if now_s is None else float(now_s)

    def observe(self, sample: MinkArmSample, *, now_s: float | None = None) -> None:
        if self.session_id is None or self.last_sequence is None:
            raise RuntimeError("acquisition guard was not seeded")
        self._validate_active_sample(sample)
        if sample.session_id != self.session_id:
            raise RuntimeError(
                "Mink session changed during authority acquisition: "
                f"{self.session_id!r}->{sample.session_id!r}"
            )
        if sample.sequence <= self.last_sequence:
            raise RuntimeError(
                "Mink sequence did not increase during authority acquisition: "
                f"{sample.sequence}<={self.last_sequence}"
            )
        self.last_sequence = sample.sequence
        self.last_receive_monotonic_s = time.monotonic() if now_s is None else float(now_s)

    def require_fresh(self, *, now_s: float | None = None) -> float:
        if self.last_receive_monotonic_s is None:
            raise RuntimeError("no ACTIVE Mink sample is available during acquisition")
        now = time.monotonic() if now_s is None else float(now_s)
        age_s = now - self.last_receive_monotonic_s
        if not math.isfinite(age_s) or age_s < 0.0:
            raise RuntimeError("invalid acquisition Mink receive age")
        if age_s > self.timeout_s:
            raise RuntimeError(
                f"Mink ACTIVE stream stale during acquisition: {age_s:.3f}s"
            )
        return age_s

    def _validate_active_sample(self, sample: MinkArmSample) -> None:
        if not (
            sample.active
            and sample.input_command_mode == "active"
            and sample.controller_state == "active"
        ):
            raise RuntimeError("Mink stream left ACTIVE during authority acquisition")
        if sample.session_id is None:
            raise RuntimeError("ACTIVE acquisition sample is missing session_id")
        if sample.input_packet_age_s is None:
            raise RuntimeError("ACTIVE acquisition sample is missing input packet age")
        if sample.input_packet_age_s > self.timeout_s:
            raise RuntimeError(
                "embedded Mink input age is stale during acquisition: "
                f"{sample.input_packet_age_s:.3f}s"
            )


def validate_full_body_snapshot_matches_precheck(
    snapshot: Any,
    precheck: dict[str, Any],
    maximum_delta_rad: float,
) -> float:
    """Bind publisher-boundary joint state to all 29 prechecked joints."""

    if not math.isfinite(maximum_delta_rad) or maximum_delta_rad <= 0.0:
        raise ValueError("maximum_delta_rad must be finite and positive")
    values = precheck.get("latest_all_joint_q_rad")
    if not isinstance(values, list) or len(values) != 29:
        raise ValueError("startup precheck is missing the canonical 29-joint pose")
    expected = tuple(float(value) for value in values)
    actual = tuple(float(value) for value in snapshot.all_q_rad)
    if len(actual) != 29 or not all(math.isfinite(value) for value in expected + actual):
        raise ValueError("publisher-boundary full-body pose is invalid")
    maximum_delta = max(abs(a - b) for a, b in zip(actual, expected))
    if maximum_delta > maximum_delta_rad:
        raise RuntimeError(
            "full-body pose changed after startup precheck: "
            f"{math.degrees(maximum_delta):.2f} deg > "
            f"{math.degrees(maximum_delta_rad):.2f} deg"
        )
    return maximum_delta


def validate_acquisition_hold_target(
    measured_all_q_rad: Sequence[float],
    target_dual_arm_q_rad: Sequence[float],
    config: Any,
) -> None:
    """Recheck joint limits and measured-target error on every acquire frame."""

    validation = validate_measured_hold(
        measured_all_q_rad,
        target_dual_arm_q_rad,
        0.0,
        config,
    )
    if not validation.allowed:
        raise RuntimeError("acquisition HOLD rejected: " + validation.reason)
