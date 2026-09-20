"""Read-only bimanual session reporting regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_session_report as report

FIXTURE = ROOT / 'backend/tests/fixtures/bimanual_quest_reengage_20260918.json.gz'


class SessionReportTests(unittest.TestCase):
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
        self.assertLessEqual(result['output_fixed_dt']['max_acceleration_deg_s2'], 60.0001)

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
