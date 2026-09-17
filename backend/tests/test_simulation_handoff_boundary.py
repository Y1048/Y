"""Producer marker -> actual relay parser with a fake sender; no sockets."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
sys.path.insert(0, str(ROOT / 'hardware/g1_arm_bridge'))
from g1_mink_command_provenance import mark_simulation_cycle_packet, mark_live_mink_packet
from test_gate7_mink_wsl_relay import _packet, RELAY_TOKEN
from gate7_mink_wsl_relay import ValidateAndForward, MinkOrderGuard
from arm_sdk_teleop_contract import Gate7ContractError
from arm_sdk_teleop_contract import parse_mink_arm_sample


class SimulationHandoffBoundaryTests(unittest.TestCase):
    def test_real_model_qpos_maps_to_g1_22_through_28(self):
        import numpy as np
        sys.path.insert(0, str(ROOT / 'experiments/twist2_right_arm_manual'))
        from replay_upstream_mink import build, base
        model, planner, trajectory = build()
        fixture = json.loads((Path(__file__).parent / 'fixtures/mink_elbow_boundary_20260909.json').read_text())
        q = np.array(fixture['current_q']); planner.configuration.update(q)
        all_ids = [int(model.joint(name + '_joint').qposadr[0]) for name in base.g1.G1_29_JOINT_NAMES]
        position = planner.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body').translation()
        packet = base._state_packet(planner.configuration, planner.qpos_ids, all_ids,
            True, position, position, False, minimum_clearance_m=planner.GetClearance(q),
            control_state='active', input_command_mode='active', session_id='model-map',
            input_packet_age_s=0., state_sequence=1)
        mark_simulation_cycle_packet(packet)
        sample = parse_mink_arm_sample(json.dumps(packet).encode())
        np.testing.assert_array_equal(sample.all_joint_q_rad, q[all_ids])
        np.testing.assert_array_equal(packet['right_arm']['joints'], q[all_ids][22:29])
        sender = Mock()
        with self.assertRaisesRegex(Gate7ContractError, 'simulation_only'):
            ValidateAndForward(json.dumps(packet).encode(), MinkOrderGuard(), sender,
                ('127.0.0.1', 5014), relay_token=RELAY_TOKEN)
        sender.sendto.assert_not_called()

    def test_cycle_packet_never_reaches_sender(self):
        for state in ('ready', 'returning', 'await_idle', 'await_active', 'fault'):
            with self.subTest(state=state):
                packet = mark_simulation_cycle_packet(json.loads(_packet(1)))
                packet['simulation_arm_cycle'] = dict(state=state, candidate_output_disabled=True)
                sender = Mock()
                with self.assertRaisesRegex(Gate7ContractError, 'simulation_only'):
                    ValidateAndForward(json.dumps(packet).encode(), MinkOrderGuard(),
                        sender, ('127.0.0.1', 5014), relay_token=RELAY_TOKEN)
                sender.sendto.assert_not_called()
                with self.assertRaisesRegex(ValueError, 'relabel'):
                    mark_live_mink_packet(packet)

    def test_old_live_label_does_not_override_simulation_marker(self):
        for fields in ({'simulation_only': True}, {'hardware_output_authorized': False},
                       {'simulation_arm_cycle': {'candidate_output_disabled': True}}):
            packet = json.loads(_packet(1)); packet.update(fields)
            sender = Mock()
            with self.assertRaisesRegex(Gate7ContractError, 'simulation_only'):
                ValidateAndForward(json.dumps(packet).encode(), MinkOrderGuard(),
                    sender, ('127.0.0.1', 5014), relay_token=RELAY_TOKEN)
            sender.sendto.assert_not_called()

    def test_live_contract_preserves_all_29_joints_and_release_event(self):
        for mode in ('active', 'pinch_disengaged', 'tracking_disengaged'):
            packet = json.loads(_packet(1))
            packet['input_command_mode'] = mode
            packet['right_arm'].update(active=mode=='active', command_state='active' if mode=='active' else 'idle')
            sender = Mock()
            ValidateAndForward(json.dumps(packet).encode(), MinkOrderGuard(), sender,
                ('127.0.0.1', 5014), relay_token=RELAY_TOKEN)
            forwarded = json.loads(sender.sendto.call_args.args[0])
            expected = [round(x, 7) for x in packet['all_joint_q_rad']]
            self.assertEqual(forwarded['all_joint_q_rad'], expected)
            self.assertEqual(forwarded['right_arm']['joints'], expected[22:29])
            self.assertEqual(forwarded['input_command_mode'], mode)


if __name__ == '__main__':
    unittest.main()
