#!/usr/bin/env python3
"""Regression tests for startup collision-distance diagnostics."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import diagnose_initial_pose_collision as diagnostics


class _FakeG1:
    RIGHT_ARM_JOINTS = ("right_joint",)
    LEFT_ARM_JOINTS = ("left_joint",)


class _FakeController:
    g1 = _FakeG1()

    @staticmethod
    def _joint_id(_model, joint_name: str) -> int:
        return 0 if joint_name == "right_joint" else 1


class CollisionDiagnosticTests(unittest.TestCase):
    def test_left_arm_mesh_zero_is_probed_with_left_joint(self) -> None:
        model = SimpleNamespace(jnt_qposadr=np.array([0, 1], dtype=int))
        data = SimpleNamespace(qpos=np.zeros(2, dtype=float))

        def fake_distance(*_args) -> float:
            if abs(float(data.qpos[1])) > 0.0:
                return 0.02
            return 0.0

        with (
            patch.object(
                diagnostics.mujoco,
                "mj_geomDistance",
                side_effect=fake_distance,
            ),
            patch.object(diagnostics.mujoco, "mj_forward"),
        ):
            distance = diagnostics._probe_zero_mesh_distance(
                model,
                data,
                _FakeController(),
                first_geom=10,
                second_geom=20,
                max_distance_m=0.04,
            )

        self.assertAlmostEqual(0.02, distance)
        np.testing.assert_allclose(data.qpos, np.zeros(2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
