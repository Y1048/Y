import json
import tempfile
import unittest
from pathlib import Path

from select_matched_resume import select_checkpoint


class ResumeSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stage1 = self.root / "stage1"
        for mode in ("fixed", "recorded"):
            path = self.stage1 / mode / "run" / "model_499.pt"
            path.parent.mkdir(parents=True)
            path.touch()

    def tearDown(self):
        self.tmp.cleanup()

    def make_run(self, name: str, complete: bool = True) -> Path:
        run = self.root / name
        run.mkdir()
        if complete:
            (run / "COMPLETE").touch()
        for mode in ("fixed", "recorded"):
            checkpoint = run / mode / "run" / "model_999.pt"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.touch()
            (run / f"{mode.upper()}_COMPLETE").touch()
            (run / f"{mode}_result.json").write_text(json.dumps({
                "status": "passed", "upper_mode": mode,
                "checkpoints": [str(checkpoint)],
            }))
        return run

    def test_falls_back_to_stage1(self):
        selected = select_checkpoint(self.root, self.stage1, "fixed")
        self.assertEqual(selected.name, "model_499.pt")

    def test_uses_newest_completed_run(self):
        self.make_run("mjlab_matched_continuation_20260915T010000Z")
        newest = self.make_run("mjlab_matched_continuation_20260915T020000Z")
        selected = select_checkpoint(self.root, self.stage1, "recorded")
        self.assertTrue(selected.is_relative_to(newest))

    def test_ignores_interrupted_run(self):
        valid = self.make_run("mjlab_matched_continuation_20260915T010000Z")
        self.make_run("mjlab_matched_continuation_20260915T020000Z", complete=False)
        selected = select_checkpoint(self.root, self.stage1, "fixed")
        self.assertTrue(selected.is_relative_to(valid))

    def test_accepts_completed_curriculum_run(self):
        newest = self.make_run("mjlab_recorded_curriculum_20260915T030000Z")
        selected = select_checkpoint(self.root, self.stage1, "recorded")
        self.assertTrue(selected.is_relative_to(newest))

    def test_timestamp_orders_across_run_kinds(self):
        self.make_run("mjlab_recorded_curriculum_20260915T030000Z")
        newest = self.make_run("mjlab_matched_continuation_20260915T040000Z")
        selected = select_checkpoint(self.root, self.stage1, "fixed")
        self.assertTrue(selected.is_relative_to(newest))


if __name__ == "__main__":
    unittest.main()
