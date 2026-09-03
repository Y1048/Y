#!/usr/bin/env python3
"""실시간 LowState MuJoCo Viewer의 네트워크 독립 단위 테스트."""

from __future__ import annotations

import json
import math
import socket
import sys
import time
import unittest
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from g1_joint_contract import G1_29_JOINT_NAMES
from gate5_lowstate_safety_monitor import LowStatePacketError, parse_lowstate_telemetry
from live_lowstate_mujoco import (
    INSPECTION_SCENE_GEOM_NAMES,
    AdvancePose,
    AdvanceQuaternion,
    ApplyBasePose,
    ApplyFullBodyPose,
    BasePoseFromPacket,
    BuildMirrorMeasurement,
    LoadModel,
    ReceiveAvailable,
    ResolveFullBodyQposAddresses,
    ResolveBaseBodyPose,
    StreamState,
)


def Packet(
    sequence: int,
    session_id: str = "live-viewer-test",
    include_base_state: bool = False,
) -> bytes:
    all_joint_q_rad = [
        sequence / 100.0 + joint_index / 1000.0
        for joint_index in range(29)
    ]
    payload: dict[str, object] = {
        "schema": "g1.lowstate.right_arm.v1",
        "mode": "READ_ONLY_LOWSTATE",
        "topic": "rt/lowstate",
        "bridge_session_id": session_id,
        "sequence": sequence,
        "sent_at_unix_ns": time.time_ns(),
        "right_arm_q_rad": [sequence / 100.0] * 7,
        "right_arm_dq_rad_s": [0.0] * 7,
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": all_joint_q_rad,
        "all_joint_dq_rad_s": [0.0] * 29,
        "publisher_present": False,
        "command_output_enabled": False,
    }
    if include_base_state:
        payload["base_state"] = {
            "valid": True,
            "topic": "rt/odommodestate",
            "received_packets": sequence,
            "invalid_packets": 0,
            "last_packet_age_s": 0.002,
            "position_m": [0.30, -0.20, 0.10],
            "quaternion_xyzw": [0.0, 0.0, math.sin(math.pi / 8.0), math.cos(math.pi / 8.0)],
            "velocity_mps": [0.0, 0.0, 0.0],
            "yaw_speed_rad_s": 0.0,
        }
    return json.dumps(payload).encode("utf-8")


class LiveLowStateMuJoCoTests(unittest.TestCase):
    def test_mirror_measurement_records_source_and_display_contract(self) -> None:
        payload = {
            "session_id": "measurement-test",
            "sequence": 8,
            "mirror_diagnostics": {
                "source_base_position_m": [0.3, 0.0, 0.0],
                "displayed_base_position_m": [0.28, 0.0, 0.0],
                "source_base_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "displayed_base_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "base_position_error_m": 0.02,
                "base_orientation_error_deg": 0.0,
                "max_joint_position_error_rad": 0.01,
            },
        }
        measurement = BuildMirrorMeasurement(payload, 0.004)
        self.assertIsNotNone(measurement)
        assert measurement is not None
        self.assertEqual(
            [0.28, 0.0, 0.0],
            measurement["mujoco_displayed_base_position_m"],
        )
        self.assertEqual(
            measurement["mujoco_displayed_base_position_m"],
            measurement["unity_commanded_base_position_m"],
        )
        self.assertEqual(0.02, measurement["source_to_mujoco_position_error_m"])

    def test_base_pose_moves_fixed_pelvis_without_changing_joint_contract(self) -> None:
        model, data, _ = LoadModel()
        base_body = ResolveBaseBodyPose(model)
        initial_position = base_body.initial_position_m.copy()
        packet = parse_lowstate_telemetry(Packet(1, include_base_state=True))
        base_pose = BasePoseFromPacket(packet)
        self.assertIsNotNone(base_pose)
        assert base_pose is not None
        ApplyBasePose(model, data, base_body, base_pose[0], base_pose[1])
        np.testing.assert_allclose(
            model.body_pos[base_body.body_id],
            initial_position + np.asarray([0.30, -0.20, 0.10]),
            atol=1e-9,
        )
        self.assertAlmostEqual(1.0, np.linalg.norm(
            model.body_quat[base_body.body_id]
        ), places=9)

    def test_base_quaternion_smoothing_is_normalized_and_shortest_path(self) -> None:
        current = np.asarray([0.0, 0.0, 0.0, 1.0])
        target = np.asarray([0.0, 0.0, -math.sin(math.pi / 4.0), -math.cos(math.pi / 4.0)])
        result = AdvanceQuaternion(current, target, 1.0 / 60.0, 0.035)
        self.assertAlmostEqual(1.0, np.linalg.norm(result), places=9)
        self.assertGreater(result[3], 0.0)
        self.assertGreater(result[2], 0.0)

    def test_packet_without_base_pose_keeps_legacy_fixed_base(self) -> None:
        packet = parse_lowstate_telemetry(Packet(1))
        self.assertIsNone(BasePoseFromPacket(packet))

    def test_live_mirror_hides_but_preserves_inspection_scene_by_default(self) -> None:
        model, _, _ = LoadModel()
        for geom_name in INSPECTION_SCENE_GEOM_NAMES:
            geom_id = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, geom_name
            )
            self.assertGreaterEqual(geom_id, 0)
            self.assertEqual(0.0, float(model.geom_rgba[geom_id, 3]))
            self.assertEqual(0, int(model.geom_contype[geom_id]))
            self.assertEqual(0, int(model.geom_conaffinity[geom_id]))

    def test_inspection_scene_can_be_shown_again(self) -> None:
        model, _, _ = LoadModel(show_inspection_scene=True)
        for geom_name in INSPECTION_SCENE_GEOM_NAMES:
            geom_id = mujoco.mj_name2id(
                model, mujoco.mjtObj.mjOBJ_GEOM, geom_name
            )
            self.assertGreater(float(model.geom_rgba[geom_id, 3]), 0.0)

    def test_smoothing_never_overshoots(self) -> None:
        current = np.zeros(29)
        target = np.ones(29)
        result = AdvancePose(current, target, 1.0 / 60.0, 0.035)
        self.assertTrue(np.all(result > current))
        self.assertTrue(np.all(result < target))

    def test_zero_smoothing_applies_exact_target(self) -> None:
        target = np.arange(29, dtype=float)
        result = AdvancePose(np.zeros(29), target, 0.01, 0.0)
        np.testing.assert_array_equal(target, result)

    def test_full_body_pose_updates_every_g1_joint(self) -> None:
        model, data, controller = LoadModel()
        self.assertEqual(
            tuple(controller.g1.G1_29_JOINT_NAMES),
            G1_29_JOINT_NAMES,
        )
        addresses = ResolveFullBodyQposAddresses(model)
        pose = np.linspace(-0.15, 0.15, 29)
        ApplyFullBodyPose(model, data, addresses, pose)
        np.testing.assert_allclose(data.qpos[addresses], pose, atol=1e-12)

    def test_stream_accepts_new_session_and_rejects_old_sequence(self) -> None:
        state = StreamState()
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            destination = receiver.getsockname()
            sender.sendto(Packet(10), destination)
            sender.sendto(Packet(9), destination)
            time.sleep(0.01)
            self.assertTrue(ReceiveAvailable(receiver, state))
            self.assertEqual(10, state.sequence)
            self.assertEqual(1, state.accepted_packets)
            self.assertEqual(1, state.rejected_packets)

            sender.sendto(Packet(1, "replacement-session"), destination)
            time.sleep(0.01)
            self.assertTrue(ReceiveAvailable(receiver, state))
            self.assertEqual(1, state.sequence)
            self.assertEqual("replacement-session", state.session_id)
        finally:
            sender.close()
            receiver.close()

    def test_invalid_joint_vector_is_rejected(self) -> None:
        state = StreamState()
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            payload = json.loads(Packet(1))
            payload["all_joint_q_rad"][2] = math.nan
            sender.sendto(json.dumps(payload).encode("utf-8"), receiver.getsockname())
            time.sleep(0.01)
            self.assertFalse(ReceiveAvailable(receiver, state))
            self.assertEqual(1, state.rejected_packets)
        finally:
            sender.close()
            receiver.close()

    def test_right_arm_only_legacy_packet_is_rejected_by_full_body_viewer(self) -> None:
        payload = json.loads(Packet(1))
        del payload["all_joint_names"]
        del payload["all_joint_q_rad"]
        del payload["all_joint_dq_rad_s"]
        packet = json.dumps(payload).encode("utf-8")

        state = StreamState()
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            sender.sendto(packet, receiver.getsockname())
            time.sleep(0.01)
            self.assertFalse(ReceiveAvailable(receiver, state))
            self.assertEqual(1, state.rejected_packets)
        finally:
            sender.close()
            receiver.close()

    def test_reordered_full_body_contract_is_rejected(self) -> None:
        payload = json.loads(Packet(1))
        payload["all_joint_names"][0], payload["all_joint_names"][1] = (
            payload["all_joint_names"][1],
            payload["all_joint_names"][0],
        )
        with self.assertRaisesRegex(LowStatePacketError, "motor order"):
            parse_lowstate_telemetry(json.dumps(payload).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
