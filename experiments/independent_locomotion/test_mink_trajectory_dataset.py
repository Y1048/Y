import json
import tempfile
import unittest
from pathlib import Path

from mink_trajectory_dataset import load_split, read_active_episode


class SplitValidationTest(unittest.TestCase):
    def test_frozen_manifest_loads_both_disjoint_splits(self):
        manifest = Path(__file__).parent / "data/mink_command_trajectories_v1.json"
        train = load_split(manifest, "train")
        validation = load_split(manifest, "validation")
        self.assertEqual(5, len(train))
        self.assertEqual(2, len(validation))
        self.assertFalse(
            {x["source_sha256"] for x in train}
            & {x["source_sha256"] for x in validation}
        )

    def test_overlap_is_rejected(self):
        manifest = Path(__file__).parent / "data/mink_command_trajectories_v1.json"
        body = json.loads(manifest.read_text(encoding="utf-8"))
        body["episodes"][-1]["source_sha256"] = body["episodes"][0]["source_sha256"]
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.json"
            bad.write_text(json.dumps(body), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overlapping"):
                load_split(bad, "validation")

    def test_nonfinite_source_is_rejected(self):
        rows = []
        for index in range(100):
            joints = [0.0] * 7
            if index == 50:
                joints[2] = float("nan")
            rows.append({"packet": {"event": "active", "sample_time_s": index / 60, "joints": joints}})
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "nonfinite.jsonl"
            source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                read_active_episode(source)


if __name__ == "__main__":
    unittest.main()
