#!/usr/bin/env python3
"""Process-level virtual hardware E2E test."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "gate7_hardware_virtual_e2e.py"


def _free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class Gate7HardwareVirtualE2ETests(unittest.TestCase):
    def test_complete_virtual_path_is_locked_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            relay_port = _free_udp_port()
            adapter_port = _free_udp_port()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--relay-port",
                    str(relay_port),
                    "--adapter-port",
                    str(adapter_port),
                    "--result-json",
                    str(result_path),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=20.0,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertTrue(result["passed"])
            self.assertFalse(result["publisher_present"])
            self.assertFalse(result["command_output_enabled"])
            self.assertEqual(2, result["relay"]["rejected_packets"])
            self.assertTrue(result["stale_lowstate_frame_removed"])
            self.assertEqual("SAFETY_HOLD", result["collision_state"])
            self.assertEqual("ruckig", result["trajectory_generator"])
            self.assertEqual("0.19.4", result["ruckig_version"])
            self.assertEqual(
                {"velocity": 1.0, "acceleration": 1.0, "jerk": 1.0},
                result["trajectory_scales"],
            )


if __name__ == "__main__":
    unittest.main()
