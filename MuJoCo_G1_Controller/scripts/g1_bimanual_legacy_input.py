"""Legacy relative-frame hand-pose smoothing.

The current Unity path uses absolute unity_display_world_v1 wrist poses and
must not pass through this filter. This module remains only for historical
relative-frame fixtures/replay.
"""

import math

import mink
import numpy as np


class PairedHandFilter:
    """Calibrated per-hand smoothing for the historical relative-frame path."""

    position_tau_s = .060
    rotation_tau_s = .050

    def __init__(self):
        self.hands = None
        self.sender_time = None

    def reset(self, packet):
        self.hands = {
            side: dict(
                position_m=np.array(packet[side]['position_m'], dtype=float),
                quaternion_wxyz=np.array(
                    packet[side]['quaternion_wxyz'], dtype=float),
            )
            for side in ('left', 'right')
        }
        for hand in self.hands.values():
            hand['quaternion_wxyz'] /= np.linalg.norm(
                hand['quaternion_wxyz'])
        self.sender_time = packet['sender_time_s']

    def update(self, packet):
        if self.hands is None:
            self.reset(packet)
            return
        dt = packet['sender_time_s'] - self.sender_time
        if dt <= 0:
            return
        self.sender_time = packet['sender_time_s']
        if not all(packet[side]['tracked'] for side in ('left', 'right')):
            return
        # A tracking/packet gap must not bypass smoothing with alpha almost 1.
        dt = min(dt, .10)
        position_alpha = -math.expm1(-dt / self.position_tau_s)
        rotation_alpha = -math.expm1(-dt / self.rotation_tau_s)
        for side, filtered in self.hands.items():
            hand = packet[side]
            filtered['position_m'] += position_alpha * (
                np.asarray(hand['position_m']) - filtered['position_m'])
            previous = mink.SO3(filtered['quaternion_wxyz'])
            raw_q = np.asarray(hand['quaternion_wxyz'], dtype=float)
            desired = mink.SO3(raw_q / np.linalg.norm(raw_q))
            filtered['quaternion_wxyz'] = (
                previous @ mink.SO3.exp(
                    rotation_alpha * (previous.inverse() @ desired).log())
            ).wxyz.copy()


def relative_target(hand, origin_position, origin_rotation, home, engage_offset_m):
    """Historical engage-relative target mapping used only by legacy fixtures."""
    hand_rotation = mink.SO3(
        np.asarray(hand["quaternion_wxyz"], dtype=float)).as_matrix()
    delta_rotation = hand_rotation @ origin_rotation.T

    # Imported lazily to keep the current world mapping module independent.
    from g1_bimanual_target import BASIS

    robot_rotation = (
        BASIS @ delta_rotation @ BASIS.T @ home.rotation().as_matrix())
    robot_position = home.translation() + BASIS @ (
        np.asarray(hand["position_m"], dtype=float)
        - np.asarray(origin_position, dtype=float)
        + np.asarray(engage_offset_m, dtype=float)
    )
    return mink.SE3.from_rotation_and_translation(
        mink.SO3.from_matrix(robot_rotation), robot_position)


def relative_targets(hands, origins, home_targets, engage_offsets):
    return {
        side: relative_target(
            hands[side],
            origins[side][0],
            origins[side][1],
            home_targets[side],
            engage_offsets[side],
        )
        for side in ("left", "right")
    }
