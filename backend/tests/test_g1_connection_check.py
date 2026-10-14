"""Generated prerequisite responses; no network, G1, capture or motor execution."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import g1_connection_check as check
import G1_VR_TELEOP_LAUNCH as launch
import G1_PORTABLE as portable


def evidence(**changes):
    return dict(schema='g1.connection.prerequisites.v1', hostname='fixture-g1',
                eth0=True, sdk_present=True, actuator=True, heading=True,
                camera_follow=True, v4l2_ctl='/usr/bin/v4l2-ctl',
                cameras=[dict(device='/dev/video8', name='Insta360-fixture',
                              readable=True, writable=True)], **{}) | changes


class ConnectionTests(unittest.TestCase):
    def run_check(self, remote=None, host='auto', endpoints=None, code=0, stderr=''):
        remote = evidence() if remote is None else remote
        result = subprocess.CompletedProcess([], code, json.dumps(remote), stderr)
        if endpoints is None:
            endpoints = [dict(host=x, reachable=True, local_ip='192.168.123.99')
                         for x in (check.CANDIDATES if host == 'auto' else (host,))]
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                mock.patch.object(check, 'tcp_probe', side_effect=endpoints), \
                mock.patch.object(check, 'ssh_executable', return_value='ssh.exe'), \
                mock.patch.object(check, 'inspect_remote', return_value=result) as inspect:
            rc = check.check_connections(host, directory)
            files = list(Path(directory).glob('*.json'))
            self.assertEqual(1, len(files))
            report = json.loads(files[0].read_text(encoding='utf-8'))
            return rc, report, inspect

    def test_all_prerequisites_pass_without_claiming_video_or_udp(self):
        rc, report, inspect = self.run_check()
        self.assertEqual(0, rc)
        self.assertTrue(report['read_only'])
        self.assertEqual(check.CANDIDATES[0], report['selected_host'])
        self.assertIn('live camera frames/PTZ', report['not_tested'])
        self.assertIn('motor operation', report['not_tested'])
        inspect.assert_called_once_with(check.CANDIDATES[0], 'ssh.exe')

    def test_closed_network_fallback_and_explicit_different_ip(self):
        endpoints = [dict(host=check.CANDIDATES[0], reachable=False, error='timeout'),
                     dict(host=check.CANDIDATES[1], reachable=True, local_ip='192.168.10.199')]
        rc, report, inspect = self.run_check(endpoints=endpoints)
        self.assertEqual(0, rc)
        self.assertEqual(check.CANDIDATES[1], report['selected_host'])
        rc, report, inspect = self.run_check(host='10.50.1.8')
        inspect.assert_called_once_with('10.50.1.8', 'ssh.exe')

    def test_no_network_skips_remote(self):
        rc, report, inspect = self.run_check(endpoints=[dict(host=x, reachable=False)
                                                       for x in check.CANDIDATES])
        self.assertEqual(1, rc)
        inspect.assert_not_called()
        self.assertIsNone(report['selected_host'])

    def test_ssh_failures_are_distinguished(self):
        for stderr, expected in [('REMOTE HOST IDENTIFICATION HAS CHANGED', 'SSH_IDENTITY_CHANGED'),
                                 ('Host key verification failed', 'SSH_HOST_NOT_TRUSTED'),
                                 ('Permission denied (publickey)', 'SSH_LOGIN_FAILED'),
                                 ('Connection timed out', 'SSH_CONNECTION_FAILED')]:
            with self.subTest(stderr=stderr):
                rc, report, _ = self.run_check(code=255, stderr=stderr)
                self.assertEqual(1, rc)
                self.assertIn(expected, [row['name'] for row in report['checks']])
                self.assertNotIn('remote', report)

    def test_missing_multiple_and_inaccessible_cameras_fail(self):
        one = evidence()['cameras'][0]
        for cameras in ([], [one, dict(one, device='/dev/video10')], [dict(one, writable=False)]):
            rc, report, _ = self.run_check(remote=evidence(cameras=cameras))
            self.assertEqual(1, rc)
            self.assertIn('camera_device', [r['name'] for r in report['checks'] if r['status'] == 'FAIL'])

    def test_each_missing_onboard_prerequisite_fails(self):
        for field in ('eth0', 'sdk_present', 'actuator', 'heading', 'camera_follow', 'v4l2_ctl'):
            with self.subTest(field=field):
                rc, report, _ = self.run_check(remote=evidence(**{field: False}))
                self.assertEqual(1, rc)

    def test_malformed_remote_data_fails_closed(self):
        for data in ([], {'schema': 'wrong'}, evidence(cameras=[{}]), evidence(eth0='true')):
            rc, report, _ = self.run_check(remote=data)
            self.assertEqual(1, rc)
            self.assertNotIn('remote', report)

    def test_tcp_records_real_selected_local_address(self):
        with mock.patch.object(check.socket, 'create_connection') as connect:
            connect.return_value.__enter__.return_value.getsockname.return_value = ('10.5.1.9', 50000)
            self.assertEqual('10.5.1.9', check.tcp_probe('10.5.1.2')['local_ip'])
            connect.assert_called_once_with(('10.5.1.2', 22), timeout=1.5)

    def test_ssh_is_strict_noninteractive_and_read_only(self):
        with mock.patch.object(check.subprocess, 'run') as run, \
                mock.patch.object(check, 'identity_options', return_value=[]):
            check.inspect_remote('10.5.1.2', 'ssh.exe')
            args = run.call_args.args[0]
            for option in ('BatchMode=yes', 'StrictHostKeyChecking=yes', 'UpdateHostKeys=no',
                           'ClearAllForwardings=yes', 'PermitLocalCommand=no'):
                self.assertIn(option, args)
            self.assertIn('unitree@10.5.1.2', args)
            self.assertEqual(subprocess.DEVNULL, run.call_args.kwargs['stdin'])
            self.assertEqual(15, run.call_args.kwargs['timeout'])
        for forbidden in ('ChannelFactoryInitialize', 'ChannelPublisher', '--enable-actuation',
                          '--stream-mmap', '--set-fmt-video', 'authorized_keys', 'subprocess'):
            self.assertNotIn(forbidden, check.REMOTE_INSPECT)
        compile(check.REMOTE_INSPECT, '<read-only-inspection>', 'exec')

    def test_invalid_host_rejected_before_any_network(self):
        with mock.patch.object(check, 'tcp_probe') as tcp:
            with self.assertRaises(ValueError): check.check_connections('x; reboot')
            tcp.assert_not_called()

    def test_client_failure_and_remote_timeout_still_write_report(self):
        for broken_client in (True, False):
            with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), \
                    mock.patch.object(check, 'tcp_probe', return_value=dict(
                        host='10.5.1.2', reachable=True, local_ip='10.5.1.9')), \
                    mock.patch.object(check, 'ssh_executable',
                        side_effect=RuntimeError('missing ssh') if broken_client else None,
                        return_value='ssh.exe'), \
                    mock.patch.object(check, 'inspect_remote',
                        side_effect=subprocess.TimeoutExpired('ssh', 15)) as inspect:
                self.assertEqual(1, check.check_connections('10.5.1.2', directory))
                report = json.loads(next(Path(directory).glob('*.json')).read_text(encoding='utf-8'))
                self.assertFalse(report['prerequisites_ok'])
                self.assertEqual(0 if broken_client else 1, inspect.call_count)

    def test_dispatch_bypasses_network_repair_bootstrap_and_actuation(self):
        with mock.patch.object(portable, 'require_embedded_interpreter'), \
                mock.patch.object(portable, 'elevated_powershell') as elevate, \
                mock.patch.object(portable.dependencies, 'ensure') as deps, \
                mock.patch.object(check, 'check_connections', return_value=1) as diagnose, \
                mock.patch.object(launch, 'select_robot_host') as select, \
                mock.patch.object(launch, 'ensure_login') as enroll, \
                mock.patch.object(launch, 'process_arguments') as processes, \
                mock.patch.object(launch, 'confirm_groot_actuation') as confirm:
            self.assertEqual(1, portable.teleop(['--check-connections', '--host', '10.5.1.2']))
            diagnose.assert_called_once_with('10.5.1.2')
            for unused in (elevate, deps, select, enroll, processes, confirm): unused.assert_not_called()

    def test_check_modes_cannot_accidentally_combine(self):
        with mock.patch.object(check, 'check_connections') as diagnose, \
                mock.patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(SystemExit):
                launch.main(['--check-only', '--check-connections'])
            diagnose.assert_not_called()

    def test_help_never_repairs_or_bootstraps(self):
        for option in ('--help', '-h'):
            with mock.patch.object(portable, 'require_embedded_interpreter'), \
                    mock.patch.object(portable, 'elevated_powershell') as elevate, \
                    mock.patch.object(portable.dependencies, 'ensure') as deps, \
                    mock.patch('g1_portable_environment.dedicated_wired_adapter_needing_address') as nic, \
                    redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as exit_result:
                    portable.teleop([option])
                self.assertEqual(0, exit_result.exception.code)
                for unused in (elevate, deps, nic): unused.assert_not_called()


if __name__ == '__main__':
    unittest.main()
