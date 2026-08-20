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
        target = np.array([0.20, -0.20, 1.00])
        projection = projector.update(target)
        np.testing.assert_allclose(projector.operator_target, target)
        np.testing.assert_allclose(projector.feasible_target, projection.feasible_target)
        self.assertTrue(projector.workspace_limited)
        self.assertGreater(projector.projection_distance_m, 0.0)

    def test_from_npz_uses_only_safe_class(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "workspace.npz"
            np.savez_compressed(
                path,
                positions_m=np.array(
                    [
                        [0.0, -0.2, 1.0],
                        [0.4, 0.0, 0.7],
                    ],
                    dtype=np.float32,
                ),
                classification=np.array([2, 0], dtype=np.uint8),
            )
            loaded = VoxelWorkspaceMap.from_npz(path, voxel_size_m=0.01)
            self.assertTrue(loaded.contains_safe(np.array([0.001, -0.199, 1.001])))
            self.assertFalse(loaded.contains_safe(np.array([0.4, 0.0, 0.7])))


if __name__ == "__main__":
    unittest.main()
