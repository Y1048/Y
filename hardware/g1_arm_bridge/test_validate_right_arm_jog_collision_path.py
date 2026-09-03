#!/usr/bin/env python3

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from arm_sdk_hold_contract import DUAL_ARM_INDICES, RIGHT_ARM_JOINT_NAMES
from g1_right_arm_jog import load_config
from validate_right_arm_jog_collision_path import (
    DEFAULT_CONFIG_PATH,
    build_endpoint_trajectories,
    find_direction_limit,
)


class ValidateRightArmJogCollisionPathTests(unittest.TestCase):
    def test_endpoint_paths_cover_only_selected_joint_range(self) -> None:
        measured = [0.0] * 29
        measured[25] = math.radians(55.0)
        config = load_config(DEFAULT_CONFIG_PATH)
        for arm_index, joint_name in enumerate(RIGHT_ARM_JOINT_NAMES):
            trajectories = build_endpoint_trajectories(
                tuple(measured),
                config,
                joint_name,
            )
            self.assertEqual(
                ("minimum", "maximum"),
                tuple(item[0] for item in trajectories),
            )
            for trajectory in (item[1] for item in trajectories):
                changed = [
                    index
                    for index, (start, goal) in enumerate(
                        zip(trajectory.start_q_rad, trajectory.goal_q_rad)
                    )
                    if not math.isclose(start, goal)
                ]
                self.assertEqual(
                    [DUAL_ARM_INDICES.index(22 + arm_index)],
                    changed,
                )

    def test_direction_search_stops_at_first_unsafe_degree(self) -> None:
        measured = tuple([0.0] * 29)
        config = load_config(DEFAULT_CONFIG_PATH)

        def fake_validate(_measured, _config, _joint, offset, _validator):
            return {
                "offset_deg": math.degrees(offset),
                "allowed": abs(math.degrees(offset)) <= 4.01,
            }

        with patch(
            "validate_right_arm_jog_collision_path.validate_offset_path",
            side_effect=fake_validate,
        ):
            limit, probes = find_direction_limit(
                measured,
                config,
                "right_elbow",
                1,
                object(),
            )
        self.assertAlmostEqual(4.0, math.degrees(limit))
        self.assertEqual(5, len(probes))
        self.assertFalse(probes[-1]["allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
