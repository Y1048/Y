import sys
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import diagnose_recorded_reach as diagnosis


class RecordedReachBoundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = diagnosis.probe
        with tempfile.TemporaryDirectory() as directory:
            path = p.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
            cls.model = p.mujoco.MjModel.from_xml_path(str(path))
        p.base._apply_operational_joint_limits(cls.model)

    def test_official_model_chain_upper_bound(self):
        self.assertAlmostEqual(diagnosis.GetReachUpperBound(self.model), 0.4103940645343519, places=10)

    def test_sampled_joint_poses_do_not_exceed_proven_bound(self):
        p = diagnosis.probe
        bound = diagnosis.GetReachUpperBound(self.model)
        configuration = p.mink.Configuration(self.model)
        rng = np.random.default_rng(1701)
        for _ in range(1000):
            q = p.base._initial_configuration(self.model)
            for name in p.base.g1.RIGHT_ARM_JOINTS:
                joint = p.base._joint_id(self.model, name)
                q[self.model.jnt_qposadr[joint]] = rng.uniform(*self.model.jnt_range[joint])
            configuration.update(q)
            shoulder = configuration.get_transform_frame_to_world("right_shoulder_pitch_link", "body").translation()
            wrist = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
            self.assertLessEqual(np.linalg.norm(wrist - shoulder), bound + 1e-10)

    def test_unrelated_branch_is_rejected(self):
        with self.assertRaises(ValueError):
            diagnosis.GetReachUpperBound(self.model, wrist_name="left_wrist_yaw_link")

    def test_offset_joint_requires_different_proof(self):
        joint = diagnosis.probe.base._joint_id(self.model, "right_elbow_joint")
        old = self.model.jnt_pos[joint].copy()
        try:
            self.model.jnt_pos[joint, 0] = 0.01
            with self.assertRaises(ValueError):
                diagnosis.GetReachUpperBound(self.model)
        finally:
            self.model.jnt_pos[joint] = old

    def test_cli_report_requires_review_even_for_inside_target(self):
        p = diagnosis.probe
        with tempfile.TemporaryDirectory() as directory:
            path = p.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
            model = p.mujoco.MjModel.from_xml_path(str(path))
            p.base._apply_operational_joint_limits(model)
            q = p.base._initial_configuration(model)
            configuration = p.mink.Configuration(model)
            configuration.update(q)
            wrist = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation().tolist()
            ids = [int(model.jnt_qposadr[p.base._joint_id(model, name)]) for name in p.base.g1.G1_29_JOINTS]
            packet = {"value": {"all_joint_q_rad": q[ids].tolist(), "right_arm": {
                "wrist_position": wrist, "target_position": wrist}}}
            output = Path(directory) / "result.json"
            with patch.object(sys, "argv", ["diagnose_recorded_reach", "mock.jsonl", "--result-json", str(output)]), \
                 patch.object(p, "_decode_capture", return_value=({"capture_id": "fixture"}, [packet])), \
                 patch.object(p.base.g1, "DEMO_XML", path), \
                 patch.object(diagnosis.replay, "GetActiveSegments", return_value=[(packet, [packet])]), \
                 patch.object(diagnosis.replay, "GetRecordedTargets", return_value=([0.0], [None])):
                self.assertEqual(diagnosis.main(), 3)
            report = json.loads(output.read_text())
            self.assertEqual(report["quality_status"], "REVIEW_REQUIRED")
            self.assertFalse(report["robot_command"])
            self.assertEqual(report["segments"][0]["provably_outside_packets"], 0)

    def test_bad_capture_saves_failure(self):
        for contents in (None, "{invalid json"):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as directory:
                capture = Path(directory) / "capture.jsonl"
                output = Path(directory) / "result.json"
                if contents is not None:
                    capture.write_text(contents)
                with patch.object(sys, "argv", ["reach", str(capture), "--result-json", str(output)]):
                    self.assertEqual(diagnosis.main(), 1)
                report = json.loads(output.read_text())
                self.assertEqual(report["quality_status"], "FAIL")
                self.assertIn("decode failed", report["error"])

    def test_fk_mismatch_saves_failure(self):
        packet = {"value": {"all_joint_q_rad": [0.0] * 29,
                            "right_arm": {"wrist_position": [100, 100, 100],
                                          "target_position": [0, 0, 0]}}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            with patch.object(sys, "argv", ["reach", "fixture", "--result-json", str(output)]), \
                 patch.object(diagnosis.probe, "_decode_capture", return_value=({"capture_id": "fixture"}, [packet])), \
                 patch.object(diagnosis.replay, "GetActiveSegments", return_value=[(packet, [packet])]):
                self.assertEqual(diagnosis.main(), 1)
            self.assertIn("FK does not match", json.loads(output.read_text())["error"])

    def test_model_failure_replaces_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            output.write_text('{"quality_status": "REVIEW_REQUIRED"}')
            with patch.object(sys, "argv", ["reach", "fixture", "--result-json", str(output)]), \
                 patch.object(diagnosis.probe, "_decode_capture", return_value=({}, [])), \
                 patch.object(diagnosis.replay, "GetActiveSegments", return_value=[({}, [{}])]), \
                 patch.object(diagnosis.probe.base, "LoadMinkModel", side_effect=ValueError("bad model")):
                self.assertEqual(diagnosis.main(), 1)
            report = json.loads(output.read_text())
            self.assertEqual(report["quality_status"], "FAIL")
            self.assertIn("bad model", report["error"])
            self.assertFalse(report["robot_command"])

    def test_runtime_failure_saves_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            with patch.object(sys, "argv", ["reach", "fixture", "--result-json", str(output)]), \
                 patch.object(diagnosis, "RunDiagnosis", side_effect=RuntimeError("solver failed")):
                self.assertEqual(diagnosis.main(), 1)
            self.assertIn("solver failed", json.loads(output.read_text())["error"])

    def test_unwritable_report_does_not_claim_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            with patch.object(sys, "argv", ["reach", "missing", "--result-json", str(output)]), \
                 patch.object(Path, "write_text", side_effect=PermissionError("denied")), \
                 patch("builtins.print") as printer:
                self.assertEqual(diagnosis.main(), 1)
            messages = " ".join(str(call) for call in printer.call_args_list)
            self.assertIn("existing report is stale", messages)
            self.assertNotIn("Result saved to:", messages)


if __name__ == "__main__":
    unittest.main()
