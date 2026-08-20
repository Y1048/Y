"""Map tracked Unity OVR poses into a location-independent G1 reference frame."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .transforms import (
    OPENXR_LEFT_WRIST_TO_G1,
    OPENXR_RIGHT_WRIST_TO_G1,
    convert_unity_ovr_pose_to_robot,
    move_pose_to_head_yaw_frame,
)


HandSide = Literal["left", "right"]


def map_unity_ovr_wrist_to_head_yaw(
    head_pose_unity: np.ndarray,
    wrist_pose_unity: np.ndarray,
    hand_side: HandSide,
) -> np.ndarray:
    """Return a wrist pose in a robot-basis, head-yaw-relative frame."""
    head_pose_robot = convert_unity_ovr_pose_to_robot(head_pose_unity)
    wrist_pose_robot = convert_unity_ovr_pose_to_robot(wrist_pose_unity)

    if hand_side == "left":
        wrist_pose_robot[:3, :3] = wrist_pose_robot[:3, :3] @ OPENXR_LEFT_WRIST_TO_G1
    elif hand_side == "right":
        wrist_pose_robot[:3, :3] = wrist_pose_robot[:3, :3] @ OPENXR_RIGHT_WRIST_TO_G1
    else:
        raise ValueError("hand_side must be 'left' or 'right'")

    return move_pose_to_head_yaw_frame(head_pose_robot, wrist_pose_robot)
