"""Exercise the shared transforms used by the active Mink controller."""

from pathlib import Path
import math
import sys
import unittest

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"))
import g1_right_arm_common as controller  # noqa: E402


class MuJoCoControlMathTest(unittest.TestCase):
    def test_operator_basis_maps_all_semantic_axes(self):
        expected = ([0, -1, 0], [0, 0, 1], [1, 0, 0])
        for axis, target in zip(np.eye(3), expected):
            np.testing.assert_allclose(
                controller.OPERATOR_TO_ROBOT_BASIS @ axis, target, atol=1e-12)

    def test_operator_up_axis_rotation_preserves_transformed_direction(self):
        half_angle = math.radians(45)
        quaternion = np.array([0, math.sin(half_angle), 0, math.cos(half_angle)])
        rotation = controller.operator_rotation_to_robot_matrix(quaternion)
        basis = controller.OPERATOR_TO_ROBOT_BASIS
        np.testing.assert_allclose(
            rotation @ (basis @ [0, 0, 1]), basis @ [1, 0, 0], atol=1e-12)

    def test_identity_rotation_remains_identity(self):
        np.testing.assert_allclose(
            controller.operator_rotation_to_robot_matrix(np.array([0, 0, 0, 1])),
            np.eye(3), atol=1e-12)

    def test_quaternion_sign_does_not_change_rotation(self):
        quaternion = np.array([0.2, 0.5, -0.4, 0.7])
        np.testing.assert_allclose(
            controller.operator_rotation_to_robot_matrix(quaternion),
            controller.operator_rotation_to_robot_matrix(-quaternion), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
