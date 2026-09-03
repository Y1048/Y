"""Boundary diagnostics distinguish a stopped unreachable goal from a stuck return."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_feasible_target_return import InterpolateGoal, GetVerdict, SummarizePreview, comparison


class ReturnTests(unittest.TestCase):
    def test_interpolation_preserves_endpoints_and_input(self):
        base = comparison.probe.base
        a = base._matrix_to_se3(np.eye(3), np.array([.5, 0, 1]))
        b = base._matrix_to_se3(np.diag([-1., -1., 1.]), np.array([.1, 0, 1]))
        before = a.as_matrix().copy()
        np.testing.assert_allclose(InterpolateGoal(a, b, 0).as_matrix(), a.as_matrix(), atol=1e-12)
        np.testing.assert_allclose(InterpolateGoal(a, b, 1).as_matrix(), b.as_matrix(), atol=1e-12)
        np.testing.assert_allclose(InterpolateGoal(a, b, .5).translation(), [.3, 0, 1])
        np.testing.assert_array_equal(a.as_matrix(), before)
        for fraction in (-.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                InterpolateGoal(a, b, fraction)

    def test_stopped_preview_does_not_mask_failed_return(self):
        def Phase():
            return {"preview": {"invalid_preview_frames": 0, "preview_fk_residual_max_m": 0.,
                    "last_second_preview_spread_cm": 0.},
                    "last_second_max_joint_speed_deg_s": 0., "sustained_settle_time_s": .5}
        phases = {name: Phase() for name in ("outside_hold", "inside_hold")}
        self.assertEqual(GetVerdict(phases)["status"], "OFFLINE_CRITERIA_MET")
        phases["inside_hold"]["sustained_settle_time_s"] = None
        self.assertEqual(GetVerdict(phases)["status"], "REVIEW_REQUIRED")
        phases["inside_hold"]["sustained_settle_time_s"] = 0.
        phases["outside_hold"]["preview"]["invalid_preview_frames"] = 1
        self.assertFalse(GetVerdict(phases)["preview_valid"])

    def test_preview_gap_is_not_actual_tracking_error(self):
        row = {"preview_position_m": [0,0,.02], "actual_position_m": [0,0,0],
               "preview_valid": True, "preview_fk_residual_m": 0., "preview_clearance_mm": 21.}
        result = SummarizePreview([row, row], 1/60)
        self.assertEqual(result["preview_to_actual_gap_final_cm"], 2.)
        self.assertEqual(result["last_second_preview_spread_cm"], 0.)


if __name__ == "__main__":
    unittest.main()
