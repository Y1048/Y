#!/usr/bin/env python3
"""Offline tests for Quest capture quality analysis and replay selection."""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from arm_sdk_teleop_contract import load_regular_arm_pose
from gate7_capture_mujoco_replay import SelectReplayWindow, SleepUntilStep
from gate7_capture_quality import BuildQualityReport, WriteHtmlReport, _decode_capture, _raw_metrics
from arm_sdk_teleop_contract import parse_mink_arm_sample
from gate7_hardware_virtual_e2e import _packet

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGULAR_PATH = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"


class Gate7CaptureQualityTests(unittest.TestCase):
    def test_capture_asset_hash_validation(self):
        regular = load_regular_arm_pose(REGULAR_PATH)
        cases = [(field, digest, digest == "a" * 64)
                 for field in ("model_assets_sha256", "model_joint_limits_sha256")
                 for digest in ["a" * 64, "bad", None, 42]]
        cases += [("mujoco_version", value, valid) for value, valid in
                  [("3.11.0", True), ("", False), (None, False), (42, False)]]
        for field, digest, valid in cases:
            with self.subTest(field=field, digest=digest), tempfile.TemporaryDirectory() as directory:
                value = json.loads(_packet(regular, 0))
                value["model_metadata"] = {"model_xml_sha256": "a" * 64,
                                           field: digest}
                records = [{"schema": "g1.mink.capture.manifest.v1", "hardware_output_authorized": False},
                           {"schema": "g1.mink.capture.packet.v1", "index": 0, "offset_s": 0,
                            "payload_base64": base64.b64encode(json.dumps(value).encode()).decode()}]
                path = Path(directory) / "capture.jsonl"
                path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
                if valid:
                    self.assertEqual(_decode_capture(path)[1][0]["value"]["model_metadata"], value["model_metadata"])
                else:
                    with self.assertRaisesRegex(ValueError, "invalid captured"):
                        _decode_capture(path)

    def test_capture_model_identity(self):
        regular = load_regular_arm_pose(REGULAR_PATH)
        for hashes, valid in [([None, None], True), (["a" * 64, "a" * 64], True),
                              (["a" * 64, "b" * 64], False), ([None, "a" * 64], False),
                              (["bad", "bad"], False)]:
            with self.subTest(hashes=hashes), tempfile.TemporaryDirectory() as directory:
                records = [{"schema": "g1.mink.capture.manifest.v1",
                            "hardware_output_authorized": False}]
                for index, digest in enumerate(hashes):
                    value = json.loads(_packet(regular, index))
                    if digest is not None:
                        value["model_metadata"] = {"model_xml_sha256": digest}
                    records.append({"schema": "g1.mink.capture.packet.v1", "index": index,
                        "offset_s": index * .02,
                        "payload_base64": base64.b64encode(json.dumps(value).encode()).decode()})
                path = Path(directory) / "capture.jsonl"
                path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
                if valid:
                    _, packets = _decode_capture(path)
                    self.assertEqual(len(packets), 2)
                    self.assertEqual(packets[0]["value"].get("model_metadata"),
                                     None if hashes[0] is None else {"model_xml_sha256": hashes[0]})
                else:
                    with self.assertRaises(ValueError):
                        _decode_capture(path)

    def test_equal_receive_times_keep_poses_without_dividing_by_zero(self):
        regular = load_regular_arm_pose(REGULAR_PATH)
        packets = []
        for index, offset in enumerate((0.0, 0.02, 0.02, 0.04, 0.06)):
            payload = _packet(regular, index)
            packets.append({"offset_s": offset,
                            "sample": parse_mink_arm_sample(payload),
                            "value": json.loads(payload)})
        result = _raw_metrics(packets, 0.25)
        self.assertEqual(5, result["active_packet_count"])
        self.assertEqual(1, result["zero_dt_active_intervals"])
        self.assertEqual(1, len(result["active_segments"]))
        json.dumps(result, allow_nan=False)

    def test_sleep_until_step_never_passes_negative_duration(self):
        sleep_calls = []
        self.assertFalse(
            SleepUntilStep(
                10.0,
                0.005,
                monotonic=lambda: 10.001,
                sleeper=sleep_calls.append,
            )
        )
        self.assertEqual([], sleep_calls)

        self.assertTrue(
            SleepUntilStep(
                10.0,
                0.005,
                monotonic=lambda: 9.999,
                sleeper=sleep_calls.append,
            )
        )
        self.assertGreater(sleep_calls[-1], 0.0)
        self.assertLessEqual(sleep_calls[-1], 0.005)

    def test_synthetic_capture_builds_quality_report_and_replay_window(self):
        regular = load_regular_arm_pose(REGULAR_PATH)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "capture.jsonl"
            records = [
                {
                    "schema": "g1.mink.capture.manifest.v1",
                    "capture_id": "quality-test",
                    "hardware_output_authorized": False,
                }
            ]
            for index in range(8):
                payload = _packet(regular, index)
                records.append(
                    {
                        "schema": "g1.mink.capture.packet.v1",
                        "capture_id": "quality-test",
                        "index": index,
                        "offset_s": index * 0.02,
                        "input_command_mode": "active",
                        "payload_base64": base64.b64encode(payload).decode("ascii"),
                    }
                )
            capture.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            report = BuildQualityReport(capture)
            self.assertEqual(8, report["raw_mink"]["active_packet_count"])
            self.assertEqual(1, len(report["raw_mink"]["active_segments"]))
            self.assertFalse(report["publisher_present"])
            self.assertFalse(report["hardware_output_authorized"])

            manifest, packets = _decode_capture(capture)
            self.assertEqual("quality-test", manifest["capture_id"])
            self.assertEqual(8, len(SelectReplayWindow(packets, 0.0)))

            html_path = root / "quality.html"
            WriteHtmlReport(report, html_path)
            document = html_path.read_text(encoding="utf-8")
            self.assertIn("G1 Gate 7 Quest Capture Quality", document)
            self.assertIn("No Unitree publisher or robot command", document)


if __name__ == "__main__":
    unittest.main()
