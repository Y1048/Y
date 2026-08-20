"""Versioned JSON contracts shared by Unity, MuJoCo, and the physical G1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from .transforms import make_pose, normalize_quaternion, split_pose


POSE_SCHEMA = "g1.teleop.pose.v1"
STATE_SCHEMA = "g1.teleop.state.v1"
POSE_SCHEMA_V2 = "g1.teleop.pose.v2"
STATE_SCHEMA_V2 = "g1.teleop.state.v2"
POSE_FRAME = "unity_ovr_tracking"
CONTROL_MODES_V2 = {"idle", "active", "hold", "workspace_exit", "shutdown"}


class ProtocolError(ValueError):
    pass


def _boolean(value: Any, field_name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ProtocolError(f"{field_name} must be a boolean")
    return value


def _finite_vector(value: Any, length: int, field_name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise ProtocolError(f"{field_name} must be numeric") from error
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ProtocolError(f"{field_name} must contain {length} finite values")
    return result


def _integer(value: Any, field_name: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError(f"{field_name} must be an integer")
    if value < minimum:
        raise ProtocolError(f"{field_name} must be >= {minimum}")
    return value


def _nonempty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{field_name} must be a non-empty string")
    return value.strip()


def _json_object(payload: bytes | str, label: str = "packet") -> dict[str, Any]:
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ProtocolError(f"{label} must be a JSON object")
    return value


@dataclass(frozen=True)
class TrackedPoseV1:
    valid: bool
    confidence: str
    position_m: np.ndarray
    quaternion_xyzw: np.ndarray

    @classmethod
    def from_dict(cls, value: dict[str, Any], field_name: str) -> "TrackedPoseV1":
        if not isinstance(value, dict):
            raise ProtocolError(f"{field_name} must be an object")
        position = _finite_vector(value.get("position_m"), 3, f"{field_name}.position_m")
        quaternion = _finite_vector(value.get("quaternion_xyzw"), 4, f"{field_name}.quaternion_xyzw")
        try:
            quaternion = normalize_quaternion(quaternion)
        except ValueError as error:
            raise ProtocolError(f"{field_name}.quaternion_xyzw is invalid") from error
        confidence = str(value.get("confidence", "unknown")).lower()
        if confidence not in {"high", "medium", "low", "unknown"}:
            raise ProtocolError(f"{field_name}.confidence is invalid")
        return cls(
            _boolean(value.get("valid"), f"{field_name}.valid"),
            confidence,
            position,
            quaternion,
        )

    @property
    def pose(self) -> np.ndarray:
        return make_pose(self.position_m, self.quaternion_xyzw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "confidence": self.confidence,
            "position_m": self.position_m.tolist(),
            "quaternion_xyzw": self.quaternion_xyzw.tolist(),
        }


@dataclass(frozen=True)
class PosePacketV1:
    sequence: int
    source_time_ns: int
    armed: bool
    clutch: bool
    calibration_request: int
    head: TrackedPoseV1
    right_wrist: TrackedPoseV1
    left_wrist: TrackedPoseV1
    frame_id: str = POSE_FRAME

    @classmethod
    def from_json(cls, payload: bytes | str) -> "PosePacketV1":
        try:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtocolError("packet is not valid UTF-8 JSON") from error

        if not isinstance(value, dict) or value.get("schema") != POSE_SCHEMA:
            raise ProtocolError(f"schema must be {POSE_SCHEMA}")
        if value.get("frame_id") != POSE_FRAME:
            raise ProtocolError(f"frame_id must be {POSE_FRAME}")

        try:
            sequence = int(value["sequence"])
            source_time_ns = int(value["source_time_ns"])
            calibration_request = int(value.get("calibration_request", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise ProtocolError("sequence and source_time_ns must be integers") from error
        if sequence < 0 or source_time_ns < 0 or calibration_request < 0:
            raise ProtocolError("sequence, source_time_ns, and calibration_request must be non-negative")

        return cls(
            sequence=sequence,
            source_time_ns=source_time_ns,
            armed=_boolean(value.get("armed"), "armed"),
            clutch=_boolean(value.get("clutch"), "clutch"),
            calibration_request=calibration_request,
            head=TrackedPoseV1.from_dict(value.get("head"), "head"),
            right_wrist=TrackedPoseV1.from_dict(value.get("right_wrist"), "right_wrist"),
            left_wrist=TrackedPoseV1.from_dict(value.get("left_wrist"), "left_wrist"),
        )

    def to_json(self) -> str:
        value = {
            "schema": POSE_SCHEMA,
            "sequence": self.sequence,
            "source_time_ns": self.source_time_ns,
            "frame_id": self.frame_id,
            "armed": self.armed,
            "clutch": self.clutch,
            "calibration_request": self.calibration_request,
            "head": self.head.to_dict(),
            "right_wrist": self.right_wrist.to_dict(),
            "left_wrist": self.left_wrist.to_dict(),
        }
        return json.dumps(value, separators=(",", ":"))


@dataclass(frozen=True)
class StatePacketV1:
    sequence: int
    robot_time_ns: int
    acknowledged_source_sequence: int
    mode: str
    armed: bool
    watchdog: str
    ik_status: str
    calibration_status: str
    right_arm_q_rad: np.ndarray
    left_arm_q_rad: np.ndarray

    @classmethod
    def from_json(cls, payload: bytes | str) -> "StatePacketV1":
        try:
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtocolError("state packet is not valid UTF-8 JSON") from error
        if not isinstance(value, dict) or value.get("schema") != STATE_SCHEMA:
            raise ProtocolError(f"schema must be {STATE_SCHEMA}")

        try:
            sequence = int(value["sequence"])
            robot_time_ns = int(value["robot_time_ns"])
            acknowledged = int(value.get("acknowledged_source_sequence", -1))
        except (KeyError, TypeError, ValueError) as error:
            raise ProtocolError("state sequence fields must be integers") from error
        if sequence < 0 or robot_time_ns < 0 or acknowledged < -1:
            raise ProtocolError("state sequence fields are out of range")

        return cls(
            sequence=sequence,
            robot_time_ns=robot_time_ns,
            acknowledged_source_sequence=acknowledged,
            mode=str(value.get("mode", "unknown")),
            armed=_boolean(value.get("armed"), "armed"),
            watchdog=str(value.get("watchdog", "unknown")),
            ik_status=str(value.get("ik_status", "unknown")),
            calibration_status=str(value.get("calibration_status", "unknown")),
            right_arm_q_rad=_finite_vector(value.get("right_arm_q_rad"), 7, "right_arm_q_rad"),
            left_arm_q_rad=_finite_vector(value.get("left_arm_q_rad"), 7, "left_arm_q_rad"),
        )

    def to_json(self) -> str:
        value = {
            "schema": STATE_SCHEMA,
            "sequence": self.sequence,
            "robot_time_ns": self.robot_time_ns,
            "acknowledged_source_sequence": self.acknowledged_source_sequence,
            "mode": self.mode,
            "armed": self.armed,
            "watchdog": self.watchdog,
            "ik_status": self.ik_status,
            "calibration_status": self.calibration_status,
            "right_arm_q_rad": self.right_arm_q_rad.tolist(),
            "left_arm_q_rad": self.left_arm_q_rad.tolist(),
        }
        return json.dumps(value, separators=(",", ":"))


@dataclass(frozen=True)
class PosePacketV2:
    session_id: str
    sequence: int
    source_time_ns: int
    mode: str
    armed: bool
    clutch: bool
    calibration_request: int
    head: TrackedPoseV1
    right_wrist: TrackedPoseV1
    left_wrist: TrackedPoseV1
    frame_id: str = POSE_FRAME

    @classmethod
    def from_json(cls, payload: bytes | str) -> "PosePacketV2":
        value = _json_object(payload)
        if value.get("schema") != POSE_SCHEMA_V2:
            raise ProtocolError(f"schema must be {POSE_SCHEMA_V2}")
        if value.get("frame_id") != POSE_FRAME:
            raise ProtocolError(f"frame_id must be {POSE_FRAME}")

        mode = value.get("mode")
        if mode not in CONTROL_MODES_V2:
            raise ProtocolError(f"mode must be one of {sorted(CONTROL_MODES_V2)}")

        packet = cls(
            session_id=_nonempty_string(value.get("session_id"), "session_id"),
            sequence=_integer(value.get("sequence"), "sequence"),
            source_time_ns=_integer(value.get("source_time_ns"), "source_time_ns"),
            mode=mode,
            armed=_boolean(value.get("armed"), "armed"),
            clutch=_boolean(value.get("clutch"), "clutch"),
            calibration_request=_integer(value.get("calibration_request", 0), "calibration_request"),
            head=TrackedPoseV1.from_dict(value.get("head"), "head"),
            right_wrist=TrackedPoseV1.from_dict(value.get("right_wrist"), "right_wrist"),
            left_wrist=TrackedPoseV1.from_dict(value.get("left_wrist"), "left_wrist"),
        )
        if packet.mode == "active" and not packet.right_wrist.valid:
            raise ProtocolError("active mode requires a valid right_wrist pose")
        return packet

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": POSE_SCHEMA_V2,
                "session_id": self.session_id,
                "sequence": self.sequence,
                "source_time_ns": self.source_time_ns,
                "frame_id": self.frame_id,
                "mode": self.mode,
                "armed": self.armed,
                "clutch": self.clutch,
                "calibration_request": self.calibration_request,
                "head": self.head.to_dict(),
                "right_wrist": self.right_wrist.to_dict(),
                "left_wrist": self.left_wrist.to_dict(),
            },
            separators=(",", ":"),
        )


@dataclass(frozen=True)
class StatePacketV2:
    sequence: int
    robot_time_ns: int
    active_session_id: str
    acknowledged_source_sequence: int
    mode: str
    armed: bool
    watchdog: str
    ik_status: str
    calibration_status: str
    workspace_status: str
    collision_limited: bool
    position_error_m: float
    right_arm_q_rad: np.ndarray
    left_arm_q_rad: np.ndarray

    @classmethod
    def from_json(cls, payload: bytes | str) -> "StatePacketV2":
        value = _json_object(payload, "state packet")
        if value.get("schema") != STATE_SCHEMA_V2:
            raise ProtocolError(f"schema must be {STATE_SCHEMA_V2}")
        mode = value.get("mode")
        if mode not in CONTROL_MODES_V2:
            raise ProtocolError(f"mode must be one of {sorted(CONTROL_MODES_V2)}")
        try:
            position_error_m = float(value.get("position_error_m"))
        except (TypeError, ValueError) as error:
            raise ProtocolError("position_error_m must be numeric") from error
        if not np.isfinite(position_error_m) or position_error_m < 0.0:
            raise ProtocolError("position_error_m must be a non-negative finite value")

        acknowledged = value.get("acknowledged_source_sequence")
        if not isinstance(acknowledged, int) or isinstance(acknowledged, bool) or acknowledged < -1:
            raise ProtocolError("acknowledged_source_sequence must be an integer >= -1")

        return cls(
            sequence=_integer(value.get("sequence"), "sequence"),
            robot_time_ns=_integer(value.get("robot_time_ns"), "robot_time_ns"),
            active_session_id=_nonempty_string(value.get("active_session_id"), "active_session_id"),
            acknowledged_source_sequence=acknowledged,
            mode=mode,
            armed=_boolean(value.get("armed"), "armed"),
            watchdog=_nonempty_string(value.get("watchdog"), "watchdog"),
            ik_status=_nonempty_string(value.get("ik_status"), "ik_status"),
            calibration_status=_nonempty_string(value.get("calibration_status"), "calibration_status"),
            workspace_status=_nonempty_string(value.get("workspace_status"), "workspace_status"),
            collision_limited=_boolean(value.get("collision_limited"), "collision_limited"),
            position_error_m=position_error_m,
            right_arm_q_rad=_finite_vector(value.get("right_arm_q_rad"), 7, "right_arm_q_rad"),
            left_arm_q_rad=_finite_vector(value.get("left_arm_q_rad"), 7, "left_arm_q_rad"),
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": STATE_SCHEMA_V2,
                "sequence": self.sequence,
                "robot_time_ns": self.robot_time_ns,
                "active_session_id": self.active_session_id,
                "acknowledged_source_sequence": self.acknowledged_source_sequence,
                "mode": self.mode,
                "armed": self.armed,
                "watchdog": self.watchdog,
                "ik_status": self.ik_status,
                "calibration_status": self.calibration_status,
                "workspace_status": self.workspace_status,
                "collision_limited": self.collision_limited,
                "position_error_m": self.position_error_m,
                "right_arm_q_rad": self.right_arm_q_rad.tolist(),
                "left_arm_q_rad": self.left_arm_q_rad.tolist(),
            },
            separators=(",", ":"),
        )


def tracked_pose_from_matrix(valid: bool, confidence: str, pose: np.ndarray) -> TrackedPoseV1:
    position, quaternion = split_pose(pose)
    return TrackedPoseV1(valid, confidence, position, quaternion)
