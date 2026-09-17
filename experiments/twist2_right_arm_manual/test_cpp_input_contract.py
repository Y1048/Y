"""Differential packet-contract tests. Reuse only the pure Python parser.

No Arm SDK controller/Regular return behavior is instantiated or ported.
"""
import json
import math
import subprocess
import unittest

from test_cpp_upper_target import Packet, ROOT
import test_cpp_upper_target as target_tests
from arm_sdk_teleop_contract import parse_mink_arm_sample


def Idle():
    value = json.loads(Packet())
    value.update(input_command_mode='idle', session_id=None, input_packet_age_s=None)
    value['right_arm'].update(active=False, command_state='idle', minimum_clearance_m=None)
    return value


def PythonDisposition(payload):
    try:
        sample = parse_mink_arm_sample(payload)
        if (sample.input_command_mode == 'idle' and not sample.active
                and sample.controller_state == 'idle'):
            return 'waiting'
        if (sample.input_command_mode != 'active' or not sample.active
                or sample.input_packet_age_s > .25 or sample.minimum_clearance_m < 0):
            return 'stopped'
        return 'ok'
    except (ValueError, TypeError, KeyError, OverflowError):
        return 'stopped'


class InputContractTests(unittest.TestCase):
    def Cpp(self, events):
        result = subprocess.run([str(ROOT / 'logs/test_results/test_input_validator.exe')],
                                input=''.join(json.dumps(e)+'\n' for e in events),
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def CheckParity(self, packet):
        payload = json.dumps(packet)
        self.assertEqual(self.Cpp([dict(now=.02, payload=payload)]), [PythonDisposition(payload)])

    def test_required_fields_and_types_active_and_idle(self):
        for label, base in [('active', json.loads(Packet())), ('idle', Idle())]:
            for path, bad_values in [
                (['timestamp'], [None, [], {}, 'nonnumeric']),
                (['right_arm','workspace_limited'], [None, 0, 'false', [], {}]),
                (['right_arm','collision_limited'], [None, 1, 'true', [], {}]),
                (['right_arm','nearest_collision_geoms'], [None, 'body', [1], [False], [{}]]),
                (['right_arm','nearest_collision_bodies'], [None, 'body', [1], [False], [{}]])]:
                for bad in bad_values:
                    with self.subTest(mode=label, path=path, bad=bad):
                        value = json.loads(json.dumps(base))
                        target = value if len(path) == 1 else value[path[0]]
                        target[path[-1]] = bad
                        self.CheckParity(value)
            for path in [['timestamp'], ['right_arm','workspace_limited'], ['right_arm','collision_limited']]:
                with self.subTest(mode=label, missing=path):
                    value = json.loads(json.dumps(base))
                    target = value if len(path) == 1 else value[path[0]]
                    del target[path[-1]]
                    self.CheckParity(value)

    def test_idle_optional_fields_are_validated_when_present(self):
        for name, values in [('session_id', [1, '', ' \t\r\n\v\f', [], {}]),
                             ('input_packet_age_s', [-.01, [], {}, 'bad'])]:
            for bad in values:
                with self.subTest(field=name, bad=bad):
                    value = Idle()
                    value[name] = bad
                    self.CheckParity(value)
        for bad in [True, '0', [], {}]:
            with self.subTest(clearance=bad):
                value = Idle()
                value['right_arm']['minimum_clearance_m'] = bad
                self.CheckParity(value)

    def test_valid_optional_fields_modes_and_signed_zero_sequence(self):
        for base in [json.loads(Packet()), Idle()]:
            for timestamp in [-1, 0, 1.25]:
                with self.subTest(timestamp=timestamp, mode=base['input_command_mode']):
                    value = json.loads(json.dumps(base))
                    value['timestamp'] = timestamp
                    value['right_arm'].update(nearest_collision_geoms=['a','b'],
                                              nearest_collision_bodies=[],
                                              wrist_limit_margin_unknown=True)
                    self.CheckParity(value)
        for mode in ['pinch_disengaged','tracking_disengaged','workspace_exit']:
            value = Idle()
            value['input_command_mode'] = mode
            with self.subTest(mode=mode):
                self.CheckParity(value)
        payload = Packet(sequence=0).replace('"sequence": 0', '"sequence": -0')
        self.assertEqual(self.Cpp([dict(now=.02, payload=payload)]), [PythonDisposition(payload)])

    def test_ascii_session_normalization_matches_python(self):
        self.assertEqual(self.Cpp([dict(now=.02, payload=Packet(1, session_id=' \tstudy\r\n')),
                                   dict(now=.04, payload=Packet(2, session_id='study'))]), ['ok','ok'])

    def test_new_validation_errors_latch_after_engage(self):
        bad = json.loads(Packet(2))
        bad['right_arm']['workspace_limited'] = 'false'
        self.assertEqual(self.Cpp([dict(now=.02, payload=Packet()),
                                   dict(now=.04, payload=json.dumps(bad)),
                                   dict(now=.06, payload=Packet(3))]), ['ok','stopped','stopped'])

    def test_intentionally_stricter_than_python_coercion_and_json(self):
        cases = []
        for name in ['timestamp','input_packet_age_s']:
            for replacement in [True, '0']:
                value = json.loads(Packet())
                value[name] = replacement
                # True age is 1 second: use False so the independent freshness gate accepts it.
                if name == 'input_packet_age_s' and replacement is True:
                    value[name] = False
                cases.append(json.dumps(value))
        for replacement in [True, '0.1']:
            value = json.loads(Packet())
            value['all_joint_q_rad'][0] = replacement
            cases.append(json.dumps(value))
        cases += [Packet().replace('"sequence": 1', '"sequence": 0, "sequence": 1'),
                  Packet(sequence=2**64)]
        diagnostic = json.loads(Packet())
        diagnostic['right_arm']['min_wrist_limit_margin_deg'] = math.inf
        cases.append(json.dumps(diagnostic))
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(PythonDisposition(payload), 'ok')
                self.assertEqual(self.Cpp([dict(now=.02, payload=payload)]), ['stopped'])

    def test_timeout_clock_validation_without_payload(self):
        for now in [-1, float('nan'), float('inf'), -float('inf')]:
            # Clock JSON is the harness envelope, not a robot packet. Nonfinite
            # clocks are represented as strings for its explicit clock decoder.
            encoded = now if math.isfinite(now) else str(now)
            with self.subTest(now=encoded):
                self.assertEqual(self.Cpp([dict(now=encoded), dict(now=1, payload=Packet())]),
                                 ['stopped','stopped'])
        self.assertEqual(self.Cpp([dict(now=2), dict(now=1, payload=json.dumps(Idle()))]),
                         ['ok','stopped'])

    def test_command_mode_state_and_active_combinations(self):
        for mode in ['active','idle','pinch_disengaged','tracking_disengaged','workspace_exit']:
            for state in ['active','idle','hold','workspace_fault']:
                for active in [False, True]:
                    with self.subTest(mode=mode, state=state, active=active):
                        value = json.loads(Packet())
                        value['input_command_mode'] = mode
                        value['right_arm'].update(command_state=state, active=active)
                        self.CheckParity(value)

    def test_metadata_failure_preserves_candidate_and_latches(self):
        for field in ['timestamp','workspace_limited','collision_limited','nearest_collision_geoms']:
            with self.subTest(field=field):
                value = json.loads(Packet(2))
                if field == 'timestamp':
                    value[field] = None
                else:
                    value['right_arm'][field] = 1
                rows = target_tests.UpperTargetTests().RunCase([
                    dict(now=.02, payload=Packet()), dict(now=.04, payload=json.dumps(value)),
                    dict(now=.06, payload=Packet(3))])
                self.assertEqual([row['mode'] for row in rows], ['active','stopped','stopped'])
                self.assertEqual(rows[0]['q'], rows[1]['q'])
                self.assertEqual(rows[0]['q'], rows[2]['q'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
