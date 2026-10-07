"""Onboard receiver regression tests; every command sink is simulated.

No G1 connection, real sockets, DDS, motors, or terminal state is used.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tools/onboard/g1_omni_heading_controller.py'
WAIT = {'status': 'WAIT', 'source_age_s': None, 'values': None}


def load_controller(path=SOURCE, name='_g1_optional_omni_test'):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with ExitStack() as stack:
        # Only terminal imports are unavailable on Windows; run() uses a fake
        # terminal below. The actual parser and command loop are unmodified.
        if sys.platform == 'win32':
            stack.enter_context(patch.dict(sys.modules, {
                'termios': ModuleType('termios'), 'tty': ModuleType('tty')}))
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return module


def packet(sequence=0, *, omni='WAIT', state='tracking'):
    base = copy.deepcopy(WAIT) if omni == 'WAIT' else {
        'status': omni, 'source_age_s': 0.0, 'source_receive_age_s': 0.0,
        'source_session': 'omni-source',
        'values': {'vx': 0.2, 'vy': -0.1, 'arm_yaw_deg': 25.0,
                   'calibrated': True}}
    return {'schema': 'g1.observation.audit.v1', 'observation_only': True,
            'session': 'a' * 32, 'sequence': sequence,
            'payload': {'omni': base, 'arm': {
                'status': 'FRESH_LIVE', 'source_age_s': 0.0,
                'source_receive_age_s': 0.0,
                'values': {'state': state, 'left_q_rad': [0.1] * 7,
                           'right_q_rad': [-0.1] * 7}}}}


def encoded(value):
    return json.dumps(value, separators=(',', ':')).encode('utf-8')


def simulated_run(module, events, duration=0.40, *, yaw_sign=-1):
    """Execute the real run() against deterministic in-memory device sockets."""
    class Clock:
        value = 100.0
        steps = 0

        def now(self):
            return self.value

        def sleep(self, seconds):
            self.steps += 1
            if self.steps > 20000:
                raise AssertionError('simulation loop did not terminate')
            self.value += max(float(seconds), 0.00001)

    clock = Clock()
    logs, sent = [], []

    class FakeSocket:
        def __init__(self, schedule=(), peer=('127.0.0.1', 49001)):
            self.schedule = list(schedule)
            self.peer = peer
            self.closed = False

        def bind(self, address):
            pass

        def setblocking(self, value):
            pass

        def recvfrom(self, size):
            if self.schedule and self.schedule[0][0] <= clock.now() - 100.0 + 1e-9:
                _, payload = self.schedule.pop(0)
                return payload, self.peer
            raise BlockingIOError()

        def sendto(self, payload, destination):
            sent.append((clock.now(), destination, payload))
            return len(payload)

        def close(self):
            self.closed = True

    class FakeLog:
        def __init__(self, path):
            self.path, self.written, self.dropped, self.error = path, 0, 0, None

        def submit(self, row):
            # Same finite-JSON requirement as AsyncJsonlLog's real writer.
            json.dumps(row, allow_nan=False)
            logs.append(dict(row, test_time=clock.now() - 100.0))
            self.written += 1

        def close(self):
            pass

    class FakeTerminal:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read_available(self):
            return ''

    states = [(i * .1, encoded({'seq': i, 'yaw': 0.0,
                                'q': [0.0] * 29, 'dq': [0.0] * 29}))
              for i in range(int(duration * 10) + 1)]
    sockets = [FakeSocket([(t, encoded(p)) for t, p in events]),
               FakeSocket(states), FakeSocket(), FakeSocket()]
    with ExitStack() as stack:
        stack.enter_context(patch.object(module.socket, 'socket', side_effect=sockets))
        stack.enter_context(patch.object(module.time, 'monotonic', clock.now))
        stack.enter_context(patch.object(module.time, 'sleep', clock.sleep))
        stack.enter_context(patch.object(module, 'RawTerminal', FakeTerminal))
        stack.enter_context(patch.object(module, 'AsyncJsonlLog', FakeLog))
        stack.enter_context(patch.object(sys, 'argv', [str(SOURCE), '--duration', str(duration),
            '--yaw-sign', str(yaw_sign), '--log', 'offline-test.jsonl']))
        stack.enter_context(redirect_stdout(io.StringIO()))
        result = module.run()
    assert result == 0 and all(s.closed for s in sockets)
    return logs, sent


class OptionalOmniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_controller()

    def parse(self, value):
        return self.module.parse_omni_observation(encoded(value), 100.0)

    def test_exact_producer_wait_allows_fresh_bilateral_tracking_and_returning(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import G1_INPUT_RECEIVE_AUDIT as producer
        self.assertEqual(producer.LiveSources().snapshot('omni', 100.0), WAIT)
        for state in ('tracking', 'returning'):
            with self.subTest(state=state):
                sample = self.parse(packet(state=state))
                self.assertTrue(sample.arms_active)
                self.assertFalse(sample.omni_live)
                self.assertIsNone(sample.source_session)
                self.assertTrue(math.isinf(sample.source_age))
                self.assertEqual((sample.vx, sample.vy, sample.arm_yaw_rad), (0.0, 0.0, 0.0))
                self.assertEqual(sample.left_q, (0.1,) * 7)
                self.assertEqual(sample.right_q, (-0.1,) * 7)

    def test_ready_blocked_missing_and_stale_arms_remain_inactive(self):
        for state in ('ready', 'blocked'):
            self.assertFalse(self.parse(packet(state=state)).arms_active)
        for arm in (None, copy.deepcopy(WAIT), {'status': 'STALE'}):
            value = packet()
            value['payload']['arm'] = arm
            self.assertFalse(self.parse(value).arms_active)
        value = packet()
        del value['payload']['arm']
        self.assertFalse(self.parse(value).arms_active)

    def test_malformed_wait_is_not_treated_as_missing(self):
        variants = [None, {}, {'status': 'WAIT'},
                    dict(WAIT, source_age_s=0), dict(WAIT, source_age_s=-1),
                    dict(WAIT, source_receive_age_s=0),
                    dict(WAIT, source_session='inconsistent'),
                    dict(WAIT, values={'calibrated': True, 'vx': 1.0})]
        for omni in variants:
            with self.subTest(omni=omni):
                value = packet()
                value['payload']['omni'] = omni
                with self.assertRaises((ValueError, TypeError)):
                    self.parse(value)
        value = packet()
        del value['payload']['omni']
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_live_omni_age_calibration_and_numeric_checks_are_preserved(self):
        bad = [('source_age_s', None), ('source_age_s', -1),
               ('source_receive_age_s', True), ('source_session', '')]
        for key, item in bad:
            value = packet(omni='FRESH_LIVE')
            value['payload']['omni'][key] = item
            with self.subTest(key=key, item=item), self.assertRaises(ValueError):
                self.parse(value)
        for key, item in [('calibrated', False), ('calibrated', 1),
                          ('vx', float('nan')), ('vy', float('inf')),
                          ('arm_yaw_deg', '0')]:
            value = packet(omni='FRESH_LIVE')
            value['payload']['omni']['values'][key] = item
            with self.subTest(key=key, item=item), self.assertRaises(ValueError):
                self.parse(value)

    def test_missing_omni_does_not_relax_any_bilateral_validation(self):
        for side in ('left_q_rad', 'right_q_rad'):
            for data in ([], [0.0] * 6, [0.0] * 8, [True] * 7,
                         [float('nan')] * 7, [float('inf')] * 7, ['0'] * 7):
                value = packet()
                value['payload']['arm']['values'][side] = data
                with self.subTest(side=side, data=data), self.assertRaises(ValueError):
                    self.parse(value)
        for key in ('source_age_s', 'source_receive_age_s'):
            for age in (None, -1, True, '0', float('inf')):
                value = packet()
                value['payload']['arm'][key] = age
                with self.subTest(key=key, age=age), self.assertRaises(ValueError):
                    self.parse(value)
        value = packet(state='invalid')
        with self.assertRaises(ValueError):
            self.parse(value)

    def test_packet_schema_session_sequence_and_budget_guards_remain(self):
        for key, data in [('schema', 'wrong'), ('observation_only', False),
                          ('session', ''), ('session', 'g' * 32),
                          ('sequence', -1), ('sequence', True), ('sequence', 2**53)]:
            value = packet()
            value[key] = data
            with self.subTest(key=key, data=data), self.assertRaises(ValueError):
                self.parse(value)
        with self.assertRaises(ValueError):
            self.module.parse_omni_observation(b' ' * 6001, 100.0)
        with self.assertRaises((UnicodeError, ValueError)):
            self.module.parse_omni_observation(b'\xff', 100.0)

    def test_original_self_test_and_new_missing_case_without_sockets(self):
        with patch.object(self.module.socket, 'socket', side_effect=AssertionError('network forbidden')):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.run_self_test(), 0)

    def test_real_loop_missing_omni_sends_zero_base_and_active_arms(self):
        logs, sent = simulated_run(self.module, [(0.0, packet())], duration=.08)
        commands = [r['packet'] for r in logs if r['kind'] == 'command_tx']
        self.assertGreaterEqual(len(commands), 3)
        for command in commands:
            self.assertEqual((command['vx'], command['vy'], command['wz']), (0., 0., 0.))
            self.assertTrue(command['arms']['active'])
        observation = next(r for r in logs if r['kind'] == 'observation_rx')
        self.assertIsNone(observation['omni_source_age_s'])
        self.assertIsNone(observation['omni_source_session'])
        forwarded = [raw for _, target, raw in sent if target == ('127.0.0.1', 15102)]
        self.assertEqual(forwarded, [encoded(packet())])

    def test_real_loop_arm_age_expires_without_an_omni_dependency(self):
        logs, _ = simulated_run(self.module, [(0.0, packet())], duration=.40)
        commands = [r for r in logs if r['kind'] == 'command_tx']
        self.assertTrue(commands[0]['packet']['arms']['active'])
        self.assertFalse(commands[-1]['packet']['arms']['active'])
        self.assertGreater(commands[-1]['test_time'], .25)

    def test_real_loop_cold_start_reconnect_keeps_initial_heading_unset_until_live(self):
        first = packet(1, omni='FRESH_LIVE')
        first['payload']['omni']['values']['arm_yaw_deg'] = 120.
        second = copy.deepcopy(first)
        second['sequence'] = 2
        second['payload']['omni']['values']['arm_yaw_deg'] = 150.
        logs, _ = simulated_run(self.module, [(0., packet()), (.10, first), (.16, second)], duration=.22)
        commands = [r for r in logs if r['kind'] == 'command_tx']
        first_live = next(r for r in commands if r['omni_fresh'])
        self.assertEqual(first_live['packet']['wz'], 0.)
        self.assertLess(commands[-1]['packet']['wz'], 0.)
        self.assertTrue(all(r['packet']['arms']['active'] for r in commands))

    def test_real_loop_reordered_wait_cannot_overwrite_newer_live_packet(self):
        logs, _ = simulated_run(self.module, [(0., packet(2, omni='FRESH_LIVE')),
                                              (.02, packet(1))], duration=.08)
        rejects = [r for r in logs if r['kind'] == 'observation_rx' and not r['accepted']]
        self.assertEqual([r['reason'] for r in rejects], ['reordered'])
        commands = [r for r in logs if r['kind'] == 'command_tx']
        self.assertTrue(all(r['omni_fresh'] for r in commands))

    def test_real_loop_all_inputs_missing_keeps_base_zero_arms_inactive(self):
        logs, _ = simulated_run(self.module, [], duration=.08)
        for row in logs:
            if row['kind'] == 'command_tx':
                self.assertEqual((row['packet']['vx'], row['packet']['vy'], row['packet']['wz']), (0., 0., 0.))
                self.assertFalse(row['packet']['arms']['active'])


if __name__ == '__main__':
    unittest.main()
