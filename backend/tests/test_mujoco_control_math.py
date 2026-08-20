from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTROLLER_PATH = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "g1_right_arm_udp_ik_demo.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "g1_right_arm_udp_ik_demo",
    CONTROLLER_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load MuJoCo controller: {CONTROLLER_PATH}")

CONTROLLER = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(CONTROLLER)


def make_z_rotation(angle_radians: float) -> np.ndarray:
    cosine_value = math.cos(angle_radians)
    sine_value = math.sin(angle_radians)
    return np.array(
        [
            [cosine_value, -sine_value, 0.0],
            [sine_value, cosine_value, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


def make_axis_quaternion(
    axis_value: np.ndarray,
    angle_radians: float,
) -> np.ndarray:
    normalized_axis = axis_value / np.linalg.norm(axis_value)
    half_angle = angle_radians * 0.5
    return np.concatenate(
        [normalized_axis * math.sin(half_angle), [math.cos(half_angle)]]
    )


class MuJoCoControlMathTest(unittest.TestCase):
    def test_operator_basis_maps_all_semantic_axes(self):
        operator_axes = {
            "right": np.array([1.0, 0.0, 0.0]),
            "up": np.array([0.0, 1.0, 0.0]),
            "forward": np.array([0.0, 0.0, 1.0]),
        }
        expected_robot_axes = {
            "right": np.array([0.0, -1.0, 0.0]),
            "up": np.array([0.0, 0.0, 1.0]),
            "forward": np.array([1.0, 0.0, 0.0]),
        }

        for axis_name, operator_axis in operator_axes.items():
            with self.subTest(axis=axis_name):
                np.testing.assert_allclose(
                    CONTROLLER.OPERATOR_TO_ROBOT_BASIS @ operator_axis,
                    expected_robot_axes[axis_name],
                    atol=1e-12,
                )

    def test_clutch_engagement_has_no_pose_jump(self):
        input_position = np.array([0.42, -0.16, 1.05])
        input_rotation = make_axis_quaternion(
            np.array([0.3, 0.8, -0.2]),
            math.radians(47.0),
        )
        robot_position = np.array([0.39, -0.18, 1.01])
        robot_rotation = make_z_rotation(math.radians(23.0))
        reference = {
            "input_position": input_position.copy(),
            "input_rotation": CONTROLLER.operator_rotation_to_robot_matrix(
                input_rotation
            ),
            "robot_position": robot_position.copy(),
            "robot_rotation": robot_rotation.copy(),
        }

        target_position, target_rotation = CONTROLLER.calculate_clutched_target(
            reference,
            input_position,
            input_rotation,
        )

        np.testing.assert_allclose(target_position, robot_position, atol=1e-12)
        np.testing.assert_allclose(target_rotation, robot_rotation, atol=1e-12)

    def test_clutch_preserves_operator_position_delta(self):
        reference = {
            "input_position": np.array([0.42, -0.16, 1.05]),
            "input_rotation": np.eye(3),
            "robot_position": np.array([0.39, -0.18, 1.01]),
            "robot_rotation": np.eye(3),
        }
        input_delta = np.array([0.07, -0.03, 0.04])

        target_position, _ = CONTROLLER.calculate_clutched_target(
            reference,
            reference["input_position"] + input_delta,
            CONTROLLER.IDENTITY_QUATERNION_XYZW,
        )

        np.testing.assert_allclose(
            target_position,
            reference["robot_position"] + input_delta,
            atol=1e-12,
        )

    def test_operator_up_axis_rotation_preserves_transformed_direction(self):
        half_angle = math.radians(45.0)
        operator_y_rotation = np.array(
            [0.0, math.sin(half_angle), 0.0, math.cos(half_angle)]
        )

        robot_rotation = CONTROLLER.operator_rotation_to_robot_matrix(
            operator_y_rotation
        )

        operator_forward = np.array([0.0, 0.0, 1.0])
        operator_rotated_forward = np.array([1.0, 0.0, 0.0])
        robot_forward = CONTROLLER.OPERATOR_TO_ROBOT_BASIS @ operator_forward
        expected_robot_direction = (
            CONTROLLER.OPERATOR_TO_ROBOT_BASIS @ operator_rotated_forward
        )

        np.testing.assert_allclose(
            robot_rotation @ robot_forward,
            expected_robot_direction,
            atol=1e-12,
        )

    def test_clutch_applies_world_rotation_change_from_engagement(self):
        engagement_rotation = make_axis_quaternion(
            np.array([0.2, 0.7, 0.4]),
            math.radians(31.0),
        )
        current_rotation = make_axis_quaternion(
            np.array([-0.4, 0.1, 0.8]),
            math.radians(54.0),
        )
        robot_rotation = make_z_rotation(math.radians(-18.0))
        engagement_robot_input = (
            CONTROLLER.operator_rotation_to_robot_matrix(engagement_rotation)
        )
        current_robot_input = (
            CONTROLLER.operator_rotation_to_robot_matrix(current_rotation)
        )
        reference = {
            "input_position": np.array([0.42, -0.16, 1.05]),
            "input_rotation": engagement_robot_input,
            "robot_position": np.array([0.39, -0.18, 1.01]),
            "robot_rotation": robot_rotation,
        }

        _, target_rotation = CONTROLLER.calculate_clutched_target(
            reference,
            reference["input_position"],
            current_rotation,
        )

        expected_rotation = (
            current_robot_input
            @ engagement_robot_input.T
            @ robot_rotation
        )
        np.testing.assert_allclose(
            target_rotation,
            expected_rotation,
            atol=1e-12,
        )


if __name__ == "__main__":
    unittest.main()
