#!/usr/bin/env python3
"""TWIST2 물리 CSV MuJoCo 재생기의 네트워크 독립 테스트."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from replay_physical_csv_mujoco import BuildSummary, LoadPhysicalCsv


class ReplayPhysicalCsvMuJoCoTests(unittest.TestCase):
    def WriteCsv(self, rows: list[dict[str, object]]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "physical.csv"
        fieldnames = ["elapsed_s", "phase"]
        fieldnames.extend(f"q_{index}" for index in range(29))
        fieldnames.extend(f"dq_{index}" for index in range(29))
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def Row(self, elapsed_s: float, q22: float = 0.0) -> dict[str, object]:
        row: dict[str, object] = {"elapsed_s": elapsed_s, "phase": "policy"}
        for index in range(29):
            row[f"q_{index}"] = q22 if index == 22 else index / 100.0
            row[f"dq_{index}"] = 0.0
        return row

    def test_loads_canonical_29_joint_samples(self) -> None:
        samples = LoadPhysicalCsv(self.WriteCsv([self.Row(0.1), self.Row(0.2, 0.3)]))
        self.assertEqual(2, len(samples))
        self.assertEqual((29,), samples[0].q_rad.shape)
        self.assertEqual(0.3, samples[1].q_rad[22])

    def test_summary_preserves_measured_shoulder_sign(self) -> None:
        samples = LoadPhysicalCsv(
            self.WriteCsv([self.Row(1.0, 0.3), self.Row(2.0, 0.1)])
        )
        summary = BuildSummary(samples)
        self.assertEqual(0.3, summary["right_shoulder_pitch_start_rad"])
        self.assertEqual(0.1, summary["right_shoulder_pitch_end_rad"])
        self.assertAlmostEqual(1.0, summary["duration_s"])

    def test_rejects_backward_time(self) -> None:
        path = self.WriteCsv([self.Row(0.2), self.Row(0.1)])
        with self.assertRaisesRegex(ValueError, "moved backward"):
            LoadPhysicalCsv(path)

    def test_rejects_nonfinite_joint(self) -> None:
        row = self.Row(0.1)
        row["q_22"] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite q_22"):
            LoadPhysicalCsv(self.WriteCsv([row]))

    def test_real_capture_loads_without_reordering(self) -> None:
        path = HERE.parents[1] / "logs" / "physical_tests" / (
            "g1_twist2_right_arm_trial_1787638008.csv"
        )
        if not path.exists():
            self.skipTest("physical CSV is not present")
        samples = LoadPhysicalCsv(path)
        np.testing.assert_allclose(samples[0].q_rad[22], 0.290641427)
        self.assertEqual(1538, len(samples))


if __name__ == "__main__":
    unittest.main()
