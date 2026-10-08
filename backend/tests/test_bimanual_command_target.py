"""Same-frame command FK display contract; offline model checks, no robot IO."""
import gzip
import json
from pathlib import Path
import sys
import unittest

import mink
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_measured_start import JOINT_NAMES, initialize_inactive_model
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_target import BASIS
from g1_bimanual_unity_sim import UnityCycle, WORLD_FRAME

SIDES = ('left', 'right')
ARM_NAMES = [side + '_' + joint + '_joint' for side in SIDES for joint in (
    'shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
    'wrist_roll', 'wrist_pitch', 'wrist_yaw')]


class CommandTargetTests(unittest.TestCase):
    def setUp(self):
        self.sim = BimanualSimulation()
        self.cycle = UnityCycle(self.sim)
        self.cycle.world_input = True
        self.cycle.input_frame = WORLD_FRAME
        self.cycle.state = self.sim.state = 'tracking'
        self.cycle.last_tick_action = 'tracking'
        self.cycle.sequence = 31
        self.cycle.feedback_sequence = 72

    def assert_command_fk(self, feedback):
        """Reconstruct from serialized command angles, not feedback wrist fields."""
        target = feedback['command_target']
        self.assertTrue(target['valid'])
        self.assertEqual(target['schema'], 'g1.bimanual.command.target.v1')
        self.assertEqual(target['status'], 'checked_command_fk')
        self.assertEqual(target['source_sequence'], feedback['sequence'])
        self.assertEqual(target['feedback_sequence'], feedback['feedback_sequence'])
        self.assertEqual(target['age_s'], 0.)
        self.assertEqual(feedback['joint_names'], ARM_NAMES)
        qids = [self.sim.model.jnt_qposadr[mujoco.mj_name2id(
            self.sim.model, mujoco.mjtObj.mjOBJ_JOINT, name)] for name in ARM_NAMES]
        independent = mujoco.MjData(self.sim.model)
        independent.qpos[:] = self.sim.config.q
        independent.qpos[qids] = feedback['q_rad']
        mujoco.mj_fwdPosition(self.sim.model, independent)
        for side in SIDES:
            body = mujoco.mj_name2id(self.sim.model, mujoco.mjtObj.mjOBJ_BODY,
                                   side + '_wrist_yaw_link')
            expected_position = BASIS.T @ independent.xpos[body]
            expected_rotation = BASIS.T @ independent.xmat[body].reshape(3, 3) @ BASIS
            np.testing.assert_allclose(target[side + '_world_m'], expected_position,
                                       atol=1e-12, rtol=0.)
            actual_rotation = mink.SO3(np.asarray(target[side + '_world_wxyz'])).as_matrix()
            np.testing.assert_allclose(actual_rotation, expected_rotation,
                                       atol=2e-12, rtol=0.)
        return target

    def test_order_is_left_15_through_21_then_right_22_through_28(self):
        self.assertEqual([name + '_joint' for name in JOINT_NAMES[15:29]], ARM_NAMES)
        self.assertEqual(list(self.sim.names), ARM_NAMES)
        q = self.sim.config.q.copy()
        # Distinct values make a swapped wrist or arm observable to independent FK.
        q[self.sim.qids] += np.linspace(-.015, .017, 14)
        self.sim.config.update(q)
        feedback = self.cycle.feedback()
        np.testing.assert_array_equal(feedback['q_rad'], q[self.sim.qids])
        self.assert_command_fk(feedback)

    def test_source_and_feedback_sequences_use_same_frame_not_prior_result(self):
        for source_sequence in (501, 502, 811):
            q = self.sim.config.q.copy()
            q[self.sim.qids[0]] -= .01
            q[self.sim.qids[11]] += .01
            self.sim.config.update(q)
            self.cycle.sequence = source_sequence
            feedback_sequence = self.cycle.feedback_sequence
            feedback = self.cycle.feedback()
            self.assertEqual(feedback['feedback_sequence'], feedback_sequence)
            self.assertEqual(self.cycle.feedback_sequence, feedback_sequence + 1)
            self.assert_command_fk(feedback)

    def test_prescribed_body_yaw_and_measured_start_use_command_source_body(self):
        fixture = json.loads((ROOT / 'backend/tests/fixtures/g1_measured_start_20261007.json').read_text(encoding='utf-8-sig'))
        self.sim.state = 'ready'
        initialize_inactive_model(self.sim, np.asarray(fixture['q_rad']))
        self.sim.state = 'tracking'
        for yaw in (0., .4, -1.2):
            with self.subTest(yaw=yaw):
                self.sim.set_base_yaw(yaw)
                self.cycle.base_yaw_rad = yaw
                self.assert_command_fk(self.cycle.feedback())

    def test_feedback_does_not_mutate_command_or_motion_history(self):
        q = self.sim.config.q.copy()
        velocity = self.sim.velocity.copy()
        acceleration = self.sim.acceleration.copy()
        ranges = self.sim.model.jnt_range.copy()
        self.sim.brake_plan = [(q.copy(), velocity.copy())]
        feedback = self.cycle.feedback()
        self.assert_command_fk(feedback)
        feedback['q_rad'][0] += 1.
        feedback['command_target']['left_world_m'][0] += 1.
        np.testing.assert_array_equal(self.sim.config.q, q)
        np.testing.assert_array_equal(self.sim.velocity, velocity)
        np.testing.assert_array_equal(self.sim.acceleration, acceleration)
        np.testing.assert_array_equal(self.sim.model.jnt_range, ranges)
        np.testing.assert_array_equal(self.sim.brake_plan[0][0], q)
        np.testing.assert_array_equal(self.sim.brake_plan[0][1], velocity)

    def test_independent_measured_pose_is_not_the_command_marker(self):
        feedback = self.cycle.feedback()
        target = self.assert_command_fk(feedback)
        # A separate model represents lagging measured joints. It must not
        # overwrite the command-derived marker or its source command angles.
        measured = mujoco.MjData(self.sim.model)
        measured.qpos[:] = self.sim.config.q
        measured.qpos[self.sim.qids[[0, 7]]] -= .12
        mujoco.mj_fwdPosition(self.sim.model, measured)
        for side in SIDES:
            body = mujoco.mj_name2id(self.sim.model, mujoco.mjtObj.mjOBJ_BODY,
                                   side + '_wrist_yaw_link')
            self.assertGreater(np.linalg.norm(np.asarray(target[side + '_world_m'])
                                              - BASIS.T @ measured.xpos[body]), .01)
        self.assertEqual(self.cycle.feedback()['command_target']['left_world_m'],
                         target['left_world_m'])

    def test_reachable_and_unreachable_requests_do_not_replace_command_fk(self):
        for side in SIDES:
            pose = self.sim.config.get_transform_frame_to_world(side + '_wrist_yaw_link', 'body')
            self.sim.motion[side].position_approach_rate_s = 1.
            self.sim.motion[side].orientation_approach_rate_s = 1.
            self.sim.motion[side].effective_target_position = pose.translation().copy()
            self.sim.motion[side].effective_target_rotation = pose.rotation().as_matrix()
        reachable = self.cycle.feedback()
        self.assert_command_fk(reachable)
        for side in SIDES:
            np.testing.assert_allclose(reachable['command_target'][side + '_world_m'],
                                       reachable[side + '_ik_target_world_m'], atol=1e-12)
            self.sim.motion[side].effective_target_position = np.array([9., 8., 7.])
        unreachable = self.cycle.feedback()
        self.assert_command_fk(unreachable)
        for side in SIDES:
            self.assertEqual(unreachable['command_target'][side + '_world_m'],
                             reachable['command_target'][side + '_world_m'])
            self.assertGreater(np.linalg.norm(np.asarray(unreachable['command_target'][side + '_world_m'])
                                              - unreachable[side + '_ik_target_world_m']), 1.)

    def test_checked_braking_uses_current_command_not_stop_tail_endpoint(self):
        end = self.sim.config.q.copy()
        end[self.sim.qids[[0, 7]]] -= .05
        self.sim.brake_plan = [(end, np.zeros(self.sim.model.nv))]
        self.cycle.last_tick_action = 'tracking_braking'
        feedback = self.cycle.feedback()
        self.assert_command_fk(feedback)
        for side in SIDES:
            self.assertGreater(np.linalg.norm(np.asarray(feedback['command_target'][side + '_world_m'])
                                              - feedback[side + '_checked_target_world_m']), .001)

    def test_inactive_or_legacy_states_do_not_advertise_active_target(self):
        for cycle_state, sim_state, world in (
                ('ready', 'ready', True), ('returning', 'tracking', True),
                ('blocked', 'blocked', True), ('tracking', 'blocked', True),
                ('tracking', 'tracking', False)):
            with self.subTest(cycle=cycle_state, sim=sim_state, world=world):
                self.cycle.state, self.sim.state = cycle_state, sim_state
                self.cycle.world_input = world
                target = self.cycle.feedback()['command_target']
                self.assertFalse(target['valid'])
                self.assertEqual(target['status'], 'inactive')

    def test_entire_recorded_618_frame_command_sequence_matches_independent_fk(self):
        fixture = json.loads(gzip.decompress((ROOT / 'backend/tests/fixtures/geometric_goal_operator_20261008.json.gz').read_bytes()))
        self.assertFalse(fixture['hardware_validation'])
        self.assertEqual(len(fixture['frames']), 618)
        for frame in fixture['frames']:
            self.sim.config.update(np.asarray(frame['q']))
            self.sim.base_rotation = np.asarray(frame['base_rotation'])
            self.cycle.sequence = frame['sequence']
            q = self.sim.config.q.copy()
            self.assert_command_fk(self.cycle.feedback())
            np.testing.assert_array_equal(self.sim.config.q, q)


if __name__ == '__main__':
    unittest.main()
