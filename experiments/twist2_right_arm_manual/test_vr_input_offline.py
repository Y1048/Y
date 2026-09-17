"""Pure offline input tests; no WSL, DDS, sockets, policy or physical output."""

import json
import math
import unittest

from vr_input_offline import VRInputStudy
from g1_joint_contract import G1_29_JOINT_NAMES


def MakePacket(sequence=1, **changes):
    q = [0.1] * 22 + [-0.1, -0.1, 0.1, 0.1, -0.1, 0.1, 0.1]
    value = {"schema": "g1.mink.right_arm.state.v1", "state_source": "mink_simulation",
             "session_id": "study", "sequence": sequence, "timestamp": 1,
             "input_command_mode": "active", "input_packet_age_s": 0,
             "all_joint_names": list(G1_29_JOINT_NAMES), "all_joint_q_rad": q,
             "right_arm": {"joints": q[22:29], "active": True, "command_state": "active",
                           "workspace_limited": False, "collision_limited": False,
                           "minimum_clearance_m": 0.02}}
    value.update(changes)
    return json.dumps(value).encode()


class VRInputTests(unittest.TestCase):
    def MakeStudy(self):
        return VRInputStudy([0.0] * 29, session_id="study", initial_sequence=0,
                            now_s=0, maximum_delta_rad=0.2, timeout_s=0.25)

    def test_only_right_arm_changes_and_no_sign_flip(self):
        study = self.MakeStudy()
        result = study.Step(MakePacket(), now_s=0.02, received_s=0.02)
        self.assertEqual(result["mode"], "active")
        self.assertEqual(result["upper_target_q_rad"][:22], (0.0,) * 22)
        self.assertAlmostEqual(result["upper_target_q_rad"][22], -0.0016)
        self.assertAlmostEqual(result["upper_target_q_rad"][25], 0.0016)
        self.assertFalse(result["hardware_output_authorized"])

    def test_rate_limit_converges_without_overshoot(self):
        study = self.MakeStudy()
        previous = study.target_q
        for sequence in range(1, 101):
            result = study.Step(MakePacket(sequence), now_s=sequence*0.02, received_s=sequence*0.02)
            self.assertEqual(result["mode"], "active")
            q = result["upper_target_q_rad"]
            self.assertLessEqual(max(abs(a-b) for a,b in zip(q, previous)), 0.00160000001)
            self.assertTrue(all(abs(x) <= 0.1 for x in q))
            previous = q
        self.assertEqual(q[22:29], (-0.1, -0.1, 0.1, 0.1, -0.1, 0.1, 0.1))

    def test_invalid_packets_stop_and_cannot_reengage(self):
        for packet in (b'{}', b'[]', b'bad', MakePacket(0), MakePacket(session_id="other"),
                       MakePacket(input_packet_age_s=1), MakePacket(input_command_mode="pinch_disengaged")):
            with self.subTest(packet=packet):
                study = self.MakeStudy()
                self.assertEqual(study.Step(packet, now_s=0.02, received_s=0.02)["mode"], "stopped")
                result = study.Step(MakePacket(2), now_s=0.04, received_s=0.04)
                self.assertEqual(result["mode"], "stopped")
                self.assertEqual(study.target_q, study.captured_q)

    def test_target_jump_and_duplicate_do_not_move(self):
        study = self.MakeStudy()
        study.Step(MakePacket(), now_s=0.02, received_s=0.02)
        before = study.target_q
        self.assertEqual(study.Step(MakePacket(), now_s=0.04, received_s=0.04)["mode"], "stopped")
        self.assertEqual(before, study.target_q)
        value = json.loads(MakePacket())
        value["all_joint_q_rad"][22] = value["right_arm"]["joints"][0] = 0.3
        study = self.MakeStudy()
        self.assertEqual(study.Step(json.dumps(value), now_s=0.02, received_s=0.02)["reason"], "start_relative_limit")

    def test_loss_freezes_then_latches_even_on_returning_packet(self):
        study = self.MakeStudy()
        study.Step(MakePacket(), now_s=0.02, received_s=0.02)
        before = study.target_q
        self.assertEqual(study.Step(None, now_s=0.10)["mode"], "waiting")
        self.assertEqual(study.target_q, before)
        self.assertEqual(study.Step(MakePacket(2), now_s=0.30, received_s=0.30)["reason"], "receiver_timeout")
        self.assertEqual(study.target_q, before)

    def test_bad_clocks_and_invalid_baseline(self):
        for now, receipt in ((0, 0), (math.nan, 0), (0.02, 1), (0.02, -1)):
            with self.subTest(now=now, receipt=receipt):
                self.assertEqual(self.MakeStudy().Step(MakePacket(), now_s=now, received_s=receipt)["mode"], "stopped")
        with self.assertRaises(ValueError):
            VRInputStudy([math.nan]*29, session_id="study", initial_sequence=0,
                         now_s=0, maximum_delta_rad=0.2, timeout_s=0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
