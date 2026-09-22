"""Offline tests for initial-yaw-relative Omni movement conversion."""
import csv
import io
import json
import math
import unittest

from . import g1_omni_velocity_gateway as gateway


def raw_body_vector(forward, right, yaw_relative_deg, offset_deg=120.0):
    theta = math.radians(yaw_relative_deg + offset_deg)
    return (forward * math.sin(theta) + right * math.cos(theta),
            forward * math.cos(theta) - right * math.sin(theta))


class OmniBodyMappingTests(unittest.TestCase):
    def assert_planar(self, actual, expected):
        self.assertAlmostEqual(actual[0], expected[0], places=12)
        self.assertAlmostEqual(actual[1], expected[1], places=12)

    def test_required_cases_a_through_d(self):
        initial = 37.0
        cases = (("A initial forward", 0., 1., 0.),
                 ("B initial right", 0., 0., 1.),
                 ("C plus 90 forward", 90., 1., 0.),
                 ("D plus 180 forward", 180., 1., 0.))
        for name, relative, forward, right in cases:
            with self.subTest(name=name):
                raw = raw_body_vector(forward, right, relative)
                actual = gateway.omni_to_body_velocity(
                    *raw, initial + relative, initial, deadzone=0.)
                self.assert_planar(actual, (forward, right))

    def test_g1_lateral_sign_is_left_positive(self):
        mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(
            calibration_s=.1, movement_deadzone=0., forward_max_m_s=1.,
            lateral_max_m_s=1., yaw_deadzone_deg_s=1000.))
        mapper.update(0., 0., 37., 0.)
        mapper.update(0., 0., 37., .1)
        velocity = mapper.update(*raw_body_vector(0., .6, 0.), 37., .2)
        self.assert_planar(velocity, (0., -.6))

    def test_vector_deadzone_and_wrap(self):
        self.assertEqual(gateway.omni_to_body_velocity(
            .06, .08, 359., 1., deadzone=.10), (0., 0.))
        for initial, yaw, relative in ((1., 359., -2.), (359., 1., 2.)):
            raw = raw_body_vector(.4, 0., relative)
            self.assert_planar(gateway.omni_to_body_velocity(
                *raw, yaw, initial, deadzone=0.), (.4, 0.))

    def test_rotation_preserves_magnitude(self):
        for relative in (0., 45., 90., 180., -90., 359.):
            body = gateway.omni_to_body_velocity(
                .3, -.4, 20. + relative, 20., deadzone=0.)
            self.assertAlmostEqual(math.hypot(*body), .5, places=12)

    def test_json_velocity_and_csv_use_same_robot_components(self):
        mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(
            calibration_s=.1, movement_deadzone=0., forward_max_m_s=1.,
            lateral_max_m_s=1., yaw_deadzone_deg_s=1000.))
        mapper.update(0., 0., 37., 0.)
        mapper.update(0., 0., 37., .1)
        raw = raw_body_vector(.4, .2, 90.)
        velocity = mapper.update(*raw, 127., .2)
        self.assert_planar(velocity, (.4, -.2))
        packet = json.loads(gateway.encode_command(
            "offline", 1, .2, velocity, "a" * 32))
        self.assert_planar(packet["velocity"], (.4, -.2))

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(gateway.OMNI_CSV_HEADER)
        writer.writerow(gateway.omni_csv_row(
            .2, 0., 1, *raw, 127., velocity, mapper, "{}"))
        row = next(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assertAlmostEqual(float(row["vx_forward"]), .4)
        self.assertAlmostEqual(float(row["vy_right"]), .2)
        self.assertAlmostEqual(float(row["vy_left"]), -.2)
        self.assertAlmostEqual(float(row["yaw_relative_deg"]), 90.)


if __name__ == "__main__":
    unittest.main()
