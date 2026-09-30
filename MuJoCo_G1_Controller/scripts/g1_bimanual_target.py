"""Current absolute world-frame wrist target mapping.

This is the canonical unity_display_world_v1 mapping. It performs exactly one
Unity-to-MuJoCo basis conversion and no filtering, comfort policy, or safety
shaping.
"""

import mink
import numpy as np


BASIS = np.array([
    [0.0, 0.0, 1.0],
    [-1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
])


def copy_world_hands(packet):
    """Copy and normalize the two absolute Unity world wrist poses."""
    hands = {
        side: {
            "position_m": np.asarray(packet[side]["position_m"], dtype=float).copy(),
            "quaternion_wxyz": np.asarray(
                packet[side]["quaternion_wxyz"], dtype=float).copy(),
        }
        for side in ("left", "right")
    }
    for hand in hands.values():
        hand["quaternion_wxyz"] /= np.linalg.norm(hand["quaternion_wxyz"])
    return hands


def world_target(hand):
    """Convert one absolute Unity world wrist pose into MuJoCo world SE3."""
    rotation = mink.SO3(np.asarray(hand["quaternion_wxyz"], dtype=float))
    robot_rotation = BASIS @ rotation.as_matrix() @ BASIS.T
    robot_position = BASIS @ np.asarray(hand["position_m"], dtype=float)
    return mink.SE3.from_rotation_and_translation(
        mink.SO3.from_matrix(robot_rotation), robot_position)


def world_targets(hands):
    return {side: world_target(hands[side]) for side in ("left", "right")}
