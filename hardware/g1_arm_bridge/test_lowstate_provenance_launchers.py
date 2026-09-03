#!/usr/bin/env python3
"""Static launcher checks for R21/R51 per-run LowState provenance."""

from __future__ import annotations

import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
TOOLS = PROJECT_ROOT / "tools"


class LowStateProvenanceLauncherTests(unittest.TestCase):
    def _text(self, name: str) -> str:
        return (TOOLS / name).read_text(encoding="utf-8")

    def test_startup_precheck_launchers_use_same_run_token_at_both_ends(self) -> None:
        for name in (
            "START_G1_RIGHT_ARM_JOG_MUJOCO.bat",
            "START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat",
            "START_G1_GATE6_INTERRUPT_RELEASE_TEST.bat",
            "START_G1_GATE7_LIVE_HARDWARE.bat",
        ):
            with self.subTest(name=name):
                source = self._text(name)
                self.assertIn("[guid]::NewGuid().ToString('N')", source)
                self.assertIn("--forward-token %LOWSTATE_TOKEN%", source)
                self.assertIn("check_startup_readiness_entry.py", source)
                self.assertIn(
                    "--expected-forward-token %LOWSTATE_TOKEN%",
                    source,
                )
                self.assertIn(
                    "[r]ead_only_lowstate_entry.py.*--forward-token %LOWSTATE_TOKEN%",
                    source,
                )
                self.assertNotIn(
                    "[r]ead_only_lowstate.py.*--forward-port 5007",
                    source,
                )

    def test_hardware_pose_sync_requires_same_token_on_snapshot_receiver(self) -> None:
        source = self._text("START_MINK_G1_HARDWARE_SYNC.bat")
        self.assertIn("[guid]::NewGuid().ToString('N')", source)
        self.assertIn("--forward-token %LOWSTATE_TOKEN%", source)
        self.assertIn(
            "--expected-forward-token %LOWSTATE_TOKEN%",
            source,
        )
        self.assertIn(
            "[r]ead_only_lowstate_entry.py.*--forward-token %LOWSTATE_TOKEN%",
            source,
        )

    def test_gate7_failed_cleanup_targets_guarded_entrypoint(self) -> None:
        source = self._text("START_G1_GATE7_LIVE_HARDWARE.bat")
        self.assertIn("[g]ate7_live_arm_sdk_entry.py", source)
        self.assertIn("--ready-file %ADAPTER_READY_WSL%", source)
        self.assertNotIn("pkill -TERM -f '[g]ate7_live_arm_sdk.py'", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
