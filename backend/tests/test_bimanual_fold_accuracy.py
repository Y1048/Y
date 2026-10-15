"""Generated model-space goals, not hardware response or motor-zero validation."""
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_sim import BimanualSimulation, mink


class FoldAccuracyTests(unittest.TestCase):
    def test_negative_model_elbow_folds_instead_of_hyperextending(self):
        sim = BimanualSimulation()
        angles = []
        for degrees in (-30., 5.):
            q = sim.home.copy()
            q[sim.qids[[3, 10]]] = np.deg2rad(degrees)
            sim.config.update(q)
            both = []
            for side in ('left', 'right'):
                def point(link):
                    return sim.config.get_transform_frame_to_world(
                        side + '_' + link + '_link', 'body').translation()
                elbow = point('elbow')
                a = point('shoulder_yaw') - elbow
                b = point('wrist_roll') - elbow
                both.append(np.rad2deg(np.arccos(np.clip(
                    np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b), -1., 1.))))
            angles.append(both)
        self.assertTrue(np.all(np.asarray(angles[0]) < np.asarray(angles[1])))
        self.assertTrue(np.all(np.asarray(angles) < 180.))

    def test_folded_pose_converges_and_can_return_and_reengage(self):
        sim = BimanualSimulation()
        witness = sim.home.copy()
        witness[sim.qids[[3, 10]]] = np.deg2rad(-15.)
        self.assertGreater(sim.clearance(witness), .005)
        probe = mink.Configuration(sim.model)
        probe.update(witness)
        targets = {side: probe.get_transform_frame_to_world(
            side + '_wrist_yaw_link', 'body') for side in ('left', 'right')}
        for _ in range(600):
            previous = sim.velocity.copy()
            self.assertTrue(sim.step(targets), sim.reason)
            self.assertTrue(np.all(abs(sim.velocity[sim.dofs]) <= sim.caps + 1e-6))
            self.assertLessEqual(np.max(abs(sim.velocity - previous)),
                                 sim.profile.joint_acceleration_limit_rad_s2 * sim.dt + 1e-6)
            self.assertGreaterEqual(sim.clearance(sim.config.q), .005)
        for side in ('left', 'right'):
            actual = sim.config.get_transform_frame_to_world(side + '_wrist_yaw_link', 'body')
            self.assertLess(np.linalg.norm(actual.translation() - targets[side].translation()), .003)
            self.assertLess(np.linalg.norm((actual.rotation().inverse() @ targets[side].rotation()).log()), np.deg2rad(1.))
        for _ in range(1800):
            self.assertTrue(sim.step(returning=True), sim.reason)
            if sim.return_motion.stage == 'complete':
                break
        self.assertEqual(sim.return_motion.stage, 'complete')
        self.assertTrue(sim.step(sim.home_targets), sim.reason)


if __name__ == '__main__':
    unittest.main()
