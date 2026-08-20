from __future__ import annotations

import ctypes
import json
import math
import sys
import unittest
import uuid
from multiprocessing import shared_memory
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.calibration import (  # noqa: E402
    ArmCalibration,
    NeutralCalibrationAccumulator,
    estimate_rigid_registration,
)
from g1_teleop.camera import CameraFrame, CameraIntrinsics, RealSenseD435iSource, save_bgr_bmp  # noqa: E402
from g1_teleop.camera_factory import create_head_camera_source, load_camera_profile  # noqa: E402
from g1_teleop.protocol import POSE_FRAME, POSE_SCHEMA, PosePacketV1, ProtocolError  # noqa: E402
from g1_teleop.transforms import make_pose  # noqa: E402
from g1_teleop.unitree_image_transport import (  # noqa: E402
    UnitreeImageHeader,
    UnitreeSimImageWriter,
)
from g1_teleop.watchdog import (  # noqa: E402
    SequenceWatchdog,
    SessionSequenceWatchdog,
    WorkspaceExitDebounce,
    WorkspaceFaultLatch,
)


class FoundationTest(unittest.TestCase):
    def test_camera_contract_and_bmp(self):
        intrinsics = CameraIntrinsics.from_vertical_fov(64, 48, 42.5)
        image = np.zeros((48, 64, 3), dtype=np.uint8)
        image[:, :32, 2] = 255
        frame = CameraFrame(3, 4, "simulation", image, intrinsics)
        self.assertEqual(frame.color_bgr.shape, (48, 64, 3))
        self.assertGreater(intrinsics.fy, 0.0)

        output = BACKEND_ROOT / "tests" / "_camera_test.bmp"
        try:
            save_bgr_bmp(output, frame.color_bgr)
            self.assertEqual(output.read_bytes()[:2], b"BM")
        finally:
            output.unlink(missing_ok=True)

    def test_real_camera_is_a_configuration_only_swap(self):
        profile_path = BACKEND_ROOT.parents[0] / "config" / "camera_profile.json"
        profile = load_camera_profile(profile_path)
        profile["active_source"] = "real_d435i"
        source = create_head_camera_source(profile)
        self.assertIsInstance(source, RealSenseD435iSource)
        self.assertEqual((source.width, source.height, source.fps), (640, 480, 30))

    def test_arm_neutral_mapping(self):
        human_neutral = make_pose([0.2, -0.1, 0.8], [0.0, 0.0, 0.0, 1.0])
        robot_neutral = make_pose([0.42, -0.16, 1.05], [0.0, 0.0, 0.0, 1.0])
        calibration = ArmCalibration(human_neutral, robot_neutral, [1.0, 0.8, 1.1])
        human_current = human_neutral.copy()
        human_current[:3, 3] += [0.10, 0.10, -0.10]
        mapped = calibration.map_pose(human_current)
        np.testing.assert_allclose(mapped[:3, 3], [0.52, -0.08, 0.94], atol=1e-9)

    def test_neutral_accumulator_preserves_zero_timestamp(self):
        accumulator = NeutralCalibrationAccumulator(minimum_samples=3)
        human = make_pose([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
        robot = make_pose([0.4, -0.2, 1.0], [0.0, 0.0, 0.0, 1.0])
        for _ in range(3):
            accumulator.add_sample(human, robot)
        profile = accumulator.build_profile(created_time_ns=0)
        self.assertEqual(profile.created_time_ns, 0)

    def test_registration_recovers_transform(self):
        source = np.array(
            [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0], [0.0, 0.3, 0.0], [0.1, 0.2, 0.2]]
        )
        angle = math.radians(30.0)
        rotation = np.array(
            [[math.cos(angle), -math.sin(angle), 0.0],
             [math.sin(angle), math.cos(angle), 0.0],
             [0.0, 0.0, 1.0]]
        )
        translation = np.array([0.6, -0.2, 0.1])
        target = (rotation @ source.T).T + translation
        result = estimate_rigid_registration(source, target)
        np.testing.assert_allclose(result.transform[:3, :3], rotation, atol=1e-9)
        np.testing.assert_allclose(result.transform[:3, 3], translation, atol=1e-9)
        self.assertLess(result.rms_error_m, 1e-9)

    def test_pose_protocol_is_strict(self):
        pose = {
            "valid": True,
            "confidence": "high",
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        }
        packet = {
            "schema": POSE_SCHEMA,
            "sequence": 1,
            "source_time_ns": 2,
            "frame_id": POSE_FRAME,
            "armed": False,
            "clutch": False,
            "head": pose,
            "right_wrist": pose,
            "left_wrist": pose,
        }
        self.assertEqual(PosePacketV1.from_json(json.dumps(packet)).sequence, 1)
        packet["armed"] = "false"
        with self.assertRaises(ProtocolError):
            PosePacketV1.from_json(json.dumps(packet))

    def test_watchdog_holds_then_disarms(self):
        watchdog = SequenceWatchdog(hold_after_s=0.1, disarm_after_s=0.3)
        self.assertTrue(watchdog.accept(1, 1_000_000_000).accepted)
        self.assertFalse(watchdog.accept(1, 1_000_000_001).accepted)
        self.assertEqual(watchdog.status(1_050_000_000), "ok")
        self.assertEqual(watchdog.status(1_150_000_000), "hold")
        self.assertEqual(watchdog.status(1_350_000_000), "disarm")

    def test_watchdog_rejects_boolean_sequence_and_arrival_time(self):
        watchdog = SequenceWatchdog()

        self.assertFalse(watchdog.accept(True, 1).accepted)
        self.assertFalse(watchdog.accept(1, False).accepted)

    def test_session_watchdog_accepts_ordered_current_session(self):
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.30)

        self.assertTrue(watchdog.accept("session-a", 0, True, 0).accepted)
        self.assertTrue(watchdog.accept("session-a", 1, True, 10).accepted)
        self.assertFalse(watchdog.accept("session-a", 1, True, 20).accepted)
        self.assertFalse(watchdog.accept("session-a", 0, True, 30).accepted)

    def test_session_watchdog_rejects_foreign_active_sender_until_stale(self):
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.30)

        self.assertTrue(watchdog.accept("session-a", 10, True, 0).accepted)
        self.assertFalse(watchdog.accept("session-b", 0, True, 299_999_999).accepted)
        self.assertTrue(watchdog.accept("session-b", 0, True, 300_000_000).accepted)

    def test_session_watchdog_rejects_foreign_invalid_until_stale(self):
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.30)

        self.assertTrue(watchdog.accept("session-a", 10, True, 0).accepted)
        acceptance = watchdog.accept("session-b", 0, False, 1)

        self.assertFalse(acceptance.accepted)
        self.assertEqual(acceptance.reason, "active session owns the stream")
        self.assertEqual(watchdog.session_id, "session-a")

    def test_session_watchdog_accepts_current_session_disengage(self):
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.30)

        self.assertTrue(watchdog.accept("session-a", 10, True, 0).accepted)
        acceptance = watchdog.accept("session-a", 11, False, 1)

        self.assertTrue(acceptance.accepted)
        self.assertEqual(acceptance.reason, "ordered packet")

    def test_session_watchdog_accepts_foreign_invalid_after_timeout(self):
        watchdog = SessionSequenceWatchdog(takeover_after_s=0.30)

        self.assertTrue(watchdog.accept("session-a", 10, True, 0).accepted)
        acceptance = watchdog.accept("session-b", 0, False, 300_000_000)

        self.assertTrue(acceptance.accepted)
        self.assertEqual(acceptance.reason, "stale session takeover")
        self.assertEqual(watchdog.session_id, "session-b")

    def test_session_watchdog_rejects_malformed_identity_fields(self):
        watchdog = SessionSequenceWatchdog()

        self.assertFalse(watchdog.accept("", 0, True, 0).accepted)
        self.assertFalse(watchdog.accept("session-a", True, True, 0).accepted)
        self.assertFalse(watchdog.accept("session-a", 0, 1, 0).accepted)
        self.assertFalse(watchdog.accept("session-a", 0, True, False).accepted)

    def test_workspace_fault_requires_exit_then_new_valid(self):
        workspace_fault = WorkspaceFaultLatch()

        self.assertTrue(workspace_fault.permit_valid())
        workspace_fault.trip()
        self.assertTrue(workspace_fault.latched)
        self.assertFalse(workspace_fault.permit_valid())

        workspace_fault.observe_workspace_exit()
        self.assertTrue(workspace_fault.latched)
        self.assertTrue(workspace_fault.reset_armed)
        self.assertTrue(workspace_fault.permit_valid())
        self.assertFalse(workspace_fault.latched)
        self.assertFalse(workspace_fault.reset_armed)

    def test_workspace_fault_retrip_requires_another_exit(self):
        workspace_fault = WorkspaceFaultLatch()

        workspace_fault.trip()
        workspace_fault.observe_workspace_exit()
        self.assertTrue(workspace_fault.permit_valid())
        workspace_fault.trip()

        self.assertFalse(workspace_fault.permit_valid())
        self.assertTrue(workspace_fault.latched)

    def test_locally_confirmed_workspace_exit_allows_next_valid(self):
        workspace_fault = WorkspaceFaultLatch()

        workspace_fault.trip_and_arm_reset()

        self.assertTrue(workspace_fault.latched)
        self.assertTrue(workspace_fault.reset_armed)
        self.assertTrue(workspace_fault.permit_valid())
        self.assertFalse(workspace_fault.latched)

    def test_workspace_exit_requires_continuous_violation(self):
        workspace_exit = WorkspaceExitDebounce(0.2)

        self.assertFalse(workspace_exit.update(False, 0.08))
        self.assertFalse(workspace_exit.update(True, 0.01))
        self.assertEqual(workspace_exit.unsafe_duration_s, 0.0)
        self.assertFalse(workspace_exit.update(False, 0.10))
        self.assertTrue(workspace_exit.update(False, 0.10))

    def test_workspace_exit_rejects_invalid_configuration(self):
        with self.assertRaises(ValueError):
            WorkspaceExitDebounce(0.0)

    def test_unitree_shared_memory_layout(self):
        image_name = f"test_{uuid.uuid4().hex[:8]}"
        shm_name = f"isaac_{image_name}_image_shm"
        memory = shared_memory.SharedMemory(name=shm_name, create=True, size=640 * 480 * 3 + 128)
        writer = UnitreeSimImageWriter()
        try:
            writer._memories[shm_name] = memory
            image = np.zeros((480, 640, 3), dtype=np.uint8)
            image[10, 20] = [4, 5, 6]
            writer.write_bgr(image_name, image)
            header_size = ctypes.sizeof(UnitreeImageHeader)
            header = UnitreeImageHeader.from_buffer_copy(bytes(memory.buf[:header_size]))
            self.assertEqual((header.height, header.width, header.channels), (480, 640, 3))
            self.assertEqual(header.encoding, 0)
            offset = header_size + (10 * 640 + 20) * 3
            self.assertEqual(bytes(memory.buf[offset : offset + 3]), b"\x04\x05\x06")
        finally:
            writer.close()
            try:
                memory.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    unittest.main()
