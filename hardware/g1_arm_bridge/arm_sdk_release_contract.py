#!/usr/bin/env python3
"""SDK-neutral release finalization for Arm SDK command owners.

This module owns only release sequencing and evidence.  It imports no Unitree
SDK and creates no DDS entities.  Callers provide frame builders and a publish
callback, which makes the failure paths testable without robot output.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable, Generic, TypeVar


FrameT = TypeVar("FrameT")


@dataclass(frozen=True)
class ReleaseEvidence:
    release_attempted: bool
    release_ramp_completed: bool
    release_zero_frames_requested: int
    release_zero_frames_sent: int
    zero_release_completed: bool
    last_successful_weight: float
    last_successful_write_unix_ns: int | None
    release_fault: str | None
    output_state_unknown: bool
    external_authority_handoff_confirmed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "release_attempted": self.release_attempted,
            "release_ramp_completed": self.release_ramp_completed,
            "release_zero_frames_requested": self.release_zero_frames_requested,
            "release_zero_frames_sent": self.release_zero_frames_sent,
            "zero_release_completed": self.zero_release_completed,
            "last_successful_weight": self.last_successful_weight,
            "last_successful_write_unix_ns": self.last_successful_write_unix_ns,
            "release_fault": self.release_fault,
            "output_state_unknown": self.output_state_unknown,
            "external_authority_handoff_confirmed": (
                self.external_authority_handoff_confirmed
            ),
        }


def _validate_release_arguments(
    start_weight: float,
    ramp_s: float,
    zero_cycles: int,
    publish_hz: float,
) -> None:
    values = (start_weight, ramp_s, publish_hz)
    if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values):
        raise ValueError("release values must be finite numbers")
    if start_weight < 0.0 or start_weight > 1.0:
        raise ValueError("start_weight must be in [0, 1]")
    if ramp_s <= 0.0:
        raise ValueError("ramp_s must be > 0")
    if publish_hz <= 0.0:
        raise ValueError("publish_hz must be > 0")
    if not isinstance(zero_cycles, int) or isinstance(zero_cycles, bool) or zero_cycles < 1:
        raise ValueError("zero_cycles must be a positive integer")


def execute_release_sequence(
    *,
    start_weight: float,
    ramp_s: float,
    zero_cycles: int,
    publish_hz: float,
    build_ramp_frame: Callable[[float], FrameT],
    build_zero_frame: Callable[[], FrameT],
    publish_frame: Callable[[FrameT], None],
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    unix_time_ns: Callable[[], int] = time.time_ns,
) -> ReleaseEvidence:
    """Attempt a monotonic ramp-down and an independent zero-weight tail.

    A ramp failure never suppresses the zero-tail attempt.  Completion means
    every requested zero frame was successfully published; it does not claim
    that firmware or another controller has taken ownership afterward.
    """

    _validate_release_arguments(start_weight, ramp_s, zero_cycles, publish_hz)
    period_s = 1.0 / float(publish_hz)
    last_successful_weight = float(start_weight)
    last_successful_write_unix_ns: int | None = None
    ramp_completed = False
    zero_sent = 0
    faults: list[str] = []

    release_started = monotonic()
    try:
        while True:
            elapsed = max(0.0, monotonic() - release_started)
            ratio = min(1.0, elapsed / float(ramp_s))
            weight = float(start_weight) * (1.0 - ratio)
            frame = build_ramp_frame(weight)
            publish_frame(frame)
            last_successful_weight = weight
            last_successful_write_unix_ns = int(unix_time_ns())
            if ratio >= 1.0:
                ramp_completed = True
                break
            sleep(period_s)
    except Exception as exc:  # caller records the exact transport/build failure
        faults.append(f"ramp:{type(exc).__name__}: {exc}")

    try:
        for _ in range(zero_cycles):
            frame = build_zero_frame()
            publish_frame(frame)
            zero_sent += 1
            last_successful_weight = 0.0
            last_successful_write_unix_ns = int(unix_time_ns())
            if zero_sent < zero_cycles:
                sleep(period_s)
    except Exception as exc:
        faults.append(f"zero_tail:{type(exc).__name__}: {exc}")

    zero_completed = zero_sent == zero_cycles
    return ReleaseEvidence(
        release_attempted=True,
        release_ramp_completed=ramp_completed,
        release_zero_frames_requested=zero_cycles,
        release_zero_frames_sent=zero_sent,
        zero_release_completed=zero_completed,
        last_successful_weight=last_successful_weight,
        last_successful_write_unix_ns=last_successful_write_unix_ns,
        release_fault="; ".join(faults) if faults else None,
        output_state_unknown=not zero_completed,
        external_authority_handoff_confirmed=False,
    )
