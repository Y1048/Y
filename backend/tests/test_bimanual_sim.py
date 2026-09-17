"""Generated kinematic fixtures only; no hardware or Unity evidence."""
import ast
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'MuJoCo_G1_Controller/scripts'))
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
            self.assertLessEqual(np.max(np.abs(s.velocity-old_v)), np.radians(60)*s.dt+1e-6)
            self.assertTrue(np.all(np.abs(s.velocity[s.dofs]) <= s.caps+1e-6))
        self.assertGreaterEqual(minimum, .005)
        self.assertGreater(np.max(moved[:7]), .05)
        self.assertGreater(np.max(moved[7:]), .05)
        return s

    def test_crossed_targets_keep_sampled_clearance(self):
        self.run_motion(True)

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
