from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from run_experiment import candidate_score, load_initial_pose, select_candidate


class MultiStrategyRecoveryExperimentTest(unittest.TestCase):
    def test_load_initial_pose_requires_seven_finite_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(
                json.dumps({"right_arm_q_rad": [0.0] * 7}),
                encoding="utf-8",
            )
            self.assertEqual(load_initial_pose(path), [0.0] * 7)

            path.write_text(
                json.dumps({"right_arm_q_rad": [0.0] * 6 + [math.inf]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "non-finite"):
                load_initial_pose(path)

    def test_candidate_score_prioritizes_clearance_then_time(self) -> None:
        safer = {
            "passed": True,
            "minimum_clearance_after_escape_m": 0.020,
            "elapsed_s": 5.0,
            "motion_profile": {"metrics": {"max_jerk_deg_s3": 200.0}},
        }
        faster = {
            "passed": True,
            "minimum_clearance_after_escape_m": 0.018,
            "elapsed_s": 3.0,
            "motion_profile": {"metrics": {"max_jerk_deg_s3": 150.0}},
        }
        self.assertGreater(candidate_score(safer), candidate_score(faster))

    def test_select_candidate_ignores_failed_results(self) -> None:
        failed = {"name": "failed", "passed": False, "result": {"passed": False}}
        passed = {
            "name": "passed",
            "passed": True,
            "result": {
                "passed": True,
                "minimum_clearance_after_escape_m": 0.015,
                "elapsed_s": 4.0,
                "motion_profile": {"metrics": {"max_jerk_deg_s3": 250.0}},
            },
        }
        self.assertIs(select_candidate([failed, passed]), passed)
        self.assertIsNone(select_candidate([failed]))

    def test_select_candidate_uses_time_inside_clearance_tolerance(self) -> None:
        slower = {
            "name": "slower",
            "passed": True,
            "result": {
                "passed": True,
                "minimum_clearance_after_escape_m": 0.0201,
                "elapsed_s": 5.0,
                "motion_profile": {"metrics": {"max_jerk_deg_s3": 200.0}},
            },
        }
        faster = {
            "name": "faster",
            "passed": True,
            "result": {
                "passed": True,
                "minimum_clearance_after_escape_m": 0.0200,
                "elapsed_s": 3.0,
                "motion_profile": {"metrics": {"max_jerk_deg_s3": 200.0}},
            },
        }
        self.assertIs(select_candidate([slower, faster]), faster)

        slower["result"]["minimum_clearance_after_escape_m"] = 0.0210
        self.assertIs(select_candidate([slower, faster]), slower)


if __name__ == "__main__":
    unittest.main()
