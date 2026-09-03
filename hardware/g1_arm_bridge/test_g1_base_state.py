#!/usr/bin/env python3
"""G1 base pose 정규화의 네트워크 독립 단위 테스트."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from g1_base_state import BasePoseNormalizer, InvalidBaseStateError


def YawQuaternionWXYZ(yaw_rad: float) -> tuple[float, float, float, float]:
    return (
        math.cos(yaw_rad / 2.0),
        0.0,
        0.0,
        math.sin(yaw_rad / 2.0),
    )


class G1BaseStateTests(unittest.TestCase):
    def test_first_valid_sample_becomes_zero_identity(self) -> None:
        normalizer = BasePoseNormalizer()
        state = normalizer.Normalize(
            [4.0, -2.0, 0.71],
            YawQuaternionWXYZ(math.radians(35.0)),
            [0.1, 0.2, 0.0],
            0.3,
        )
        self.assertEqual((0.0, 0.0, 0.0), state.position_m)
        self.assertAlmostEqual(0.0, state.quaternion_xyzw[0], places=7)
        self.assertAlmostEqual(0.0, state.quaternion_xyzw[1], places=7)
        self.assertAlmostEqual(0.0, state.quaternion_xyzw[2], places=7)
        self.assertAlmostEqual(1.0, state.quaternion_xyzw[3], places=7)

    def test_world_translation_is_expressed_in_initial_heading_frame(self) -> None:
        normalizer = BasePoseNormalizer()
        initial_yaw = math.radians(90.0)
        normalizer.Normalize(
            [2.0, 3.0, 0.7],
            YawQuaternionWXYZ(initial_yaw),
            [0.0, 0.0, 0.0],
            0.0,
        )
        state = normalizer.Normalize(
            [2.0, 4.0, 0.8],
            YawQuaternionWXYZ(initial_yaw),
            [0.0, 1.0, 0.0],
            0.0,
        )
        self.assertAlmostEqual(1.0, state.position_m[0], places=7)
        self.assertAlmostEqual(0.0, state.position_m[1], places=7)
        self.assertAlmostEqual(0.1, state.position_m[2], places=7)
        self.assertAlmostEqual(1.0, state.velocity_mps[0], places=7)
        self.assertAlmostEqual(0.0, state.velocity_mps[1], places=7)

    def test_relative_yaw_keeps_expected_sign(self) -> None:
        normalizer = BasePoseNormalizer()
        normalizer.Normalize(
            [0.0, 0.0, 0.7],
            YawQuaternionWXYZ(math.radians(-40.0)),
            [0.0, 0.0, 0.0],
            0.0,
        )
        state = normalizer.Normalize(
            [0.0, 0.0, 0.7],
            YawQuaternionWXYZ(math.radians(-10.0)),
            [0.0, 0.0, 0.0],
            0.2,
        )
        expected_z = math.sin(math.radians(30.0) / 2.0)
        expected_w = math.cos(math.radians(30.0) / 2.0)
        self.assertAlmostEqual(expected_z, state.quaternion_xyzw[2], places=7)
        self.assertAlmostEqual(expected_w, state.quaternion_xyzw[3], places=7)
        self.assertEqual(0.2, state.yaw_speed_rad_s)

    def test_non_unit_input_is_normalized_and_sign_is_stable(self) -> None:
        normalizer = BasePoseNormalizer()
        normalizer.Normalize(
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            0.0,
        )
        state = normalizer.Normalize(
            [0.0, 0.0, 0.0],
            [-2.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0],
            0.0,
        )
        self.assertEqual((0.0, 0.0, 0.0, 1.0), state.quaternion_xyzw)

    def test_invalid_input_is_rejected(self) -> None:
        normalizer = BasePoseNormalizer()
        with self.assertRaisesRegex(InvalidBaseStateError, "zero length"):
            normalizer.Normalize(
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                0.0,
            )
        with self.assertRaisesRegex(InvalidBaseStateError, "non-finite"):
            normalizer.Normalize(
                [math.nan, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                0.0,
            )


if __name__ == "__main__":
    unittest.main()
