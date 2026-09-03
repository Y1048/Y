"""Strict localhost-only Gate 7 feedback contract for MuJoCo visualization."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Final, Sequence


SCHEMA: Final[str] = "g1.gate7.simulation_feedback.v1"
DUAL_ARM_JOINT_INDICES: Final[tuple[int, ...]] = tuple(range(15, 29))
SIMULATION_APPLY_STATES: Final[frozenset[str]] = frozenset(
    {"REGULAR_RETURN", "REGULAR_HOLD"}
)
KNOWN_STATES: Final[frozenset[str]] = frozenset(
    {
        "HOLD_CURRENT",
        "TRACK_MINK_RIGHT",
        "SAFETY_HOLD",
        "REGULAR_RETURN",
        "REGULAR_HOLD",
    }
)


class Gate7SimulationFeedbackError(ValueError):
    """Raised when a simulation feedback packet violates the locked contract."""


@dataclass(frozen=True)
class Gate7SimulationFeedback:
    stream_id: str
    sequence: int
    source_time_s: float
    state: str
    reason: str
    return_progress: float
    dual_arm_q_rad: tuple[float, ...]


def _finite_vector(values: Sequence[object], length: int) -> tuple[float, ...]:
    if len(values) != length:
        raise Gate7SimulationFeedbackError(
            f"dual_arm_q_rad must contain exactly {length} values"
        )
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise Gate7SimulationFeedbackError("dual_arm_q_rad must be finite")
    return result


def build_packet(
    *,
    stream_id: str,
    sequence: int,
    source_time_s: float,
    state: str,
    reason: str,
    return_progress: float,
    dual_arm_q_rad: Sequence[float],
) -> bytes:
    """Build a packet that cannot be mistaken for a physical command."""
    if not isinstance(stream_id, str) or not stream_id or len(stream_id) > 128:
        raise Gate7SimulationFeedbackError("stream_id must be a non-empty string")
    if sequence < 0:
        raise Gate7SimulationFeedbackError("sequence must be non-negative")
    if state not in KNOWN_STATES:
        raise Gate7SimulationFeedbackError(f"unknown Gate 7 state: {state}")
    source_time = float(source_time_s)
    progress = float(return_progress)
    if not math.isfinite(source_time):
        raise Gate7SimulationFeedbackError("source_time_s must be finite")
    if not math.isfinite(progress) or not 0.0 <= progress <= 1.0:
        raise Gate7SimulationFeedbackError("return_progress must be within [0, 1]")
    joints = _finite_vector(dual_arm_q_rad, len(DUAL_ARM_JOINT_INDICES))
    value = {
        "schema": SCHEMA,
        "stream_id": stream_id,
        "sequence": int(sequence),
        "source_time_s": source_time,
        "state": state,
        "reason": str(reason),
        "return_progress": progress,
        "dual_arm_joint_indices": list(DUAL_ARM_JOINT_INDICES),
        "dual_arm_q_rad": list(joints),
        "simulation_only": True,
        "hardware_output_authorized": False,
    }
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def parse_packet(payload: bytes | str) -> Gate7SimulationFeedback:
    """Parse and validate the simulation-only safety boundary."""
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate7SimulationFeedbackError("invalid feedback JSON") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise Gate7SimulationFeedbackError("unsupported feedback schema")
    if value.get("simulation_only") is not True:
        raise Gate7SimulationFeedbackError("simulation_only must be true")
    if value.get("hardware_output_authorized") is not False:
        raise Gate7SimulationFeedbackError(
            "hardware_output_authorized must be false"
        )
    if tuple(value.get("dual_arm_joint_indices", ())) != DUAL_ARM_JOINT_INDICES:
        raise Gate7SimulationFeedbackError("dual-arm joint indices must be 15..28")
    stream_id = value.get("stream_id")
    if not isinstance(stream_id, str) or not stream_id or len(stream_id) > 128:
        raise Gate7SimulationFeedbackError("stream_id must be a non-empty string")
    sequence = value.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise Gate7SimulationFeedbackError("sequence must be a non-negative integer")
    state = value.get("state")
    if state not in KNOWN_STATES:
        raise Gate7SimulationFeedbackError(f"unknown Gate 7 state: {state}")
    source_time = float(value.get("source_time_s"))
    progress = float(value.get("return_progress"))
    if not math.isfinite(source_time):
        raise Gate7SimulationFeedbackError("source_time_s must be finite")
    if not math.isfinite(progress) or not 0.0 <= progress <= 1.0:
        raise Gate7SimulationFeedbackError("return_progress must be within [0, 1]")
    return Gate7SimulationFeedback(
        stream_id=stream_id,
        sequence=sequence,
        source_time_s=source_time,
        state=state,
        reason=str(value.get("reason", "")),
        return_progress=progress,
        dual_arm_q_rad=_finite_vector(
            value.get("dual_arm_q_rad", ()),
            len(DUAL_ARM_JOINT_INDICES),
        ),
    )


def should_apply(
    feedback: Gate7SimulationFeedback | None,
    *,
    command_active: bool,
    packet_age_s: float,
    timeout_s: float,
) -> bool:
    """Only a fresh return/hold packet may override MuJoCo visualization."""
    return bool(
        feedback is not None
        and not command_active
        and math.isfinite(packet_age_s)
        and 0.0 <= packet_age_s <= timeout_s
        and feedback.state in SIMULATION_APPLY_STATES
    )
