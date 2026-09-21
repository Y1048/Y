"""IK goal markers must differ from the lagging wrist, without control effects."""
import json
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import UnityCycle, BASIS, mink
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation
from test_bimanual_unity_sim import packet
from g1_bimanual_unity_sim import decode
from unittest.mock import Mock


class MarkerFeedbackTests(unittest.TestCase):
    def test_engage_residual_is_in_real_goal_and_latched_per_cycle(self):
        sim = Mock()
        sim.state = 'tracking'
        sim.home_targets = {s: mink.SE3.identity() for s in ('left', 'right')}
        cycle = UnityCycle(sim)
        cycle.receive(packet(), 0)
        engaged = packet(1, True)
        offsets = {'left': [.0234, .0426, .0379], 'right': [-.0117, .0449, -.0276]}
        for side in offsets:
            engaged[side]['engage_offset_m'] = offsets[side]
        cycle.receive(decode(json.dumps(engaged).encode()), .02)
        cycle.tick(.02)
        for side in offsets:
            np.testing.assert_allclose(sim.step.call_args.args[0][side].translation(), BASIS@offsets[side])
        changed = packet(2, True)
        for side in offsets:
            changed[side]['engage_offset_m'] = [0., 0., 0.]
        cycle.receive(changed, .04)
        cycle.tick(.04)
        for side in offsets:
            np.testing.assert_allclose(sim.step.call_args.args[0][side].translation(), BASIS@offsets[side])
        cycle.state = 'ready'
        cycle.receive(packet(3), .06)
        cycle.receive(packet(4, True), .08)
        cycle.tick(.08)
        for side in offsets:
            np.testing.assert_allclose(sim.step.call_args.args[0][side].translation(), np.zeros(3))

    def test_invalid_engage_offsets_rejected(self):
        for offset in ([0, 0], [0, 0, float('nan')], [.151, 0, 0], [True, 0, 0], None):
            with self.subTest(offset=offset):
                p = packet()
                p['left']['engage_offset_m'] = offset
                with self.assertRaises(ValueError):
                    decode(json.dumps(p).encode())

    def test_engage_offset_first_step_remains_acceleration_bounded(self):
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        cycle.receive(packet(), 0)
        p = packet(1, True)
        for side in ('left', 'right'):
            p[side]['engage_offset_m'] = [0., 0., .06]
        cycle.receive(p, .02)
        before = sim.config.q.copy()
        cycle.tick(.02)
        self.assertNotEqual(cycle.state, 'blocked')
        self.assertLessEqual(float(np.max(np.abs(sim.velocity))), JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt+1e-6)
        self.assertLessEqual(float(np.max(np.abs(sim.config.q-before))), JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt**2+1e-6)
        self.assertGreaterEqual(sim.clearance(sim.config.q), .005)

    def test_marker_is_requested_goal_and_feedback_does_not_change_motion(self):
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        goals = {side: mink.SE3.from_rotation_and_translation(home.rotation(),
                 home.translation()+np.array([.05, 0, 0]))
                 for side, home in sim.home_targets.items()}
        self.assertTrue(sim.step(goals))
        cycle.state = 'tracking'
        cycle.last_tick_action = 'tracking'
        q, velocity = sim.config.q.copy(), sim.velocity.copy()
        tail = [(a.copy(), b.copy()) for a, b in sim.brake_plan]
        feedback = cycle.feedback()
        self.assertTrue(feedback['ik_target_valid'])
        for side in goals:
            delta = feedback[side+'_ik_target_operator_delta']
            accepted = sim.home_targets[side].translation()+BASIS@np.asarray(delta)
            pose = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link','body')
            np.testing.assert_allclose(accepted, goals[side].translation(), atol=1e-12)
            self.assertGreater(np.linalg.norm(accepted-pose.translation()), .04)
        np.testing.assert_array_equal(sim.config.q, q)
        np.testing.assert_array_equal(sim.velocity, velocity)
        for before, after in zip(tail, sim.brake_plan):
            for a, b in zip(before, after):
                np.testing.assert_array_equal(a, b)
        self.assertLess(len(json.dumps(feedback).encode()), 4096)

    def test_inactive_braking_and_blocked_do_not_advertise_target(self):
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        for state, action, sim_state, reason in (
                ('ready','idle','ready',''), ('returning','returning','returning',''),
                ('tracking','tracking_braking','tracking','checked_braking:lost'),
                ('blocked','tracking','blocked','swept_clearance')):
            with self.subTest(state=state, action=action, reason=reason):
                cycle.state, cycle.last_tick_action = state, action
                sim.state, sim.reason = sim_state, reason
                result = cycle.feedback()
                self.assertFalse(result['ik_target_valid'])
                self.assertIsNone(result['left_ik_target_operator_delta'])
                self.assertIsNone(result['right_ik_target_operator_delta'])

    def test_torso_projection_is_shown_instead_of_impossible_raw_goal(self):
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        for side, policy in sim.motion.items():
            center = sim.config.data.geom_xpos[policy.torso_geom_ids[0]].copy()
            goal = mink.SE3.from_rotation_and_translation(sim.home_targets[side].rotation(), center)
            policy.prepare(goal, .04)
            self.assertTrue(policy.target_projected)
        cycle.state = sim.state = 'tracking'
        cycle.last_tick_action = 'tracking'
        sim.reason = 'checked_braking:solver'
        result = cycle.feedback()
        self.assertTrue(result['ik_target_valid'])
        for side, policy in sim.motion.items():
            delta = result[side+'_ik_target_operator_delta']
            shown = sim.home_targets[side].translation()+BASIS@np.asarray(delta)
            np.testing.assert_allclose(shown, policy.effective_target_position, atol=1e-12)
            self.assertGreater(np.linalg.norm(shown-policy.raw_target_position), .005)


if __name__ == '__main__':
    unittest.main()
