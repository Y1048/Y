from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_sweep import BuildHTML, GenerateCases, JointLimitFailure, ParseOffsets


class StartupRecoveryPostureSweepTests(unittest.TestCase):
    def test_offset_parser_is_finite_and_deduplicated(self) -> None:
        self.assertEqual(ParseOffsets("-15,0,15,0"), (-15.0, 0.0, 15.0))

    def test_case_grid_contains_base_pose(self) -> None:
        base = np.radians([6.0, -3.0, -18.0, 75.0, -15.0, -7.0, -2.0])
        cases = GenerateCases(base, (0.0,), (-15.0, 0.0, 15.0), (-15.0, 0.0, 15.0))
        self.assertEqual(9, len(cases))
        center = next(
            case
            for case in cases
            if case.roll_offset_deg == 0.0 and case.elbow_offset_deg == 0.0
        )
        np.testing.assert_allclose(center.pose_rad, base)

    def test_joint_limit_screen_rejects_unsafe_pose(self) -> None:
        self.assertIsNone(JointLimitFailure(tuple(np.radians([0, -7, 2, 57, 0, 0, 0]))))
        failure = JointLimitFailure(tuple(np.radians([0, -7, 2, 57, 0, 0, 100])))
        self.assertIn("right_wrist_yaw", failure or "")

    def test_html_map_contains_status_and_sample_warning(self) -> None:
        case = {
            "case_id": "p00_e00_r00",
            "status": "PASS",
            "passed": True,
            "pitch_offset_deg": 0.0,
            "roll_offset_deg": 0.0,
            "elbow_offset_deg": 0.0,
            "recovery_time_s": 3.8,
            "minimum_clearance_after_escape_m": 0.012,
            "failure": None,
            "result_path": str((HERE / "result.json").resolve()),
        }
        summary = {
            "run_name": "test",
            "generated_at_utc": "2026-08-28T00:00:00+00:00",
            "case_count": 1,
            "passed_count": 1,
            "success_rate_percent": 100.0,
            "total_wall_time_s": 1.0,
            "status_counts": {"PASS": 1},
            "base_q_deg": [0.0, -7.0, 2.0, 57.0, 0.0, 0.0, 0.0],
            "axes": {
                "shoulder_pitch_offset_deg": [0.0],
                "shoulder_roll_offset_deg": [0.0],
                "elbow_offset_deg": [0.0],
            },
            "cases": [case],
        }
        rendered = BuildHTML(summary)
        self.assertIn("BASE", rendered)
        self.assertIn("tested samples only", rendered)
        self.assertIn("12.00 mm", rendered)


if __name__ == "__main__":
    unittest.main()
