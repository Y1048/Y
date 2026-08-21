from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.workspace_map import VoxelWorkspaceMap, WorkspaceTargetProjector  # noqa: E402


class WorkspaceMapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.points = np.array(
            [
                [0.00, -0.20, 1.00],
                [0.01, -0.20, 1.00],
                [0.02, -0.20, 1.00],
            ],
            dtype=float,
        )
        self.workspace = VoxelWorkspaceMap(self.points, voxel_size_m=0.01)

    def test_safe_voxel_contains_original_point(self):
        self.assertTrue(self.workspace.contains_safe(np.array([0.001, -0.199, 1.001])))

    def test_projection_preserves_target_inside_safe_voxel(self):
        target = np.array([0.001, -0.199, 1.001])
        projection = self.workspace.project(target)
        np.testing.assert_allclose(projection.operator_target, target)
        np.testing.assert_allclose(projection.feasible_target, target)
        self.assertFalse(projection.projected)
        self.assertAlmostEqual(projection.distance_m, 0.0)

    def test_projection_moves_outside_target_to_safe_voxel(self):
        target = np.array([0.20, -0.20, 1.00])
        projection = self.workspace.project(target)
        np.testing.assert_allclose(projection.operator_target, target)
        self.assertTrue(self.workspace.contains_safe(projection.feasible_target))
        self.assertTrue(projection.projected)
        self.assertGreater(projection.distance_m, 0.0)

    def test_target_projector_keeps_operator_and_feasible_targets_separate(self):
        projector = WorkspaceTargetProjector(self.workspace)
        projector.update(np.array([0.001, -0.199, 1.001]))
        target = np.array([0.20, -0.20, 1.00])
        projection = projector.update(target)
        np.testing.assert_allclose(projector.operator_target, target)
        np.testing.assert_allclose(projector.feasible_target, projection.feasible_target)
        self.assertTrue(projector.workspace_limited)
        self.assertGreater(projector.projection_distance_m, 0.0)

    def test_directional_projection_advances_from_current_safe_anchor(self):
        workspace = VoxelWorkspaceMap(
            np.array(
                [
                    [0.00, 0.00, 0.00],
                    [0.01, 0.00, 0.00],
                    [0.02, 0.00, 0.00],
                ],
                dtype=float,
            ),
            voxel_size_m=0.01,
        )
        start = np.array([0.001, 0.001, 0.001])
        target = np.array([0.08, 0.001, 0.001])
        projection = workspace.project_from(start, target)
        self.assertTrue(workspace.contains_safe(projection.feasible_target))
        self.assertGreater(projection.feasible_target[0], start[0])
        self.assertLess(
            np.linalg.norm(target - projection.feasible_target),
            np.linalg.norm(target - start),
        )

    def test_directional_projection_can_slide_along_safe_boundary(self):
        workspace = VoxelWorkspaceMap(
            np.array(
                [
                    [0.00, 0.00, 0.00],
                    [0.01, 0.00, 0.00],
                    [0.02, 0.00, 0.00],
                    [0.02, 0.01, 0.00],
                    [0.02, 0.02, 0.00],
                ],
                dtype=float,
            ),
            voxel_size_m=0.01,
        )
        projection = workspace.project_from(
            np.array([0.001, 0.001, 0.001]),
            np.array([0.05, 0.05, 0.001]),
        )
        self.assertTrue(workspace.contains_safe(projection.feasible_target))
        self.assertGreater(projection.feasible_target[0], 0.015)
        self.assertGreater(projection.feasible_target[1], 0.015)

    def test_stateful_filtered_projection_does_not_global_jump(self):
        workspace = VoxelWorkspaceMap(
            np.array(
                [
                    [0.00, 0.00, 0.00],
                    [0.01, 0.00, 0.00],
                    [0.02, 0.00, 0.00],
                    [0.50, 0.00, 0.00],
                ],
                dtype=float,
            ),
            voxel_size_m=0.01,
        )
        workspace.project(np.array([0.001, 0.001, 0.001]))
        projection = workspace.project(np.array([0.08, 0.001, 0.001]))
        self.assertLess(projection.feasible_target[0], 0.10)
        self.assertGreater(projection.feasible_target[0], 0.01)

    def test_from_npz_defaults_to_safe_class(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array(
                    [
                        [0.0, -0.2, 1.0],
                        [0.2, -0.2, 1.0],
                        [0.4, 0.0, 0.7],
                    ],
                    dtype=np.float32,
                ),
                classification=np.array([2, 1, 0], dtype=np.uint8),
            )
            loaded = VoxelWorkspaceMap.from_npz(path, voxel_size_m=0.01)
            self.assertTrue(loaded.contains_safe(np.array([0.001, -0.199, 1.001])))
            self.assertFalse(loaded.contains_safe(np.array([0.201, -0.199, 1.001])))
            self.assertFalse(loaded.contains_safe(np.array([0.4, 0.0, 0.7])))

    def test_from_npz_can_load_all_collision_free_classes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array(
                    [
                        [0.0, -0.2, 1.0],
                        [0.2, -0.2, 1.0],
                        [0.4, 0.0, 0.7],
                    ],
                    dtype=np.float32,
                ),
                classification=np.array([2, 1, 0], dtype=np.uint8),
            )
            loaded = VoxelWorkspaceMap.from_npz(
                path,
                voxel_size_m=0.01,
                allowed_classes=(1, 2),
            )
            self.assertTrue(loaded.contains_safe(np.array([0.001, -0.199, 1.001])))
            self.assertTrue(loaded.contains_safe(np.array([0.201, -0.199, 1.001])))
            self.assertFalse(loaded.contains_safe(np.array([0.4, 0.0, 0.7])))

    def test_dilation_fills_unsampled_neighbor_but_not_known_collision_voxel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array(
                    [
                        [0.0, 0.0, 0.0],
                        [0.01, 0.0, 0.0],
                    ],
                    dtype=np.float32,
                ),
                classification=np.array([2, 0], dtype=np.uint8),
            )
            loaded = VoxelWorkspaceMap.from_npz(
                path,
                voxel_size_m=0.01,
                dilation_voxels=1,
            )
            self.assertGreater(len(loaded.safe_voxel_indices), 1)
            self.assertFalse(loaded.contains_safe(np.array([0.011, 0.001, 0.001])))
            self.assertTrue(loaded.contains_safe(np.array([-0.001, 0.001, 0.001])))

    def test_default_dilation_can_be_injected_by_configured_runtime(self):
        previous = VoxelWorkspaceMap.DEFAULT_DILATION_VOXELS
        self.addCleanup(setattr, VoxelWorkspaceMap, "DEFAULT_DILATION_VOXELS", previous)
        VoxelWorkspaceMap.DEFAULT_DILATION_VOXELS = 1
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
                classification=np.array([2], dtype=np.uint8),
            )
            loaded = VoxelWorkspaceMap.from_npz(path, voxel_size_m=0.01)
            self.assertGreater(len(loaded.safe_voxel_indices), 1)

    def test_from_npz_rejects_conflicting_class_filters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array([[0.0, -0.2, 1.0]], dtype=np.float32),
                classification=np.array([2], dtype=np.uint8),
            )
            with self.assertRaises(ValueError):
                VoxelWorkspaceMap.from_npz(
                    path,
                    safe_class=2,
                    allowed_classes=(1, 2),
                )


if __name__ == "__main__":
    unittest.main()
