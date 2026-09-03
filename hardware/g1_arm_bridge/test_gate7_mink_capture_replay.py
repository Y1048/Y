#!/usr/bin/env python3
"""Offline process tests for Mink capture, replay and regression."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from arm_sdk_teleop_contract import load_regular_arm_pose
from gate7_capture_regression import BuildRegressionTrace, CompareTrace
from gate7_hardware_virtual_e2e import _packet
from gate7_mink_replay import LoadCapture

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
REGULAR = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class Gate7MinkCaptureReplayTests(unittest.TestCase):
    def test_record_forward_replay_and_regression_are_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture_path = root / "capture.jsonl"
            listen_port = _free_udp_port()
            forward_port = _free_udp_port()
            forward_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            forward_receiver.bind(("127.0.0.1", forward_port))
            forward_receiver.settimeout(2.0)
            recorder = subprocess.Popen(
                [
                    sys.executable,
                    str(BRIDGE / "gate7_mink_capture.py"),
                    "--listen-port",
                    str(listen_port),
                    "--forward-port",
                    str(forward_port),
                    "--duration-s",
                    "1.0",
                    "--output",
                    str(capture_path),
                ],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            regular = load_regular_arm_pose(REGULAR)
            try:
                time.sleep(0.2)
                for sequence in range(6):
                    sender.sendto(
                        _packet(regular, sequence),
                        ("127.0.0.1", listen_port),
                    )
                    time.sleep(0.02)
                forwarded = [forward_receiver.recvfrom(65535)[0] for _ in range(6)]
                output, _ = recorder.communicate(timeout=3.0)
            finally:
                sender.close()
                forward_receiver.close()
                if recorder.poll() is None:
                    recorder.terminate()
                    recorder.wait(timeout=2.0)
            self.assertEqual(0, recorder.returncode, output)
            _manifest, packets = LoadCapture(capture_path)
            self.assertEqual(6, len(packets))
            self.assertEqual([packet.payload for packet in packets], forwarded)

            replay_port = _free_udp_port()
            replay_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            replay_receiver.bind(("127.0.0.1", replay_port))
            replay_receiver.settimeout(2.0)
            try:
                replay = subprocess.run(
                    [
                        sys.executable,
                        str(BRIDGE / "gate7_mink_replay.py"),
                        str(capture_path),
                        "--port",
                        str(replay_port),
                        "--no-timing",
                    ],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                replayed = [replay_receiver.recvfrom(65535)[0] for _ in range(6)]
            finally:
                replay_receiver.close()
            self.assertEqual(0, replay.returncode, replay.stdout + replay.stderr)
            self.assertEqual(6, len(replayed))

            first = BuildRegressionTrace(capture_path, 13.0)
            second = BuildRegressionTrace(capture_path, 13.0)
            matched, differences = CompareTrace(first, second)
            self.assertTrue(matched, differences)
            self.assertEqual("REGULAR_HOLD", first["final_state"])
            self.assertFalse(first["publisher_present"])


if __name__ == "__main__":
    unittest.main()
