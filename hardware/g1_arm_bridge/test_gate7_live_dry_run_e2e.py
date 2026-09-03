#!/usr/bin/env python3
"""Real UDP E2E test for the Gate 7 live dry-run process."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
RECEIVER = BRIDGE / "gate7_live_dry_run.py"
GENERATOR = BRIDGE / "generate_fake_mink_targets.py"
BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from g1_teleop.gate7_simulation_feedback import parse_packet  # noqa: E402


def _free_udp_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


class Gate7LiveDryRunE2ETests(unittest.TestCase):
    def test_udp_stream_creates_candidates_without_output_path(self):
        port = _free_udp_port()
        feedback_port = _free_udp_port()
        feedback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        feedback_sock.bind(("127.0.0.1", feedback_port))
        feedback_sock.settimeout(0.1)
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            event_path = Path(directory) / "events.jsonl"
            receiver = subprocess.Popen(
                [
                    sys.executable,
                    str(RECEIVER),
                    "--mink-port",
                    str(port),
                    "--duration-s",
                    "3.0",
                    "--simulation-feedback-port",
                    str(feedback_port),
                    "--result-json",
                    str(result_path),
                    "--event-log",
                    str(event_path),
                ],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                time.sleep(1.5)
                generator = subprocess.run(
                    [
                        sys.executable,
                        str(GENERATOR),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--hz",
                        "60",
                        "--duration",
                        "1.0",
                    ],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                self.assertEqual(0, generator.returncode, generator.stdout + generator.stderr)
                output, _ = receiver.communicate(timeout=8.0)
            finally:
                if receiver.poll() is None:
                    receiver.kill()
                    receiver.wait(timeout=2.0)

            self.assertEqual(0, receiver.returncode, output)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertGreater(result["mink_packets"], 0)
            self.assertGreater(result["candidate_frames"], 0)
            self.assertEqual(0, result["denied_frames"])
            self.assertFalse(result["unitree_sdk_imported"])
            self.assertFalse(result["dds_entity_created"])
            self.assertFalse(result["publisher_present"])
            self.assertFalse(result["command_output_enabled"])
            self.assertTrue(result["simulation_feedback_enabled"])
            self.assertGreater(result["simulation_feedback_frames"], 0)
            self.assertTrue(event_path.exists())
            self.assertGreater(event_path.stat().st_size, 0)
            events = [
                json.loads(line)
                for line in event_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(
                any(event["state"] == "TRACK_MINK_RIGHT" for event in events)
            )
            self.assertFalse(
                any(
                    event.get("mink_active") is True
                    and event["reason"] == "input_stale"
                    and event.get("mink_transport_age_s", 1.0) <= 0.35
                    for event in events
                )
            )
            feedback_packets = []
            while True:
                try:
                    payload, _source = feedback_sock.recvfrom(16384)
                except socket.timeout:
                    break
                feedback_packets.append(parse_packet(payload))
            self.assertGreater(len(feedback_packets), 0)
            self.assertTrue(
                all(packet.stream_id for packet in feedback_packets)
            )
        feedback_sock.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
