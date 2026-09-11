"""Synthetic-file integrity tests. These are NOT simulated or physical PD data."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from mujoco_pd_validate_results import compare, digest, validate


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        csv_path = self.folder / "candidate_000.csv"
        fields = ["time_s", "trial_time_s", "kp_proximal", "kd_proximal", "cycle", "segment",
                  "ref_22", "cmd_22", "q_22", "dq_22", "actual_tau_22", "contacts",
                  "torque_target_limited_arm", "hard_clipped_arm"]
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for cycle in range(3):
                for i, segment in enumerate(("out", "positive_hold", "cross", "negative_hold", "return", "ready_hold")):
                    writer.writerow(dict(zip(fields, [(cycle*6+i)*.002, (cycle*6+i)*.002,
                                                       40, 5, cycle, segment, .1, .04, 0, .2, 2, 0, 0, 0])))
        self.run = {"schema": "g1.mujoco.pd.run.v1", "simulation_only": True, "hardware_validated": False,
                    "mujoco": "fixture-not-mujoco", "numpy": "fixture", "gain_pairs": [[40, 5]],
                    "max_limit_ratio": .05, "timestep_s": .001, "reference_hz": 50, "writer_hz": 500,
                    "asset_sha256": {"model.xml": "synthetic"}, "source_sha256": {"test.py": "synthetic"}}
        self.metrics = {"reference_rmse_joint22_rad": .1, "command_rmse_joint22_rad": .04,
                        "peak_reference_error_joint22_rad": .1, "peak_torque_joint22_nm": 2.,
                        "peak_speed_joint22_rad_s": .2, "contact_sample_ratio": 0.,
                        "torque_target_limit_arm_sample_ratio": 0., "hard_clip_arm_sample_ratio": 0.}
        self.candidate = {"kp_proximal": 40, "kd_proximal": 5, "csv": csv_path.name,
                          "csv_sha256": digest(csv_path), "samples": 18, "completed": True,
                          "eligible": True, "reason": "", "exclusion_reasons": [], "metrics": self.metrics}
        self.summary = {"schema": "g1.mujoco.pd.sweep.v1", "simulation_only": True,
                        "hardware_config_modified": False, "recommended_hardware_gains": None,
                        "sweep_complete": True, "candidates": [self.candidate],
                        "ranking": [{"kp": 40, "kd": 5}]}
        self.save()

    def save(self):
        (self.folder / "run.json").write_text(json.dumps(self.run))
        self.summary["run_sha256"] = digest(self.folder / "run.json")
        (self.folder / "summary.json").write_text(json.dumps(self.summary))

    def test_valid_artifact_and_matching_comparison(self):
        a = validate(self.folder)
        b = copy.deepcopy(a)
        b["timestep_s"] = .0005
        result = compare([a, b])
        self.assertTrue(result["same_ranking"])
        self.assertEqual(result["candidate_deltas"][0]["rmse_absolute_delta_rad"], 0)

    def test_csv_tampering_fails(self):
        with (self.folder / "candidate_000.csv").open("a") as stream:
            stream.write("corrupt\n")
        with self.assertRaisesRegex(ValueError, "CSV hash mismatch"):
            validate(self.folder)

    def test_wrong_metric_fails(self):
        self.metrics["reference_rmse_joint22_rad"] = 0
        self.save()
        with self.assertRaisesRegex(ValueError, "metric differs"):
            validate(self.folder)

    def test_failed_candidate_cannot_be_eligible(self):
        self.candidate["completed"] = False
        self.candidate["reason"] = "guard_failure"
        self.save()
        with self.assertRaisesRegex(ValueError, "eligibility"):
            validate(self.folder)

    def test_bad_ranking_fails(self):
        self.summary["ranking"] = [{"kp": 56, "kd": 5}]
        self.save()
        with self.assertRaisesRegex(ValueError, "ranking order"):
            validate(self.folder)

    def test_changed_model_not_a_timestep_comparison(self):
        a = validate(self.folder)
        b = copy.deepcopy(a)
        b["asset_sha256"]["model.xml"] = "changed"
        with self.assertRaisesRegex(ValueError, "incomparable sweeps"):
            compare([a, b])

    def test_hardware_recommendation_rejected(self):
        self.summary["recommended_hardware_gains"] = [56, 3]
        self.save()
        with self.assertRaisesRegex(ValueError, "must not recommend hardware"):
            validate(self.folder)


if __name__ == "__main__":
    unittest.main()
