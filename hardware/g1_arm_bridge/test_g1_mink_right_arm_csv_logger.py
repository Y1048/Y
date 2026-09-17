import json
import math
import csv
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from .g1_mink_right_arm_csv_logger import JOINT_NAMES, parse_mink_state, row_for


def packet():
    q = [index / 100.0 for index in range(29)]
    return {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": 7,
        "state_source": "mink_simulation",
        "all_joint_names": [f"joint_{i}" for i in range(22)] + list(JOINT_NAMES),
        "all_joint_q_rad": q,
        "right_arm": {
            "joints": q[22:29], "active": True,
            "command_state": "tracking", "position_error": 0.01,
            "minimum_clearance_m": 0.02, "collision_limited": False,
            "trajectory_status": "accepted",
        },
        "input_command_mode": "tracked",
        "session_id": "fixture",
        "input_packet_age_s": 0.003,
        "timestamp": 123.5,
    }


class MinkCsvLoggerTests(unittest.TestCase):
    def test_schema_and_joint_order_round_trip(self):
        raw = json.dumps(packet(), separators=(",", ":"))
        parsed = parse_mink_state(raw.encode())
        self.assertEqual(parsed["q_rad"], [index / 100.0 for index in range(22, 29)])
        row = row_for(parsed, 10.0)
        self.assertEqual(row[-8:-1], parsed["q_rad"])
        self.assertEqual(row[-1], raw)

    def test_duplicate_joint_copy_must_match(self):
        value = packet()
        value["right_arm"]["joints"][0] += 0.1
        with self.assertRaisesRegex(ValueError, "duplicate mismatch"):
            parse_mink_state(json.dumps(value).encode())

    def test_nonfinite_rejected(self):
        value = packet()
        value["all_joint_q_rad"][22] = math.nan
        with self.assertRaisesRegex(ValueError, "all_joint_q_rad"):
            parse_mink_state(json.dumps(value).encode())

    def test_duplicate_json_key_rejected(self):
        raw = b'{"schema":"g1.mink.right_arm.state.v1","schema":"x"}'
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            parse_mink_state(raw)

    def test_non_utf8_raw_packet_rejected(self):
        with self.assertRaises(UnicodeDecodeError):
            parse_mink_state(b"\xff")

    def test_receive_only_loopback_writes_csv(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        script = Path(__file__).with_name("g1_mink_right_arm_csv_logger.py")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ik.csv"
            process = subprocess.Popen([
                sys.executable, "-B", str(script), "--output", str(output),
                "--port", str(port), "--duration-seconds", "0.8",
            ])
            try:
                time.sleep(0.2)
                sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sender.sendto(json.dumps(packet()).encode(), ("127.0.0.1", port))
                sender.close()
                self.assertEqual(process.wait(timeout=3), 0)
            finally:
                if process.poll() is None:
                    process.kill()
            with output.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["q22_right_shoulder_pitch_joint_rad"], "0.22")
            self.assertEqual(json.loads(rows[0]["raw_json_text"])["sequence"], 7)


if __name__ == "__main__":
    unittest.main()
