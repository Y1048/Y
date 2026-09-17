"""Real loopback UDP tests, with no robot address or SDK."""

import json
import queue
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from receive_vr_shadow import Run
from test_vr_input_offline import MakePacket


class ReceiverTests(unittest.TestCase):
    def test_loopback_active_and_pinch(self):
        with tempfile.TemporaryDirectory() as folder:
            ports, results = queue.Queue(), queue.Queue()
            output = Path(folder) / "run"
            thread = threading.Thread(target=lambda: results.put(
                Run(output, port=0, duration_s=1, ready=ports.put)))
            thread.start()
            try:
                port = ports.get(timeout=2)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(MakePacket(1), ("127.0.0.1", port))
                    time.sleep(0.03)
                    value = json.loads(MakePacket(2))
                    value["all_joint_q_rad"][22] = value["right_arm"]["joints"][0] = -0.12
                    sender.sendto(json.dumps(value).encode(), ("127.0.0.1", port))
                    time.sleep(0.03)
                    sender.sendto(MakePacket(3, input_command_mode="pinch_disengaged"), ("127.0.0.1", port))
            finally:
                thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            result = results.get_nowait()
            self.assertEqual(result["active_updates"], 1)
            self.assertEqual(result["stop_reason"], "input_disengaged")
            self.assertFalse(result["robot_command_sent"])
            rows = [json.loads(line) for line in (output / "samples.jsonl").read_text().splitlines()]
            active = next(row["candidate"] for row in rows if row["candidate"] and row["candidate"]["mode"] == "active")
            self.assertLess(active["upper_target_q_rad"][22], -0.1)
            self.assertEqual(active["upper_target_q_rad"][:22], [0.1]*22)

    def test_no_data_is_not_successful_input(self):
        with tempfile.TemporaryDirectory() as folder:
            result = Run(Path(folder) / "empty", port=0, duration_s=0.03)
            self.assertFalse(result["input_observed"])
            self.assertFalse(result["baseline_captured"])

    def test_baseline_then_silence_times_out(self):
        with tempfile.TemporaryDirectory() as folder:
            def SendBaseline(port):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(MakePacket(1), ("127.0.0.1", port))
            result = Run(Path(folder) / "loss", port=0, duration_s=1, ready=SendBaseline)
            self.assertEqual(result["stop_reason"], "receiver_timeout")
            self.assertTrue(result["baseline_captured"])
            self.assertFalse(result["input_observed"])

    def test_busy_port_reports_error_without_reuse(self):
        with tempfile.TemporaryDirectory() as folder, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            result = Run(Path(folder) / "busy", port=occupied.getsockname()[1], duration_s=0.03)
            self.assertIsNotNone(result["transport_error"])
            self.assertFalse(result["completed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
