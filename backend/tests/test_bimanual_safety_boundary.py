import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import mink
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))

from g1_bimanual_sim import BimanualSimulation


class BimanualSafetyBoundaryTests(unittest.TestCase):
    def test_simulation_exposes_one_named_safety_boundary(self):
        sim = BimanualSimulation()
        self.assertIs(sim.limits, sim.safety.limits)
        self.assertIs(sim.profile, sim.safety.profile)
        self.assertIs(sim.check_data, sim.safety.check_data)
        self.assertIs(sim.pair_array, sim.safety.pair_array)
        self.assertIs(
            sim._clearance_local_centers,
            sim.safety.clearance_local_centers)
        self.assertIs(
            sim._clearance_bounding_radii,
            sim.safety.clearance_bounding_radii)
        self.assertEqual(
            sim.clearance(sim.home),
            sim.safety.clearance(sim.home))
        self.assertEqual(len(sim.limits), 3)

    def test_checked_stop_plan_proxy_delegates_to_safety(self):
        sim = BimanualSimulation()
        expected = ([(sim.config.q.copy(), np.zeros(sim.model.nv))], "")
        delegate = Mock(return_value=expected)
        sim.safety.checked_stop_plan = delegate
        velocity = np.zeros(sim.model.nv)
        actual = sim.checked_stop_plan(velocity)
        self.assertIs(actual, expected)
        delegate.assert_called_once_with(velocity)

    def test_raw_torso_intrusion_stays_outside_hard_clearance_and_recovers(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                sim = BimanualSimulation()
                policy = sim.motion[side]
                start = sim.home_targets[side].translation().copy()
                centers = np.array([
                    sim.config.data.geom_xpos[geom]
                    for geom in policy.torso_geom_ids
                ])
                center = centers[
                    np.argmin(np.linalg.norm(centers - start, axis=1))]
                direction = center - start
                direction /= np.linalg.norm(direction)

                entry = None
                for distance in np.arange(0.0, 0.5, 0.0005):
                    point = start + direction * distance
                    inside = False
                    for geom in policy.torso_geom_ids:
                        geom_center = sim.config.data.geom_xpos[geom]
                        rotation = sim.config.data.geom_xmat[geom].reshape(3, 3)
                        half = (
                            sim.model.geom_size[geom]
                            + policy.wrist_target_radius_m
                            + sim.clearance_m
                        )
                        local = rotation.T @ (point - geom_center)
                        if np.all(np.abs(local) < half):
                            inside = True
                            break
                    if inside:
                        entry = distance
                        break
                self.assertIsNotNone(entry)

                raw_position = start + direction * (entry + 0.020)
                target = mink.SE3.from_rotation_and_translation(
                    sim.home_targets[side].rotation(), raw_position)
                targets = dict(sim.home_targets)
                targets[side] = target

                minimum_clearance = float("inf")
                for _ in range(300):
                    self.assertTrue(sim.step(targets), sim.reason)
                    minimum_clearance = min(
                        minimum_clearance, sim.clearance(sim.config.q))
                    self.assertNotEqual(sim.state, "blocked")
                self.assertFalse(policy.target_projected)
                np.testing.assert_allclose(
                    policy.effective_target_position,
                    raw_position,
                    atol=1e-12)
                self.assertGreaterEqual(
                    minimum_clearance,
                    sim.clearance_m - 1e-8)

                for _ in range(360):
                    self.assertTrue(
                        sim.step(dict(sim.home_targets)), sim.reason)
                    minimum_clearance = min(
                        minimum_clearance, sim.clearance(sim.config.q))
                wrist = sim.config.get_transform_frame_to_world(
                    side + "_wrist_yaw_link", "body")
                self.assertLess(
                    np.linalg.norm(wrist.translation() - start),
                    0.003)
                self.assertGreaterEqual(
                    minimum_clearance,
                    sim.clearance_m - 1e-8)

    def test_live_step_passes_qp_through_safety_boundary(self):
        sim = BimanualSimulation()
        original = sim.safety.constrain_problem
        calls = []

        def record(problem, *, returning=False):
            calls.append(returning)
            return original(problem, returning=returning)

        sim.safety.constrain_problem = record
        self.assertTrue(sim.step(dict(sim.home_targets)), sim.reason)
        self.assertEqual(calls, [False])


if __name__ == "__main__":
    unittest.main()
