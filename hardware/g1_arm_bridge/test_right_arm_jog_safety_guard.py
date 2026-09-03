#!/usr/bin/env python3
"""SDK-neutral/static tests for the supported Jog R42 guards."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from right_arm_jog_safety_guard import (
    PROVENANCE_SCHEMA,
    validate_jog_permit_provenance,
    validate_jog_runtime_full_body,
)


class RightArmJogSafetyGuardTests(unittest.TestCase):
    def test_runtime_full_body_guard_detects_nonarm_change(self) -> None:
        precheck = {"latest_all_joint_q_rad": [0.0] * 29}
        measured = [0.0] * 29
        measured[5] = 0.03
        with self.assertRaisesRegex(RuntimeError, "full-body pose changed"):
            validate_jog_runtime_full_body(measured, precheck, 0.01)

    def test_permit_without_provenance_is_rejected_before_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing supported provenance"):
                validate_jog_permit_provenance({"passed": True}, config_path)

    def test_provenance_schema_is_explicit(self) -> None:
        self.assertEqual(
            "g1.right_arm_jog.path_permit.provenance.v1",
            PROVENANCE_SCHEMA,
        )

    def test_supported_launchers_use_provenance_generator(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        for relative in (
            "tools/START_G1_RIGHT_ARM_JOG_MUJOCO.bat",
            "tools/START_G1_SHOULDER_PITCH_FULL_AUTHORITY_TRIAL.bat",
        ):
            text = (project_root / relative).read_text(
                encoding="utf-8-sig",
                errors="replace",
            )
            self.assertIn("validate_right_arm_jog_collision_path_entry.py", text)
            self.assertNotIn(
                "hardware\\g1_arm_bridge\\validate_right_arm_jog_collision_path.py --",
                text,
            )

    def test_supported_jog_entry_installs_runtime_full_body_and_collision_checks(self) -> None:
        source = (
            Path(__file__).resolve().parent / "g1_right_arm_jog_entry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("validate_jog_permit_provenance", source)
        self.assertIn("validate_jog_runtime_full_body", source)
        self.assertIn("validate_jog_final_segment", source)
        self.assertIn("ArmJointJogController.advance = guarded_advance", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
