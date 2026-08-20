"""Session and user calibration for location-independent G1 teleoperation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .transforms import average_quaternions, make_pose, split_pose


CALIBRATION_SCHEMA = "g1.teleop.calibration.v1"


def _pose_matrix(value: np.ndarray, field_name: str) -> np.ndarray:
    pose = np.asarray(value, dtype=float)
    if pose.shape != (4, 4) or not np.all(np.isfinite(pose)):
        raise ValueError(f"{field_name} must be a finite 4x4 pose")
    if not np.allclose(pose[3], [0.0, 0.0, 0.0, 1.0], atol=1e-7):
        raise ValueError(f"{field_name} has an invalid homogeneous row")
    return pose.copy()


def _scale_vector(value: float | Iterable[float]) -> np.ndarray:
    scale = np.asarray(value, dtype=float)
    if scale.ndim == 0:
        scale = np.repeat(scale, 3)
    if scale.shape != (3,) or not np.all(np.isfinite(scale)) or np.any(scale <= 0.0):
        raise ValueError("translation_scale must contain three positive finite values")
    return scale


def _pose_to_dict(pose: np.ndarray) -> dict[str, list[float]]:
    position, quaternion = split_pose(pose)
    return {
        "position_m": position.tolist(),
        "quaternion_xyzw": quaternion.tolist(),
    }


def _pose_from_dict(value: object, field_name: str) -> np.ndarray:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    try:
        position = np.asarray(value["position_m"], dtype=float)
        quaternion = np.asarray(value["quaternion_xyzw"], dtype=float)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} is malformed") from error
    if position.shape != (3,) or not np.all(np.isfinite(position)):
        raise ValueError(f"{field_name}.position_m is invalid")
    return make_pose(position, quaternion)


@dataclass(frozen=True)
class ArmCalibration:
    """Maps a human wrist pose delta onto a robot wrist neutral pose."""

    source_neutral: np.ndarray
    robot_neutral: np.ndarray
    translation_scale: np.ndarray

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_neutral", _pose_matrix(self.source_neutral, "source_neutral"))
        object.__setattr__(self, "robot_neutral", _pose_matrix(self.robot_neutral, "robot_neutral"))
        object.__setattr__(self, "translation_scale", _scale_vector(self.translation_scale))

    def map_pose(self, source_pose: np.ndarray) -> np.ndarray:
        """Map the current source wrist pose while preserving the calibrated neutral."""
        source = _pose_matrix(source_pose, "source_pose")
        target = np.eye(4, dtype=float)
        source_delta = source[:3, 3] - self.source_neutral[:3, 3]
        target[:3, 3] = self.robot_neutral[:3, 3] + self.translation_scale * source_delta
        target[:3, :3] = (
            self.robot_neutral[:3, :3]
            @ self.source_neutral[:3, :3].T
            @ source[:3, :3]
        )
        return target

    def with_scale(self, translation_scale: float | Iterable[float]) -> "ArmCalibration":
        return ArmCalibration(self.source_neutral, self.robot_neutral, _scale_vector(translation_scale))

    def to_dict(self) -> dict[str, object]:
        return {
            "source_neutral": _pose_to_dict(self.source_neutral),
            "robot_neutral": _pose_to_dict(self.robot_neutral),
            "translation_scale": self.translation_scale.tolist(),
        }

    @classmethod
    def from_dict(cls, value: object, field_name: str) -> "ArmCalibration":
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be an object")
        return cls(
            _pose_from_dict(value.get("source_neutral"), f"{field_name}.source_neutral"),
            _pose_from_dict(value.get("robot_neutral"), f"{field_name}.robot_neutral"),
            _scale_vector(value.get("translation_scale", 1.0)),
        )


@dataclass(frozen=True)
class CalibrationProfile:
    """Per-session neutral anchors plus a reusable user movement scale."""

    right: ArmCalibration | None
    left: ArmCalibration | None
    created_time_ns: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": CALIBRATION_SCHEMA,
            "created_time_ns": int(self.created_time_ns),
            "right": None if self.right is None else self.right.to_dict(),
            "left": None if self.left is None else self.left.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str | bytes) -> "CalibrationProfile":
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        value = json.loads(payload)
        if not isinstance(value, dict) or value.get("schema") != CALIBRATION_SCHEMA:
            raise ValueError(f"schema must be {CALIBRATION_SCHEMA}")
        right_value = value.get("right")
        left_value = value.get("left")
        return cls(
            None if right_value is None else ArmCalibration.from_dict(right_value, "right"),
            None if left_value is None else ArmCalibration.from_dict(left_value, "left"),
            int(value["created_time_ns"]),
        )

    def save(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationProfile":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def _average_pose(poses: list[np.ndarray]) -> np.ndarray:
    positions = []
    quaternions = []
    for pose in poses:
        position, quaternion = split_pose(pose)
        positions.append(position)
        quaternions.append(quaternion)
    return make_pose(np.mean(positions, axis=0), average_quaternions(np.asarray(quaternions)))


def _rotation_angle(rotation: np.ndarray) -> float:
    cosine = np.clip((np.trace(rotation) - 1.0) * 0.5, -1.0, 1.0)
    return float(np.arccos(cosine))


def _stability_metrics(poses: list[np.ndarray]) -> tuple[float, float]:
    average = _average_pose(poses)
    positions = np.asarray([pose[:3, 3] for pose in poses])
    position_rms = float(np.sqrt(np.mean(np.sum((positions - average[:3, 3]) ** 2, axis=1))))
    angles = [
        _rotation_angle(average[:3, :3].T @ pose[:3, :3])
        for pose in poses
    ]
    orientation_rms = float(np.sqrt(np.mean(np.square(angles))))
    return position_rms, orientation_rms


class NeutralCalibrationAccumulator:
    """Collect stable human and actual-robot poses before creating anchors."""

    def __init__(
        self,
        minimum_samples: int = 45,
        maximum_position_rms_m: float = 0.008,
        maximum_orientation_rms_rad: float = np.deg2rad(4.0),
    ) -> None:
        if minimum_samples < 2:
            raise ValueError("minimum_samples must be at least two")
        self.minimum_samples = minimum_samples
        self.maximum_position_rms_m = maximum_position_rms_m
        self.maximum_orientation_rms_rad = maximum_orientation_rms_rad
        self._human_right: list[np.ndarray] = []
        self._robot_right: list[np.ndarray] = []
        self._human_left: list[np.ndarray] = []
        self._robot_left: list[np.ndarray] = []

    @property
    def sample_count(self) -> int:
        counts = [len(self._human_right), len(self._robot_right)]
        if self._human_left or self._robot_left:
            counts.extend([len(self._human_left), len(self._robot_left)])
        return min(counts, default=0)

    def clear(self) -> None:
        self._human_right.clear()
        self._robot_right.clear()
        self._human_left.clear()
        self._robot_left.clear()

    def add_sample(
        self,
        human_right: np.ndarray,
        robot_right: np.ndarray,
        human_left: np.ndarray | None = None,
        robot_left: np.ndarray | None = None,
    ) -> None:
        if (human_left is None) != (robot_left is None):
            raise ValueError("human_left and robot_left must be provided together")
        self._human_right.append(_pose_matrix(human_right, "human_right"))
        self._robot_right.append(_pose_matrix(robot_right, "robot_right"))
        if human_left is not None and robot_left is not None:
            self._human_left.append(_pose_matrix(human_left, "human_left"))
            self._robot_left.append(_pose_matrix(robot_left, "robot_left"))

    def _check_stability(self, poses: list[np.ndarray], field_name: str) -> None:
        position_rms, orientation_rms = _stability_metrics(poses)
        if position_rms > self.maximum_position_rms_m:
            raise ValueError(
                f"{field_name} moved during calibration: position RMS {position_rms:.4f} m"
            )
        if orientation_rms > self.maximum_orientation_rms_rad:
            raise ValueError(
                f"{field_name} rotated during calibration: orientation RMS "
                f"{np.rad2deg(orientation_rms):.2f} deg"
            )

    def build_profile(
        self,
        translation_scale: float | Iterable[float] = 1.0,
        created_time_ns: int | None = None,
    ) -> CalibrationProfile:
        if self.sample_count < self.minimum_samples:
            raise ValueError(
                f"need at least {self.minimum_samples} stable samples; got {self.sample_count}"
            )

        sample_groups = [
            (self._human_right, "human_right"),
            (self._robot_right, "robot_right"),
        ]
        if self._human_left:
            sample_groups.extend(
                [
                    (self._human_left, "human_left"),
                    (self._robot_left, "robot_left"),
                ]
            )
        for poses, field_name in sample_groups:
            self._check_stability(poses, field_name)

        scale = _scale_vector(translation_scale)
        right = ArmCalibration(_average_pose(self._human_right), _average_pose(self._robot_right), scale)
        left = None
        if self._human_left:
            left = ArmCalibration(_average_pose(self._human_left), _average_pose(self._robot_left), scale)
        timestamp = time.time_ns() if created_time_ns is None else created_time_ns
        return CalibrationProfile(right, left, timestamp)


class WorkspaceScaleEstimator:
    """Estimate a conservative user scale from deliberate workspace motion."""

    def __init__(self) -> None:
        self._positions: list[np.ndarray] = []

    def add_position(self, position_m: Iterable[float]) -> None:
        position = np.asarray(position_m, dtype=float)
        if position.shape != (3,) or not np.all(np.isfinite(position)):
            raise ValueError("position_m must contain three finite values")
        self._positions.append(position)

    @property
    def sample_count(self) -> int:
        return len(self._positions)

    def estimate_safe_isotropic_scale(
        self,
        robot_safe_span_m: Iterable[float],
        coverage: float = 0.80,
        percentile_range: tuple[float, float] = (5.0, 95.0),
        minimum_user_span_m: float = 0.08,
        scale_bounds: tuple[float, float] = (0.20, 1.50),
    ) -> float:
        if len(self._positions) < 30:
            raise ValueError("at least 30 workspace samples are required")
        if not 0.0 < coverage <= 1.0:
            raise ValueError("coverage must be in (0, 1]")

        robot_span = np.asarray(robot_safe_span_m, dtype=float)
        if robot_span.shape != (3,) or np.any(robot_span <= 0.0):
            raise ValueError("robot_safe_span_m must contain three positive values")

        lower_percentile, upper_percentile = percentile_range
        if not 0.0 <= lower_percentile < upper_percentile <= 100.0:
            raise ValueError("percentile_range is invalid")

        samples = np.asarray(self._positions)
        user_lower = np.percentile(samples, lower_percentile, axis=0)
        user_upper = np.percentile(samples, upper_percentile, axis=0)
        user_span = user_upper - user_lower
        active_axes = user_span >= minimum_user_span_m
        if np.count_nonzero(active_axes) < 2:
            raise ValueError("workspace motion did not cover at least two axes")

        candidates = coverage * robot_span[active_axes] / user_span[active_axes]
        raw_scale = float(np.min(candidates))
        return float(np.clip(raw_scale, scale_bounds[0], scale_bounds[1]))


@dataclass(frozen=True)
class RigidRegistrationResult:
    transform: np.ndarray
    rms_error_m: float
    maximum_error_m: float


def estimate_rigid_registration(
    source_points_m: Iterable[Iterable[float]],
    target_points_m: Iterable[Iterable[float]],
) -> RigidRegistrationResult:
    """Estimate target_from_source with Kabsch; intended only for visual overlay."""
    source = np.asarray(source_points_m, dtype=float)
    target = np.asarray(target_points_m, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3:
        raise ValueError("source and target points must both have shape (N, 3)")
    if len(source) < 3 or not np.all(np.isfinite(source)) or not np.all(np.isfinite(target)):
        raise ValueError("at least three finite point pairs are required")

    source_centered = source - np.mean(source, axis=0)
    target_centered = target - np.mean(target, axis=0)
    if np.linalg.matrix_rank(source_centered) < 2:
        raise ValueError("registration points are collinear")

    covariance = source_centered.T @ target_centered
    left_vectors, _, right_vectors_t = np.linalg.svd(covariance)
    rotation = right_vectors_t.T @ left_vectors.T
    if np.linalg.det(rotation) < 0.0:
        right_vectors_t[-1] *= -1.0
        rotation = right_vectors_t.T @ left_vectors.T

    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
    translation = target_center - rotation @ source_center
    transform = np.eye(4, dtype=float)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation

    transformed = (rotation @ source.T).T + translation
    errors = np.linalg.norm(transformed - target, axis=1)
    return RigidRegistrationResult(
        transform=transform,
        rms_error_m=float(np.sqrt(np.mean(errors**2))),
        maximum_error_m=float(np.max(errors)),
    )
