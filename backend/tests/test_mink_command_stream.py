from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.mink_command_stream import MinkCommandStream  # noqa: E402


class FakeSocket:
    def __init__(self) -> None:
        self.payloads: list[bytes] = []
        self.source_host = "127.0.0.1"

    def queue(self, *payloads: bytes) -> None:
        self.payloads.extend(payloads)

    def recvfrom(self, _bufsize):
        if not self.payloads:
            raise BlockingIOError
        return self.payloads.pop(0), (self.source_host, 5005)


def packet(
    sequence: int,
    *,
    session_id: str = "session-a",
    mode: str = "active",
    position: tuple[float, float, float] = (0.42, -0.16, 1.05),
    source: str = "quest3s_head_relative",
    timestamp_s: float | None = None,
) -> bytes:
    valid = mode == "active"
    if timestamp_s is None:
        timestamp_s = sequence / 60.0
    value = {
        "session_id": session_id,
        "sequence": sequence,
        "command_state": mode,
        "right": {
            "pos": list(position),
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": valid,
        },
        "source": source,
        "timestamp": timestamp_s,
    }
    return json.dumps(value).encode("utf-8")


class MinkCommandStreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sock = FakeSocket()
        self.stream = MinkCommandStream(
            np.array([0.3, 0.1, 0.8]),
            np.array([0.0, 0.0, 0.0, 1.0]),
            input_timeout_s=0.75,
        )

    def test_tracking_idle_holds_reference_and_active_recovers_without_rebase(self):
        self.sock.queue(packet(1, position=(0.45, -0.12, 1.08)))
        first = self.stream.poll(self.sock)
        self.assertTrue(first.engage_clutch)
        self.assertTrue(first.command_active)
        self.assertEqual("127.0.0.1", first.input_source_host)

        self.sock.queue(packet(2, mode="idle"))
        held = self.stream.poll(self.sock)
        self.assertEqual(held.control_state, "hold")
        self.assertEqual(held.input_command_mode, "idle")
        self.assertTrue(held.clutch_engaged)
        self.assertFalse(held.command_active)
        self.assertFalse(held.reset_clutch)
        np.testing.assert_allclose(held.target_position_m, [0.45, -0.12, 1.08])

        self.sock.queue(packet(3, position=(0.47, -0.10, 1.10)))
        resumed = self.stream.poll(self.sock)
        self.assertTrue(resumed.command_active)
        self.assertFalse(resumed.engage_clutch)
        self.assertFalse(resumed.reset_clutch)

    def test_network_timeout_holds_without_disengaging(self):
        self.sock.queue(packet(1))
        active = self.stream.poll(self.sock)
        stale_now = (
            self.stream.watchdog.last_arrival_time_ns
            + self.stream.input_timeout_ns
            + 1
        )

        held = self.stream.poll(self.sock, now_ns=stale_now)

        self.assertTrue(active.command_active)
        self.assertEqual(held.control_state, "hold")
        self.assertEqual(held.input_command_mode, "active")
        self.assertTrue(held.clutch_engaged)
        self.assertFalse(held.reset_clutch)

    def test_workspace_exit_is_an_automatic_disengage_path(self):
        self.sock.queue(packet(1))
        self.stream.poll(self.sock)
        self.sock.queue(packet(2, mode="workspace_exit"))

        exited = self.stream.poll(self.sock)

        self.assertEqual(exited.control_state, "workspace_fault")
        self.assertTrue(exited.workspace_fault)
        self.assertTrue(exited.reset_clutch)
        self.assertFalse(exited.engage_clutch)
        self.assertFalse(exited.clutch_engaged)

        self.sock.queue(packet(3, position=(0.40, -0.14, 1.02)))
        reengaged = self.stream.poll(self.sock)
        self.assertTrue(reengaged.engage_clutch)
        self.assertTrue(reengaged.command_active)

    def test_sustained_pinch_is_an_intentional_manual_disengage_path(self):
        self.sock.queue(packet(1))
        self.stream.poll(self.sock)
        self.sock.queue(packet(2, mode="pinch_disengaged"))

        disengaged = self.stream.poll(self.sock)

        self.assertEqual(disengaged.control_state, "idle")
        self.assertEqual(disengaged.input_command_mode, "pinch_disengaged")
        self.assertTrue(disengaged.reset_clutch)
        self.assertFalse(disengaged.engage_clutch)
        self.assertFalse(disengaged.clutch_engaged)
        self.assertFalse(disengaged.workspace_fault)

        self.sock.queue(packet(3, position=(0.44, -0.15, 1.06)))
        reengaged = self.stream.poll(self.sock)
        self.assertTrue(reengaged.engage_clutch)
        self.assertTrue(reengaged.command_active)

    def test_confirmed_tracking_loss_resets_clutch_before_reengagement(self):
        self.sock.queue(packet(1))
        self.stream.poll(self.sock)
        self.sock.queue(packet(2, mode="tracking_disengaged"))

        disengaged = self.stream.poll(self.sock)

        self.assertEqual(disengaged.control_state, "idle")
        self.assertEqual(disengaged.input_command_mode, "tracking_disengaged")
        self.assertTrue(disengaged.reset_clutch)
        self.assertFalse(disengaged.engage_clutch)
        self.assertFalse(disengaged.clutch_engaged)
        self.assertFalse(disengaged.workspace_fault)

        self.sock.queue(packet(3, position=(0.44, -0.15, 1.06)))
        reengaged = self.stream.poll(self.sock)
        self.assertTrue(reengaged.engage_clutch)
        self.assertTrue(reengaged.command_active)

    def test_pinch_backlog_preserves_one_disengaged_cycle(self):
        self.sock.queue(packet(1, position=(0.45, -0.12, 1.08)))
        self.stream.poll(self.sock)
        previous_target = self.stream._target_position_m.copy()
        self.sock.queue(
            packet(2, mode="pinch_disengaged"),
            packet(3, position=(0.62, 0.02, 1.24)),
        )

        disengaged = self.stream.poll(self.sock)

        self.assertTrue(disengaged.reset_clutch)
        self.assertFalse(disengaged.engage_clutch)
        self.assertFalse(disengaged.command_active)
        self.assertFalse(disengaged.clutch_engaged)
        self.assertEqual(disengaged.input_command_mode, "pinch_disengaged")
        np.testing.assert_allclose(disengaged.target_position_m, previous_target)
        self.assertEqual(len(self.sock.payloads), 1)

        reengaged = self.stream.poll(self.sock)
        self.assertFalse(reengaged.reset_clutch)
        self.assertTrue(reengaged.engage_clutch)
        self.assertTrue(reengaged.command_active)
        np.testing.assert_allclose(reengaged.target_position_m, [0.62, 0.02, 1.24])

    def test_workspace_backlog_preserves_one_fault_cycle(self):
        self.sock.queue(packet(1))
        self.stream.poll(self.sock)
        self.sock.queue(
            packet(2, mode="workspace_exit"),
            packet(3, position=(0.40, -0.14, 1.02)),
        )

        faulted = self.stream.poll(self.sock)

        self.assertTrue(faulted.workspace_fault)
        self.assertEqual(faulted.control_state, "workspace_fault")
        self.assertEqual(faulted.input_command_mode, "workspace_exit")
        self.assertTrue(faulted.reset_clutch)
        self.assertFalse(faulted.engage_clutch)
        self.assertFalse(faulted.command_active)
        self.assertEqual(len(self.sock.payloads), 1)

        reengaged = self.stream.poll(self.sock)
        self.assertFalse(reengaged.workspace_fault)
        self.assertTrue(reengaged.engage_clutch)
        self.assertTrue(reengaged.command_active)

    def test_duplicate_is_rejected_without_changing_target(self):
        self.sock.queue(packet(4, position=(0.46, -0.11, 1.09)))
        self.stream.poll(self.sock)
        self.sock.queue(packet(4, position=(0.70, 0.20, 1.40)))

        duplicate = self.stream.poll(self.sock)

        self.assertEqual(duplicate.accepted_count, 0)
        self.assertEqual(duplicate.rejected_count, 1)
        np.testing.assert_allclose(duplicate.target_position_m, [0.46, -0.11, 1.09])

    def test_stale_session_takeover_rebases_once(self):
        self.sock.queue(packet(1))
        self.stream.poll(self.sock)
        self.stream.watchdog.last_arrival_time_ns = (
            time.monotonic_ns() - self.stream.watchdog.takeover_after_ns - 1
        )
        self.sock.queue(packet(1, session_id="session-b"))

        takeover = self.stream.poll(self.sock)

        self.assertEqual(takeover.session_id, "session-b")
        self.assertTrue(takeover.reset_clutch)
        self.assertTrue(takeover.engage_clutch)
        self.assertTrue(takeover.command_active)

    def test_retired_session_cannot_take_control_again(self):
        self.sock.queue(packet(1, session_id="session-a"))
        self.stream.poll(self.sock)
        self.stream.watchdog.last_arrival_time_ns -= self.stream.watchdog.takeover_after_ns + 1
        self.sock.queue(packet(1, session_id="session-b"))
        takeover = self.stream.poll(self.sock)
        self.assertEqual("session-b", takeover.session_id)

        self.stream.watchdog.last_arrival_time_ns -= self.stream.watchdog.takeover_after_ns + 1
        self.sock.queue(packet(2, session_id="session-a"))
        replay = self.stream.poll(self.sock)
        self.assertEqual(0, replay.accepted_count)
        self.assertGreaterEqual(replay.rejected_count, 1)
        self.assertEqual("session-b", replay.session_id)

    def test_wrong_sender_host_is_rejected(self):
        self.sock.source_host = "192.168.1.20"
        self.sock.queue(packet(1))
        rejected = self.stream.poll(self.sock)
        self.assertEqual(0, rejected.accepted_count)
        self.assertEqual(1, rejected.rejected_count)
        self.assertFalse(rejected.command_active)

    def test_missing_source_timestamp_is_rejected(self):
        raw = json.loads(packet(1))
        raw.pop("timestamp")
        self.sock.queue(json.dumps(raw).encode("utf-8"))
        rejected = self.stream.poll(self.sock)
        self.assertEqual(0, rejected.accepted_count)
        self.assertEqual(1, rejected.rejected_count)
        self.assertFalse(rejected.command_active)


if __name__ == "__main__":
    unittest.main()
