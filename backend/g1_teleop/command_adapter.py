"""Compatibility adapter from legacy and V2 wire packets to one command model."""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .protocol import POSE_SCHEMA_V2, PosePacketV2, ProtocolError
from .transforms import normalize_quaternion


@dataclass(frozen=True)
class InternalCommand:
    session_id: str
    sequence: int
    mode: str
    valid: bool
    position_m: np.ndarray
    quaternion_xyzw: np.ndarray
    source_time_ns: int | None
    frame_id: str
    protocol: str

    @property
    def workspace_exit(self) -> bool:
        return self.mode == "workspace_exit"


def _legacy_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProtocolError(f"{field_name} must be a non-negative integer")
    return value


def _legacy_vector(value: object, length: int, field_name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"{field_name} must be numeric") from error
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ProtocolError(f"{field_name} must contain {length} finite values")
    return result


def parse_legacy_command(payload: bytes | str) -> InternalCommand:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("legacy packet is not valid UTF-8 JSON") from error

    if not isinstance(value, dict):
        raise ProtocolError("legacy packet must be a JSON object")
    if "schema" in value:
        raise ProtocolError("legacy packet must not contain schema")

    session_id = value.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ProtocolError("session_id must be a non-empty string")

    sequence = _legacy_integer(value.get("sequence"), "sequence")
    right = value.get("right")
    if not isinstance(right, dict):
        raise ProtocolError("right must be an object")

    valid = right.get("valid")
    if not isinstance(valid, bool):
        raise ProtocolError("right.valid must be a boolean")

    mode = value.get("command_state")
    if mode is None:
        mode = "active" if valid else "idle"
    if mode not in {"active", "idle", "workspace_exit"}:
        raise ProtocolError("legacy command_state is invalid")
    if mode == "active" and not valid:
        raise ProtocolError("active legacy command requires right.valid=true")
    if mode != "active" and valid:
        raise ProtocolError("inactive legacy command requires right.valid=false")

    if valid:
        position = _legacy_vector(right.get("pos", value.get("pos")), 3, "right.pos")
        quaternion = _legacy_vector(right.get("rot", value.get("rot")), 4, "right.rot")
        try:
            quaternion = normalize_quaternion(quaternion)
        except ValueError as error:
            raise ProtocolError("right.rot is invalid") from error
    else:
        position = np.zeros(3, dtype=float)
        quaternion = np.array([0.0, 0.0, 0.0, 1.0], dtype=float)

    return InternalCommand(
        session_id=session_id.strip(),
        sequence=sequence,
        mode=mode,
        valid=valid,
        position_m=position,
        quaternion_xyzw=quaternion,
        source_time_ns=None,
        frame_id=str(value.get("source", "legacy_controller_target")),
        protocol="legacy_v0",
    )


def parse_v2_command(payload: bytes | str) -> InternalCommand:
    packet = PosePacketV2.from_json(payload)
    valid = (
        packet.mode == "active"
        and packet.armed
        and packet.clutch
        and packet.right_wrist.valid
    )
    return InternalCommand(
        session_id=packet.session_id,
        sequence=packet.sequence,
        mode=packet.mode,
        valid=valid,
        position_m=packet.right_wrist.position_m.copy(),
        quaternion_xyzw=packet.right_wrist.quaternion_xyzw.copy(),
        source_time_ns=packet.source_time_ns,
        frame_id=packet.frame_id,
        protocol="pose_v2",
    )


def parse_command_packet(payload: bytes | str) -> InternalCommand:
    """Parse a packet without silently treating unknown schemas as legacy."""
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("command packet is not valid UTF-8 JSON") from error

    if not isinstance(value, dict):
        raise ProtocolError("command packet must be a JSON object")

    schema = value.get("schema")
    if schema is None:
        return parse_legacy_command(text)
    if schema == POSE_SCHEMA_V2:
        return parse_v2_command(text)
    raise ProtocolError(f"unsupported command schema: {schema}")
