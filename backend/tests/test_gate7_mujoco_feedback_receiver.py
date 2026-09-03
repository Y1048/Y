from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path

import mujoco
import mink
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.gate7_simulation_feedback import (  # noqa: E402
    DUAL_ARM_JOINT_INDICES,
    build_packet,
    parse_packet,
)
import run_mink_g1_right_arm_prototype as base  # noqa: E402
from run_mink_g1_right_arm_virtual_center_live import (  # noqa: E402
    apply_gate7_simulation_feedback,
    drain_gate7_simulation_feedback,
)


def _payload(stream_id: str, sequence: int, value: float = 0.0) -> bytes:
    return build_packet(
        stream_id=stream_id,
        sequence=sequence,
        source_time_s=1.0,
        state="REGULAR_RETURN",
        reason="test",
        return_progress=0.5,
        dual_arm_q_rad=[value] * 14,
    )


class Gate7MujocoFeedbackReceiverTest(unittest.TestCase):
    def test_receiver_rejects_out_of_order_and_accepts_new_stream(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            receiver.bind(("127.0.0.1", 0))
            receiver.setblocking(False)
            destination = receiver.getsockname()
            sender.sendto(_payload("first", 1), destination)
            sender.sendto(_payload("first", 0), destination)
            packet, stream, sequence, accepted, rejected = (
                drain_gate7_simulation_feedback(receiver, None, -1)
            )
            self.assertIsNotNone(packet)
            self.assertEqual("first", stream)
            self.assertEqual(1, sequence)
            self.assertEqual(1, accepted)
            self.assertEqual(1, rejected)

            sender.sendto(_payload("second", 0), destination)
            packet, stream, sequence, accepted, rejected = (
                drain_gate7_simulation_feedback(receiver, stream, sequence)
            )
            self.assertIsNotNone(packet)
            self.assertEqual("second", stream)
            self.assertEqual(0, sequence)
            self.assertEqual(1, accepted)
            self.assertEqual(0, rejected)
        finally:
            receiver.close()
            sender.close()

    def test_apply_changes_only_dual_arm_qpos(self) -> None:
        base._prepare_mink_xml()
        model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
        configuration = mink.Configuration(model)
        initial = base._initial_configuration(model)
        configuration.update(initial)
        all_qpos_ids = [
            int(model.jnt_qposadr[base._joint_id(model, name)])
            for name in base.g1.G1_29_JOINTS
        ]
        target = [0.01 * (index + 1) for index in range(14)]
        packet = parse_packet(
            build_packet(
                stream_id="apply",
                sequence=0,
                source_time_s=1.0,
                state="REGULAR_RETURN",
                reason="test",
                return_progress=0.5,
                dual_arm_q_rad=target,
            )
        )
        before = configuration.q.copy()
        apply_gate7_simulation_feedback(configuration, all_qpos_ids, packet)
        for joint_index, expected in zip(DUAL_ARM_JOINT_INDICES, target):
            self.assertAlmostEqual(
                expected,
                float(configuration.q[all_qpos_ids[joint_index]]),
            )
        non_arm_qpos = [
            all_qpos_ids[index]
            for index in range(29)
            if index not in DUAL_ARM_JOINT_INDICES
        ]
        np.testing.assert_allclose(
            configuration.q[non_arm_qpos],
            before[non_arm_qpos],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
