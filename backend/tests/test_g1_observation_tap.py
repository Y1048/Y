"""Observation copies and controller preservation; no WS, DDS or robot access."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'tools/g1_observation_tap.py'
SPEC = importlib.util.spec_from_file_location('observation_tap_test', PATH)
tap_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tap_module)


class ObservationTapTests(unittest.TestCase):
    def test_omni_view_copy_is_separate_and_failure_does_not_affect_audit(self):
        socket_factory = self.enabled()
        sock = socket_factory.return_value
        with patch.dict(os.environ, {'G1_OMNI_UNITY_HEADING': '1'}):
            tap = tap_module.ObservationTap('omni')
            self.addCleanup(tap.close)
            self.assertTrue(tap.publish({'arm_yaw_deg': 112.}, 10.))
            calls = sock.sendto.call_args_list
            self.assertEqual(tap_module.ADDRESS, calls[-2].args[1])
            self.assertEqual(('127.0.0.1', 55072), calls[-1].args[1])
            self.assertEqual([0, 10., 112.], json.loads(calls[-1].args[0])['sample'])
            sock.sendto.side_effect = [None, OSError('Unity absent')]
            self.assertTrue(tap.publish({'arm_yaw_deg': 113.}, 10.02))
            self.assertEqual(0, tap.dropped)
            self.assertEqual(1, tap.visual_dropped)

    def test_compute_deadlines_skip_missed_slots_without_catchup(self):
        period = 1./60.
        deadline, missed = tap_module.next_deadline(10., 10.008, period)
        self.assertAlmostEqual(deadline, 10.+period)
        self.assertEqual(missed, 0)
        deadline, missed = tap_module.next_deadline(10., 10.080, period)
        self.assertAlmostEqual(deadline, 10.+5*period)
        self.assertEqual(missed, 4)
        self.assertGreater(deadline, 10.080)

    def enabled(self):
        environment = patch.dict(os.environ, {'G1_OBSERVATION_TAP': '1'})
        environment.start()
        self.addCleanup(environment.stop)
        factory = patch.object(tap_module.socket, 'socket')
        mocked = factory.start()
        self.addCleanup(factory.stop)
        return mocked

    def test_default_and_nonexplicit_values_create_no_socket(self):
        for value in (None, '', '0', 'true', 'yes'):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ['G1_OBSERVATION_TAP'] = value
                with patch.object(tap_module.socket, 'socket') as socket_factory:
                    tap = tap_module.ObservationTap('arm')
                    self.assertFalse(tap.publish({'unused': float('nan')}, 1.0))
                    tap.close()
                    socket_factory.assert_not_called()
                    self.assertEqual((tap.sequence, tap.dropped), (0, 0))

    def test_explicit_enable_is_nonblocking_and_loopback_only(self):
        socket_factory = self.enabled()
        tap = tap_module.ObservationTap('arm')
        self.addCleanup(tap.close)
        socket_factory.assert_called_once_with(
            tap_module.socket.AF_INET, tap_module.socket.SOCK_DGRAM)
        socket_factory.return_value.setblocking.assert_called_once_with(False)
        self.assertEqual(tap_module.ADDRESS, ('127.0.0.1', 55071))
        self.assertNotIn(tap_module.ADDRESS[1], (5008, 5014, 5017, 5020, 55070))
        self.assertTrue(tap.publish({'example': 1.0}, 123.5))
        _, address = socket_factory.return_value.sendto.call_args.args
        self.assertEqual(address, tap_module.ADDRESS)
        socket_factory.return_value.bind.assert_not_called()
        socket_factory.return_value.connect.assert_not_called()

    def test_arm14_and_omni_raw_values_roundtrip_without_mutation(self):
        socket_factory = self.enabled()
        samples = {
            'arm': dict(source_origin='bimanual_ik_simulation', simulation_only=True,
                        joint_indices=list(range(15, 29)),
                        joint_names=['left_' + name + '_joint' for name in
                            ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw',
                             'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw')] +
                            ['right_' + name + '_joint' for name in
                            ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw',
                             'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw')],
                        left_q_rad=[.1 * index for index in range(7)],
                        right_q_rad=[-.1 * index for index in range(7)],
                        state='tracking', session='unity-fixture', sequence=72,
                        unity_input_age_s=.015, unity_input_status='FRESH'),
            'omni': dict(source_origin='omni_connect_readonly', sample_sequence=19,
                         mx=.28, my=-.31, arm_yaw_deg=112.25,
                         omni_yaw_rate_deg_s=36.0, vx=-.2, vy=-.15,
                         yaw_rate=.42, yaw_diff_deg=12.25,
                         yaw_step_diff_deg=.6, calibrated=True),
        }
        for stream, values in samples.items():
            with self.subTest(stream=stream):
                original = copy.deepcopy(values)
                tap = tap_module.ObservationTap(stream)
                self.assertTrue(tap.publish(values, 987.123456789))
                raw, address = socket_factory.return_value.sendto.call_args.args
                packet = json.loads(raw)
                self.assertEqual(packet['schema'], 'g1.observation.source.v1')
                self.assertIs(packet['observation_only'], True)
                self.assertEqual(packet['stream'], stream)
                self.assertEqual(packet['sequence'], 0)
                self.assertEqual(packet['source_monotonic_s'], 987.123456789)
                self.assertEqual(packet['producer_dropped'], 0)
                self.assertEqual(packet['values'], original)
                self.assertEqual(values, original)
                self.assertEqual(address, ('127.0.0.1', 55071))
                self.assertEqual(len(packet['session']), 32)
                tap.close()
        self.assertEqual(len(samples['arm']['left_q_rad'] +
                             samples['arm']['right_q_rad']), 14)

    def test_nonfinite_invalid_timestamp_and_oversize_are_not_sent(self):
        socket_factory = self.enabled()
        cases = [({'q': [value]}, 1.0) for value in
                 (float('nan'), float('inf'), -float('inf'))]
        cases += [({'ok': 1}, value) for value in
                  (float('nan'), float('inf'), -.001, None)]
        cases += [({'text': 'x' * 6000}, 1.0)]
        tap = tap_module.ObservationTap('arm')
        self.addCleanup(tap.close)
        for index, (values, timestamp) in enumerate(cases, 1):
            with self.subTest(index=index):
                self.assertFalse(tap.publish(values, timestamp))
                self.assertEqual((tap.sequence, tap.dropped), (index, index))
        socket_factory.return_value.sendto.assert_not_called()

    def test_udp_drop_preserves_sequence_gap_and_next_copy(self):
        socket_factory = self.enabled()
        sock = socket_factory.return_value
        sock.sendto.side_effect = [BlockingIOError('queue full'),
                                  OSError('receiver unavailable'), 100]
        tap = tap_module.ObservationTap('omni')
        self.addCleanup(tap.close)
        values = dict(vx=.2, vy=.1, yaw_rate=-.3)
        self.assertFalse(tap.publish(values, 1.0))
        self.assertFalse(tap.publish(values, 1.02))
        self.assertTrue(tap.publish(values, 1.04))
        packet = json.loads(sock.sendto.call_args.args[0])
        self.assertEqual(packet['sequence'], 2)
        self.assertEqual(packet['producer_dropped'], 2)
        self.assertEqual(packet['values'], values)
        tap.close()
        tap.close()
        sock.close.assert_called_once()
        self.assertFalse(tap.publish(values, 1.06))

    def test_invalid_stream_rejected_before_socket_creation(self):
        socket_factory = self.enabled()
        with self.assertRaisesRegex(ValueError, 'observation stream'):
            tap_module.ObservationTap('robot_command')
        socket_factory.assert_not_called()

    def test_socket_initialization_failure_disables_only_the_copy(self):
        socket_factory = self.enabled()
        for stage in ('create', 'configure'):
            with self.subTest(stage=stage):
                socket_factory.reset_mock(side_effect=True)
                socket_factory.return_value.setblocking.side_effect = None
                if stage == 'create':
                    socket_factory.side_effect = OSError('synthetic socket unavailable')
                else:
                    socket_factory.return_value.setblocking.side_effect = OSError('synthetic setup failure')
                tap = tap_module.ObservationTap('arm')
                self.assertIsNone(tap.sock)
                self.assertEqual(tap.dropped, 1)
                self.assertIn('synthetic', tap.error)
                self.assertFalse(tap.publish({'ignored': 1}, 1.0))
                if stage == 'configure':
                    socket_factory.return_value.close.assert_called_once()


class ProducerPreservationTests(unittest.TestCase):
    def test_unmodified_state_machine_and_command_encoding_match_git_head(self):
        targets = {
            'MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py':
                ('UnityCycle', 'PairedHandFilter', 'decode'),
            'hardware/g1_arm_bridge/g1_omni_velocity_gateway.py':
                # World -> body movement correction is now explicitly requested.
                # Its mapper behavior has dedicated directional regression tests.
                ('OmniVelocityConfig', 'encode_command',
                 'parse_omni_message', 'omni_csv_row'),
        }
        for relative, names in targets.items():
            original = subprocess.run(
                ['git', 'show', 'HEAD:' + relative], cwd=ROOT,
                capture_output=True, text=True, encoding='utf-8',
                check=True, timeout=10).stdout
            current = (ROOT / relative).read_text(encoding='utf-8')
            trees = [ast.parse(text) for text in (original, current)]
            for name in names:
                with self.subTest(file=relative, symbol=name):
                    nodes = [next(node for node in tree.body
                                  if getattr(node, 'name', '') == name)
                             for tree in trees]
                    self.assertEqual(ast.dump(nodes[0], include_attributes=False),
                                     ast.dump(nodes[1], include_attributes=False))

    def test_tap_has_no_sdk_dds_subprocess_or_hardware_import(self):
        tree = ast.parse(PATH.read_text(encoding='utf-8'))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split('.')[0])
        self.assertEqual(imports, {'json', 'math', 'os', 'socket', 'uuid'})


if __name__ == '__main__':
    unittest.main()
