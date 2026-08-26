from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.motion_reference import step_position, step_rotation  # noqa: E402


class MotionReferenceTest(unittest.TestCase):
    def test_position_step_respects_speed_limit(self):
        result = step_position(
            np.zeros(3),
            np.array([1.0, 0.0, 0.0]),
            0.08,
            1.0 / 60.0,
        )
        self.assertAlmostEqual(float(np.linalg.norm(result)), 0.08 / 60.0)

    def test_rotation_step_respects_angular_speed_limit(self):
        desired = np.array(
            [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            dtype=float,
        )
        result = step_rotation(np.eye(3), desired, math.radians(70.0), 0.1)
        angle = math.acos(float(np.clip((np.trace(result) - 1.0) * 0.5, -1.0, 1.0)))
        self.assertAlmostEqual(angle, math.radians(7.0), places=7)
        np.testing.assert_allclose(result.T @ result, np.eye(3), atol=1e-10)

    def test_reachable_reference_is_returned_exactly(self):
        desired_position = np.array([0.001, -0.002, 0.003])
        desired_rotation = np.eye(3)
        np.testing.assert_allclose(
            step_position(np.zeros(3), desired_position, 1.0, 1.0),
            desired_position,
        )
        np.testing.assert_allclose(
            step_rotation(np.eye(3), desired_rotation, 1.0, 1.0),
            desired_rotation,
        )


if __name__ == "__main__":
    unittest.main()
