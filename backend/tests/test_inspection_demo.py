from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.inspection_demo import (  # noqa: E402
    InspectionDemoState,
    InspectionDemoTracker,
    append_inspection_result,
)


class InspectionDemoTrackerTest(unittest.TestCase):
    def make_tracker(self) -> InspectionDemoTracker:
        return InspectionDemoTracker(
            approach_radius_m=0.08,
            contact_radius_m=0.04,
            hold_seconds=0.75,
        )

    def test_approach_hold_and_completion_are_deterministic(self):
        tracker = self.make_tracker()
        approach = tracker.update(active=True, distance_m=0.06, now_s=1.0)
        holding = tracker.update(active=True, distance_m=0.03, now_s=1.1)
        complete = tracker.update(active=True, distance_m=0.02, now_s=1.86)

        self.assertEqual(approach.state, InspectionDemoState.APPROACH)
        self.assertEqual(holding.state, InspectionDemoState.HOLDING)
        self.assertEqual(complete.state, InspectionDemoState.COMPLETE)
        self.assertTrue(complete.just_completed)
        self.assertEqual(complete.hold_progress, 1.0)

    def test_leaving_contact_resets_only_hold_progress(self):
        tracker = self.make_tracker()
        tracker.update(active=True, distance_m=0.03, now_s=1.0)
        reset = tracker.update(active=True, distance_m=0.06, now_s=1.4)
        holding = tracker.update(active=True, distance_m=0.03, now_s=1.5)

        self.assertEqual(reset.state, InspectionDemoState.APPROACH)
        self.assertEqual(reset.hold_progress, 0.0)
        self.assertEqual(holding.hold_progress, 0.0)

    def test_completion_remains_latched_until_reset(self):
        tracker = self.make_tracker()
        tracker.update(active=True, distance_m=0.01, now_s=1.0)
        tracker.update(active=True, distance_m=0.01, now_s=1.8)
        latched = tracker.update(active=False, distance_m=0.50, now_s=2.0)
        self.assertEqual(latched.state, InspectionDemoState.COMPLETE)

        tracker.reset()
        waiting = tracker.update(active=False, distance_m=0.50, now_s=2.1)
        self.assertEqual(waiting.state, InspectionDemoState.WAITING)

    def test_completed_result_is_written_with_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inspection_runs.csv"
            append_inspection_result(path, {"session_id": "test", "elapsed_s": 1.2})
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["session_id"], "test")
            self.assertEqual(rows[0]["elapsed_s"], "1.2")


if __name__ == "__main__":
    unittest.main()
