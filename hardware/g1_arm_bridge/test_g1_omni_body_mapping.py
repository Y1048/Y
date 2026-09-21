"""Offline world-to-body mapping and existing output-field regression tests."""

import copy
import csv
import io
import json
import math
import unittest
from unittest.mock import patch

from tools import G1_INPUT_RECEIVE_AUDIT as receive_audit

from . import g1_omni_velocity_gateway as gateway


HEADINGS = (0.0, 45.0, 90.0, 112.0, -90.0, 180.0, 359.0)


def world_direction(body_forward, body_left, yaw_deg):
    """Construct a physical world vector from the heading and left basis."""
    yaw = math.radians(yaw_deg)
    heading = (math.cos(yaw), math.sin(yaw))
    left = (-math.sin(yaw), math.cos(yaw))
    return tuple(body_forward * f + body_left * l for f, l in zip(heading, left))


class OmniBodyMappingTests(unittest.TestCase):
    def setUp(self):
        # A regression must not accidentally open command/discovery transports.
        for owner, name in ((gateway.socket, 'socket'), (gateway, 'make_listener')):
            guard = patch.object(owner, name, side_effect=AssertionError('offline test opened transport'))
            guard.start()
            self.addCleanup(guard.stop)

    def mapper(self, **overrides):
        options = dict(calibration_s=.1, movement_deadzone=0.,
                       forward_max_m_s=1., lateral_max_m_s=1.)
        options.update(overrides)
        return gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(**options))

    def calibrate(self, mapper, yaw=0., bias=(0., 0.)):
        self.assertEqual(mapper.update(*bias, yaw, 0.), (0., 0., 0.))
        self.assertEqual(mapper.update(*bias, yaw, .1), (0., 0., 0.))
        self.assertTrue(mapper.calibrated)

    def assert_planar(self, actual, expected):
        self.assertAlmostEqual(actual[0], expected[0], places=12)
        self.assertAlmostEqual(actual[1], expected[1], places=12)

    def test_explicit_cardinal_world_axes_anchor_yaw_and_left_signs(self):
        cases = (
            (0., (.6, 0.), (.6, 0.)),
            (0., (0., .6), (0., .6)),
            (90., (0., .6), (.6, 0.)),
            (90., (.6, 0.), (0., -.6)),
            (-90., (0., -.6), (.6, 0.)),
            (-90., (.6, 0.), (0., .6)),
            (180., (-.6, 0.), (.6, 0.)),
            (180., (0., .6), (0., -.6)),
        )
        for yaw, world, body in cases:
            with self.subTest(yaw=yaw, world=world):
                self.assert_planar(gateway.world_movement_to_body(*world, yaw), body)
                mapper = self.mapper()
                self.calibrate(mapper, yaw)
                self.assert_planar(mapper.update(*world, yaw, .2), body)

    def test_forward_backward_left_right_at_every_heading(self):
        directions = {'forward': (.6, 0.), 'backward': (-.6, 0.),
                      'left': (0., .6), 'right': (0., -.6)}
        for yaw in HEADINGS:
            for direction, body in directions.items():
                with self.subTest(yaw=yaw, direction=direction):
                    world = world_direction(*body, yaw)
                    mapper = self.mapper()
                    self.calibrate(mapper, yaw)
                    velocity = mapper.update(*world, yaw, .2)
                    self.assert_planar(velocity, body)
                    self.assertEqual(velocity[2], 0.)

    def test_forward_stays_forward_as_heading_changes(self):
        mapper = self.mapper()
        self.calibrate(mapper, 112.)
        for index, yaw in enumerate(HEADINGS):
            with self.subTest(yaw=yaw):
                world = world_direction(.4, 0., yaw)
                self.assert_planar(mapper.update(*world, yaw, .2 + index * .1), (.4, 0.))

    def test_rotation_preserves_magnitude_before_deadzone_and_clamp(self):
        for yaw in HEADINGS:
            for world in ((0., 0.), (.003, -.004), (.3, .4), (-.7, .2), (2., -3.)):
                with self.subTest(yaw=yaw, world=world):
                    body = gateway.world_movement_to_body(*world, yaw)
                    self.assertAlmostEqual(math.hypot(*body), math.hypot(*world), places=12)

    def test_default_speed_scales_do_not_normalize_small_movement(self):
        for yaw in HEADINGS:
            with self.subTest(yaw=yaw):
                mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(
                    calibration_s=.1, movement_deadzone=0.))
                self.calibrate(mapper, yaw)
                velocity = mapper.update(*world_direction(.03, -.04, yaw), yaw, .2)
                self.assert_planar(velocity, (.024, -.032))
                self.assertAlmostEqual(math.hypot(*velocity[:2]), .04, places=12)

    def test_default_deadzone_is_applied_after_rotation(self):
        mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(calibration_s=.1))
        self.calibrate(mapper, 45.)
        # Each world component is below .08; together they exceed the body-forward deadzone.
        velocity = mapper.update(.07, .07, 45., .2)
        expected_forward = (.07 * math.sqrt(2.) - .08) / .92 * .8
        self.assert_planar(velocity, (expected_forward, 0.))
        self.assertGreater(velocity[0], 0.)

    def test_default_deadzone_and_scales_apply_per_body_axis(self):
        mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(calibration_s=.1))
        self.calibrate(mapper, 112.)
        velocity = mapper.update(*world_direction(.28, -.54, 112.), 112., .2)
        self.assert_planar(velocity, ((.28 - .08) / .92 * .8, -.4))

    def test_body_components_are_clamped_after_rotation(self):
        mapper = self.mapper(forward_max_m_s=.8, lateral_max_m_s=.3)
        self.calibrate(mapper, 45.)
        self.assert_planar(mapper.update(.8, .8, 45., .2), (.8, 0.))
        self.assert_planar(mapper.update(*world_direction(-2., 2., 45.), 45., .3), (-.8, .3))

    def test_initial_112_degree_heading_is_absolute_for_translation(self):
        mapper = self.mapper()
        self.calibrate(mapper, 112.)
        # Absolute forward at 112 degrees points toward world -X and +Y.
        velocity = mapper.update(-.2247639560495472, .5563103127400724, 112., .2)
        self.assert_planar(velocity, (.6, 0.))
        self.assertEqual(mapper.zero_yaw_deg, 112.)
        self.assertEqual(mapper.yaw_from_origin_deg, 0.)
        self.assertEqual(velocity[2], 0.)

    def test_calibration_bias_is_subtracted_in_world_frame_before_rotation(self):
        mapper = self.mapper()
        mapper.update(.10, -.06, 112., 0.)
        mapper.update(.12, -.08, 112., .1)
        self.assertAlmostEqual(mapper.zero_x, .11)
        self.assertAlmostEqual(mapper.zero_y, -.07)
        # At yaw 90, world +Y is forward and world -X is body left.
        self.assert_planar(mapper.update(.11 - .2, -.07 + .4, 90., .2), (.4, .2))
        self.assert_planar(mapper.update(.11, -.07, 180., .3), (0., 0.))

    def test_current_sample_heading_is_used_without_one_sample_delay(self):
        mapper = self.mapper()
        self.calibrate(mapper, 0.)
        self.assert_planar(mapper.update(.6, 0., 90., .2), (0., -.6))
        self.assert_planar(mapper.update(.6, 0., 180., .3), (-.6, 0.))

    def test_translation_is_continuous_across_yaw_wrap(self):
        mapper = self.mapper()
        self.calibrate(mapper, 359.999)
        before = mapper.update(.4, 0., 359.999, .2)
        at_wrap = mapper.update(.4, 0., 0., .3)
        after = mapper.update(.4, 0., .001, .4)
        self.assert_planar(at_wrap, (.4, 0.))
        self.assertAlmostEqual(before[0], after[0], places=12)
        self.assertAlmostEqual(before[1], -after[1], places=12)
        self.assertLess(math.dist(before[:2], after[:2]), .00002)
        self.assert_planar(gateway.world_movement_to_body(.3, .4, 359.),
                           gateway.world_movement_to_body(.3, .4, -1.))

    def test_observation_command_and_csv_share_corrected_existing_fields(self):
        mapper = self.mapper()
        processor = gateway.ClockedOmniProcessor(mapper, 60., 0.)
        for sequence, stamp in enumerate((0., .1)):
            raw = '{"movementXY":[0.0,0.0],"armYaw":90.0}'
            sample = gateway.ReceivedOmniSample(sequence, stamp, gateway.parse_omni_message(raw), raw)
            processor.process(sample, sequence, stamp, 0)

        raw = '{"armYaw":90.0,"movementXY":[0.4,0.2],"fixture":"preserve exactly"}'
        sample = gateway.ReceivedOmniSample(2, .2, gateway.parse_omni_message(raw), raw)
        observation = processor.process(sample, 12, 10.2, 1)
        observed_json = json.loads(json.dumps(observation, allow_nan=False))
        self.assert_planar((observed_json['vx'], observed_json['vy']), (.2, -.4))
        self.assertEqual((observed_json['mx'], observed_json['my']), (.4, .2))
        self.assertEqual(observed_json['arm_yaw_deg'], 90.)
        self.assertEqual(observed_json['yaw_diff_deg'], 0.)
        self.assertEqual(observed_json['processed_monotonic_s'], 10.2)
        self.assertEqual(sample.values, (.4, .2, 90.))
        self.assertEqual(sample.raw_json_text, raw)
        self.assertEqual(mapper.previous_time_s, .2)
        self.assertIsNone(processor.process(sample, 13, 10.3, 1))

        source_packet = dict(schema=receive_audit.SOURCE_SCHEMA, observation_only=True,
                             stream='omni', session='b' * 32, sequence=2,
                             source_monotonic_s=sample.received_monotonic_s,
                             values=observed_json, producer_dropped=0)
        self.assertIs(receive_audit.validate_source(source_packet), source_packet)
        receiver = receive_audit.LiveSources()
        self.assertTrue(receiver.accept(receive_audit.encode(source_packet),
                                        ('127.0.0.1', 54321), .21))
        snapshot = receiver.snapshot('omni', .22)
        self.assertEqual(snapshot['status'], 'FRESH_LIVE')
        self.assertEqual(snapshot['source_sequence'], 2)
        self.assertEqual(snapshot['values'], dict(observed_json, source_monotonic_s=.2))
        self.assert_planar((snapshot['values']['vx'], snapshot['values']['vy']), (.2, -.4))
        self.assertEqual((snapshot['values']['mx'], snapshot['values']['my']), (.4, .2))
        self.assertAlmostEqual(snapshot['source_age_s'], .02)

        velocity = (observation['vx'], observation['vy'], observation['yaw_rate'])
        packet = json.loads(gateway.encode_command('offline', 2, .2, velocity, 'a' * 32))
        self.assertEqual(packet['schema'], 'g1.velocity.command.v1')
        self.assert_planar(packet['velocity'], (.2, -.4))
        self.assertEqual(packet['velocity'][2], 0.)
        self.assertEqual(packet['source_monotonic_s'], .2)

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(gateway.OMNI_CSV_HEADER)
        writer.writerow(gateway.omni_csv_row(.2, 0., 2, *sample.values, velocity, mapper, raw))
        row = next(csv.DictReader(io.StringIO(stream.getvalue())))
        self.assert_planar((float(row['vx']), float(row['vy'])), (.2, -.4))
        self.assertEqual((float(row['mx']), float(row['my'])), (.4, .2))
        self.assertEqual(float(row['yaw_rate']), 0.)
        self.assertEqual(float(row['arm_yaw_deg']), 90.)
        self.assertEqual(float(row['receive_monotonic_s']), .2)
        self.assertEqual(row['raw_json_text'], raw)

    def test_gap_still_emits_zero_then_next_sample_uses_current_heading(self):
        mapper = self.mapper()
        self.calibrate(mapper, 112.)
        mapper.update(*world_direction(.4, 0., 112.), 112., .2)
        self.assertEqual(mapper.update(0., .6, 90., 1.), (0., 0., 0.))
        self.assertEqual(mapper.previous_yaw, 90.)
        self.assertEqual(mapper.previous_time_s, 1.)
        self.assertEqual(mapper.filtered_yaw_rate, 0.)
        self.assertEqual(mapper.yaw_rate_raw_deg_s, 0.)
        self.assertEqual(mapper.yaw_step_diff_deg, 0.)
        self.assert_planar(mapper.update(0., .6, 90., 1.1), (.6, 0.))

    def test_equal_and_backward_timestamps_do_not_change_mapping_state(self):
        mapper = self.mapper()
        self.calibrate(mapper, 90.)
        previous = mapper.update(.4, .2, 90., .2)
        state = copy.deepcopy(mapper.__dict__)
        self.assertEqual(mapper.update(-.7, .8, 180., .2), previous)
        self.assertEqual(mapper.__dict__, state)
        with self.assertRaisesRegex(ValueError, 'non-monotonic'):
            mapper.update(-.7, .8, 180., .19)
        self.assertEqual(mapper.__dict__, state)

    def test_nonfinite_samples_are_rejected_without_state_changes(self):
        mapper = self.mapper()
        self.calibrate(mapper, 112.)
        mapper.update(*world_direction(.4, .2, 112.), 112., .2)
        state = copy.deepcopy(mapper.__dict__)
        for index in range(4):
            for invalid in (float('nan'), float('inf'), -float('inf')):
                with self.subTest(index=index, invalid=invalid):
                    values = [.4, .2, 90., .3]
                    values[index] = invalid
                    with self.assertRaisesRegex(ValueError, 'nonfinite'):
                        mapper.update(*values)
                    self.assertEqual(mapper.__dict__, state)


if __name__ == '__main__':
    unittest.main()
