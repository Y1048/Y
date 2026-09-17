from __future__ import annotations

import math
import sys
import unittest
import tempfile
import subprocess
from unittest.mock import patch
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_sweep import BuildHTML, GenerateCases, JointLimitFailure, ParseOffsets, GetSweepOutcome
from single_pose_runner import UseIsolatedModel, SCRIPTS_DIR
from run_sweep import BuildProvenance, ValidateResumeProvenance
from run_sweep import RunCase, ValidateRetainedArtifacts


class StartupRecoveryPostureSweepTests(unittest.TestCase):
    def test_case_retry_never_reuses_previous_result(self):
        case = GenerateCases(np.radians([0, -7, 2, 57, 0, 0, 0]), (0,), (0,), (0,))[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def complete(command, **kwargs):
                Path(command[command.index("--result") + 1]).write_text('{"passed": true}', encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")
            with patch("run_sweep.subprocess.run", side_effect=complete):
                first = RunCase(case, root, root / "source.json", 1)
            with patch("run_sweep.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")):
                second = RunCase(case, root, root / "source.json", 1)
            self.assertEqual(first["status"], "PASS")
            ValidateRetainedArtifacts(first, root)
            self.assertEqual(second["status"], "ERROR")
            self.assertIn("missing_result", second["failure"])
            self.assertNotEqual(first["result_path"], second["result_path"])
            self.assertEqual(Path(first["result_path"]).read_text(), '{"passed": true}')
            for field in ("state", "result", "log"):
                with self.subTest(field=field):
                    path = Path(first[f"{field}_path"])
                    content = path.read_bytes()
                    path.write_bytes(content + b" ")
                    with self.assertRaisesRegex(ValueError, "changed or unhashed"):
                        ValidateRetainedArtifacts(first, root)
                    path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, "contradicts"):
                ValidateRetainedArtifacts(first | {"status": "FAIL"}, root)
            with self.assertRaisesRegex(ValueError, "changed or unhashed"):
                ValidateRetainedArtifacts(first | {"result_sha256": None}, root)
            Path(first["result_path"]).unlink()
            with self.assertRaisesRegex(ValueError, "missing or external"):
                ValidateRetainedArtifacts(first, root)

    def test_skipped_artifact_does_not_require_result(self):
        case = GenerateCases(np.radians([0, -7, 2, 57, 0, 0, 100]), (0,), (0,), (0,))[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("run_sweep.subprocess.run") as process:
                result = RunCase(case, root, root / "source.json", 1)
                process.assert_not_called()
            self.assertEqual(result["status"], "SKIPPED")
            ValidateRetainedArtifacts(result, root)

    def test_malformed_results_are_infrastructure_errors(self):
        case = GenerateCases(np.radians([0, -7, 2, 57, 0, 0, 0]), (0,), (0,), (0,))[0]
        for payload in ("{", "[]", '{"passed": "true"}', "{}"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                def complete(command, **kwargs):
                    Path(command[command.index("--result") + 1]).write_text(payload, encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")
                with patch("run_sweep.subprocess.run", side_effect=complete):
                    result = RunCase(case, Path(directory), Path(directory) / "source.json", 1)
                self.assertEqual(result["status"], "ERROR")
                self.assertIn("invalid_result", result["failure"])

    def test_timeout_preserves_mixed_output(self):
        case = GenerateCases(np.radians([0, -7, 2, 57, 0, 0, 0]), (0,), (0,), (0,))[0]
        with tempfile.TemporaryDirectory() as directory:
            with patch("run_sweep.subprocess.run", side_effect=subprocess.TimeoutExpired("test", 1, output=b"out", stderr="err")):
                result = RunCase(case, Path(directory), Path(directory) / "source.json", 1)
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(Path(result["log_path"]).read_text(), "outerr")

    def test_resume_requires_matching_provenance(self):
        current = {"schema": "g1.sweep.provenance.v1", "sha256": {"input": "a"}}
        ValidateResumeProvenance({"provenance": current}, current)
        for previous in ({}, {"provenance": {"sha256": {"input": "b"}}}):
            with self.assertRaisesRegex(ValueError, "Resume blocked"):
                ValidateResumeProvenance(previous, current)

    def test_provenance_detects_changed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            state.write_text("{}", encoding="utf-8")
            before = BuildProvenance(state)
            self.assertEqual(before, BuildProvenance(state))
            state.write_text('{"changed": true}', encoding="utf-8")
            self.assertNotEqual(before, BuildProvenance(state))

    def test_isolated_model_load_and_exception_cleanup(self):
        import mujoco
        sys.path.insert(0, str(SCRIPTS_DIR))
        import run_mink_g1_right_arm_prototype as controller

        original_path = controller.g1.DEMO_XML
        original_bytes = original_path.read_bytes() if original_path.exists() else None
        original_prepare = controller._prepare_mink_xml
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with UseIsolatedModel(controller) as model_path:
                self.assertNotEqual(model_path, original_path)
                self.assertEqual(controller._prepare_mink_xml(), model_path)
                model = mujoco.MjModel.from_xml_path(str(model_path))
                self.assertGreater(model.nq, 0)
                raise RuntimeError("test failure")
        self.assertFalse(model_path.exists())
        self.assertEqual(controller.g1.DEMO_XML, original_path)
        self.assertIs(controller._prepare_mink_xml, original_prepare)
        self.assertEqual(original_path.read_bytes() if original_path.exists() else None, original_bytes)

    def test_sweep_outcome_distinguishes_completion_from_success(self):
        cases = [([], ("NO_EVALUATED_POSES", 3)),
                 (["SKIPPED"], ("NO_EVALUATED_POSES", 3)),
                 (["FAIL"], ("NO_SUCCESSFUL_POSES", 3)),
                 (["PASS", "FAIL"], ("COMPLETED_PARTIAL_MAP", 0)),
                 (["PASS"], ("COMPLETED_ALL_SAMPLED_POSES", 0)),
                 (["PASS", "ERROR"], ("INFRASTRUCTURE_ERROR", 2)),
                 (["UNKNOWN"], ("INFRASTRUCTURE_ERROR", 2))]
        for statuses, expected in cases:
            with self.subTest(statuses=statuses):
                self.assertEqual(GetSweepOutcome([{"status": s} for s in statuses]), expected)

    def test_offset_parser_is_finite_and_deduplicated(self) -> None:
        self.assertEqual(ParseOffsets("-15,0,15,0"), (-15.0, 0.0, 15.0))

    def test_case_grid_contains_base_pose(self) -> None:
        base = np.radians([6.0, -3.0, -18.0, 75.0, -15.0, -7.0, -2.0])
        cases = GenerateCases(base, (0.0,), (-15.0, 0.0, 15.0), (-15.0, 0.0, 15.0))
        self.assertEqual(9, len(cases))
        center = next(
            case
            for case in cases
            if case.roll_offset_deg == 0.0 and case.elbow_offset_deg == 0.0
        )
        np.testing.assert_allclose(center.pose_rad, base)

    def test_joint_limit_screen_rejects_unsafe_pose(self) -> None:
        self.assertIsNone(JointLimitFailure(tuple(np.radians([0, -7, 2, 57, 0, 0, 0]))))
        failure = JointLimitFailure(tuple(np.radians([0, -7, 2, 57, 0, 0, 100])))
        self.assertIn("right_wrist_yaw", failure or "")

    def test_html_map_contains_status_and_sample_warning(self) -> None:
        case = {
            "case_id": "p00_e00_r00",
            "status": "PASS",
            "passed": True,
            "pitch_offset_deg": 0.0,
            "roll_offset_deg": 0.0,
            "elbow_offset_deg": 0.0,
            "recovery_time_s": 3.8,
            "minimum_clearance_after_escape_m": 0.012,
            "failure": None,
            "result_path": str((HERE / "result.json").resolve()),
        }
        summary = {
            "run_name": "test",
            "generated_at_utc": "2026-08-28T00:00:00+00:00",
            "case_count": 1,
            "passed_count": 1,
            "success_rate_percent": 100.0,
            "total_wall_time_s": 1.0,
            "status_counts": {"PASS": 1},
            "base_q_deg": [0.0, -7.0, 2.0, 57.0, 0.0, 0.0, 0.0],
            "axes": {
                "shoulder_pitch_offset_deg": [0.0],
                "shoulder_roll_offset_deg": [0.0],
                "elbow_offset_deg": [0.0],
            },
            "cases": [case],
        }
        rendered = BuildHTML(summary)
        self.assertIn("BASE", rendered)
        self.assertIn("tested samples only", rendered)
        self.assertIn("12.00 mm", rendered)


if __name__ == "__main__":
    unittest.main()
