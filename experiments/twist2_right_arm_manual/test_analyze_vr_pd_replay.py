import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_vr_pd_replay import analyze


class ReplayAnalysisTest(unittest.TestCase):
    def test_reports_known_tracking_error_and_gains(self):
        fields = ["phase", "writer_valid", "writer_sequence", "writer_write_returned_s"]
        for j in range(22, 29):
            fields += [f"writer_target_{j}", f"writer_q_{j}", f"writer_dq_{j}", f"writer_kp_{j}", f"writer_kd_{j}"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "policy.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
                for n in range(40):
                    row = {"phase": "arm_tracking", "writer_valid": "1", "writer_sequence": n + 1, "writer_write_returned_s": n * 0.02}
                    for j in range(22, 29):
                        row.update({f"writer_target_{j}": n * 0.01, f"writer_q_{j}": n * 0.01 - 0.02, f"writer_dq_{j}": 0.5, f"writer_kp_{j}": 40, f"writer_kd_{j}": 5})
                    writer.writerow(row)
            report = analyze(path)
            self.assertEqual(report["tracking_samples"], 40)
            self.assertAlmostEqual(report["joints"][0]["rmse_rad"], 0.02)
            self.assertEqual(report["joints"][0]["kp"], 40)
            self.assertFalse(report["counterfactual_gain_ranking"])


if __name__ == "__main__":
    unittest.main()
