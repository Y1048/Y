#!/usr/bin/env python3
"""Offline tests for Gate 7 recorded-replay provenance separation."""

from __future__ import annotations

import json
import unittest

from arm_sdk_teleop_contract import Gate7ContractError
from g1_joint_contract import G1_29_JOINT_NAMES
from gate7_mink_replay import LIVE_GATE7_RELAY_PORT, NormalizePayload, validate_replay_destination
from gate7_relay_provenance_guard import (
    COMMAND_PROVENANCE_REPLAY,
    require_live_candidate_for_relay,
)


class Gate7ReplayProvenanceTests(unittest.TestCase):
    def _packet(self) -> bytes:
        return json.dumps(
            {
                "schema": "g1.mink.right_arm.state.v1",
                "sequence": 1,
                "state_source": "mink_simulation",
                "all_joint_names": list(G1_29_JOINT_NAMES),
                "all_joint_q_rad": [0.0] * 29,
                "right_arm": {
                    "joints": [0.0] * 7,
                    "active": True,
                    "workspace_limited": False,
                    "collision_limited": False,
                    "minimum_clearance_m": 0.04,
                    "command_state": "active",
                },
                "input_command_mode": "active",
                "session_id": "captured-live-session",
                "input_packet_age_s": 99.0,
                "timestamp": 1.0,
            }
        ).encode("utf-8")

    def test_normalized_replay_is_explicitly_marked(self) -> None:
        normalized = NormalizePayload(
            self._packet(),
            session_id="replay-0123456789abcdef",
            sequence=0,
        )
        value = json.loads(normalized)
        self.assertEqual(COMMAND_PROVENANCE_REPLAY, value["command_provenance"])
        self.assertEqual("replay-0123456789abcdef", value["session_id"])
        self.assertEqual(0.0, value["input_packet_age_s"])
        with self.assertRaisesRegex(Gate7ContractError, "recorded_replay"):
            require_live_candidate_for_relay(normalized)

    def test_exact_transport_cannot_target_live_relay_port(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact-transport"):
            validate_replay_destination(
                host="127.0.0.1",
                port=LIVE_GATE7_RELAY_PORT,
                exact_transport=True,
            )

    def test_exact_transport_can_use_dedicated_offline_port(self) -> None:
        validate_replay_destination(
            host="127.0.0.1",
            port=15008,
            exact_transport=True,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
