"""Offline launcher decisions; subprocesses and sockets are always mocked."""

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
        rows = [worker_row(worker) for worker in launcher.INTEGRATED_WORKERS]
        existing = launcher.running_workers(rows, ROOT, HOST)
        self.assertEqual(set(launcher.INTEGRATED_WORKERS), existing)
        self.assertEqual([], launcher.launch_plan(existing | {'camera_follow'}, True, True))
        self.assertEqual(['omni', 'lowstate', 'camera', 'groot', 'camera_follow'],
                         launcher.launch_plan({'send', 'arm'}, False, False))
        self.assertEqual(['omni', 'lowstate', 'camera_follow'],
                         launcher.launch_plan(
                             {'send', 'arm'}, True, True, no_receiver=True))

    def test_stale_launcher_windows_do_not_count_as_running_workers(self):
        rows = [[sys.executable, '-u', '-B',
                 str(TOOLS / 'G1_INPUT_OBSERVATION_LAUNCH.py'),
                 '--worker', worker, '--host', HOST]
                for worker in launcher.INTEGRATED_WORKERS]
        self.assertEqual(set(), launcher.running_workers(rows, ROOT, HOST))
        self.assertEqual(
            ['send', 'omni', 'arm', 'lowstate', 'camera', 'groot', 'camera_follow'],
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
        for worker in launcher.INTEGRATED_WORKERS:
            with self.subTest(worker=worker):
                row = worker_row(worker)
                with self.assertRaises(RuntimeError):
                    launcher.running_workers([row, list(row)], ROOT, HOST)

    def test_exact_groot_supervisor_is_reused(self):
        row = [
            sys.executable, '-I', '-u', '-B', str(launcher.GROOT_LAUNCHER),
            '--host', HOST, '--confirmed',
        ]
        self.assertTrue(launcher.groot_launcher_running([row], HOST))
        self.assertFalse(launcher.groot_launcher_running([], HOST))

    def test_conflicting_or_duplicate_groot_supervisor_is_refused(self):
        exact = [
            sys.executable, '-I', '-u', '-B', str(launcher.GROOT_LAUNCHER),
            '--host', HOST, '--confirmed',
        ]
        wrong = list(exact)
        wrong[wrong.index(HOST)] = '192.168.123.165'
        with self.assertRaises(RuntimeError):
            launcher.groot_launcher_running([wrong], HOST)
        with self.assertRaises(RuntimeError):
            launcher.groot_launcher_running([exact, list(exact)], HOST)

    def test_actuation_confirmation_requires_exact_token(self):
        with mock.patch('builtins.input', return_value='ACTUATE'), \
                redirect_stdout(io.StringIO()):
            launcher.confirm_groot_actuation()
        with mock.patch('builtins.input', return_value='yes'), \
                redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                launcher.confirm_groot_actuation()

    @unittest.skipUnless(os.name == 'nt', 'Uses Windows command-line parsing API')
    def test_windows_quoted_paths_and_remote_command_round_trip(self):
        root = Path(r'C:\test work\G1 project')
        with mock.patch.object(launcher.observation, 'ROOT', root):
            rows = [worker_row(worker) for worker in launcher.INTEGRATED_WORKERS]
        rows[0][0] = r'C:\Program Files\OpenSSH\ssh.exe'
        for row in rows[1:]:
            row[0] = r'C:\Program Files\Python 3.11\python.exe'
        parsed = [launcher.windows_arguments(subprocess.list2cmdline(row)) for row in rows]
        self.assertEqual(rows, parsed)
        self.assertEqual(set(launcher.INTEGRATED_WORKERS),
                         launcher.running_workers(parsed, root, HOST))


class UnityLaunchTests(unittest.TestCase):
    def test_exact_project_is_reused_and_other_project_is_ignored(self):
        editor = r'C:\Program Files\Unity\Editor\Unity.exe'
        exact = [editor, '-projectPath', str(launcher.UNITY_PROJECT)]
        other = [editor, '-projectPath', str(ROOT / 'another-project')]
        self.assertTrue(launcher.unity_project_running([exact, other]))
        self.assertFalse(launcher.unity_project_running([other]))

    def test_project_path_flag_is_case_insensitive(self):
        row = [r'C:\Unity\Unity.exe', '-PROJECTPATH', str(launcher.UNITY_PROJECT)]
        self.assertTrue(launcher.unity_project_running([row]))

    def test_duplicate_exact_project_is_reused(self):
        row = [r'C:\Unity\Unity.exe', '-projectPath', str(launcher.UNITY_PROJECT)]
        self.assertTrue(launcher.unity_project_running([row, list(row)]))

    def test_asset_import_worker_is_not_an_editor_window(self):
        worker = [r'C:\Unity\Unity.exe', '-adb2', '-batchMode',
                  '-name', 'AssetImportWorkerHW0', '-projectPath',
                  str(launcher.UNITY_PROJECT)]
        self.assertFalse(launcher.unity_project_running([worker]))

    def test_editor_resolution_prefers_valid_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / 'Unity.exe'
            editor.write_bytes(b'editor')
            resolved = launcher.resolve_unity_editor({'UNITY_EXE': str(editor)})
            self.assertEqual(editor.resolve(), resolved)

    def test_missing_editor_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, 'was not found'):
                launcher.resolve_unity_editor({
                    'ProgramFiles': temporary,
                    'ProgramW6432': temporary,
                    'USERPROFILE': temporary,
                    'SystemDrive': 'Z:',
                })

    def test_editor_resolution_uses_system_drive_program_files_fallback(self):
        expected = (Path(r'C:\Program Files') / 'Unity/Hub/Editor' /
                    launcher.UNITY_VERSION / 'Editor/Unity.exe')
        environment = {'SystemDrive': 'C:', 'USERPROFILE': r'C:\NoUnityHere'}
        with mock.patch.object(
                Path, 'is_file', autospec=True,
                side_effect=lambda path: str(path).casefold() == str(expected).casefold()):
            resolved = launcher.resolve_unity_editor(environment)
        self.assertEqual(expected.resolve(), resolved)

    def test_start_uses_detached_editor_without_play_mode(self):
        editor = Path(r'C:\Unity\Unity.exe')
        with mock.patch.object(launcher.subprocess, 'Popen') as spawn:
            launcher.start_unity(editor)
        command = spawn.call_args.args[0]
        self.assertEqual(str(editor), command[0])
        self.assertEqual('-projectPath', command[1])
        self.assertNotIn('-executeMethod', command)
        self.assertEqual(ROOT, spawn.call_args.kwargs['cwd'])
        self.assertTrue(spawn.call_args.kwargs['creationflags'] & subprocess.DETACHED_PROCESS)

    def test_unity_environment_fills_process_local_windows_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            local = Path(temporary)
            (local / 'Temp').mkdir()
            environment = {
                'SystemDrive': 'C:',
                'LOCALAPPDATA': str(local),
                'ProgramFiles': r'C:\Program Files',
            }
            with mock.patch.object(Path, 'is_dir', autospec=True,
                                   side_effect=lambda path: True if str(path).endswith('ProgramData') else Path.exists(path)):
                result = launcher.unity_environment(environment)
            self.assertEqual(r'C:\ProgramData', result['PROGRAMDATA'])
            self.assertEqual(result['PROGRAMDATA'], result['ALLUSERSPROFILE'])
            self.assertEqual(str(local / 'Temp'), result['TEMP'])
            self.assertEqual(result['TEMP'], result['TMP'])
            self.assertNotIn('PROGRAMDATA', environment)



@unittest.skipUnless(os.name == 'nt', 'Windows visible-console launcher')
class OrchestrationTests(unittest.TestCase):
    def invoke(self, rows=(), camera=False, unity=False, groot=False,
               args=(), preflight_error=None):
        """Execute only the decision code; never enumerate or start real processes."""
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(mock.patch.object(launcher, 'select_robot_host',
                                             side_effect=lambda host: HOST if host == 'auto' else host))
        inventory = list(rows)
        if camera:
            inventory.append([sys.executable, str(ROOT/'tools/G1_CAMERA_LAUNCH.py'),
                              '--robot-host', HOST])
        if groot:
            inventory.append([
                sys.executable, '-I', '-u', '-B', str(launcher.GROOT_LAUNCHER),
                '--host', HOST, '--confirmed',
            ])
        if unity:
            inventory.append([r'C:\Unity\Unity.exe', '-projectPath', str(launcher.UNITY_PROJECT)])
        stack.enter_context(mock.patch.object(launcher, 'process_arguments', return_value=inventory))
        environment = {'G1_OBSERVATION_TAP': '1', 'TEST_ONLY': '1'}
        stack.enter_context(mock.patch.object(launcher.observation, 'engine_environment', return_value=environment))
        check = stack.enter_context(mock.patch.object(launcher, 'preflight', side_effect=preflight_error))
        stack.enter_context(mock.patch.object(launcher, 'ensure_login'))
        stack.enter_context(mock.patch.object(launcher, 'validate_unity_project'))
        stack.enter_context(mock.patch.object(launcher, 'resolve_unity_editor',
                                             return_value=Path(r'C:\Unity\Unity.exe')))
        unity_start = stack.enter_context(mock.patch.object(launcher, 'start_unity'))
        confirm = stack.enter_context(
            mock.patch.object(launcher, 'confirm_groot_actuation'))
        spawn = stack.enter_context(mock.patch.object(launcher.subprocess, 'Popen'))
        run = stack.enter_context(mock.patch.object(launcher.subprocess, 'run',
                                                   side_effect=AssertionError('Unexpected subprocess execution')))
        result = launcher.main(['--show-consoles'] + list(args))
        run.assert_not_called()
        return result, spawn, check, confirm, environment, unity_start

    def test_fresh_start_adds_groot_after_explicit_confirmation(self):
        result, spawn, check, confirm, environment, unity_start = self.invoke()
        self.assertEqual(0, result)
        check.assert_called_once_with(
            ['send', 'omni', 'arm', 'lowstate', 'camera', 'groot', 'camera_follow'], environment)
        confirm.assert_called_once_with()
        self.assertEqual(7, spawn.call_count)
        unity_start.assert_called_once()
        commands = [call.args[0] for call in spawn.call_args_list]
        self.assertEqual(
            ['send', 'omni', 'arm', 'lowstate'],
            [launcher.option(command, '--worker') for command in commands[:4]])
        self.assertEqual(
            [sys.executable, '-I', '-u', '-B', str(ROOT/'tools/G1_CAMERA_LAUNCH.py'),
             '--robot-host', HOST],
            commands[4])
        self.assertEqual(
            [sys.executable, '-I', '-u', '-B', str(launcher.GROOT_LAUNCHER),
             '--host', HOST, '--confirmed'],
            commands[5])
        for call in spawn.call_args_list:
            self.assertEqual(ROOT, call.kwargs['cwd'])
            self.assertEqual(environment, call.kwargs['env'])
            self.assertEqual(subprocess.CREATE_NEW_CONSOLE, call.kwargs['creationflags'])
        omni_command = worker_row('omni')
        self.assertIn('--dry-run', omni_command)
        self.assertEqual(
            str(launcher.observation.UNITY_ALIGNMENT_PORT),
            launcher.option(omni_command, '--unity-alignment-port'))

    def test_all_running_produces_no_new_windows(self):
        rows = [worker_row(worker) for worker in launcher.INTEGRATED_WORKERS]
        rows.append([sys.executable, str(TOOLS/'G1_CAMERA_FOLLOW_LAUNCH.py'), '--host', HOST])
        result, spawn, check, confirm, environment, unity_start = self.invoke(
            rows, camera=True, unity=True, groot=True)
        self.assertEqual(0, result)
        check.assert_called_once_with([], environment)
        confirm.assert_not_called()
        spawn.assert_not_called()
        unity_start.assert_not_called()

    def test_closed_network_host_reaches_all_integrated_launches(self):
        result, spawn, _, _, _, _ = self.invoke(args=['--host', '192.168.10.165'])
        self.assertEqual(0, result)
        commands = [call.args[0] for call in spawn.call_args_list]
        for command in commands[:4]:
            self.assertEqual('192.168.10.165', launcher.option(command, '--host'))
        self.assertEqual('192.168.10.165', launcher.option(commands[4], '--robot-host'))
        self.assertEqual('192.168.10.165', launcher.option(commands[5], '--host'))

    def test_partial_start_only_creates_missing_workers(self):
        result, spawn, check, confirm, environment, _ = self.invoke(
            [worker_row('send'), worker_row('arm')], camera=True, groot=True)
        self.assertEqual(0, result)
        check.assert_called_once_with(['omni', 'lowstate', 'camera_follow'], environment)
        confirm.assert_not_called()
        self.assertEqual(
            ['omni', 'lowstate', 'camera_follow'],
            [launcher.option(call.args[0], '--worker') or 'camera_follow' for call in spawn.call_args_list])

    def test_check_only_never_confirms_or_starts_groot(self):
        result, spawn, check, confirm, _, unity_start = self.invoke(
            args=['--check-only'])
        self.assertEqual(0, result)
        check.assert_called_once()
        confirm.assert_not_called()
        spawn.assert_not_called()
        unity_start.assert_not_called()

    def test_no_groot_actuation_preserves_old_observation_only_start(self):
        result, spawn, check, confirm, environment, _ = self.invoke(
            args=['--no-groot-actuation'])
        self.assertEqual(0, result)
        check.assert_called_once_with(
            ['send', 'omni', 'arm', 'lowstate', 'camera', 'camera_follow'], environment)
        confirm.assert_not_called()
        self.assertEqual(6, spawn.call_count)
        self.assertFalse(any(
            str(launcher.GROOT_LAUNCHER) in call.args[0]
            for call in spawn.call_args_list))

    def test_no_unity_skips_resolution_and_launch(self):
        result, _, _, _, _, unity_start = self.invoke(args=['--no-unity'])
        self.assertEqual(0, result)
        unity_start.assert_not_called()

    def test_conflicting_inventory_fails_before_any_spawn(self):
        with mock.patch.object(launcher, 'select_robot_host', return_value=HOST), \
                mock.patch.object(launcher, 'process_arguments', return_value=[worker_row('send', 'other-host')]), \
                mock.patch.object(launcher.subprocess, 'Popen') as spawn, \
                mock.patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                launcher.main([])
            spawn.assert_not_called()
            run.assert_not_called()

    def test_both_networks_unreachable_starts_no_workers(self):
        with mock.patch.object(launcher, 'select_robot_host', side_effect=RuntimeError('unreachable')), \
                mock.patch.object(launcher, 'process_arguments') as inventory, \
                mock.patch.object(launcher.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'unreachable'):
                launcher.main([])
            inventory.assert_not_called()
            spawn.assert_not_called()


@unittest.skipUnless(os.name == 'nt', 'Windows socket and subprocess constants')
class PreflightTests(unittest.TestCase):
    def test_unrelated_udp_owner_blocks_before_any_dependency_process(self):
        for worker, port in (
                ('send', 55071),
                ('arm', 5020),
                ('omni', launcher.observation.UNITY_ALIGNMENT_PORT)):
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

    def test_ssh_camera_preflight_requires_only_local_ssh(self):
        with mock.patch.object(launcher.shutil, 'which',
                               side_effect=lambda name: 'ssh.exe' if name == 'ssh.exe' else None), \
                mock.patch.object(launcher.subprocess, 'run',
                                  side_effect=AssertionError('No subprocess required')):
            launcher.preflight(['camera'], {})

    def test_reused_workers_do_not_probe_their_occupied_udp_ports(self):
        with mock.patch.object(launcher.shutil, 'which', return_value='available.exe'), \
                mock.patch.object(launcher.socket, 'socket') as socket_factory, \
                mock.patch.object(launcher.subprocess, 'run') as run:
            launcher.preflight([], {})
            socket_factory.assert_not_called()
            run.assert_not_called()



if __name__ == '__main__':
    unittest.main()
