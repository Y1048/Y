import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

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
