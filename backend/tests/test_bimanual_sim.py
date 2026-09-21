"""Generated kinematic fixtures only; no hardware or Unity evidence."""
import ast
import json
import time
from types import SimpleNamespace
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
import g1_bimanual_sim as module
from g1_bimanual_sim import BimanualSimulation, targets_from_json, mink, mujoco


class BimanualTests(unittest.TestCase):
    def setUp(self):
        self.s = BimanualSimulation()

    def test_order_and_hand_pairs(self):
        s = self.s
        self.assertEqual(len(s.names), 14)
        self.assertEqual(s.names, module.base.g1.G1_29_JOINTS[15:29])
        hands = [mujoco.mj_name2id(s.model, mujoco.mjtObj.mjOBJ_GEOM,
                 'mink_' + side + '_rubber_hand_collision') for side in ('left', 'right')]
        self.assertIn(tuple(sorted(hands)), [tuple(sorted(p)) for p in s.pairs])
        self.assertGreater(s.clearance(s.home), .005)

    def test_all_fourteen_limits_and_checked_stop_use_90_180_60(self):
        s = self.s
        self.assertAlmostEqual(JOINT_VELOCITY_LIMIT_RAD_S, np.pi)
        self.assertAlmostEqual(JOINT_ACCELERATION_LIMIT_RAD_S2, np.pi/3)
        np.testing.assert_array_equal(s.caps, np.tile(np.deg2rad([90]*4+[180]*3), 2))
        np.testing.assert_array_equal(s.return_motion.acceleration_limits, np.full(14, np.pi/3))
        for policy in s.motion.values():
            np.testing.assert_array_equal(policy.acceleration_limits, np.full(7, np.pi/3))
        # Isolate the discrete limit boundary from the independent geometry guard.
        wrist = s.motion['right'].dofs[4]
        s.velocity[wrist] = np.pi - (np.pi/3)*s.dt
        proposed = s.velocity.copy()
        proposed[wrist] = np.pi
        # Isolate numerical velocity/acceleration boundaries from travel limits.
        with patch.object(s, 'clearance', return_value=.2), patch.object(
                s, 'ranges', np.tile([-100., 100.], (14, 1))):
            plan, reason = s.checked_stop_plan(proposed)
            self.assertIsNotNone(plan, reason)
            previous = s.velocity.copy()
            for _, velocity in plan:
                self.assertLessEqual(np.max(np.abs(velocity-previous))/s.dt, np.pi/3+1e-6)
                previous = velocity
            self.assertEqual(np.max(np.abs(previous)), 0.)
            proposed[wrist] = np.pi + .001
            self.assertEqual(s.checked_stop_plan(proposed), (None, 'velocity_acceleration'))
            s.velocity[wrist] = 0.
            proposed[wrist] = (np.pi/3)*s.dt + .001
            self.assertEqual(s.checked_stop_plan(proposed), (None, 'velocity_acceleration'))

    def test_no_transport_in_entrypoint(self):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertFalse(any(x.startswith(('socket', 'unitree', 'cyclonedds', 'subprocess')) for x in imports))
        # Guard against an inherited command-stream sender ever being invoked.
        with patch.object(module.base.MinkCommandStream, '__init__', side_effect=AssertionError('sender')):
            self.assertTrue(self.s.step(self.s.home_targets))

    def test_missing_nonfinite_and_quaternion(self):
        with self.assertRaises(ValueError):
            self.s.step({'left': self.s.home_targets['left']})
        for quaternion in ([0, 0, 0, 0], [float('nan'), 0, 0, 1]):
            with self.assertRaises(ValueError):
                targets_from_json(dict(schema='g1.bimanual.sim.v1', simulation_only=True,
                    left=dict(position_m=[0, 0, 0], quaternion_wxyz=quaternion)))
        with self.assertRaises(ValueError):
            targets_from_json({'schema': 'g1.mink.cycle.live.v1'})

    def test_clearance_guard_rejects_interior_and_latches(self):
        q = self.s.config.q.copy()
        with patch.object(self.s, 'clearance', side_effect=[.004]):
            self.assertFalse(self.s.step(self.s.home_targets))
        np.testing.assert_array_equal(q, self.s.config.q)
        self.assertEqual(self.s.reason, 'swept_clearance')
        self.assertFalse(self.s.step(self.s.home_targets))

    def run_motion(self, crossed):
        s = self.s
        frozen = np.ones(s.model.nq, dtype=bool)
        frozen[s.qids] = False
        minimum = .2
        moved = np.zeros(14)
        for tick in range(420):
            targets = {}
            for side, sign in (('left', 1), ('right', -1)):
                home = s.home_targets[side]
                p = home.translation().copy()
                p += np.array([.08, -sign*(.45 if crossed else .06), .04])*min(tick/180, 1)
                targets[side] = mink.SE3.from_rotation_and_translation(home.rotation(), p)
            old_v = s.velocity.copy()
            accepted = s.step(targets)
            np.testing.assert_array_equal(s.config.q[frozen], s.home[frozen])
            minimum = min(minimum, s.clearance(s.config.q))
            moved = np.maximum(moved, np.abs((s.config.q-s.home)[s.qids]))
            if not accepted:
                break
            self.assertLessEqual(np.max(np.abs(s.velocity-old_v)), JOINT_ACCELERATION_LIMIT_RAD_S2*s.dt+1e-6)
            self.assertTrue(np.all(np.abs(s.velocity[s.dofs]) <= s.caps+1e-6))
        self.assertGreaterEqual(minimum, .005)
        self.assertGreater(np.max(moved[:7]), .05)
        self.assertGreater(np.max(moved[7:]), .05)
        return s

    def test_crossed_targets_keep_sampled_clearance(self):
        self.run_motion(True)

    def test_checked_tail_stops_on_infeasible_qp_without_reset(self):
        targets = {}
        for side, home in self.s.home_targets.items():
            targets[side] = mink.SE3.from_rotation_and_translation(home.rotation(), home.translation()+[.05, 0, .03])
        for _ in range(20):
            self.assertTrue(self.s.step(targets))
        self.assertGreater(np.max(np.abs(self.s.velocity)), .01)
        with patch.object(module.qpsolvers, 'solve_problem', return_value=SimpleNamespace(found=False, x=None)):
            for _ in range(100):
                previous = self.s.velocity.copy()
                self.assertTrue(self.s.step(targets))
                self.assertLessEqual(np.max(np.abs(self.s.velocity-previous)), JOINT_ACCELERATION_LIMIT_RAD_S2*self.s.dt+1e-6)
                self.assertGreaterEqual(self.s.clearance(self.s.config.q), .005)
        self.assertEqual(np.max(np.abs(self.s.velocity)), 0)
        self.assertTrue(self.s.step(targets))

    def test_broadphase_matches_full_clearance_decision(self):
        rng = np.random.default_rng(1809)
        for _ in range(120):
            q = self.s.home.copy()
            q[self.s.qids] = rng.uniform(self.s.ranges[:,0], self.s.ranges[:,1])
            exact = self.s.clearance(q)
            fast = self.s.clearance(q, threshold=.005)
            self.assertEqual(exact < .005, fast < .005)

    def test_bounding_sphere_exclusion_is_conservative(self):
        rng = np.random.default_rng(2026091817)
        fromto = np.zeros(6)
        a, b = self.s.pair_array.T
        for _ in range(300):
            q = self.s.home.copy()
            q[self.s.qids] = rng.uniform(self.s.ranges[:,0], self.s.ranges[:,1])
            self.s.check_data.qpos[:] = q
            mujoco.mj_kinematics(self.s.model, self.s.check_data)
            rotation = self.s.check_data.geom_xmat.reshape(-1, 3, 3)
            center = self.s.check_data.geom_xpos + np.einsum(
                'nij,nj->ni', rotation, self.s._clearance_local_centers)
            lower = (np.linalg.norm(center[a]-center[b], axis=1)
                     - self.s._clearance_bounding_radii[a]
                     - self.s._clearance_bounding_radii[b])
            for index in np.flatnonzero(lower > self.s.clearance_m + 1e-8):
                distance = mujoco.mj_geomDistance(
                    self.s.model, self.s.check_data, int(a[index]), int(b[index]), .2, fromto)
                self.assertGreater(distance, self.s.clearance_m + 1e-8)

    def test_kinematic_clearance_matches_full_forward(self):
        rng = np.random.default_rng(20260918)
        data = mujoco.MjData(self.s.model)
        for _ in range(500):
            q = self.s.home.copy()
            fraction = rng.uniform(.05, .95, len(self.s.qids))
            q[self.s.qids] = (self.s.ranges[:,0]
                + fraction*(self.s.ranges[:,1]-self.s.ranges[:,0]))
            data.qpos[:] = q
            mujoco.mj_forward(self.s.model, data)
            expected = module.base._nearest_pair_distance(
                self.s.model, data, self.s.pairs)
            expected_distance = .2 if expected is None else expected[0]
            actual_distance = self.s.clearance(q)
            self.assertEqual(expected_distance, actual_distance)
            np.testing.assert_array_equal(data.geom_xpos, self.s.check_data.geom_xpos)
            np.testing.assert_array_equal(data.geom_xmat, self.s.check_data.geom_xmat)

    def test_kinematic_clearance_promotes_zero_distance_to_contact_path(self):
        with (patch.object(module.mujoco, 'mj_geomDistance', return_value=0.),
              patch.object(module.mujoco, 'mj_fwdPosition') as promoted,
              patch.object(module.base, '_robust_geom_distance', return_value=.123) as robust):
            self.assertEqual(self.s.clearance(self.s.home), .123)
        promoted.assert_called_once_with(self.s.model, self.s.check_data)
        self.assertEqual(robust.call_count, len(self.s.pairs))

    def test_kinematic_clearance_nonzero_path_skips_contact_promotion(self):
        with (patch.object(module.mujoco, 'mj_geomDistance', return_value=.1),
              patch.object(module.mujoco, 'mj_fwdPosition') as promoted,
              patch.object(module.base, '_robust_geom_distance',
                           side_effect=AssertionError('unexpected robust path'))):
            self.assertEqual(self.s.clearance(self.s.home), .1)
        promoted.assert_not_called()

    def test_nonfinite_clearance_rejects_new_plan(self):
        with patch.object(self.s, 'clearance', return_value=float('nan')):
            self.assertFalse(self.s.step(self.s.home_targets))
        self.assertEqual(self.s.state, 'blocked')

    def test_recorded_unity_failure_replay(self):
        # Recorded Quest/Unity simulation input; NOT measured G1 data.
        from g1_bimanual_unity_sim import UnityCycle
        cycle = UnityCycle(self.s)
        timing = []
        reached_old_failure = False
        states = set()
        fixture = Path(__file__).parent/'fixtures/bimanual_recorded_engage_20260918.jsonl'
        for line in fixture.read_text().splitlines():
            row = json.loads(line)
            if row['kind'] == 'input':
                cycle.receive(json.loads(row['raw_json_text']), row['receive_monotonic_s'])
            else:
                old_v = self.s.velocity.copy()
                start = time.perf_counter()
                cycle.tick(row['monotonic_s'])
                timing.append((time.perf_counter()-start)*1000)
                states.add(cycle.state)
                self.assertNotEqual(cycle.state, 'blocked', cycle.reason)
                self.assertLessEqual(np.max(np.abs(self.s.velocity-old_v)), JOINT_ACCELERATION_LIMIT_RAD_S2*self.s.dt+1e-6)
                self.assertTrue(np.all(np.abs(self.s.velocity[self.s.dofs]) <= self.s.caps+1e-6))
                self.assertTrue(np.all(self.s.config.q[self.s.qids] >= self.s.ranges[:,0]-1e-8))
                self.assertTrue(np.all(self.s.config.q[self.s.qids] <= self.s.ranges[:,1]+1e-8))
                self.assertGreaterEqual(self.s.clearance(self.s.config.q), .005)
                reached_old_failure |= row['sequence'] == 607
        self.assertTrue(reached_old_failure)
        self.assertIn('tracking', states)
        # The new approach policy may avoid this fixture's old failure entirely.
        # Forced-QP-failure coverage above still requires checked braking to stop.
        self.assertTrue(self.s.brake_plan, 'A checked stopping tail must remain available')
        print('Recorded simulation replay: ticks=%d braking=%d p95_ms=%.2f max_ms=%.2f' %
              (len(timing), self.s.braking_steps, np.percentile(timing,95), max(timing)))

    def test_reach_return_reengage(self):
        s = self.run_motion(False)
        self.assertNotEqual(s.state, 'blocked')
        for _ in range(1380):
            self.assertTrue(s.step(returning=True), s.reason)
        self.assertEqual(s.state, 'ready')
        self.assertTrue(s.step(s.home_targets))
        self.assertEqual(s.state, 'tracking')


if __name__ == '__main__':
    unittest.main()
