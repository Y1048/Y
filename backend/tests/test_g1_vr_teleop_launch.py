"""Offline launcher decisions; subprocesses and sockets are always mocked."""

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
try:
    SPEC = importlib.util.spec_from_file_location(
        'g1_vr_teleop_launcher_test', TOOLS / 'G1_VR_TELEOP_LAUNCH.py')
    launcher = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(launcher)
finally:
    sys.path.remove(str(TOOLS))

HOST = '192.168.123.164'


def worker_row(worker, host=HOST):
    return launcher.observation.worker_command(worker, host, 'test_only')


class WorkerRecognitionTests(unittest.TestCase):
    def test_exact_existing_workers_and_partial_plan(self):
        rows = [worker_row(worker) for worker in launcher.observation.WORKERS]
        existing = launcher.running_workers(rows, ROOT, HOST)
        self.assertEqual(set(launcher.observation.WORKERS), existing)
        self.assertEqual([], launcher.launch_plan(existing, True))
        self.assertEqual(['receive', 'omni', 'camera'],
                         launcher.launch_plan({'send', 'arm'}, False))
        self.assertEqual(['omni'],
                         launcher.launch_plan({'send', 'arm'}, True, no_receiver=True))

    def test_stale_launcher_windows_do_not_count_as_running_workers(self):
        rows = [[sys.executable, '-u', '-B',
                 str(TOOLS / 'G1_INPUT_OBSERVATION_LAUNCH.py'),
                 '--worker', worker, '--host', HOST]
                for worker in launcher.observation.WORKERS]
        self.assertEqual(set(), launcher.running_workers(rows, ROOT, HOST))
        self.assertEqual(['receive', 'send', 'omni', 'arm', 'camera'],
                         launcher.launch_plan(set(), False))

    def test_incompatible_worker_options_are_refused(self):
        rows = [worker_row('send', '192.168.123.165')]
        arm = worker_row('arm')
        del arm[arm.index('--compute-hz'):arm.index('--compute-hz') + 2]
        rows.append(arm)
        omni = worker_row('omni')
        omni.remove('--dry-run')
        rows.append(omni)
        for row in rows:
            with self.subTest(row=row):
                with self.assertRaises(RuntimeError):
                    launcher.running_workers([row], ROOT, HOST)

    def test_duplicate_worker_is_refused(self):
        for worker in launcher.observation.WORKERS:
            with self.subTest(worker=worker):
                row = worker_row(worker)
                with self.assertRaises(RuntimeError):
                    launcher.running_workers([row, list(row)], ROOT, HOST)

    @unittest.skipUnless(os.name == 'nt', 'Uses Windows command-line parsing API')
    def test_windows_quoted_paths_and_remote_command_round_trip(self):
        root = Path(r'C:\test work\G1 project')
        with mock.patch.object(launcher.observation, 'ROOT', root):
            rows = [worker_row(worker) for worker in launcher.observation.WORKERS]
        rows[0][0] = r'C:\Program Files\OpenSSH\ssh.exe'
        for row in rows[1:]:
            row[0] = r'C:\Program Files\Python 3.11\python.exe'
        parsed = [launcher.windows_arguments(subprocess.list2cmdline(row)) for row in rows]
        self.assertEqual(rows, parsed)
        self.assertEqual(set(launcher.observation.WORKERS),
                         launcher.running_workers(parsed, root, HOST))


@unittest.skipUnless(os.name == 'nt', 'Windows visible-console launcher')
class OrchestrationTests(unittest.TestCase):
    def invoke(self, rows=(), camera=False, args=(), preflight_error=None):
        """Execute only the decision code; never enumerate or start real processes."""
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(mock.patch.object(launcher, 'process_arguments', return_value=list(rows)))
        camera_mock = stack.enter_context(mock.patch.object(launcher, 'camera_running', return_value=camera))
        environment = {'G1_OBSERVATION_TAP': '1', 'TEST_ONLY': '1'}
        stack.enter_context(mock.patch.object(launcher.observation, 'engine_environment', return_value=environment))
        check = stack.enter_context(mock.patch.object(launcher, 'preflight', side_effect=preflight_error))
        spawn = stack.enter_context(mock.patch.object(launcher.subprocess, 'Popen'))
        run = stack.enter_context(mock.patch.object(launcher.subprocess, 'run',
                                                   side_effect=AssertionError('Unexpected subprocess execution')))
        result = launcher.main(list(args))
        run.assert_not_called()
        return result, spawn, check, camera_mock, environment

    def test_fresh_start_creates_exactly_five_observation_and_camera_windows(self):
        result, spawn, check, _, environment = self.invoke()
        self.assertEqual(0, result)
        check.assert_called_once_with(['receive', 'send', 'omni', 'arm', 'camera'], environment)
        self.assertEqual(5, spawn.call_count)
        commands = [call.args[0] for call in spawn.call_args_list]
        self.assertEqual(list(launcher.observation.WORKERS),
                         [launcher.option(command, '--worker') for command in commands[:-1]])
        self.assertEqual(['cmd.exe', '/d', '/c', r'tools\START_G1_CAMERA_TO_UNITY.bat'], commands[-1])
        for call in spawn.call_args_list:
            self.assertEqual(ROOT, call.kwargs['cwd'])
            self.assertEqual(environment, call.kwargs['env'])
            self.assertEqual(subprocess.CREATE_NEW_CONSOLE, call.kwargs['creationflags'])
        self.assertIn('--dry-run', worker_row('omni'))
        self.assertEqual('unity', launcher.option(worker_row('arm'), '--mode'))
        self.assertEqual('60', launcher.option(worker_row('send'), '--send-hz'))
        self.assertIn('receive --print-hz 100', worker_row('receive')[-1])

    def test_all_running_produces_no_new_windows(self):
        rows = [worker_row(worker) for worker in launcher.observation.WORKERS]
        result, spawn, check, _, environment = self.invoke(rows, camera=True)
        self.assertEqual(0, result)
        check.assert_called_once_with([], environment)
        spawn.assert_not_called()

    def test_partial_start_only_creates_missing_workers(self):
        result, spawn, check, _, environment = self.invoke(
            [worker_row('send'), worker_row('arm')], camera=True)
        self.assertEqual(0, result)
        check.assert_called_once_with(['receive', 'omni'], environment)
        self.assertEqual(['receive', 'omni'],
                         [launcher.option(call.args[0], '--worker') for call in spawn.call_args_list])

    def test_check_only_does_not_start_workers_camera_or_ssh(self):
        result, spawn, check, _, _ = self.invoke(args=['--check-only'])
        self.assertEqual(0, result)
        check.assert_called_once()
        spawn.assert_not_called()

    def test_conflicting_inventory_fails_before_any_spawn(self):
        with mock.patch.object(launcher, 'process_arguments', return_value=[worker_row('send', 'other-host')]), \
                mock.patch.object(launcher, 'camera_running') as camera, \
                mock.patch.object(launcher.subprocess, 'Popen') as spawn, \
                mock.patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                launcher.main([])
            camera.assert_not_called()
            spawn.assert_not_called()
            run.assert_not_called()


@unittest.skipUnless(os.name == 'nt', 'Windows socket and subprocess constants')
class PreflightTests(unittest.TestCase):
    def test_unrelated_udp_owner_blocks_before_any_dependency_process(self):
        for worker, port in (('send', 55071), ('arm', 5020)):
            with self.subTest(worker=worker), \
                    mock.patch.object(launcher.shutil, 'which', return_value='available.exe'), \
                    mock.patch.object(launcher.socket, 'socket') as socket_factory, \
                    mock.patch.object(launcher.subprocess, 'run') as run:
                sock = socket_factory.return_value.__enter__.return_value
                sock.bind.side_effect = OSError('address already in use')
                with self.assertRaisesRegex(RuntimeError, 'UDP %d is occupied' % port):
                    launcher.preflight([worker], {})
                sock.bind.assert_called_once_with(('127.0.0.1', port))
                run.assert_not_called()

    def test_reused_workers_do_not_probe_their_occupied_udp_ports(self):
        with mock.patch.object(launcher.shutil, 'which', return_value='available.exe'), \
                mock.patch.object(launcher.socket, 'socket') as socket_factory, \
                mock.patch.object(launcher.subprocess, 'run') as run:
            launcher.preflight([], {})
            socket_factory.assert_not_called()
            run.assert_not_called()


@unittest.skipUnless(os.name == 'nt', 'Windows subprocess constants')
class CameraRecognitionTests(unittest.TestCase):
    def test_absent_and_matching_read_only_camera(self):
        results = [
            (1, b'', False),
            (0, b'123 /venv/bin/python hardware/g1_arm_bridge/g1_camera_tcp_bridge.py eth0 --host 127.0.0.1 --port 5011\n', True),
            (0, b'124 /venv/bin/python hardware/g1_arm_bridge/g1_camera_tcp_bridge.py eth0\n', True),
        ]
        for returncode, stdout, expected in results:
            with self.subTest(returncode=returncode, stdout=stdout), \
                    mock.patch.object(launcher.subprocess, 'run',
                                      return_value=subprocess.CompletedProcess([], returncode, stdout=stdout)) as run, \
                    mock.patch.object(launcher.socket, 'socket') as socket_factory:
                self.assertEqual(expected, launcher.camera_running())
                self.assertEqual(['wsl.exe', '-d', 'Ubuntu', '--', 'bash', '-lc'],
                                 run.call_args.args[0][:-1])
                self.assertIn('pgrep -af', run.call_args.args[0][-1])
                # Unity owns the TCP listener; camera inspection must not bind it.
                socket_factory.assert_not_called()

    def test_incompatible_camera_options_are_refused(self):
        for suffix in ('--host 10.0.0.2 --port 5011', '--host 127.0.0.1 --port 5012'):
            stdout = ('123 /venv/bin/python hardware/g1_arm_bridge/g1_camera_tcp_bridge.py eth0 ' + suffix + '\n').encode()
            with self.subTest(suffix=suffix), \
                    mock.patch.object(launcher.subprocess, 'run',
                                      return_value=subprocess.CompletedProcess([], 0, stdout=stdout)):
                with self.assertRaises(RuntimeError):
                    launcher.camera_running()

    def test_failed_or_empty_camera_inspection_is_not_treated_as_absent(self):
        for returncode, stdout in ((2, b''), (0, b''), (0, b'123 unrelated-process\n')):
            with self.subTest(returncode=returncode, stdout=stdout), \
                    mock.patch.object(launcher.subprocess, 'run',
                                      return_value=subprocess.CompletedProcess([], returncode, stdout=stdout)):
                with self.assertRaises(RuntimeError):
                    launcher.camera_running()


if __name__ == '__main__':
    unittest.main()
