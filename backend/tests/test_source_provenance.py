from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.command_adapter import parse_command_packet  # noqa: E402
from g1_teleop.source_provenance import CommandSourceGuard  # noqa: E402


def command(sequence: int, timestamp_s: float, source: str = "quest3s_head_relative"):
    payload = {
        "session_id": "source-session",
        "sequence": sequence,
        "command_state": "active",
        "right": {
            "pos": [0.42, -0.16, 1.05],
            "rot": [0.0, 0.0, 0.0, 1.0],
            "valid": True,
        },
        "timestamp": timestamp_s,
        "source": source,
    }
    return parse_command_packet(json.dumps(payload).encode("utf-8"))


class CommandSourceGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = CommandSourceGuard(maximum_source_lag_s=0.75)

    def test_legacy_timestamp_is_preserved_in_source_clock_domain(self) -> None:
        item = command(1, 12.345678)
        self.assertEqual(12_345_678_000, item.source_time_ns)
        self.assertEqual("quest3s_head_relative", item.frame_id)

    def test_same_pc_loopback_and_relative_clock_progress_are_accepted(self) -> None:
        first = self.guard.accept(
            command(1, 10.0),
            source_host="127.0.0.1",
            arrival_time_ns=100_000_000_000,
        )
        second = self.guard.accept(
            command(2, 10.1),
            source_host="127.0.0.1",
            arrival_time_ns=100_105_000_000,
        )
        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertAlmostEqual(0.005, second.estimated_source_lag_s, places=6)

    def test_controller_pause_backlog_older_than_timeout_is_rejected(self) -> None:
        self.guard.accept(
            command(1, 20.0),
            source_host="127.0.0.1",
            arrival_time_ns=200_000_000_000,
        )
        stale = self.guard.accept(
            command(2, 20.1),
            source_host="127.0.0.1",
            arrival_time_ns=201_000_000_000,
        )
        self.assertFalse(stale.accepted)
        self.assertGreater(stale.estimated_source_lag_s, 0.75)

    def test_newer_packet_can_catch_up_after_stale_backlog(self) -> None:
        self.guard.accept(
            command(1, 30.0),
            source_host="127.0.0.1",
            arrival_time_ns=300_000_000_000,
        )
        self.guard.accept(
            command(2, 30.1),
            source_host="127.0.0.1",
            arrival_time_ns=301_000_000_000,
        )
        caught_up = self.guard.accept(
            command(3, 31.0),
            source_host="127.0.0.1",
            arrival_time_ns=301_005_000_000,
        )
        self.assertTrue(caught_up.accepted)
        self.assertLess(caught_up.estimated_source_lag_s, 0.75)

    def test_wrong_host_source_or_nonincreasing_source_time_is_rejected(self) -> None:
        item = command(1, 40.0)
        self.assertFalse(
            self.guard.accept(
                item,
                source_host="192.168.1.4",
                arrival_time_ns=400_000_000_000,
            ).accepted
        )
        wrong_source = command(2, 40.1, source="other_sender")
        self.assertFalse(
            self.guard.accept(
                wrong_source,
                source_host="127.0.0.1",
                arrival_time_ns=400_100_000_000,
            ).accepted
        )

        first = self.guard.accept(
            command(3, 40.2),
            source_host="127.0.0.1",
            arrival_time_ns=400_200_000_000,
        )
        self.assertTrue(first.accepted)
        repeated_time = self.guard.accept(
            command(4, 40.2),
            source_host="127.0.0.1",
            arrival_time_ns=400_220_000_000,
        )
        self.assertFalse(repeated_time.accepted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
