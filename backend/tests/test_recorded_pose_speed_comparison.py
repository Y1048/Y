import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import compare_recorded_pose_speeds as replay


def MakePacket(time, active, session="a"):
    return {
        "offset_s": time,
        "sample": SimpleNamespace(active=active, input_command_mode="active" if active else "idle"),
        "value": {"session_id": session, "right_arm": {
            "target_position": [0.1, 0.2, 0.3],
            "target_rotation_matrix_robot": np.eye(3).tolist(),
        }},
    }


class RecordedPoseSpeedComparisonTest(unittest.TestCase):
    def test_segments_use_preceding_inactive_pose_and_keep_reengagement_separate(self):
        packets = [MakePacket(0, False), MakePacket(1, True), MakePacket(2, True),
                   MakePacket(3, False), MakePacket(4, True)]
        segments = replay.GetActiveSegments(packets)
        self.assertEqual(len(segments), 2)
        self.assertIs(segments[0][0], packets[0])
        self.assertIs(segments[1][0], packets[3])
        self.assertEqual([len(s[1]) for s in segments], [2, 1])

    def test_new_session_does_not_reuse_old_pose(self):
        packets = [MakePacket(0, True), MakePacket(1, True, "b")]
        segments = replay.GetActiveSegments(packets)
        self.assertEqual(len(segments), 2)
        self.assertIs(segments[1][0], packets[1])

    def test_time_dilation_and_final_hold_keep_recorded_targets(self):
        times = np.array([0, 1, 2])
        self.assertEqual(replay.GetTargetIndex(times, 1, 1), 1)
        self.assertEqual(replay.GetTargetIndex(times, 1, 0.5), 0)
        self.assertEqual(replay.GetTargetIndex(times, 4, 0.25), 1)
        self.assertEqual(replay.GetTargetIndex(times, 100, 0.25), 2)

    def test_missing_or_invalid_rotation_is_not_fabricated(self):
        for rotation in (None, [[float("nan")]*3]*3, np.diag([1, 1, -1]).tolist()):
            packet = MakePacket(0, True)
            packet["value"]["right_arm"]["target_rotation_matrix_robot"] = rotation
            with self.assertRaises(ValueError):
                replay.GetRecordedTargets([packet])

    def test_target_pose_roundtrip(self):
        times, targets = replay.GetRecordedTargets([MakePacket(5, True), MakePacket(6, True)])
        np.testing.assert_allclose(times, [0, 1])
        np.testing.assert_allclose(targets[1].rotation().as_matrix(), np.eye(3))
        np.testing.assert_allclose(targets[1].translation(), [.1, .2, .3])


if __name__ == "__main__":
    unittest.main()
