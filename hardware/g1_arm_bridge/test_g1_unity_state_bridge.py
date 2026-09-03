#!/usr/bin/env python3
"""실제 G1 LowState에서 Unity 29관절 상태로 가는 계약 테스트."""

from __future__ import annotations

import json
import math
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from g1_joint_contract import G1_29_JOINT_NAMES
from gate5_lowstate_safety_monitor import (
    LowStatePacketError,
    parse_lowstate_telemetry,
)
from g1_unity_state_bridge import (
    UNITY_HARDWARE_STATE_SOURCE,
    BuildUnityHardwareStatePacket,
    EncodeUnityHardwareStatePacket,
)


def LowStatePacket(
    *,
    names: tuple[str, ...] = G1_29_JOINT_NAMES,
    q_rad: list[float] | None = None,
    dq_rad_s: list[float] | None = None,
    include_base_state: bool = False,
) -> bytes:
    q_values = q_rad if q_rad is not None else [index / 100.0 for index in range(29)]
    dq_values = dq_rad_s if dq_rad_s is not None else [index / 1000.0 for index in range(29)]
    payload = {
            "schema": "g1.lowstate.right_arm.v1",
            "mode": "READ_ONLY_LOWSTATE",
            "topic": "rt/lowstate",
            "bridge_session_id": "unity-hardware-test",
            "sequence": 42,
            "sent_at_unix_ns": time.time_ns(),
            "right_arm_q_rad": q_values[22:29],
            "right_arm_dq_rad_s": dq_values[22:29],
            "all_joint_names": list(names),
            "all_joint_q_rad": q_values,
            "all_joint_dq_rad_s": dq_values,
            "publisher_present": False,
            "command_output_enabled": False,
        }
    if include_base_state:
        payload["base_state"] = {
            "valid": True,
            "topic": "rt/odommodestate",
            "received_packets": 123,
            "invalid_packets": 0,
            "last_packet_age_s": 0.003,
            "position_m": [0.25, -0.10, 0.02],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            "velocity_mps": [0.1, 0.0, 0.0],
            "yaw_speed_rad_s": 0.04,
        }
    return json.dumps(payload).encode("utf-8")


class G1UnityStateBridgeTests(unittest.TestCase):
    def test_preserves_normalized_base_state_for_unity(self) -> None:
        lowstate = parse_lowstate_telemetry(
            LowStatePacket(include_base_state=True)
        )
        unity = BuildUnityHardwareStatePacket(lowstate, timestamp=123.5)
        self.assertTrue(unity["base_state"]["valid"])
        self.assertEqual(
            [0.25, -0.10, 0.02],
            unity["base_state"]["position_m"],
        )
        self.assertEqual(
            [0.0, 0.0, 0.0, 1.0],
            unity["base_state"]["quaternion_xyzw"],
        )

    def test_legacy_packet_does_not_invent_base_state(self) -> None:
        lowstate = parse_lowstate_telemetry(LowStatePacket())
        unity = BuildUnityHardwareStatePacket(lowstate, timestamp=123.5)
        self.assertNotIn("base_state", unity)

    def test_preserves_all_29_joint_positions_and_velocities(self) -> None:
        lowstate = parse_lowstate_telemetry(LowStatePacket())
        unity = BuildUnityHardwareStatePacket(lowstate, timestamp=123.5)
        self.assertEqual(UNITY_HARDWARE_STATE_SOURCE, unity["state_source"])
        self.assertEqual(list(G1_29_JOINT_NAMES), unity["all_joint_names"])
        self.assertEqual(list(lowstate.all_joint_q_rad), unity["all_joint_q_rad"])
        self.assertEqual(list(lowstate.all_joint_dq_rad_s), unity["all_joint_dq_rad_s"])
        self.assertEqual(list(lowstate.all_joint_q_rad[22:29]), unity["right_arm"]["joints"])
        self.assertFalse(unity["right_arm"]["active"])
        self.assertEqual(42, unity["sequence"])
        self.assertEqual(123.5, unity["timestamp"])

    def test_forwards_mujoco_displayed_pose_and_reports_source_lag(self) -> None:
        lowstate = parse_lowstate_telemetry(
            LowStatePacket(include_base_state=True)
        )
        displayed_joints = [value + 0.01 for value in lowstate.all_joint_q_rad]
        displayed_yaw_rad = math.radians(10.0)
        unity = BuildUnityHardwareStatePacket(
            lowstate,
            timestamp=123.5,
            displayed_all_joint_q_rad=displayed_joints,
            displayed_base_position_m=[0.20, -0.08, 0.02],
            displayed_base_quaternion_xyzw=[
                0.0,
                0.0,
                math.sin(displayed_yaw_rad / 2.0),
                math.cos(displayed_yaw_rad / 2.0),
            ],
        )

        self.assertEqual(displayed_joints, unity["all_joint_q_rad"])
        self.assertEqual(displayed_joints[22:29], unity["right_arm"]["joints"])
        self.assertEqual(
            [0.20, -0.08, 0.02],
            unity["base_state"]["position_m"],
        )
        diagnostics = unity["mirror_diagnostics"]
        self.assertEqual(
            [0.25, -0.10, 0.02],
            diagnostics["source_base_position_m"],
        )
        self.assertAlmostEqual(
            math.sqrt(0.05 ** 2 + 0.02 ** 2),
            diagnostics["base_position_error_m"],
        )
        self.assertAlmostEqual(
            10.0,
            diagnostics["base_orientation_error_deg"],
        )
        self.assertAlmostEqual(
            0.01,
            diagnostics["max_joint_position_error_rad"],
        )

    def test_displayed_base_override_requires_position_and_rotation(self) -> None:
        lowstate = parse_lowstate_telemetry(
            LowStatePacket(include_base_state=True)
        )
        with self.assertRaisesRegex(LowStatePacketError, "supplied together"):
            BuildUnityHardwareStatePacket(
                lowstate,
                displayed_base_position_m=[0.0, 0.0, 0.0],
            )

    def test_encoded_packet_is_valid_json(self) -> None:
        lowstate = parse_lowstate_telemetry(LowStatePacket())
        payload = json.loads(EncodeUnityHardwareStatePacket(lowstate))
        self.assertEqual(29, len(payload["all_joint_q_rad"]))
        self.assertEqual("g1_lowstate_read_only", payload["state_source"])

    def test_missing_full_body_state_is_rejected(self) -> None:
        payload = json.loads(LowStatePacket())
        del payload["all_joint_q_rad"]
        lowstate = parse_lowstate_telemetry(json.dumps(payload).encode("utf-8"))
        with self.assertRaisesRegex(LowStatePacketError, "full 29-joint"):
            BuildUnityHardwareStatePacket(lowstate)

    def test_nonfinite_state_is_rejected_by_lowstate_parser(self) -> None:
        q_rad = [0.0] * 29
        q_rad[14] = math.nan
        with self.assertRaisesRegex(LowStatePacketError, "non-finite"):
            parse_lowstate_telemetry(LowStatePacket(q_rad=q_rad))


if __name__ == "__main__":
    unittest.main()
