#!/usr/bin/env python3
"""저장 LowState 재생기의 네트워크 독립 계약 테스트."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from g1_joint_contract import G1_29_JOINT_NAMES
from gate5_lowstate_safety_monitor import parse_lowstate_telemetry
from replay_saved_lowstate_mujoco import BuildPacket, LoadSnapshot


class ReplaySavedLowStateMuJoCoTests(unittest.TestCase):
    def WriteJson(self, payload: dict[str, object]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "snapshot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_new_read_only_status_as_actual_capture(self) -> None:
        payload = {
            "details": {
                "all_joint_names": list(G1_29_JOINT_NAMES),
                "all_joint_q_rad": [index / 100.0 for index in range(29)],
                "all_joint_dq_rad_s": [index / 1000.0 for index in range(29)],
                "mode_pr": 0,
                "mode_machine": 5,
            }
        }
        snapshot = LoadSnapshot(self.WriteJson(payload))
        self.assertTrue(snapshot.actual_full_body_capture)
        self.assertEqual("read_only_lowstate_status", snapshot.source_kind)
        self.assertEqual(0.28, snapshot.q_rad[28])

    def test_loads_pose_sync_artifact_as_explicit_fallback(self) -> None:
        payload = {
            "unity_packet_all_joint_names": list(G1_29_JOINT_NAMES),
            "unity_packet_all_joint_q_rad": [0.1] * 29,
        }
        snapshot = LoadSnapshot(self.WriteJson(payload))
        self.assertFalse(snapshot.actual_full_body_capture)
        self.assertEqual("pose_sync_validation", snapshot.source_kind)
        self.assertEqual((0.0,) * 29, snapshot.dq_rad_s)

    def test_built_packet_preserves_all_joints_and_right_arm_slice(self) -> None:
        payload = {
            "all_joint_names": list(G1_29_JOINT_NAMES),
            "all_joint_q_rad": [index / 10.0 for index in range(29)],
            "all_joint_dq_rad_s": [0.0] * 29,
            "mode_pr": 0,
            "mode_machine": 5,
        }
        snapshot = LoadSnapshot(self.WriteJson(payload))
        packet = parse_lowstate_telemetry(
            BuildPacket(
                snapshot,
                session_id="saved-packet-test",
                sequence=7,
                sent_at_unix_ns=1,
            )
        )
        self.assertEqual(snapshot.q_rad, packet.all_joint_q_rad)
        self.assertEqual(snapshot.q_rad[22:29], packet.measured_q_rad)
        self.assertEqual(7, packet.sequence)

    def test_reordered_joint_names_are_rejected(self) -> None:
        names = list(G1_29_JOINT_NAMES)
        names[0], names[1] = names[1], names[0]
        payload = {
            "all_joint_names": names,
            "all_joint_q_rad": [0.0] * 29,
            "all_joint_dq_rad_s": [0.0] * 29,
        }
        with self.assertRaisesRegex(ValueError, "canonical G1 motor order"):
            LoadSnapshot(self.WriteJson(payload))

    def test_legacy_status_explains_required_recapture(self) -> None:
        payload = {"details": {"right_arm": []}}
        with self.assertRaisesRegex(ValueError, "START_G1_READ_ONLY"):
            LoadSnapshot(self.WriteJson(payload))


if __name__ == "__main__":
    unittest.main()
