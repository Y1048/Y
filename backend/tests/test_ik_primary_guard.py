from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.ik_primary_guard import should_reject_primary_step  # noqa: E402


class PrimaryTaskGuardTest(unittest.TestCase):
    def test_accepts_improving_step(self):
        self.assertFalse(should_reject_primary_step(0.02, 0.01))

    def test_accepts_numerically_equal_step_within_tolerance(self):
        self.assertFalse(should_reject_primary_step(0.02, 0.0200005, tolerance_m=1e-6))

    def test_rejects_position_error_increase(self):
        self.assertTrue(should_reject_primary_step(0.01, 0.02))

    def test_rejects_nonfinite_candidate(self):
        self.assertTrue(should_reject_primary_step(0.01, math.inf))

    def test_rejects_invalid_tolerance(self):
        with self.assertRaises(ValueError):
            should_reject_primary_step(0.01, 0.01, tolerance_m=-1.0)


if __name__ == "__main__":
    unittest.main()
