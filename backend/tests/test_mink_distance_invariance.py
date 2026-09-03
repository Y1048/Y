"""The diagnostic must flag inconsistent collision signs, not suppress them."""

import sys
import unittest
from pathlib import Path

import numpy as np
from itertools import product

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diagnose_mink_distance_invariance import ClassifyRows, GetSupportGap, GetSeparationCertificate, GetWorldVertices, GetEnclosingVertices, comparison


class DistanceInvarianceTests(unittest.TestCase):
    def test_support_gap_is_rigid_translation_invariant(self):
        first = np.array([[0., 0, 0], [1., 1, 1]])
        second = first + [2., 0, 0]
        for offset in (0., 1e-12, -1e-6, 12.):
            self.assertAlmostEqual(GetSupportGap(first + offset, second + offset, np.array([1., 0, 0])), 1.)
        self.assertIsNone(GetSupportGap(first, second, np.zeros(3)))

    def test_separated_hulls_cannot_have_negative_guard_distance(self):
        result = ClassifyRows([{"raw_distance_m": 0., "guard_distance_m": -.076,
                                "support_gap_m": .04}])
        self.assertEqual(result["status"], "DISTANCE_INCONSISTENT")
        self.assertTrue(result["separation_sign_contradiction"])

    def test_equal_values_pass_but_translation_dependent_signs_fail(self):
        rows = [{"raw_distance_m": .076, "guard_distance_m": .076, "support_gap_m": .07}] * 2
        self.assertEqual(ClassifyRows(rows)["status"], "NO_INCONSISTENCY_OBSERVED")
        rows = [rows[0], {"raw_distance_m": 0., "guard_distance_m": -.076, "support_gap_m": .07}]
        self.assertEqual(ClassifyRows(rows)["status"], "DISTANCE_INCONSISTENT")

    def test_certificate_rejects_contact_penetration_and_insufficient_clearance(self):
        first = np.array(list(product((-.05, .05), repeat=3)))
        for gap in (-.05, -.001, 0., .001, .019, .02, .0200005):
            result = GetSeparationCertificate(first, first + [.1 + gap, 0, 0], np.eye(3))
            self.assertEqual(result["status"], "UNRESOLVED", gap)
        result = GetSeparationCertificate(first, first + [.13, 0, 0], np.eye(3))
        self.assertEqual(result["status"], "CLEARANCE_CERTIFIED")
        self.assertLessEqual(result["lower_bound_m"], .03)

    def test_rotated_translated_boxes_keep_conservative_lower_bound(self):
        rng = np.random.default_rng(507)
        vertices = np.array(list(product((-.05, .05), repeat=3)))
        for _ in range(150):
            rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
            offset = rng.uniform(-10, 10, 3)
            gap = rng.uniform(-.04, .1)
            a = vertices @ rotation.T + offset
            b = (vertices + [.1 + gap, 0, 0]) @ rotation.T + offset
            result = GetSeparationCertificate(a, b, rotation.T)
            self.assertLessEqual(result["lower_bound_m"], max(0., gap) + 1e-12)
            self.assertEqual(result["status"] == "CLEARANCE_CERTIFIED", gap >= .020001)

    def test_shared_point_hulls_never_certify_clearance(self):
        rng = np.random.default_rng(808)
        for _ in range(200):
            shared = rng.uniform(-1, 1, (1, 3))
            a = np.vstack((shared, shared + rng.normal(size=(30, 3)) * .1))
            b = np.vstack((shared, shared + rng.normal(size=(20, 3)) * .1))
            result = GetSeparationCertificate(a, b, rng.normal(size=(64, 3)))
            self.assertEqual(result["status"], "UNRESOLVED")

    def test_invalid_input_fails_closed(self):
        vertices = np.array(list(product((-.05, .05), repeat=3)))
        for a, b, directions, margin in (
            ([], vertices, np.eye(3), .02),
            (vertices * np.nan, vertices, np.eye(3), .02),
            (vertices, vertices, np.zeros((1, 3)), .02),
            (vertices, vertices, np.full((3, 3), np.inf), .02),
            (vertices, vertices, np.eye(3), -.01),
            (vertices, vertices, np.eye(3), np.nan),
        ):
            with np.errstate(invalid="ignore"):
                self.assertEqual(GetSeparationCertificate(a, b, directions, margin)["status"], "INVALID_INPUT")

    def test_incomplete_axes_do_not_prove_collision(self):
        vertices = np.array(list(product((-.05, .05), repeat=3)))
        result = GetSeparationCertificate(vertices, vertices + [.2, 0, 0], [[0, 1, 0]])
        self.assertEqual(result["status"], "UNRESOLVED")

    def test_compiled_mesh_vertices_cover_contact_and_separation(self):
        mujoco = comparison.probe.mujoco
        vertices = " ".join(str(v) for row in product((-.05, .05), repeat=3) for v in row)
        for gap in (-.01, 0., .01, .03):
            model = mujoco.MjModel.from_xml_string(f'''<mujoco><asset>
              <mesh name="cube" vertex="{vertices}"/></asset><worldbody>
              <body><freejoint/><geom type="mesh" mesh="cube"/></body>
              <body pos="{.1 + gap} 0 0"><freejoint/><geom type="mesh" mesh="cube"/></body>
              </worldbody></mujoco>''')
            data = mujoco.MjData(model)
            mujoco.mj_forward(model, data)
            raw_distance = mujoco.mj_geomDistance(model, data, 0, 1, .2, np.zeros(6))
            self.assertAlmostEqual(raw_distance, gap, places=6)
            result = GetSeparationCertificate(GetWorldVertices(model, data, 0), GetWorldVertices(model, data, 1), np.eye(3))
            self.assertEqual(result["status"] == "CLEARANCE_CERTIFIED", gap > .02)
            self.assertLessEqual(result["lower_bound_m"], max(0, gap) + 1e-7)

    def test_primitive_enclosures_and_unsupported_plane(self):
        mujoco = comparison.probe.mujoco
        for kind, size, extent in (("sphere", ".05", [.05] * 3),
                                   ("capsule", ".05 .1", [.05, .05, .15]),
                                   ("cylinder", ".05 .1", [.05, .05, .1]),
                                   ("box", ".02 .03 .04", [.02, .03, .04]),
                                   ("ellipsoid", ".02 .03 .04", [.02, .03, .04])):
            model = mujoco.MjModel.from_xml_string(f'<mujoco><worldbody><geom type="{kind}" size="{size}"/></worldbody></mujoco>')
            data = mujoco.MjData(model)
            mujoco.mj_forward(model, data)
            vertices = GetEnclosingVertices(model, data, 0)
            np.testing.assert_allclose(np.max(vertices, axis=0), extent)
            np.testing.assert_allclose(np.min(vertices, axis=0), -np.array(extent))
        model = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom type="plane" size="1 1 .1"/></worldbody></mujoco>')
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        self.assertIsNone(GetEnclosingVertices(model, data, 0))


if __name__ == "__main__":
    unittest.main()
