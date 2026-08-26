from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from run_mink_g1_right_arm_prototype import (  # noqa: E402
    _update_reachability_limit,
)


class MinkReachabilityLimitTest(unittest.TestCase):
    def test_large_tracking_error_enters_dynamic_workspace_limit(self):
        self.assertTrue(_update_reachability_limit(False, True, 0.036, 0.0))
        self.assertTrue(_update_reachability_limit(False, True, 0.0, 16.0))

    def test_hysteresis_prevents_limit_chatter(self):
        self.assertTrue(_update_reachability_limit(True, True, 0.025, 9.0))
        self.assertFalse(_update_reachability_limit(True, True, 0.017, 7.0))

    def test_hold_does_not_change_existing_limit_state(self):
        self.assertTrue(_update_reachability_limit(True, False, 0.0, 0.0))
        self.assertFalse(_update_reachability_limit(False, False, 1.0, 180.0))


if __name__ == "__main__":
    unittest.main()
