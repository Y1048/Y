#!/usr/bin/env python3
"""Offline tests for the Gate 7 Windows-to-WSL UDP relay."""

from __future__ import annotations

import json
import socket
import unittest
from pathlib import Path

from arm_sdk_teleop_contract import Gate7ContractError, load_regular_arm_pose
from g1_joint_contract import G1_29_JOINT_NAMES
from gate7_mink_wsl_relay import (
    MAX_RELAY_PACKET_BYTES,
    MinkOrderGuard,
    ValidateAndForward,
    ValidateRelayEndpoint,
)
from gate7_relay_provenance_guard import (
    COMMAND_PROVENANCE_LIVE,
    COMMAND_PROVENANCE_REPLAY,
    require_live_hardware_provenance,
    require_relay_token,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGULAR_POSE = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
RELAY_TOKEN = "0123456789abcdef0123456789abcdef"


def _packet(
    sequence: int,
    session_id: str = "relay-test",
    *,
    command_provenance: str | None = COMMAND_PROVENANCE_LIVE,
) -> bytes:
    pose = load_regular_arm_pose(REGULAR_POSE)
    all_q = list(pose.reference_all_joint_q_rad)
    for index, value in zip(range(15, 29), pose.dual_arm_q_rad):
        all_q[index] = value
    value = {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": sequence,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": all_q,
        "right_arm": {
            "joints": all_q[22:29],
            "active": True,
            "workspace_limited": False,
            "collision_limited": False,
            "minimum_clearance_m": 0.04,
            "command_state": "active",
        },
        "input_command_mode": "active",
        "session_id": session_id,
        "input_packet_age_s": 0.0,
        "timestamp": 1.0,
    }
    if command_provenance is not None:
        value["command_provenance"] = command_provenance
    return json.dumps(value).encode("utf-8")


class Gate7MinkWslRelayTests(unittest.TestCase):
    def test_endpoint_is_localhost_only(self):
        ValidateRelayEndpoint("127.0.0.1", "127.0.0.1", 5013)
        ValidateRelayEndpoint("127.0.0.1", "172.30.0.2", 5013)
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            ValidateRelayEndpoint("0.0.0.0", "172.30.0.2", 5013)

    def test_order_guard_rejects_duplicate_in_same_session(self):
        guard = MinkOrderGuard()
        guard.Accept("a", 1)
        with self.assertRaises(Gate7ContractError):
            guard.Accept("a", 1)
        guard.Accept("b", 0)

    def test_order_guard_rejects_retired_session_reappearance(self):
        guard = MinkOrderGuard()
        guard.Accept("a", 100)
        guard.Accept("b", 0)
        with self.assertRaisesRegex(Gate7ContractError, "retired"):
            guard.Accept("a", 101)
        self.assertEqual(("a",), guard.retired_sessions)

    def test_missing_provenance_is_rejected_before_forwarding(self):
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            with self.assertRaisesRegex(Gate7ContractError, "live_mink_provenance_required"):
                ValidateAndForward(
                    _packet(1, command_provenance=None),
                    MinkOrderGuard(),
                    sender,
                    ("127.0.0.1", 9),
                    relay_token=RELAY_TOKEN,
                )
        finally:
            sender.close()

    def test_recorded_replay_is_rejected_before_forwarding(self):
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            with self.assertRaisesRegex(Gate7ContractError, "recorded_replay"):
                ValidateAndForward(
                    _packet(
                        1,
                        session_id="replay-test",
                        command_provenance=COMMAND_PROVENANCE_REPLAY,
                    ),
                    MinkOrderGuard(),
                    sender,
                    ("127.0.0.1", 9),
                    relay_token=RELAY_TOKEN,
                )
        finally:
            sender.close()

    def test_live_packet_with_replay_session_prefix_is_rejected(self):
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            with self.assertRaisesRegex(Gate7ContractError, "replay_session"):
                ValidateAndForward(
                    _packet(
                        1,
                        session_id="replay-legacy-capture",
                        command_provenance=COMMAND_PROVENANCE_LIVE,
                    ),
                    MinkOrderGuard(),
                    sender,
                    ("127.0.0.1", 9),
                    relay_token=RELAY_TOKEN,
                )
        finally:
            sender.close()

    def test_valid_packet_is_live_token_bound_and_forwarded(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(1.0)
            target = receiver.getsockname()
            payload = _packet(1)
            ValidateAndForward(
                payload,
                MinkOrderGuard(),
                sender,
                target,
                relay_token=RELAY_TOKEN,
            )
            forwarded, _source = receiver.recvfrom(65535)
            parsed_original = json.loads(payload)
            parsed_forwarded = json.loads(forwarded)
            self.assertLessEqual(len(forwarded), MAX_RELAY_PACKET_BYTES)
            self.assertEqual(parsed_original["sequence"], parsed_forwarded["sequence"])
            self.assertEqual(
                parsed_original["all_joint_names"],
                parsed_forwarded["all_joint_names"],
            )
            self.assertEqual(
                parsed_original["right_arm"]["active"],
                parsed_forwarded["right_arm"]["active"],
            )
            self.assertEqual(
                COMMAND_PROVENANCE_LIVE,
                parsed_forwarded["command_provenance"],
            )
            self.assertEqual(RELAY_TOKEN, parsed_forwarded["relay_token"])
            require_relay_token(forwarded, RELAY_TOKEN)
            require_live_hardware_provenance(forwarded)
            with self.assertRaisesRegex(Gate7ContractError, "relay_token_mismatch"):
                require_relay_token(forwarded, "f" * 32)
        finally:
            receiver.close()
            sender.close()


if __name__ == "__main__":
    unittest.main()
