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
from g1_teleop.protocol import (  # noqa: E402
    POSE_FRAME,
    POSE_SCHEMA_V2,
    STATE_SCHEMA_V2,
    PosePacketV2,
    ProtocolError,
    StatePacketV2,
)


def tracked(valid: bool = True) -> dict[str, object]:
    return {
        "valid": valid,
        "confidence": "high" if valid else "unknown",
        "position_m": [0.1, 0.2, 0.3] if valid else [0.0, 0.0, 0.0],
        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    }


def pose_v2(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema": POSE_SCHEMA_V2,
        "session_id": "session-a",
        "sequence": 7,
        "source_time_ns": 123456789,
        "frame_id": POSE_FRAME,
        "mode": "active",
        "armed": True,
        "clutch": True,
        "calibration_request": 0,
        "head": tracked(),
        "right_wrist": tracked(),
        "left_wrist": tracked(False),
    }
    packet.update(overrides)
    return packet


class ProtocolV2Test(unittest.TestCase):
    def test_pose_v2_round_trip(self):
        packet = PosePacketV2.from_json(json.dumps(pose_v2()))
        reparsed = PosePacketV2.from_json(packet.to_json())

        self.assertEqual(reparsed.session_id, "session-a")
        self.assertEqual(reparsed.sequence, 7)
        self.assertEqual(reparsed.mode, "active")
        np.testing.assert_allclose(reparsed.right_wrist.position_m, [0.1, 0.2, 0.3])

    def test_pose_v2_rejects_boolean_sequence(self):
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(sequence=True)))

    def test_pose_v2_rejects_empty_session(self):
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(session_id="")))

    def test_pose_v2_rejects_unknown_mode(self):
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(mode="teleport")))

    def test_pose_v2_active_requires_valid_right_wrist(self):
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(right_wrist=tracked(False))))

    def test_pose_v2_rejects_nonfinite_position(self):
        bad_pose = tracked()
        bad_pose["position_m"] = [0.0, float("nan"), 0.0]
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(right_wrist=bad_pose)))

    def test_pose_v2_rejects_zero_quaternion(self):
        bad_pose = tracked()
        bad_pose["quaternion_xyzw"] = [0.0, 0.0, 0.0, 0.0]
        with self.assertRaises(ProtocolError):
            PosePacketV2.from_json(json.dumps(pose_v2(right_wrist=bad_pose)))

    def test_legacy_adapter_preserves_live_command(self):
        legacy = {
            "session_id": "legacy-a",
            "sequence": 3,
            "command_state": "active",
            "right": {
                "pos": [0.42, -0.16, 1.05],
                "rot": [0.0, 0.0, 0.0, 1.0],
                "valid": True,
            },
        }
        command = parse_command_packet(json.dumps(legacy))

        self.assertEqual(command.protocol, "legacy_v0")
        self.assertTrue(command.valid)
        self.assertEqual(command.mode, "active")
        np.testing.assert_allclose(command.position_m, [0.42, -0.16, 1.05])

    def test_v2_adapter_produces_internal_command(self):
        command = parse_command_packet(json.dumps(pose_v2()))

        self.assertEqual(command.protocol, "pose_v2")
        self.assertEqual(command.session_id, "session-a")
        self.assertTrue(command.valid)
        np.testing.assert_allclose(command.position_m, [0.1, 0.2, 0.3])

    def test_v2_hold_is_not_a_new_target(self):
        command = parse_command_packet(json.dumps(pose_v2(mode="hold", armed=True, clutch=True)))
        self.assertFalse(command.valid)
        self.assertEqual(command.mode, "hold")

    def test_unknown_schema_is_not_treated_as_legacy(self):
        packet = pose_v2(schema="g1.teleop.pose.v99")
        with self.assertRaises(ProtocolError):
            parse_command_packet(json.dumps(packet))

    def test_legacy_adapter_rejects_boolean_sequence(self):
        legacy = {
            "session_id": "legacy-a",
            "sequence": True,
            "right": {"valid": False},
        }
        with self.assertRaises(ProtocolError):
            parse_command_packet(json.dumps(legacy))

    def test_state_v2_round_trip(self):
        state = {
            "schema": STATE_SCHEMA_V2,
            "sequence": 10,
            "robot_time_ns": 20,
            "active_session_id": "session-a",
            "acknowledged_source_sequence": 7,
            "mode": "active",
            "armed": True,
            "watchdog": "ok",
            "ik_status": "tracking",
            "calibration_status": "ready",
            "workspace_status": "inside",
            "collision_limited": False,
            "position_error_m": 0.012,
            "right_arm_q_rad": [0.0] * 7,
            "left_arm_q_rad": [0.0] * 7,
        }
        packet = StatePacketV2.from_json(json.dumps(state))
        reparsed = StatePacketV2.from_json(packet.to_json())
        self.assertEqual(reparsed.acknowledged_source_sequence, 7)
        self.assertAlmostEqual(reparsed.position_error_m, 0.012)


if __name__ == "__main__":
    unittest.main()
