#!/usr/bin/env python3
"""Static checks that supported physical entries consume token-bound prechecks."""

from __future__ import annotations

import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class PhysicalPrecheckProvenanceEntryTests(unittest.TestCase):
    def test_supported_entries_install_precheck_provenance_guard(self) -> None:
        for name in (
            "gate6_arm_sdk_hold_entry.py",
            "gate7_live_arm_sdk_entry.py",
            "g1_right_arm_jog_entry.py",
        ):
            with self.subTest(name=name):
                source = (HERE / name).read_text(encoding="utf-8")
                self.assertIn("require_provenance_bound_precheck", source)
                self.assertIn("validate_precheck", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
