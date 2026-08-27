"""Unity, OpenXR, G1 좌표 규약을 명시한 작은 SE(3) 변환 함수 모음.

모든 자세는 4x4 동차변환 또는 xyzw quaternion으로 다루며, 위치와 회전에 동일한
기저 변환을 적용한다. 좌표 축을 호출부에서 임의로 다시 뒤집지 않는다.
"""

from __future__ import annotations

import math

import numpy as np


UNITY_TO_OPENXR = np.diag([1.0, 1.0, -1.0])
OPENXR_TO_ROBOT = np.array(
    [
        [0.0, 0.0, -1.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=float,
)

OPENXR_LEFT_WRIST_TO_G1 = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=float,
)

OPENXR_RIGHT_WRIST_TO_G1 = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
    ],
    dtype=float,
)


def normalize_quaternion(quaternion_xyzw: np.ndarray) -> np.ndarray:
    quaternion = np.asarray(quaternion_xyzw, dtype=float)
    if quaternion.shape != (4,) or not np.all(np.isfinite(quaternion)):
        raise ValueError("quaternion must contain four finite values")

    norm = np.linalg.norm(quaternion)
    if norm < 1e-9:
        raise ValueError("quaternion norm is zero")
    return quaternion / norm


def quaternion_to_matrix(quaternion_xyzw: np.ndarray) -> np.ndarray:
    x_value, y_value, z_value, w_value = normalize_quaternion(quaternion_xyzw)
    return np.array(
        [
            [
                1.0 - 2.0 * (y_value * y_value + z_value * z_value),
                2.0 * (x_value * y_value - z_value * w_value),
                2.0 * (x_value * z_value + y_value * w_value),
            ],
            [
                2.0 * (x_value * y_value + z_value * w_value),
                1.0 - 2.0 * (x_value * x_value + z_value * z_value),
                2.0 * (y_value * z_value - x_value * w_value),
            ],
            [
                2.0 * (x_value * z_value - y_value * w_value),
                2.0 * (y_value * z_value + x_value * w_value),
                1.0 - 2.0 * (x_value * x_value + y_value * y_value),
            ],
        ],
        dtype=float,
    )


def matrix_to_quaternion(rotation: np.ndarray) -> np.ndarray:
    matrix = np.asarray(rotation, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("rotation must be a finite 3x3 matrix")

    trace_value = np.trace(matrix)
    if trace_value > 0.0:
        scale_value = math.sqrt(trace_value + 1.0) * 2.0
        quaternion = np.array(
            [
                (matrix[2, 1] - matrix[1, 2]) / scale_value,
                (matrix[0, 2] - matrix[2, 0]) / scale_value,
                (matrix[1, 0] - matrix[0, 1]) / scale_value,
                0.25 * scale_value,
            ]
        )
    else:
        diagonal_index = int(np.argmax(np.diag(matrix)))
        if diagonal_index == 0:
            scale_value = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    0.25 * scale_value,
                    (matrix[0, 1] + matrix[1, 0]) / scale_value,
                    (matrix[0, 2] + matrix[2, 0]) / scale_value,
                    (matrix[2, 1] - matrix[1, 2]) / scale_value,
                ]
            )
        elif diagonal_index == 1:
            scale_value = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (matrix[0, 1] + matrix[1, 0]) / scale_value,
                    0.25 * scale_value,
                    (matrix[1, 2] + matrix[2, 1]) / scale_value,
                    (matrix[0, 2] - matrix[2, 0]) / scale_value,
                ]
            )
        else:
            scale_value = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quaternion = np.array(
                [
                    (matrix[0, 2] + matrix[2, 0]) / scale_value,
                    (matrix[1, 2] + matrix[2, 1]) / scale_value,
                    0.25 * scale_value,
                    (matrix[1, 0] - matrix[0, 1]) / scale_value,
                ]
            )

    quaternion = normalize_quaternion(quaternion)
    if quaternion[3] < 0.0:
        quaternion = -quaternion
    return quaternion


def make_pose(position: np.ndarray, quaternion_xyzw: np.ndarray) -> np.ndarray:
    pose = np.eye(4, dtype=float)
    pose[:3, :3] = quaternion_to_matrix(quaternion_xyzw)
    pose[:3, 3] = np.asarray(position, dtype=float)
    return pose


def split_pose(pose: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(pose, dtype=float)
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise ValueError("pose must be a finite 4x4 matrix")
    return matrix[:3, 3].copy(), matrix_to_quaternion(matrix[:3, :3])


def invert_pose(pose: np.ndarray) -> np.ndarray:
    matrix = np.asarray(pose, dtype=float)
    result = np.eye(4, dtype=float)
    result[:3, :3] = matrix[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ matrix[:3, 3]
    return result


def convert_unity_ovr_pose_to_openxr(pose_unity: np.ndarray) -> np.ndarray:
    """Convert Unity x-right/y-up/z-forward into OpenXR x-right/y-up/z-back."""
    pose_openxr = np.eye(4, dtype=float)
    pose_openxr[:3, :3] = UNITY_TO_OPENXR @ pose_unity[:3, :3] @ UNITY_TO_OPENXR
    pose_openxr[:3, 3] = UNITY_TO_OPENXR @ pose_unity[:3, 3]
    return pose_openxr


def convert_openxr_pose_to_robot(pose_openxr: np.ndarray) -> np.ndarray:
    """Apply the official TeleVuer OpenXR-to-Unitree basis change."""
    pose_robot = np.eye(4, dtype=float)
    pose_robot[:3, :3] = OPENXR_TO_ROBOT @ pose_openxr[:3, :3] @ OPENXR_TO_ROBOT.T
    pose_robot[:3, 3] = OPENXR_TO_ROBOT @ pose_openxr[:3, 3]
    return pose_robot


def convert_unity_ovr_pose_to_robot(pose_unity: np.ndarray) -> np.ndarray:
    return convert_openxr_pose_to_robot(convert_unity_ovr_pose_to_openxr(pose_unity))


def get_head_yaw_rotation(head_rotation_robot: np.ndarray) -> np.ndarray:
    head_x_axis = np.asarray(head_rotation_robot, dtype=float)[:, 0].copy()
    head_x_axis[2] = 0.0
    norm = np.linalg.norm(head_x_axis)
    if norm < 1e-6:
        return np.eye(3, dtype=float)

    head_x_axis /= norm
    head_z_axis = np.array([0.0, 0.0, 1.0])
    head_y_axis = np.cross(head_z_axis, head_x_axis)
    head_y_axis /= np.linalg.norm(head_y_axis)
    return np.column_stack([head_x_axis, head_y_axis, head_z_axis])


def move_pose_to_head_yaw_frame(head_pose_robot: np.ndarray, wrist_pose_robot: np.ndarray) -> np.ndarray:
    yaw_rotation = get_head_yaw_rotation(head_pose_robot[:3, :3])
    relative_pose = np.eye(4, dtype=float)
    relative_pose[:3, :3] = yaw_rotation.T @ wrist_pose_robot[:3, :3]
    relative_pose[:3, 3] = yaw_rotation.T @ (wrist_pose_robot[:3, 3] - head_pose_robot[:3, 3])
    return relative_pose


def average_quaternions(quaternions_xyzw: np.ndarray) -> np.ndarray:
    quaternions = np.asarray(quaternions_xyzw, dtype=float)
    if quaternions.ndim != 2 or quaternions.shape[1] != 4 or len(quaternions) == 0:
        raise ValueError("quaternions must have shape (N, 4)")

    reference = normalize_quaternion(quaternions[0])
    aligned = []
    for quaternion in quaternions:
        normalized = normalize_quaternion(quaternion)
        if np.dot(normalized, reference) < 0.0:
            normalized = -normalized
        aligned.append(normalized)

    accumulator = np.zeros((4, 4), dtype=float)
    for quaternion in aligned:
        accumulator += np.outer(quaternion, quaternion)
    eigenvalues, eigenvectors = np.linalg.eigh(accumulator)
    result = eigenvectors[:, np.argmax(eigenvalues)]
    if np.dot(result, reference) < 0.0:
        result = -result
    return normalize_quaternion(result)
