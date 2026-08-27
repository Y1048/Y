from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.command_adapter import parse_command_packet  # noqa: E402
from g1_teleop.live_receiver import receive_available_commands  # noqa: E402
from g1_teleop.runtime_state import TeleopRuntimeStateMachine  # noqa: E402
from g1_teleop.watchdog import SessionSequenceWatchdog  # noqa: E402


class FakeSocket:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def recvfrom(self, _bufsize):
        if not self.payloads:
            raise BlockingIOError
        return self.payloads.pop(0), ("127.0.0.1", 5005)


def legacy_packet(sequence: int, x: float = 0.42) -> bytes:
    value = {
        "session_id": "legacy-session",
        "sequence": sequence,
        "command_state": "active",
        "right": {
            "pos": [x, -0.16, 1.05],
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": True,
        },
        "source": "quest3s_head_relative",
    }
    return json.dumps(value).encode("utf-8")


def legacy_disengage_packet(sequence: int) -> bytes:
    value = {
        "session_id": "legacy-session",
        "sequence": sequence,
        "command_state": "pinch_disengaged",
        "right": {
            "pos": [0.42, -0.16, 1.05],
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": False,
        },
        "source": "quest3s_head_relative",
    }
    return json.dumps(value).encode("utf-8")


def legacy_tracking_disengage_packet(sequence: int) -> bytes:
    value = {
        "session_id": "legacy-session",
        "sequence": sequence,
        "command_state": "tracking_disengaged",
        "right": {
            "pos": [0.42, -0.16, 1.05],
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": False,
        },
        "source": "quest3s_head_relative",
    }
    return json.dumps(value).encode("utf-8")


def v2_packet(sequence: int) -> bytes:
    pose = {
        "valid": True,
        "confidence": "high",
        "position_m": [0.3, 1.2, 0.4],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    }
    value = {
        "schema": "g1.teleop.pose.v2",
        "session_id": "v2-session",
        "sequence": sequence,
        "source_time_ns": 1,
        "frame_id": "unity_ovr_tracking",
        "mode": "active",
        "armed": True,
        "clutch": True,
        "calibration_request": 0,
        "head": pose,
        "right_wrist": pose,
        "left_wrist": pose,
    }
    return json.dumps(value).encode("utf-8")


class LiveReceiverTest(unittest.TestCase):
    def test_legacy_adapter_keeps_existing_target_coordinates(self):
        command = parse_command_packet(legacy_packet(1, x=0.55))
        self.assertEqual(command.protocol, "legacy_v0")
        np.testing.assert_allclose(command.position_m, [0.55, -0.16, 1.05])
        np.testing.assert_allclose(command.quaternion_xyzw, [0.0, 0.0, 0.0, 1.0])

    def test_receiver_drains_queue_and_keeps_newest_accepted_command(self):
        sock = FakeSocket([legacy_packet(1, 0.43), legacy_packet(2, 0.44)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)
        state = TeleopRuntimeStateMachine()

        batch = receive_available_commands(sock, watchdog, state)

        self.assertEqual(batch.accepted_count, 2)
        self.assertEqual(batch.rejected_count, 0)
        self.assertEqual(batch.latest_command.sequence, 2)
        self.assertAlmostEqual(batch.latest_command.position_m[0], 0.44)
        self.assertEqual(state.state, "active")

    def test_duplicate_sequence_is_rejected(self):
        sock = FakeSocket([legacy_packet(3), legacy_packet(3)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)

        batch = receive_available_commands(sock, watchdog)

        self.assertEqual(batch.accepted_count, 1)
        self.assertEqual(batch.rejected_count, 1)
        self.assertEqual(batch.latest_command.sequence, 3)

    def test_pinch_disengage_is_accepted_and_reported(self):
        sock = FakeSocket([legacy_disengage_packet(1)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)
        state = TeleopRuntimeStateMachine()

        batch = receive_available_commands(sock, watchdog, state)

        self.assertEqual(batch.accepted_count, 1)
        self.assertTrue(batch.operator_disengage)
        self.assertEqual(batch.latest_command.mode, "pinch_disengaged")
        self.assertEqual(state.state, "idle")

    def test_tracking_disengage_is_accepted_and_resets_operator_clutch(self):
        sock = FakeSocket([legacy_tracking_disengage_packet(1)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)
        state = TeleopRuntimeStateMachine()

        batch = receive_available_commands(sock, watchdog, state)

        self.assertEqual(batch.accepted_count, 1)
        self.assertTrue(batch.operator_disengage)
        self.assertEqual(batch.latest_command.mode, "tracking_disengaged")
        self.assertEqual(state.state, "idle")

    def test_v2_is_parsed_but_not_allowed_to_take_live_control_yet(self):
        sock = FakeSocket([v2_packet(1)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)
        state = TeleopRuntimeStateMachine()

        batch = receive_available_commands(sock, watchdog, state)

        self.assertIsNone(batch.latest_command)
        self.assertEqual(batch.accepted_count, 0)
        self.assertEqual(batch.rejected_count, 1)
        self.assertIsNone(watchdog.session_id)
        self.assertEqual(state.state, "idle")

    def test_v2_can_be_enabled_explicitly_after_mapping_is_ready(self):
        sock = FakeSocket([v2_packet(1)])
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.75)

        batch = receive_available_commands(sock, watchdog, allow_v2_control=True)

        self.assertEqual(batch.accepted_count, 1)
        self.assertEqual(batch.latest_command.protocol, "pose_v2")
        self.assertEqual(watchdog.session_id, "v2-session")


if __name__ == "__main__":
    unittest.main()
