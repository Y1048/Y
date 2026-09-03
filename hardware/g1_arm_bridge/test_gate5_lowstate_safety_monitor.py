#!/usr/bin/env python3
"""Gate 5 LowState Safety 모니터의 오프라인 계약 테스트."""

from __future__ import annotations

import json
import math
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from gate5_lowstate_safety_monitor import (
    LOWSTATE_TELEMETRY_SCHEMA,
    LowStatePacketError,
    PacketOrderTracker,
    evaluate_measured_hold,
    parse_lowstate_telemetry,
)
from safety_gate import SafetyConfig

HERE = Path(__file__).resolve().parent
MONITOR = HERE / "gate5_lowstate_safety_monitor.py"
READ_ONLY_FORWARDER = HERE / "read_only_lowstate.py"
SAFE_Q = tuple(
    math.radians(value)
    for value in (10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0)
)


def _packet(sequence: int, session_id: str = "offline-gate5-session") -> bytes:
    payload = {
        "schema": LOWSTATE_TELEMETRY_SCHEMA,
        "mode": "READ_ONLY_LOWSTATE",
        "topic": "rt/lowstate",
        "bridge_session_id": session_id,
        "sequence": sequence,
        "received_packets": sequence,
        "sent_at_unix": time.time(),
        "sent_at_unix_ns": time.time_ns(),
        "mode_pr": 0,
        "mode_machine": 5,
        "right_arm_q_rad": list(SAFE_Q),
        "right_arm_dq_rad_s": [0.0] * 7,
        "publisher_present": False,
        "command_output_enabled": False,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _base_state() -> dict[str, object]:
    return {
        "valid": True,
        "topic": "rt/odommodestate",
        "received_packets": 100,
        "invalid_packets": 0,
        "last_packet_age_s": 0.002,
        "position_m": [0.2, -0.1, 0.0],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        "velocity_mps": [0.1, 0.0, 0.0],
        "yaw_speed_rad_s": 0.05,
    }


def _unused_local_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
    finally:
        probe.close()


class Gate5LowStateSafetyTests(unittest.TestCase):
    def test_optional_base_state_is_parsed_without_changing_arm_contract(self) -> None:
        payload = json.loads(_packet(9))
        payload["base_state"] = _base_state()
        packet = parse_lowstate_telemetry(json.dumps(payload).encode("utf-8"))
        self.assertIsNotNone(packet.base_state)
        assert packet.base_state is not None
        self.assertTrue(packet.base_state.valid)
        self.assertEqual((0.2, -0.1, 0.0), packet.base_state.position_m)
        self.assertEqual(SAFE_Q, packet.measured_q_rad)

    def test_legacy_packet_without_base_state_remains_valid(self) -> None:
        packet = parse_lowstate_telemetry(_packet(8))
        self.assertIsNone(packet.base_state)

    def test_malformed_base_quaternion_is_rejected(self) -> None:
        payload = json.loads(_packet(7))
        payload["base_state"] = _base_state()
        payload["base_state"]["quaternion_xyzw"] = [0.0, 0.0, 0.0, 2.0]
        with self.assertRaisesRegex(LowStatePacketError, "normalized"):
            parse_lowstate_telemetry(json.dumps(payload).encode("utf-8"))

    def test_fresh_measured_pose_becomes_hold_candidate(self) -> None:
        packet = parse_lowstate_telemetry(_packet(10))
        self.assertEqual(0, packet.mode_pr)
        self.assertEqual(5, packet.mode_machine)
        decision = evaluate_measured_hold(
            packet,
            age_s=0.01,
            dt_s=1.0 / 30.0,
            config=SafetyConfig(),
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(packet.measured_q_rad, decision.command_q_rad)
        self.assertFalse(decision.rate_limited)

    def test_stale_measured_pose_has_no_candidate(self) -> None:
        packet = parse_lowstate_telemetry(_packet(11))
        decision = evaluate_measured_hold(
            packet,
            age_s=SafetyConfig().lowstate_timeout_s + 0.001,
            dt_s=1.0 / 30.0,
            config=SafetyConfig(),
        )
        self.assertFalse(decision.allowed)
        self.assertEqual("lowstate_stale", decision.reason)
        self.assertIsNone(decision.command_q_rad)

    def test_packet_contract_rejects_non_finite_joint(self) -> None:
        payload = json.loads(_packet(12).decode("utf-8"))
        payload["right_arm_q_rad"][3] = float("nan")
        with self.assertRaisesRegex(LowStatePacketError, "non-finite"):
            parse_lowstate_telemetry(json.dumps(payload).encode("utf-8"))

    def test_sequence_and_session_are_latched(self) -> None:
        tracker = PacketOrderTracker()
        tracker.accept(parse_lowstate_telemetry(_packet(20)))
        tracker.accept(parse_lowstate_telemetry(_packet(21)))
        with self.assertRaisesRegex(LowStatePacketError, "non_increasing"):
            tracker.accept(parse_lowstate_telemetry(_packet(21)))
        with self.assertRaisesRegex(LowStatePacketError, "session_changed"):
            tracker.accept(
                parse_lowstate_telemetry(_packet(22, "replacement-session"))
            )

    def test_runtime_accepts_fresh_packets_then_fails_closed_on_stale(self) -> None:
        port = _unused_local_port()
        with tempfile.TemporaryDirectory() as temp_dir:
            status_path = Path(temp_dir) / "status.json"
            event_path = Path(temp_dir) / "events.jsonl"
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(MONITOR),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--startup-timeout",
                    "2.0",
                    "--report-hz",
                    "20.0",
                    "--status-json",
                    str(status_path),
                    "--event-log",
                    str(event_path),
                ],
                cwd=HERE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                time.sleep(0.20)
                for sequence in range(100, 108):
                    sender.sendto(_packet(sequence), ("127.0.0.1", port))
                    time.sleep(1.0 / 30.0)
                output, _ = process.communicate(timeout=3.0)
            finally:
                sender.close()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=1.0)

            self.assertEqual(4, process.returncode, output)
            self.assertIn("[HOLD_READY]", output)
            self.assertIn("[FAULT]", output)
            self.assertIn("No command candidate was produced", output)

            status = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertEqual("FAULT", status["phase"])
            self.assertEqual("LOWSTATE_TIMEOUT", status["fault"]["code"])
            self.assertFalse(status["publisher_present"])
            self.assertFalse(status["command_output_enabled"])
            self.assertIsNone(status["details"]["candidate_q_rad"])
            self.assertFalse(status["details"]["candidate_forwarded"])

            events = [
                json.loads(line)
                for line in event_path.read_text(encoding="utf-8").splitlines()
            ]
            ready = [event for event in events if event["phase"] == "HOLD_READY"]
            self.assertTrue(ready)
            self.assertEqual(
                ready[-1]["details"]["measured_q_rad"],
                ready[-1]["details"]["candidate_q_rad"],
            )
            self.assertEqual("FAULT", events[-1]["phase"])

    def test_gate5_processes_have_no_command_capable_import(self) -> None:
        monitor_source = MONITOR.read_text(encoding="utf-8")
        forwarder_source = READ_ONLY_FORWARDER.read_text(encoding="utf-8")
        self.assertNotIn("unitree_sdk2py", monitor_source)
        self.assertNotIn("ChannelPublisher", monitor_source)
        self.assertNotIn("ChannelPublisher", forwarder_source)
        self.assertNotIn("LowCmd", monitor_source)
        self.assertNotIn("LowCmd", forwarder_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
