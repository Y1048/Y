"""Read-only bimanual session reporting regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_session_report as report

FIXTURE = ROOT / 'backend/tests/fixtures/bimanual_quest_reengage_20260918.json.gz'


class SessionReportTests(unittest.TestCase):
    def _analyze_motion(self, positions, **run_metadata):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.jsonl'
            rows = [dict(kind='run', **run_metadata)]
            rows.extend(dict(kind='state', state='tracking', q_rad=q)
                        for q in positions)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            return report.analyze_session(path)

    def test_confirmed_quest_fixture_static_summary(self):
        result = report.analyze_session(FIXTURE)
        self.assertEqual(result['counts'], {'run': 1, 'input': 2016, 'state': 2927})
        self.assertEqual(result['tracking_starts'], 2)
        self.assertEqual(result['reengage_count'], 1)
        self.assertEqual(len(result['returns']), 2)
        self.assertEqual(result['operator_summary']['pinch_returns'], 2)
        self.assertEqual(result['operator_summary']['near_hands_recoveries'], 0)
        self.assertEqual(result['operator_summary']['separation_sides'], {})
        self.assertEqual([item['reason'] for item in result['returns']], ['pinch', 'pinch'])
        self.assertEqual([item['stages'] for item in result['returns']],
                         [['safe_waypoint', 'home', 'complete']] * 2)
        self.assertTrue(all(item['replans'] == 0 for item in result['returns']))
        self.assertAlmostEqual(result['returns'][0]['wall_s'], 5.781, places=3)
        self.assertAlmostEqual(result['returns'][1]['wall_s'], 5.437, places=3)
        self.assertEqual(result['final_state'], 'ready')
        self.assertEqual(result['final_reason'], 'pinch')
        self.assertEqual(result['failures'], [])
        self.assertIn('logged_source_differs_from_current', result['warnings'])
        self.assertIn('tracking_tick_p95_exceeds_nominal_60hz_period', result['warnings'])
        self.assertLessEqual(result['output_fixed_dt']['max_speed_excess_deg_s'], 1e-9)
        self.assertLessEqual(
            result['output_fixed_dt']['max_acceleration_deg_s2'],
            report.LEGACY_ACCELERATION_LIMIT_DEG_S2
            + report.ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2)
        self.assertEqual(result['validation_motion_limits']['source'], 'legacy_defaults')

    def test_acceleration_report_tolerance_matches_controller_regressions(self):
        self.assertAlmostEqual(
            report.ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2,
            float(report.np.rad2deg(1e-4)), places=12)
        self.assertGreater(
            report.LEGACY_ACCELERATION_LIMIT_DEG_S2
            + report.ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2, 60.0032)
        self.assertLess(
            report.LEGACY_ACCELERATION_LIMIT_DEG_S2
            + report.ACCELERATION_NUMERICAL_TOLERANCE_DEG_S2, 60.006)

    def test_recorded_three_rad_limits_accept_new_speed_and_acceleration(self):
        limits = dict(velocity_rad_s=[3.0] * 14, acceleration_rad_s2=[3.0] * 14)
        dt = report.SIM_DT
        for positions in (
                [[0.0] * 14, [3.0 * dt] * 14, [6.0 * dt] * 14],
                [[0.0] * 14, [0.0] * 14, [3.0 * dt**2] * 14]):
            with self.subTest(positions=positions):
                result = self._analyze_motion(positions, motion_limits=limits)
                self.assertEqual(result['failures'], [])
                self.assertEqual(result['validation_motion_limits'],
                                 dict(source='run.motion_limits', **limits))
                self.assertIn('Validation limit source: `run.motion_limits`',
                              report.markdown_report(result))

    def test_recorded_limits_reject_speed_and_acceleration_excess_on_every_joint(self):
        dt = report.SIM_DT
        limits = dict(velocity_rad_s=3.0, acceleration_rad_s2=3.0)
        for joint in range(14):
            for sign in (-1.0, 1.0):
                q_speed = [0.0] * 14
                q_speed[joint] = sign * 3.001 * dt
                q_acceleration = [0.0] * 14
                q_acceleration[joint] = sign * 3.001 * dt**2
                with self.subTest(joint=joint, sign=sign):
                    speed = self._analyze_motion(
                        [[0.0] * 14, q_speed], motion_limits=limits)
                    acceleration = self._analyze_motion(
                        [[0.0] * 14, [0.0] * 14, q_acceleration], motion_limits=limits)
                    self.assertIn('output_speed_limit_exceeded', speed['failures'])
                    self.assertIn('output_acceleration_limit_exceeded', acceleration['failures'])

    def test_historical_limits_keep_old_shoulder_wrist_and_acceleration_rules(self):
        dt = report.SIM_DT
        for joint, expected_failure in ((0, True), (7, True), (4, False), (11, False)):
            q = [0.0] * 14
            q[joint] = 3.1 * dt
            with self.subTest(joint=joint):
                result = self._analyze_motion([[0.0] * 14, q])
                self.assertEqual('output_speed_limit_exceeded' in result['failures'], expected_failure)
                self.assertEqual(result['validation_motion_limits']['source'], 'legacy_defaults')
        acceleration = self._analyze_motion(
            [[0.0] * 14, [0.0] * 14, [2.0 * dt**2] * 14])
        self.assertIn('output_acceleration_limit_exceeded', acceleration['failures'])

    def test_recorded_per_joint_limits_are_not_replaced_with_current_caps(self):
        dt = report.SIM_DT
        limits = dict(velocity_rad_s=[3.0] * 14, acceleration_rad_s2=[3.0] * 14)
        limits['velocity_rad_s'][7] = 2.0
        limits['acceleration_rad_s2'][7] = 2.0
        q_speed = [0.0] * 14
        q_speed[7] = 2.5 * dt
        q_acceleration = [0.0] * 14
        q_acceleration[7] = 2.5 * dt**2
        speed = self._analyze_motion([[0.0] * 14, q_speed], motion_limits=limits)
        acceleration = self._analyze_motion(
            [[0.0] * 14, [0.0] * 14, q_acceleration], motion_limits=limits)
        self.assertIn('output_speed_limit_exceeded', speed['failures'])
        self.assertIn('output_acceleration_limit_exceeded', acceleration['failures'])

    def test_invalid_recorded_limits_cannot_pass_as_legacy_logs(self):
        for invalid in (None, {}, {'velocity_rad_s': 3.0},
                        dict(velocity_rad_s=[3.0] * 13, acceleration_rad_s2=3.0),
                        dict(velocity_rad_s=3.0, acceleration_rad_s2=-3.0),
                        dict(velocity_rad_s=True, acceleration_rad_s2=3.0),
                        dict(velocity_rad_s=3.0, acceleration_rad_s2=float('inf'))):
            with self.subTest(limits=invalid):
                result = self._analyze_motion([[0.0] * 14], motion_limits=invalid)
                self.assertIn('invalid_motion_limits_metadata', result['failures'])
                self.assertEqual(result['validation_motion_limits']['source'],
                                 'invalid_metadata_legacy_fallback')

    def test_current_replay_uses_current_limits_and_checks_speed_and_acceleration(self):
        # This tests replay validation only; the stub starts no simulator or transport.
        for speed, acceleration, passed in ((1.5707963267948966, 1.0471975511965976, True), (1.572, 0.0, False),
                                             (0.1, 1.049, False)):
            sim = SimpleNamespace(
                caps=report.np.asarray(report.JOINT_VELOCITY_LIMITS_RAD_S),
            dofs=report.np.arange(14), qids=report.np.arange(14), dt=report.SIM_DT,
                velocity=report.np.full(14, speed - acceleration * report.SIM_DT),
                config=SimpleNamespace(q=report.np.zeros(14)), clearance_m=0.01,
                clearance=lambda q: 0.02,
                return_motion=SimpleNamespace(stage='complete', replans=0))
            cycle = SimpleNamespace(state='tracking', reason='')
            cycle.tick = lambda now: sim.velocity.fill(speed)
            modules = {
                'g1_bimanual_sim': SimpleNamespace(BimanualSimulation=lambda: sim),
                'g1_bimanual_unity_sim': SimpleNamespace(UnityCycle=lambda model: cycle, decode=None)}
            with self.subTest(speed=speed, acceleration=acceleration), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'session.jsonl'
                rows = [dict(kind='run', motion_limits=dict(
                    velocity_rad_s=1.0, acceleration_rad_s2=1.0)),
                    dict(kind='state', state='tracking', reason='', monotonic_s=0.0,
                         tick_action='tracking', q_rad=[0.0] * 14)]
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
                with patch.dict(sys.modules, modules):
                    replay = report.replay_session(path)
                self.assertIsNone(replay['passed'])
                self.assertIsNone(replay['exact_replay_passed'])
                self.assertEqual(replay['comparison'], 'different_motion_limits')
                self.assertEqual(replay['current_validation']['passed'], passed)
                self.assertEqual(replay['validation_motion_limits'], dict(
                    source='current_code', velocity_rad_s=list(report.JOINT_VELOCITY_LIMITS_RAD_S),
                    acceleration_rad_s2=[report.JOINT_ACCELERATION_LIMIT_RAD_S2] * 14))

    def _replay_states(self, logged_states, current_states, *, same_profile=False,
                       q_difference=0.0, reason_difference=False):
        sim = SimpleNamespace(
            caps=report.np.asarray(report.JOINT_VELOCITY_LIMITS_RAD_S),
            dofs=report.np.arange(14), qids=report.np.arange(14), dt=report.SIM_DT,
            velocity=report.np.zeros(14),
            config=SimpleNamespace(q=report.np.full(14, q_difference)), clearance_m=0.01,
            clearance=lambda q: 0.02,
            return_motion=SimpleNamespace(stage='complete', replans=0))
        cycle = SimpleNamespace(state='ready', reason='')
        state_iter = iter(current_states)

        def tick(now):
            cycle.state = next(state_iter)
            cycle.reason = ('diagnostic' if reason_difference else
                            'pinch' if cycle.state in ('returning', 'ready') else '')

        cycle.tick = tick
        modules = {
            'g1_bimanual_sim': SimpleNamespace(BimanualSimulation=lambda: sim),
            'g1_bimanual_unity_sim': SimpleNamespace(UnityCycle=lambda model: cycle, decode=None)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.jsonl'
            run = dict(kind='run', motion_limits=dict(velocity_rad_s=3.0, acceleration_rad_s2=3.0))
            if same_profile:
                run['motion_limits'] = dict(velocity_rad_s=list(report.JOINT_VELOCITY_LIMITS_RAD_S), acceleration_rad_s2=report.JOINT_ACCELERATION_LIMIT_RAD_S2)
            rows = [run] + [dict(
                kind='state', state=state,
                reason='pinch' if state in ('returning', 'ready') else '',
                monotonic_s=index * report.SIM_DT, tick_action=state, q_rad=[0.0] * 14)
                for index, state in enumerate(logged_states)]
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            with patch.dict(sys.modules, modules):
                return report.replay_session(path)

    def test_different_profile_keeps_mismatch_diagnostics_without_claiming_exact_replay(self):
        replay = self._replay_states(
            ['tracking', 'ready'], ['ready', 'tracking'], q_difference=0.1,
            reason_difference=True)
        self.assertEqual(replay['comparison'], 'different_motion_limits')
        self.assertEqual(replay['recorded_motion_limits']['source'], 'run.motion_limits')
        self.assertEqual(replay['state_mismatches'], 2)
        self.assertEqual(replay['reason_mismatches'], 2)
        self.assertEqual(replay['maximum_logged_q_difference_rad'], 0.1)
        self.assertIsNone(replay['exact_replay_passed'])
        self.assertIsNone(replay['passed'])
        self.assertTrue(replay['current_validation']['passed'])

    def test_same_profile_still_requires_exact_q_state_and_reason(self):
        for states, q_difference, reason_difference, expected in (
                (['tracking', 'ready'], 0.0, False, True),
                (['tracking', 'ready'], 0.1, False, False),
                (['ready', 'tracking'], 0.0, False, False),
                (['tracking', 'ready'], 0.0, True, False)):
            with self.subTest(states=states, q=q_difference, reason=reason_difference):
                replay = self._replay_states(
                    ['tracking', 'ready'], states, same_profile=True,
                    q_difference=q_difference, reason_difference=reason_difference)
                self.assertEqual(replay['comparison'], 'same_motion_limits')
                self.assertTrue(replay['current_validation']['passed'])
                self.assertEqual(replay['exact_replay_passed'], expected)
                self.assertEqual(replay['passed'], expected)

    def test_different_profile_validation_requires_returns_reengage_and_no_blocked_state(self):
        logged = ['tracking', 'returning', 'ready', 'tracking', 'returning', 'ready']
        for current, failure in (
                (logged, None),
                (['tracking'] * 6, 'recorded_return_completion_not_observed'),
                (['tracking', 'returning', 'ready', 'ready', 'ready', 'ready'],
                 'recorded_tracking_or_reengage_not_observed'),
                (['tracking', 'returning', 'ready', 'tracking', 'returning', 'returning'],
                 'final_state_not_ready_or_tracking'),
                (['tracking', 'blocked', 'ready', 'tracking', 'returning', 'ready'],
                 'blocked_state_observed')):
            with self.subTest(current=current):
                replay = self._replay_states(logged, current)
                self.assertIsNone(replay['passed'])
                validation = replay['current_validation']
                self.assertEqual(validation['expected_tracking_starts'], 2)
                self.assertEqual(validation['expected_completed_returns'], {'pinch': 2})
                self.assertEqual(validation['passed'], failure is None)
                if failure is not None:
                    self.assertIn(failure, validation['failures'])

    def test_strict_cli_warns_for_different_profile_but_fails_current_validation(self):
        for current, expected_code in ((['tracking', 'ready'], 0), (['tracking', 'blocked'], 1)):
            replay = self._replay_states(['tracking', 'ready'], current, q_difference=0.1)
            with self.subTest(current=current), patch.object(report, 'replay_session', return_value=replay):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = report.main([str(FIXTURE), '--strict', '--replay'])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, expected_code)
                self.assertIn('replay_not_comparable_motion_limits', payload['warnings'])
                self.assertEqual('replay_mismatch_or_safety_failure' in payload['failures'],
                                 expected_code == 1)
                self.assertIn('Exact replay passed: not comparable', report.markdown_report(payload))

    def test_cli_writes_machine_and_human_reports_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            json_path = directory / 'report.json'
            markdown_path = directory / 'report.md'
            with contextlib.redirect_stdout(io.StringIO()):
                code = report.main([str(FIXTURE), '--strict',
                                    '--json-output', str(json_path),
                                    '--markdown-output', str(markdown_path)])
            self.assertEqual(code, 0)
            payload = json.loads(json_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['reengage_count'], 1)
            self.assertNotIn('replay', payload)
            markdown = markdown_path.read_text(encoding='utf-8')
            self.assertIn('Tracking starts: 2; re-engages: 1', markdown)
            self.assertIn('Returns completed: 2; pinch: 2', markdown)
            self.assertIn('Near-hands recoveries: 0', markdown)
            self.assertIn('Failures: none', markdown)

    def test_latest_skips_newer_headless_log_without_operator_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'logs/test_results/bimanual'
            folder.mkdir(parents=True)
            operator = folder / 'unity_operator.jsonl'
            smoke = folder / 'unity_smoke.jsonl'
            operator.write_text('{"kind":"run"}\n{"kind":"input","accepted":true}\n', encoding='utf-8')
            smoke.write_text('{"kind":"run"}\n{"kind":"state"}\n', encoding='utf-8')
            os.utime(operator, (1, 1))
            os.utime(smoke, (2, 2))
            with patch.object(report, 'ROOT', root):
                self.assertEqual(report._latest_session(), operator)

    def test_latest_finds_operator_input_after_more_than_5000_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'logs/test_results/bimanual'
            folder.mkdir(parents=True)
            operator = folder / 'unity_operator.jsonl'
            smoke = folder / 'unity_smoke.jsonl'
            with operator.open('w', encoding='utf-8') as stream:
                stream.write('{"kind":"run"}\n')
                for _ in range(5005):
                    stream.write('{"kind":"state"}\n')
                stream.write('{broken json\n')
                stream.write('{"kind":"input","accepted":true}\n')
            smoke.write_text('{"kind":"run"}\n{"kind":"state"}\n', encoding='utf-8')
            os.utime(operator, (1, 1))
            os.utime(smoke, (2, 2))
            with patch.object(report, 'ROOT', root):
                self.assertEqual(report._latest_session(), operator)

    def test_reason_changes_do_not_create_fake_reengage_or_restart_return(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.jsonl'
            run = {'kind': 'run', 'source_sha256': report._current_source_hashes()}
            q = [0.0] * 14
            rows = [
                run,
                {'kind':'state','state':'ready','reason':'','sequence':0,'monotonic_s':0.0,'q_rad':q},
                {'kind':'state','state':'tracking','reason':'','sequence':1,'monotonic_s':1.0,'q_rad':q},
                {'kind':'state','state':'tracking','reason':'diagnostic','sequence':2,'monotonic_s':2.0,'q_rad':q},
                {'kind':'state','state':'returning','reason':'pinch','sequence':3,'monotonic_s':3.0,'q_rad':q,
                 'return_motion':{'stage':'safe_waypoint','elapsed_simulation_s':0.1,'replans':0,
                                  'near_hands_recovery':True,'separation_side':'left',
                                  'return_start_clearance_m':0.006,
                                  'near_hands_start_clearance_m':0.008}},
                {'kind':'state','state':'returning','reason':'diagnostic','sequence':4,'monotonic_s':4.0,'q_rad':q,
                 'return_motion':{'stage':'home','elapsed_simulation_s':0.2,'replans':0}},
                {'kind':'state','state':'ready','reason':'pinch','sequence':5,'monotonic_s':5.0,'q_rad':q,
                 'return_motion':{'stage':'complete','elapsed_simulation_s':0.3,'replans':0}},
            ]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
            result = report.analyze_session(path)
            self.assertEqual(result['tracking_starts'], 1)
            self.assertEqual(result['reengage_count'], 0)
            self.assertEqual(len(result['returns']), 1)
            self.assertEqual(result['returns'][0]['reason'], 'pinch')
            self.assertEqual(result['returns'][0]['stages'], ['safe_waypoint','home','complete'])
            self.assertEqual(result['returns'][0]['wall_s'], 2.0)
            self.assertTrue(result['returns'][0]['near_hands_recovery'])
            self.assertEqual(result['returns'][0]['separation_side'], 'left')
            self.assertEqual(result['operator_summary']['near_hands_recoveries'], 1)
            self.assertEqual(result['operator_summary']['separation_sides'], {'left': 1})

    def test_malformed_json_row_is_reported_without_aborting_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.jsonl'
            run = {'kind':'run','source_sha256':report._current_source_hashes()}
            state = {'kind':'state','state':'ready','reason':'','sequence':0,
                     'monotonic_s':0.0,'q_rad':[0.0]*14}
            path.write_text(json.dumps(run)+'\n{truncated\n'+json.dumps(state)+'\n', encoding='utf-8')
            result = report.analyze_session(path)
            self.assertEqual(result['malformed_json_rows'], 1)
            self.assertEqual(result['final_state'], 'ready')
            self.assertIn('malformed_json_rows_present', result['failures'])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(report.main([str(path), '--strict']), 1)

    def test_quest_cycle_requirement_accepts_confirmed_fixture_and_rejects_incomplete_flow(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(report.main([
                str(FIXTURE), '--require-quest-cycle', '--strict']), 0)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'incomplete.jsonl'
            run = {'kind':'run','source_sha256':report._current_source_hashes()}
            packet = {
                'engage':True, 'return_home':False,
                'left':{'tracked':True}, 'right':{'tracked':True}}
            q = [0.0] * 14
            rows = [
                run,
                {'kind':'input','accepted':True,'raw_json_text':json.dumps(packet)},
                {'kind':'state','state':'ready','reason':'','sequence':0,
                 'monotonic_s':0.0,'q_rad':q},
                {'kind':'state','state':'tracking','reason':'','sequence':1,
                 'monotonic_s':1.0,'q_rad':q},
            ]
            path.write_text(
                ''.join(json.dumps(row)+'\n' for row in rows),
                encoding='utf-8')
            result = report.analyze_session(path)
            failures = report._quest_cycle_failures(result)
            self.assertIn('quest_cycle_no_reengage', failures)
            self.assertIn('quest_cycle_no_completed_pinch_return', failures)

    def test_latest_requires_project_relative_session_and_launchers_are_read_only(self):
        source = (ROOT / 'tools/REPORT_LATEST_BIMANUAL_SESSION.bat').read_text(encoding='utf-8')
        self.assertIn('--mode report --latest', source)
        self.assertNotIn('START_BIMANUAL_UNITY_SIM', source)
        self.assertIn('g1_bimanual_runtime.py --mode report --latest', source)
        self.assertNotIn('unitree', source.lower())

        verify = (ROOT / 'tools/VERIFY_LATEST_BIMANUAL_QUEST_CYCLE.bat').read_text(encoding='utf-8')
        self.assertIn('--mode report --latest --replay', verify)
        self.assertIn('--require-quest-cycle --strict', verify)
        self.assertNotIn('START_BIMANUAL_UNITY_SIM', verify)
        self.assertNotIn('adb ', verify.lower())
        self.assertNotIn('unitree', verify.lower())


if __name__ == '__main__':
    unittest.main()
