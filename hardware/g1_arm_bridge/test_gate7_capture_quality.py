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
