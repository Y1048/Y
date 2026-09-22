"""Offline rotating-base invariance: no transport, viewer or physical robot."""
import copy
import json
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import UnityCycle, BASIS, WORLD_SCHEMA, WORLD_FRAME, decode, mink
from g1_bimanual_sim import BimanualSimulation


def packet(sim, sequence, yaw, engage, offset=None):
    rotation = mink.SO3.exp(np.array([0., 0., yaw])).as_matrix()
    result = dict(schema=WORLD_SCHEMA, simulation_only=True, session='omni-world', sequence=sequence,
                  sender_time_s=sequence/60, engage=engage, return_home=False,
                  input_frame=WORLD_FRAME, base_yaw_rad=yaw)
    for side in ('left', 'right'):
        home = sim.home_targets[side]
        p = home.translation().copy()
        if offset is not None: p += offset[side]
        world_rotation = rotation @ home.rotation().as_matrix()
        result[side] = dict(tracked=True, position_m=(BASIS.T @ rotation @ p).tolist(),
            quaternion_wxyz=mink.SO3.from_matrix(BASIS.T @ world_rotation @ BASIS).wxyz.tolist())
    return result


class OmniWorldTests(unittest.TestCase):
    def test_protocol_rejects_missing_nonfinite_or_unknown_frame(self):
        sim = BimanualSimulation()
        p = packet(sim, 0, 0., False)
        self.assertEqual(decode(json.dumps(p)), p)
        for value in (None, True, float('nan'), '90'):
            bad = copy.deepcopy(p); bad['base_yaw_rad'] = value
            with self.assertRaises(ValueError): decode(json.dumps(bad))
        bad = copy.deepcopy(p); bad['input_frame'] = 'unknown'
        with self.assertRaises(ValueError): decode(json.dumps(bad))

    def test_protocol_preserves_world_diagnostics(self):
        sim = BimanualSimulation()
        p = packet(sim, 0, 0., False)
        p.update(quest_origin_world_m=[0., 1.6, 0.], hmd_world_m=[.01, 1.61, -.02],
                 unity_robot_root_position_m=[0., 0., 0.], unity_robot_root_wxyz=[1., 0., 0., 0.],
                 unity_shoulder_center_m=[0., 1.3, 0.], unity_left_wrist_world_m=[-.2, 1., .3],
                 unity_right_wrist_world_m=[.2, 1., .3])
        p['left']['raw_position_m'] = [-.3, 1.2, .4]
        p['left']['raw_quaternion_wxyz'] = [1., 0., 0., 0.]
        self.assertEqual(decode(json.dumps(p)), p)
        bad = copy.deepcopy(p); bad['unity_shoulder_center_m'] = [0., float('nan'), 0.]
        with self.assertRaises(ValueError): decode(json.dumps(bad))

    def test_common_rotation_keeps_hand_body_pose_and_joints(self):
        sim = BimanualSimulation(); cycle = UnityCycle(sim)
        cycle.receive(packet(sim, 0, 0., False), 0.)
        cycle.receive(packet(sim, 1, 0., True), 1/60)
        initial = sim.config.q[sim.qids].copy()
        for seq, yaw in enumerate(np.linspace(0, 2*np.pi, 65), 2):
            cycle.receive(packet(sim, seq, yaw, True), seq/60)
            cycle.tick(seq/60)
            self.assertEqual(cycle.state, 'tracking')
            self.assertNotEqual(sim.state, 'blocked', sim.reason)
            np.testing.assert_allclose(sim.config.q[sim.qids], initial, atol=2e-5)
            for side in ('left', 'right'):
                fk = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link', 'body')
                expected = sim.base_rotation @ sim.home_targets[side].translation()
                np.testing.assert_allclose(fk.translation(), expected, atol=2e-5)
                feedback = cycle.feedback()
                np.testing.assert_allclose(feedback[side+'_ik_target_world_m'], BASIS.T @ expected, atol=1e-8)
                np.testing.assert_allclose(feedback[side+'_actual_wrist_world_m'], BASIS.T @ fk.translation(), atol=1e-8)
                self.assertLess(feedback[side+'_ik_position_error_m'], 2e-5)

    def test_forward_and_lateral_reaches_are_rotation_invariant(self):
        offsets = [dict(left=np.array([.04,0.,.01]), right=np.array([.04,0.,.01])),
                   dict(left=np.array([0.,.04,0.]), right=np.array([0.,-.04,0.]))]
        for offset in offsets:
            results = []
            for yaw in (0., np.pi/2, np.pi, -np.pi/2):
                sim = BimanualSimulation(); cycle = UnityCycle(sim)
                cycle.receive(packet(sim, 0, yaw, False), 0.)
                cycle.receive(packet(sim, 1, yaw, True), 1/60)
                for seq in range(2, 22):
                    cycle.receive(packet(sim, seq, yaw, True, offset), seq/60)
                    cycle.tick(seq/60)
                self.assertNotEqual(sim.state, 'blocked', sim.reason)
                results.append(sim.config.q[sim.qids].copy())
            for q in results[1:]: np.testing.assert_allclose(q, results[0], atol=2e-4)

    def test_reaching_while_turning_matches_stationary_arm_motion(self):
        sims = [BimanualSimulation(), BimanualSimulation()]
        cycles = [UnityCycle(sim) for sim in sims]
        for sim, cycle in zip(sims, cycles):
            cycle.receive(packet(sim, 0, 0., False), 0.)
            cycle.receive(packet(sim, 1, 0., True), 1/60)
        offset = dict(left=np.array([.05,.025,.02]), right=np.array([.05,-.025,.02]))
        for seq in range(2, 62):
            for index, (sim, cycle) in enumerate(zip(sims, cycles)):
                yaw = index*(seq-2)*np.pi/60
                cycle.receive(packet(sim, seq, yaw, True, offset), seq/60)
                cycle.tick(seq/60)
                self.assertNotEqual(sim.state, 'blocked', sim.reason)
            np.testing.assert_allclose(sims[0].config.q[sims[0].qids], sims[1].config.q[sims[1].qids], atol=2e-4)

    def test_braking_tail_keeps_latest_base_rotation(self):
        sim = BimanualSimulation(); cycle = UnityCycle(sim)
        cycle.receive(packet(sim, 0, 0., False), 0.)
        cycle.receive(packet(sim, 1, 0., True), 1/60)
        offset = dict(left=np.array([.04,0.,0.]), right=np.array([.04,0.,0.]))
        for seq in range(2, 12):
            cycle.receive(packet(sim, seq, 0., True, offset), seq/60)
            cycle.tick(seq/60)
        p = packet(sim, 12, np.pi/2, True)
        p['left']['tracked'] = False
        cycle.receive(p, 12/60); cycle.tick(12/60)
        self.assertEqual(cycle.last_tick_action, 'tracking_braking')
        a = sim.base_qadr
        np.testing.assert_allclose(sim.config.q[a:a+7], sim.home[a:a+7], atol=1e-10)

    def test_frame_switch_is_rejected_while_engaged(self):
        sim = BimanualSimulation(); cycle = UnityCycle(sim)
        cycle.receive(packet(sim, 0, 0., False), 0.)
        cycle.receive(packet(sim, 1, 0., True), 1/60)
        p = packet(sim, 2, 0., True); p['input_frame'] = 'legacy_relative'
        self.assertFalse(cycle.receive(p, 2/60))
        self.assertEqual(cycle.reason, 'input_frame_changed')

if __name__ == '__main__': unittest.main()
