"""Versioned JSON contracts shared by Unity, MuJoCo, and the physical G1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from .transforms import make_pose, normalize_quaternion, split_pose


POSE_SCHEMA = "g1.teleop.pose.v1"
STATE_SCHEMA = "g1.teleop.state.v1"
POSE_FRAME = "unity_ovr_tracking"


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


def tracked_pose_from_matrix(valid: bool, confidence: str, pose: np.ndarray) -> TrackedPoseV1:
    position, quaternion = split_pose(pose)
    return TrackedPoseV1(valid, confidence, position, quaternion)
