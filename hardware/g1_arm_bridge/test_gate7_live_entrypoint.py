#!/usr/bin/env python3
"""Static entrypoint checks for the supported Gate 7 physical wrapper."""

from __future__ import annotations

import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class Gate7LiveEntrypointTests(unittest.TestCase):
    def test_wsl_starter_uses_supported_guarded_entrypoint(self) -> None:
        starter = (HERE / "start_gate7_live_arm_sdk_wsl.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("gate7_live_arm_sdk_entry.py", starter)
        self.assertNotIn(
            'exec "${python_path}" -u hardware/g1_arm_bridge/gate7_live_arm_sdk.py',
            starter,
        )

    def test_entrypoint_installs_clearance_and_final_segment_guards(self) -> None:
        source = (HERE / "gate7_live_arm_sdk_entry.py").read_text(encoding="utf-8")
        self.assertIn("require_active_collision_evidence", source)
        self.assertIn("validate_final_command_segment", source)
        self.assertIn("frame=None", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
