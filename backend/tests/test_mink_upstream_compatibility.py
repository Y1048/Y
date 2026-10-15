"""Numerical contracts required by the pinned bundled Mink revision."""
import unittest
import mink
import mujoco
import numpy as np


class MinkUpstreamCompatibilityTests(unittest.TestCase):
    def test_zero_rotation_keeps_translation_rotation_coupling(self):
        translation = np.array([.025, .020, -.010])
        x, y, z = translation
        skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
        expected = np.eye(6)
        expected[:3, 3:] = .5 * skew
        np.testing.assert_allclose(
            mink.SE3.from_translation(translation).jlog(), expected,
            atol=1e-14, rtol=0)

    def test_collision_bound_is_displacement_not_velocity(self):
        model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
          <body name="obstacle"><geom name="a" type="sphere" size=".1"/></body>
          <body name="moving" pos=".3 0 0">
            <joint type="slide" axis="1 0 0"/>
            <geom name="b" type="sphere" size=".1"/>
          </body></worldbody></mujoco>''')
        config = mink.Configuration(model)
        limit = mink.CollisionAvoidanceLimit(
            model, geom_pairs=[(['a'], ['b'])], gain=.5,
            minimum_distance_from_collisions=.01,
            collision_detection_distance=.2)
        for dt in (1/30, 1/60, 1/120):
            with self.subTest(dt=dt):
                bound = limit.compute_qp_inequalities(config, dt)
                # Sphere surface gap .1m; allow half of (.1-.01) per step.
                np.testing.assert_allclose(bound.h, [.045], atol=1e-14)
                np.testing.assert_allclose(bound.G, [[-1.]], atol=1e-14)


if __name__ == '__main__':
    unittest.main()
