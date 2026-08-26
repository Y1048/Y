"""Rate-limited Cartesian references for live wrist teleoperation."""

from __future__ import annotations

import math

import numpy as np


def step_position(
    current: np.ndarray,
    desired: np.ndarray,
    maximum_speed_mps: float,
    delta_time_s: float,
) -> np.ndarray:
    current_value = np.asarray(current, dtype=float)
    desired_value = np.asarray(desired, dtype=float)
    difference = desired_value - current_value
    distance = float(np.linalg.norm(difference))
    maximum_step = max(0.0, float(maximum_speed_mps) * float(delta_time_s))
    if distance <= maximum_step or distance < 1e-12:
        return desired_value.copy()
    return current_value + difference * (maximum_step / distance)


def step_rotation(
    current: np.ndarray,
    desired: np.ndarray,
    maximum_speed_rad_s: float,
    delta_time_s: float,
) -> np.ndarray:
    current_value = np.asarray(current, dtype=float)
    desired_value = np.asarray(desired, dtype=float)
    relative = desired_value @ current_value.T
    cosine = float(np.clip((np.trace(relative) - 1.0) * 0.5, -1.0, 1.0))
    angle = math.acos(cosine)
    maximum_step = max(0.0, float(maximum_speed_rad_s) * float(delta_time_s))
    if angle <= maximum_step or angle < 1e-10:
        return desired_value.copy()

    axis = np.array(
        [
            relative[2, 1] - relative[1, 2],
            relative[0, 2] - relative[2, 0],
            relative[1, 0] - relative[0, 1],
        ],
        dtype=float,
    )
    axis_norm = float(np.linalg.norm(axis))
    if axis_norm < 1e-10:
        eigenvalues, eigenvectors = np.linalg.eig(relative)
        axis = np.real(eigenvectors[:, int(np.argmin(np.abs(eigenvalues - 1.0)))])
        axis_norm = float(np.linalg.norm(axis))
    axis /= axis_norm

    x_value, y_value, z_value = axis
    skew = np.array(
        [[0.0, -z_value, y_value], [z_value, 0.0, -x_value], [-y_value, x_value, 0.0]],
        dtype=float,
    )
    sine = math.sin(maximum_step)
    one_minus_cosine = 1.0 - math.cos(maximum_step)
    incremental = np.eye(3) + sine * skew + one_minus_cosine * (skew @ skew)
    return incremental @ current_value
