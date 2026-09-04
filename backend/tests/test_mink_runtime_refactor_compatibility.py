"""Compatibility checks for the split virtual-center runtime modules."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from mink.tasks.task import Task


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (SCRIPT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import g1_gate7_feedback as feedback  # noqa: E402
import g1_mink_collision_policy as collision  # noqa: E402
import g1_mink_diagnostics as diagnostics  # noqa: E402
import g1_virtual_center_tasks as tasks  # noqa: E402
import run_mink_g1_right_arm_virtual_center_live as live  # noqa: E402


class MinkRuntimeRefactorCompatibilityTest(unittest.TestCase):
    def test_existing_runtime_symbols_remain_public(self) -> None:
        expected_aliases = {
            "VirtualCenterOrientationTask": tasks.VirtualCenterOrientationTask,
            "orientation_limit_policy": tasks.orientation_limit_policy,
            "virtual_center_damping_costs": tasks.virtual_center_damping_costs,
            "virtual_center_posture_costs": tasks.virtual_center_posture_costs,
            "virtual_center_velocity_limits": tasks.virtual_center_velocity_limits,
            "ResolveCollisionProfile": collision.ResolveCollisionProfile,
            "orientation_diagnostics": diagnostics.orientation_diagnostics,
            "drain_gate7_simulation_feedback": feedback.drain_gate7_simulation_feedback,
            "apply_gate7_simulation_feedback": feedback.apply_gate7_simulation_feedback,
            "parse_gate7_feedback_packet": feedback.parse_gate7_feedback_packet,
            "should_apply_gate7_feedback": feedback.should_apply_gate7_feedback,
        }
        for name, extracted in expected_aliases.items():
            with self.subTest(name=name):
                self.assertIs(getattr(live, name), extracted)

        self.assertIs(live.Task, Task)

    def test_collision_profiles_preserve_distances_and_compatibility_target(self) -> None:
        self.assertEqual((0.005, 0.010), live.ResolveCollisionProfile("mink-default"))
        self.assertEqual(
            (0.020, 0.040),
            live.ResolveCollisionProfile("hardware-guarded"),
        )
        self.assertEqual(0.020, live.TELEOP_COLLISION_TARGET_DISTANCE_M)
        self.assertEqual(0.0005, live.MINK_DEFAULT_QP_RESERVE_M)

    def test_orientation_diagnostics_contract_is_unchanged(self) -> None:
        target = np.eye(3)
        wrist = np.diag([1.0, -1.0, -1.0])
        self.assertEqual(
            {
                "target_rotation_matrix_robot": target.tolist(),
                "wrist_rotation_matrix_robot": wrist.tolist(),
                "orientation_solver_policy": "exact_jacobian_weighted_posture_v1",
            },
            live.orientation_diagnostics(target, wrist),
        )


if __name__ == "__main__":
    unittest.main()
