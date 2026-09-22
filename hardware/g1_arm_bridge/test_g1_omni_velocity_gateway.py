import json
import math
import csv
import io
import unittest

from .g1_omni_velocity_gateway import (
    OmniVelocityConfig,
    OmniVelocityMapper,
    OMNI_CSV_HEADER,
    encode_command,
    omni_to_body_velocity,
    omni_csv_row,
    parse_omni_message,
    wrapped_delta_degrees,
)


class OmniVelocityGatewayTests(unittest.TestCase):
    def mapper(self):
        return OmniVelocityMapper(OmniVelocityConfig(
            calibration_s=0.1,
            movement_deadzone=0.05,
            yaw_deadzone_deg_s=0.0,
            yaw_output_deadzone_rad_s=0.0,
            yaw_filter_alpha=1.0,
        ))

    def calibrate(self, mapper):
        self.assertEqual(mapper.update(0.01, -0.02, 110.0, 0.0), (0.0, 0.0, 0.0))
        self.assertEqual(mapper.update(0.01, -0.02, 110.0, 0.1), (0.0, 0.0, 0.0))
        self.assertTrue(mapper.calibrated)

    def test_starting_yaw_does_not_command_rotation(self):
        mapper = self.mapper()
        self.calibrate(mapper)
        self.assertEqual(mapper.update(0.01, -0.02, 110.0, 0.2), (0.0, 0.0, 0.0))

    def test_translation_uses_calibrated_input_and_relative_yaw_offset(self):
        mapper = self.mapper()
        self.calibrate(mapper)
        vx, vy, _ = mapper.update(0.51, 0.48, 110.0, 0.2)
        forward, right = omni_to_body_velocity(
            .50, .50, 110., 110., deadzone=.05)
        self.assertAlmostEqual(vx, forward * .8)
        self.assertAlmostEqual(vy, -right * .8)

    def test_yaw_wrap_is_continuous(self):
        self.assertAlmostEqual(wrapped_delta_degrees(-179.0, 179.0), 2.0)
        mapper = self.mapper()
        mapper.update(0.0, 0.0, 179.0, 0.0)
        mapper.update(0.0, 0.0, 179.0, 0.1)
        _, _, wz = mapper.update(0.0, 0.0, -179.0, 0.2)
        self.assertAlmostEqual(wz, math.radians(20.0), places=5)
        self.assertAlmostEqual(mapper.yaw_from_origin_deg, 2.0)
        self.assertAlmostEqual(mapper.yaw_step_diff_deg, 2.0)
        self.assertAlmostEqual(mapper.yaw_rate_raw_deg_s, 20.0)

    def test_starting_yaw_is_recorded_as_relative_origin(self):
        mapper = self.mapper()
        self.calibrate(mapper)
        mapper.update(0.01, -0.02, 125.0, 0.2)
        self.assertAlmostEqual(mapper.yaw_from_origin_deg, 15.0)

    def test_gap_resets_rotation_to_zero(self):
        mapper = self.mapper()
        self.calibrate(mapper)
        self.assertEqual(mapper.update(0.0, 0.0, 150.0, 1.0), (0.0, 0.0, 0.0))

    def test_default_output_deadzone_removes_stationary_yaw_noise(self):
        mapper = OmniVelocityMapper(OmniVelocityConfig(
            calibration_s=0.1, yaw_deadzone_deg_s=0.0,
            yaw_filter_alpha=1.0))
        mapper.update(0.0, 0.0, 110.0, 0.0)
        mapper.update(0.0, 0.0, 110.0, 0.1)
        _, _, wz = mapper.update(0.0, 0.0, 110.2, 0.2)
        self.assertEqual(wz, 0.0)

    def test_default_yaw_output_is_bounded_at_1_6_rad_s(self):
        mapper = OmniVelocityMapper(OmniVelocityConfig(
            calibration_s=0.1, yaw_deadzone_deg_s=0.0,
            yaw_output_deadzone_rad_s=0.0, yaw_filter_alpha=1.0))
        mapper.update(0.0, 0.0, 0.0, 0.0)
        mapper.update(0.0, 0.0, 0.0, 0.1)
        _, _, wz = mapper.update(0.0, 0.0, 90.0, 0.2)
        self.assertEqual(wz, 1.6)

    def test_packet_parse_and_command_schema(self):
        self.assertEqual(parse_omni_message('{"armYaw":112,"movementXY":[-0.2,0.4]}'), (-0.2, 0.4, 112.0))
        packet = json.loads(encode_command("s", 1, 2.0, (0.1, 0.2, 0.3), "a" * 32))
        self.assertEqual(packet["schema"], "g1.velocity.command.v1")
        self.assertEqual(packet["command_provenance"], "omni_gateway")
        self.assertEqual(packet["velocity"], [0.1, 0.2, 0.3])

    def test_nonfinite_rejected(self):
        mapper = self.mapper()
        with self.assertRaises(ValueError):
            mapper.update(float("nan"), 0.0, 0.0, 0.0)

    def test_equal_receive_timestamp_is_coalesced(self):
        mapper = self.mapper()
        first = mapper.update(0.0, 0.0, 110.0, 0.0)
        self.assertEqual(mapper.update(0.1, 0.1, 120.0, 0.0), first)

    def test_backward_receive_timestamp_is_rejected(self):
        mapper = self.mapper()
        mapper.update(0.0, 0.0, 110.0, 1.0)
        with self.assertRaises(ValueError):
            mapper.update(0.0, 0.0, 110.0, 0.9)

    def test_csv_keeps_raw_and_mapped_timeseries_on_the_same_row(self):
        mapper = self.mapper()
        self.calibrate(mapper)
        velocity = mapper.update(0.31, 0.48, 112.0, 0.2)
        raw = '{"armYaw":112.0,"movementXY":[0.31,0.48]}'
        row = omni_csv_row(10.2, 10.0, 7, 0.31, 0.48, 112.0,
                           velocity, mapper, raw)
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(OMNI_CSV_HEADER)
        writer.writerow(row)
        parsed = next(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assertEqual(parsed["schema"], "g1.omni.timeseries.v1")
        self.assertEqual(parsed["sample_sequence"], "7")
        self.assertAlmostEqual(float(parsed["mx"]), 0.31)
        self.assertAlmostEqual(float(parsed["my"]), 0.48)
        self.assertAlmostEqual(float(parsed["omni_yaw_rate_deg_s"]), 20.0)
        self.assertAlmostEqual(float(parsed["vx"]), velocity[0])
        self.assertAlmostEqual(float(parsed["vy"]), velocity[1])
        self.assertAlmostEqual(float(parsed["yaw_rate"]), velocity[2])
        self.assertAlmostEqual(float(parsed["yaw_diff_deg"]), 2.0)
        self.assertAlmostEqual(float(parsed["yaw_step_diff_deg"]), 2.0)
        self.assertEqual(parsed["raw_json_text"], raw)


if __name__ == "__main__":
    unittest.main()
