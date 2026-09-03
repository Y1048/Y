"""Offline tracking diagnosis keeps solver dt fixed and separates final settling."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diagnose_mink_tracking_lag import GetSchedule, GetSustainedSettleTime, GetReachSummary


class TrackingLagTests(unittest.TestCase):
    def test_reach_bound_excludes_only_provably_outside_targets(self):
        rows = [{"shoulder_target_distance_m": d, "position_cm": e}
                for d, e in ((.3, 1.), (.4, 3.), (.4000001, 5.), (.5, 10.))]
        result = GetReachSummary(rows, .4)
        self.assertEqual(result["provably_outside_frames"], 1)
        self.assertEqual(result["provably_outside_percent"], 25.)
        self.assertAlmostEqual(result["maximum_position_error_lower_bound_cm"], 10.)
        self.assertEqual(result["outside_position_cm_p95"], 10.)
        self.assertIsNone(GetReachSummary(rows[:1], .4)["outside_position_cm_p95"])

    def test_slow_replay_stretches_only_moving_phase(self):
        for speed, expected in ((1., 4), (.5, 8), (.25, 16)):
            schedule = list(GetSchedule(1., speed, .25, .5))
            self.assertEqual(sum(p == "recorded" for p, _ in schedule), expected)
            self.assertEqual(sum(p == "hold" for p, _ in schedule), 2)
            self.assertEqual(sum(p == "return" for p, _ in schedule), 2)
            self.assertEqual(schedule[1][1], .25 * speed)

    def test_schedule_rejects_nonpositive_and_nonfinite_values(self):
        for value in (0., -1., float("nan"), float("inf")):
            for index in range(4):
                args = [1., 1., .1, 1.]
                args[index] = value
                with self.assertRaises(ValueError):
                    list(GetSchedule(*args))

    def test_transient_match_is_not_settling(self):
        good = {"position_cm": .1, "rotation_deg": 1.}
        bad = {"position_cm": .1, "rotation_deg": 6.}
        self.assertIsNone(GetSustainedSettleTime([good] * 10 + [bad], .1))
        self.assertIsNone(GetSustainedSettleTime([bad] + [good] * 4, .1))
        self.assertAlmostEqual(GetSustainedSettleTime([bad] * 2 + [good] * 5, .1), .2)
        self.assertEqual(GetSustainedSettleTime([good] * 5, .1), 0.)


if __name__ == "__main__":
    unittest.main()
