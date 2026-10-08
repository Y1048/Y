"""Display geometric segments must enforce the same operational yaw envelope."""
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_geometric_goal as geometric
from g1_bimanual_sim import BimanualSimulation


class GeometricEnvelopeTests(unittest.TestCase):
    def boundary_case(self, side, sign):
        sim = BimanualSimulation()
        policy = sim.motion[side]
        index = (0 if side == 'left' else 7) + 2
        origin = sim.config.q.copy()
        # The current, independently collision-valid home pose lies precisely
        # on an operational boundary while remaining inside authored limits.
        policy.priority_shoulder_yaw_envelope_rad = .2
        policy.posture_reference[policy.qpos_ids[2]] = origin[policy.qpos_ids[2]] - sign * .2
        self.assertGreater(sim.clearance(origin), sim.clearance_m)
        return sim, origin, index

    def test_segment_rejects_yaw_envelope_violation_inside_authored_range(self):
        for side in ('left', 'right'):
            for sign in (-1, 1):
                with self.subTest(side=side, sign=sign):
                    sim, origin, index = self.boundary_case(side, sign)
                    displacement = np.zeros(14)
                    displacement[index] = sign * 1e-8
                    endpoint = origin.copy()
                    endpoint[sim.qids[index]] += displacement[index]
                    self.assertGreaterEqual(endpoint[sim.qids[index]], sim.ranges[index, 0])
                    self.assertLessEqual(endpoint[sim.qids[index]], sim.ranges[index, 1])
                    self.assertGreater(sim.clearance(endpoint), sim.clearance_m)
                    candidate, clearance = geometric._checked_segment(
                        sim, origin, displacement, sim.clearance(origin))
                    self.assertIsNone(candidate)
                    self.assertIsNone(clearance)
                    np.testing.assert_array_equal(sim.config.q, origin)

    def test_segment_inside_same_operational_envelope_remains_valid(self):
        for side in ('left', 'right'):
            for sign in (-1, 1):
                with self.subTest(side=side, sign=sign):
                    sim, origin, index = self.boundary_case(side, sign)
                    displacement = np.zeros(14)
                    displacement[index] = -sign * 1e-8
                    candidate, clearance = geometric._checked_segment(
                        sim, origin, displacement, sim.clearance(origin))
                    self.assertIsNotNone(candidate)
                    self.assertGreaterEqual(clearance, sim.clearance_m)
                    lower, upper = geometric._ranges(sim)
                    self.assertTrue(np.all(candidate[sim.qids] >= lower - 1e-9))
                    self.assertTrue(np.all(candidate[sim.qids] <= upper + 1e-9))
                    np.testing.assert_array_equal(sim.config.q, origin)

    def test_segment_rejects_value_just_outside_existing_numeric_tolerance(self):
        # Recorded replay failures were only about 1.01e-9 rad outside the
        # operational bound. Preserve the existing 1e-9 comparison tolerance.
        sim, origin, index = self.boundary_case('right', 1)
        displacement = np.zeros(14)
        displacement[index] = 1.01e-9
        candidate, clearance = geometric._checked_segment(
            sim, origin, displacement, sim.clearance(origin))
        self.assertIsNone(candidate)
        self.assertIsNone(clearance)


if __name__ == '__main__':
    unittest.main()
