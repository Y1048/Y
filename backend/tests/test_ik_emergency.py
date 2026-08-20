from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.ik_emergency import load_severe_ik_fallback_settings  # noqa: E402


class SevereIKFallbackSettingsTest(unittest.TestCase):
    def _load(self, fallback):
        payload = {"ik": {"fallback": fallback}}
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "teleop.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return load_severe_ik_fallback_settings(path)

    def test_loads_severe_thresholds(self):
        settings = self._load(
            {
                "position_error_enter_m": 0.035,
                "rotation_error_enter_deg": 12.0,
                "severe_position_error_m": 0.05,
                "severe_rotation_error_deg": 25.0,
            }
        )
        self.assertAlmostEqual(settings.position_error_m, 0.05)
        self.assertAlmostEqual(settings.rotation_error_rad, math.radians(25.0))

    def test_severe_position_must_exceed_normal_threshold(self):
        with self.assertRaises(ValueError):
            self._load(
                {
                    "position_error_enter_m": 0.035,
                    "rotation_error_enter_deg": 12.0,
                    "severe_position_error_m": 0.03,
                    "severe_rotation_error_deg": 25.0,
                }
            )

    def test_severe_rotation_must_exceed_normal_threshold(self):
        with self.assertRaises(ValueError):
            self._load(
                {
                    "position_error_enter_m": 0.035,
                    "rotation_error_enter_deg": 12.0,
                    "severe_position_error_m": 0.05,
                    "severe_rotation_error_deg": 10.0,
                }
            )


if __name__ == "__main__":
    unittest.main()
