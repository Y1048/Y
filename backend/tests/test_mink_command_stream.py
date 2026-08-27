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

    def queue(self, *payloads: bytes) -> None:
        self.payloads.extend(payloads)

    def recvfrom(self, _bufsize):
        if not self.payloads:
            raise BlockingIOError
        return self.payloads.pop(0), ("127.0.0.1", 5005)


def packet(
    sequence: int,
    *,
    session_id: str = "session-a",
    mode: str = "active",
    position: tuple[float, float, float] = (0.42, -0.16, 1.05),
) -> bytes:
    valid = mode == "active"
    value = {
        "session_id": session_id,
        "sequence": sequence,
        "command_state": mode,
        "right": {
            "pos": list(position),
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": valid,
        },
        "source": "test",
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

        self.sock.queue(packet(2, mode="idle"))
        held = self.stream.poll(self.sock)
        self.assertEqual(held.control_state, "hold")
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
        self.assertTrue(disengaged.reset_clutch)
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
        self.assertTrue(disengaged.reset_clutch)
        self.assertFalse(disengaged.clutch_engaged)
        self.assertFalse(disengaged.workspace_fault)

        self.sock.queue(packet(3, position=(0.44, -0.15, 1.06)))
        reengaged = self.stream.poll(self.sock)
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


if __name__ == "__main__":
    unittest.main()
