"""Voxelized right-arm workspace projection built from offline MuJoCo samples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


# NPZ workspace samples are stored as float32. Values that are mathematically on
# a voxel boundary (for example -0.20 m at 10 mm resolution) can therefore load
# as -0.20000000298... and floor into the neighboring negative voxel. Apply a
# tiny tolerance in voxel-coordinate space so serialization precision does not
# change occupancy. The tolerance is far smaller than any physical resolution.
_VOXEL_INDEX_EPSILON = 1e-6


@dataclass(frozen=True)
class WorkspaceProjection:
    operator_target: np.ndarray
    feasible_target: np.ndarray
    projected: bool
    distance_m: float


class VoxelWorkspaceMap:
    """Represent collision-free workspace as occupied 3D voxels.

    The map is intentionally dependency-light: NumPy is sufficient for loading
    samples, checking occupancy, and projecting a target to the nearest allowed
    voxel center. Runtime control normally loads both collision-free classes
    (reachable-but-poor and safe) so the map describes physical reachability;
    quality thresholds remain a separate concern.
    """

    def __init__(self, safe_points_m: np.ndarray, *, voxel_size_m: float = 0.01) -> None:
        points = np.asarray(safe_points_m, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0:
            raise ValueError("safe_points_m must be a non-empty Nx3 array")
        if not np.all(np.isfinite(points)):
            raise ValueError("safe_points_m must contain only finite values")
        if not np.isfinite(voxel_size_m) or voxel_size_m <= 0.0:
            raise ValueError("voxel_size_m must be positive")

        self.voxel_size_m = float(voxel_size_m)
        minimum_voxel_index = np.floor(
            points.min(axis=0) / self.voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int64)
        self.origin_m = minimum_voxel_index.astype(float) * self.voxel_size_m
        voxel_indices = np.floor(
            (points - self.origin_m) / self.voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int32)
        self.safe_voxel_indices = np.unique(voxel_indices, axis=0)
        self.safe_voxel_centers_m = (
            self.origin_m
            + (self.safe_voxel_indices.astype(float) + 0.5) * self.voxel_size_m
        )
        self._safe_keys = {
            tuple(int(value) for value in row)
            for row in self.safe_voxel_indices
        }

    @classmethod
    def from_npz(
        cls,
        path: str | Path,
        *,
        voxel_size_m: float = 0.01,
        safe_class: int | None = None,
        allowed_classes: Iterable[int] | None = None,
    ) -> "VoxelWorkspaceMap":
        if safe_class is not None and allowed_classes is not None:
            raise ValueError("use either safe_class or allowed_classes, not both")

        if allowed_classes is None:
            classes = (2 if safe_class is None else int(safe_class),)
        else:
            classes = tuple(sorted({int(value) for value in allowed_classes}))
            if not classes:
                raise ValueError("allowed_classes must not be empty")

        with np.load(Path(path), allow_pickle=False) as workspace:
            positions = np.asarray(workspace["positions_m"], dtype=float)
            classification = np.asarray(workspace["classification"], dtype=np.uint8)
        if positions.shape[0] != classification.shape[0]:
            raise ValueError("workspace positions and classification lengths differ")

        allowed_mask = np.isin(classification, np.asarray(classes, dtype=np.uint8))
        safe_points = positions[allowed_mask]
        if len(safe_points) == 0:
            raise ValueError("workspace contains no samples in the requested classes")
        return cls(safe_points, voxel_size_m=voxel_size_m)

    def point_to_index(self, point_m: np.ndarray) -> tuple[int, int, int]:
        point = np.asarray(point_m, dtype=float)
        if point.shape != (3,) or not np.all(np.isfinite(point)):
            raise ValueError("point_m must be a finite 3-vector")
        index = np.floor(
            (point - self.origin_m) / self.voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int32)
        return tuple(int(value) for value in index)

    def contains_safe(self, point_m: np.ndarray) -> bool:
        return self.point_to_index(point_m) in self._safe_keys

    def nearest_safe_point(self, point_m: np.ndarray) -> np.ndarray:
        point = np.asarray(point_m, dtype=float)
        if point.shape != (3,) or not np.all(np.isfinite(point)):
            raise ValueError("point_m must be a finite 3-vector")
        if self.contains_safe(point):
            return point.copy()
        delta = self.safe_voxel_centers_m - point
        nearest_index = int(np.argmin(np.einsum("ij,ij->i", delta, delta)))
        return self.safe_voxel_centers_m[nearest_index].copy()

    def project(self, operator_target_m: np.ndarray) -> WorkspaceProjection:
        operator_target = np.asarray(operator_target_m, dtype=float)
        feasible_target = self.nearest_safe_point(operator_target)
        distance_m = float(np.linalg.norm(feasible_target - operator_target))
        return WorkspaceProjection(
            operator_target=operator_target.copy(),
            feasible_target=feasible_target,
            projected=distance_m > 1e-9,
            distance_m=distance_m,
        )


class WorkspaceTargetProjector:
    """Keep operator intent separate from the robot's feasible target."""

    def __init__(self, workspace: VoxelWorkspaceMap) -> None:
        self.workspace = workspace
        self.operator_target: np.ndarray | None = None
        self.feasible_target: np.ndarray | None = None
        self.projection_distance_m = 0.0
        self.workspace_limited = False

    def update(self, operator_target_m: np.ndarray) -> WorkspaceProjection:
        projection = self.workspace.project(operator_target_m)
        self.operator_target = projection.operator_target.copy()
        self.feasible_target = projection.feasible_target.copy()
        self.projection_distance_m = projection.distance_m
        self.workspace_limited = projection.projected
        return projection
