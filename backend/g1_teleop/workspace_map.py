"""Voxelized right-arm workspace projection built from offline MuJoCo samples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


# NPZ workspace samples are stored as float32. Values that are mathematically on
# a voxel boundary can load a few nanometers across that boundary. Keep indexing
# stable without changing any physical workspace dimension.
_VOXEL_INDEX_EPSILON = 1e-6
_NEIGHBOR_OFFSETS = np.array(
    [
        [dx, dy, dz]
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if not (dx == 0 and dy == 0 and dz == 0)
    ],
    dtype=np.int32,
)


@dataclass(frozen=True)
class WorkspaceProjection:
    operator_target: np.ndarray
    feasible_target: np.ndarray
    projected: bool
    distance_m: float


class VoxelWorkspaceMap:
    """Represent collision-free workspace as occupied 3D voxels.

    Runtime projection is deliberately local and directional: when an operator
    target leaves the sampled workspace, motion advances from the current safe
    point toward the requested target until the boundary is reached, then walks
    neighboring safe voxels that continue reducing target distance. This avoids
    teleporting to an unrelated globally-nearest voxel.
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
        dilation_voxels: int = 0,
    ) -> "VoxelWorkspaceMap":
        if safe_class is not None and allowed_classes is not None:
            raise ValueError("use either safe_class or allowed_classes, not both")
        if isinstance(dilation_voxels, bool) or not isinstance(dilation_voxels, int):
            raise ValueError("dilation_voxels must be an integer")
        if dilation_voxels < 0:
            raise ValueError("dilation_voxels must be >= 0")

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
        if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
            raise ValueError("workspace positions must be a non-empty Nx3 array")

        global_min_index = np.floor(
            positions.min(axis=0) / voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int64)
        global_origin = global_min_index.astype(float) * voxel_size_m
        all_indices = np.floor(
            (positions - global_origin) / voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int32)

        allowed_mask = np.isin(classification, np.asarray(classes, dtype=np.uint8))
        allowed_keys = {
            tuple(int(value) for value in row)
            for row in all_indices[allowed_mask]
        }
        # A voxel with an observed collision sample is never introduced by the
        # sampling-gap dilation, even if a nearby collision-free sample exists.
        forbidden_keys = {
            tuple(int(value) for value in row)
            for row in all_indices[classification == 0]
        }
        allowed_keys.difference_update(forbidden_keys)
        if not allowed_keys:
            raise ValueError("workspace contains no samples in the requested classes")

        if dilation_voxels:
            frontier = set(allowed_keys)
            expanded = set(allowed_keys)
            for _ in range(dilation_voxels):
                next_frontier: set[tuple[int, int, int]] = set()
                for key in frontier:
                    base_index = np.asarray(key, dtype=np.int32)
                    for offset in _NEIGHBOR_OFFSETS:
                        candidate = tuple(int(value) for value in base_index + offset)
                        if candidate in forbidden_keys or candidate in expanded:
                            continue
                        expanded.add(candidate)
                        next_frontier.add(candidate)
                frontier = next_frontier
                if not frontier:
                    break
            allowed_keys = expanded

        allowed_indices = np.asarray(sorted(allowed_keys), dtype=np.int32)
        safe_points = (
            global_origin
            + (allowed_indices.astype(float) + 0.5) * float(voxel_size_m)
        )
        return cls(safe_points, voxel_size_m=voxel_size_m)

    def point_to_index(self, point_m: np.ndarray) -> tuple[int, int, int]:
        point = np.asarray(point_m, dtype=float)
        if point.shape != (3,) or not np.all(np.isfinite(point)):
            raise ValueError("point_m must be a finite 3-vector")
        index = np.floor(
            (point - self.origin_m) / self.voxel_size_m + _VOXEL_INDEX_EPSILON
        ).astype(np.int32)
        return tuple(int(value) for value in index)

    def index_to_center(self, index: tuple[int, int, int]) -> np.ndarray:
        values = np.asarray(index, dtype=float)
        return self.origin_m + (values + 0.5) * self.voxel_size_m

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
        """Stateless fallback projection used for initial anchoring."""
        operator_target = np.asarray(operator_target_m, dtype=float)
        feasible_target = self.nearest_safe_point(operator_target)
        distance_m = float(np.linalg.norm(feasible_target - operator_target))
        return WorkspaceProjection(
            operator_target=operator_target.copy(),
            feasible_target=feasible_target,
            projected=distance_m > 1e-9,
            distance_m=distance_m,
        )

    def project_from(
        self,
        safe_start_m: np.ndarray,
        operator_target_m: np.ndarray,
        *,
        max_boundary_steps: int = 128,
    ) -> WorkspaceProjection:
        """Project locally from a safe anchor while preserving motion direction.

        The direct segment is sampled at half-voxel spacing until occupancy ends.
        If blocked, a local 26-neighbor hill climb follows the safe boundary only
        while each move reduces Euclidean distance to the operator target.
        """
        start = np.asarray(safe_start_m, dtype=float)
        target = np.asarray(operator_target_m, dtype=float)
        if start.shape != (3,) or target.shape != (3,):
            raise ValueError("safe_start_m and operator_target_m must be 3-vectors")
        if not np.all(np.isfinite(start)) or not np.all(np.isfinite(target)):
            raise ValueError("workspace projection points must be finite")
        if isinstance(max_boundary_steps, bool) or not isinstance(max_boundary_steps, int):
            raise ValueError("max_boundary_steps must be an integer")
        if max_boundary_steps < 0:
            raise ValueError("max_boundary_steps must be >= 0")

        if self.contains_safe(target):
            feasible = target.copy()
            return WorkspaceProjection(target.copy(), feasible, False, 0.0)

        if not self.contains_safe(start):
            start = self.nearest_safe_point(start)

        delta = target - start
        distance = float(np.linalg.norm(delta))
        last_safe = start.copy()
        if distance > 1e-12:
            sample_spacing = 0.5 * self.voxel_size_m
            sample_count = max(1, int(np.ceil(distance / sample_spacing)))
            for step_index in range(1, sample_count + 1):
                alpha = step_index / sample_count
                candidate = start + alpha * delta
                if not self.contains_safe(candidate):
                    break
                last_safe = candidate

        current_key = self.point_to_index(last_safe)
        current_distance_sq = float(np.dot(target - last_safe, target - last_safe))
        visited = {current_key}
        moved_on_boundary = False
        for _ in range(max_boundary_steps):
            best_key = None
            best_distance_sq = current_distance_sq
            current_index = np.asarray(current_key, dtype=np.int32)
            for offset in _NEIGHBOR_OFFSETS:
                candidate_key = tuple(int(value) for value in current_index + offset)
                if candidate_key in visited or candidate_key not in self._safe_keys:
                    continue
                center = self.index_to_center(candidate_key)
                candidate_distance_sq = float(np.dot(target - center, target - center))
                if candidate_distance_sq + 1e-12 < best_distance_sq:
                    best_key = candidate_key
                    best_distance_sq = candidate_distance_sq
            if best_key is None:
                break
            current_key = best_key
            visited.add(current_key)
            current_distance_sq = best_distance_sq
            moved_on_boundary = True

        feasible = self.index_to_center(current_key) if moved_on_boundary else last_safe
        projection_distance = float(np.linalg.norm(feasible - target))
        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=feasible.copy(),
            projected=projection_distance > 1e-9,
            distance_m=projection_distance,
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
        if self.feasible_target is None:
            projection = self.workspace.project(operator_target_m)
        else:
            projection = self.workspace.project_from(
                self.feasible_target,
                operator_target_m,
            )
        self.operator_target = projection.operator_target.copy()
        self.feasible_target = projection.feasible_target.copy()
        self.projection_distance_m = projection.distance_m
        self.workspace_limited = projection.projected
        return projection
