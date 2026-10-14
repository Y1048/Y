import signal
import json
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import g1_quiet_observation as quiet


class QuietTests(unittest.TestCase):
    def test_journal_creation_failure_prevents_worker_start(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch.object(quiet, 'SessionJournal', side_effect=OSError('disk full')), \
                patch.object(quiet.subprocess, 'Popen') as spawn:
            with self.assertRaises(OSError):
                quiet.run_workers(Path(directory), ['groot'], 'example', {})
            spawn.assert_not_called()

    def test_later_journal_write_failure_does_not_abort_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = quiet.SessionJournal(Path(directory) / 'events.jsonl')
            with patch.object(Path, 'open', side_effect=OSError('disk full')), \
                    patch('builtins.print') as output:
                journal.record('shutdown_requested')
                output.assert_called_once()

    def test_unexpected_exit_including_zero_is_logged_and_fails(self):
        for exit_code in (0, 1, 255):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as directory, \
                    patch.object(quiet, 'bind_session_lifetime'), \
                    patch.object(quiet.threading, 'Thread'), \
                    patch.object(quiet.threading, 'Event') as event, \
                    patch.object(quiet.subprocess, 'Popen') as spawn, \
                    patch.object(quiet.subprocess, 'run') as kill:
                event.return_value.wait.return_value = False
                spawn.return_value.pid = 301
                spawn.return_value.poll.return_value = exit_code
                self.assertEqual(1, quiet.run_workers(Path(directory), ['camera_follow'], 'example', {}))
                rows = [json.loads(s) for s in next(Path(directory).rglob('supervisor.jsonl')).read_text().splitlines()]
                failure = next(r for r in rows if r['event'] == 'unexpected_worker_exit')
                self.assertEqual([['camera_follow', exit_code]], failure['workers'])
                self.assertEqual(1, rows[-1]['returncode'])
                self.assertEqual('session_end', rows[-1]['event'])
                self.assertEqual(sorted(r['monotonic_s'] for r in rows), [r['monotonic_s'] for r in rows])
                kill.assert_not_called()

    def test_start_failure_cleans_up_started_children_and_keeps_reason(self):
        child = MagicMock(pid=302)
        child.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch.object(quiet.subprocess, 'Popen', side_effect=[child, OSError('spawn failed')]), \
                patch.object(quiet.subprocess, 'run') as kill:
            self.assertEqual(1, quiet.run_workers(Path(directory), ['send', 'arm'], 'example', {}))
            rows = [json.loads(s) for s in next(Path(directory).rglob('supervisor.jsonl')).read_text().splitlines()]
            self.assertIn('spawn failed', next(r['error'] for r in rows if r['event'] == 'supervisor_exception'))
            kill.assert_called_once()

    def test_shutdown_unverified_propagates_and_stops_groot_before_other_workers(self):
        groot = MagicMock(pid=401)
        arm = MagicMock(pid=402)
        groot.poll.return_value = arm.poll.return_value = None
        calls = []
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch('builtins.input', return_value=''), \
                patch.object(quiet.subprocess, 'Popen', side_effect=[groot, arm]), \
                patch.object(quiet, '_stop_groot_supervisor', side_effect=lambda c, p: calls.append('groot') or 2), \
                patch.object(quiet.subprocess, 'run', side_effect=lambda *a, **k: calls.append('arm')):
            self.assertEqual(2, quiet.run_workers(Path(directory), ['groot', 'arm'], 'example', {}))
            self.assertEqual(['groot', 'arm'], calls)

    def test_eof_is_not_a_successful_operator_stop(self):
        child = MagicMock(pid=403)
        child.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch('builtins.input', side_effect=EOFError), \
                patch.object(quiet.subprocess, 'Popen', return_value=child), \
                patch.object(quiet.subprocess, 'run'):
            self.assertEqual(1, quiet.run_workers(Path(directory), ['arm'], 'example', {}))

    def test_error_batch_preserves_failure_status_across_pause(self):
        text = (Path(__file__).resolve().parents[2] / 'START_G1_VR_TELEOP.bat').read_text()
        self.assertIn('set "G1_TELEOP_EXIT=%ERRORLEVEL%"', text)
        self.assertIn('if not "%G1_TELEOP_EXIT%"=="0"', text)
        self.assertLess(text.index('pause'), text.index('exit /b %G1_TELEOP_EXIT%'))

    @unittest.skipUnless(os.name == 'nt', 'Windows BAT behavior')
    def test_actual_cmd_error_wrapper_pauses_and_preserves_exit_code(self):
        text = (Path(__file__).resolve().parents[2] / 'START_G1_VR_TELEOP.bat').read_text()
        command = next(line for line in text.splitlines() if 'G1_PORTABLE.py' in line)
        for code in (0, 7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                fixture = Path(directory) / 'fixture.bat'
                # Only replace the robot-capable command with a harmless CMD exit.
                fixture.write_text(text.replace(command, 'cmd.exe /d /c exit ' + str(code)))
                result = subprocess.run(['cmd.exe', '/d', '/c', str(fixture)], input='\n',
                                        capture_output=True, text=True, errors='replace', timeout=5)
                self.assertEqual(code, result.returncode)
                self.assertEqual(code != 0, '[G1 TELEOP FAILED]' in result.stdout)

    def test_local_workers_hidden_and_own_children_stopped(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet.subprocess, 'Popen') as spawn, \
                patch('builtins.input', return_value=''), \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch.object(quiet.subprocess, 'run') as kill:
            child = MagicMock()
            child.pid = 101
            child.poll.return_value = None
            spawn.return_value = child
            quiet.run_workers(
                Path(directory), ['send', 'omni', 'arm', 'camera_follow'], 'example', {})
            self.assertEqual(4, spawn.call_count)
            for call in spawn.call_args_list:
                self.assertEqual(
                    quiet.subprocess.CREATE_NO_WINDOW,
                    call.kwargs['creationflags'])
                self.assertEqual(
                    quiet.subprocess.DEVNULL, call.kwargs['stdin'])
                self.assertIn('stdout', call.kwargs)
            send_command = spawn.call_args_list[0].args[0]
            self.assertEqual(
                send_command[send_command.index('--print-hz') + 1], '1')
            self.assertEqual(
                send_command[send_command.index('--send-hz') + 1], '60')
            self.assertEqual(4, kill.call_count)
            self.assertEqual(0, child.terminate.call_count)
            for call in kill.call_args_list:
                self.assertIn('/T', call.args[0])

    def test_lifetime_failure_prevents_all_worker_launches(self):
        with patch.object(
                quiet, 'bind_session_lifetime',
                side_effect=OSError('job failed')), \
                patch.object(quiet.subprocess, 'Popen') as spawn:
            with self.assertRaises(OSError):
                quiet.run_workers(
                    Path('unused'), ['send', 'camera'], 'example', {})
            spawn.assert_not_called()

    def test_camera_is_owned_by_same_supervisor(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime') as bind, \
                patch.object(quiet.subprocess, 'Popen') as spawn, \
                patch.object(quiet.subprocess, 'run'), \
                patch('builtins.input', return_value=''):
            spawn.return_value.poll.return_value = None
            spawn.return_value.pid = 102
            quiet.run_workers(Path(directory), ['camera'], 'example', {})
            bind.assert_called_once()
            self.assertEqual(
                spawn.call_args.args[0][-4:],
                ['--robot-host', 'example', '--camera-codec', 'h264'])
            self.assertEqual(
                spawn.call_args.kwargs['creationflags'],
                quiet.subprocess.CREATE_NEW_CONSOLE)

    def test_groot_gets_own_process_group_and_controlled_stop(self):
        child = MagicMock()
        child.pid = 103
        child.poll.return_value = None
        child.wait.return_value = 0
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime') as bind, \
                patch.object(quiet.subprocess, 'Popen', return_value=child) as spawn, \
                patch.object(quiet.subprocess, 'run') as taskkill, \
                patch('builtins.input', return_value=''):
            quiet.run_workers(Path(directory), ['groot'], 'example', {})
            request = next(Path(directory).rglob('groot.stop'))
            self.assertEqual('stop\n', request.read_text())
        bind.assert_called_once()
        command = spawn.call_args.args[0]
        self.assertIn('G1_GROOT_REMOTE_LAUNCH.py', ' '.join(command))
        self.assertEqual('example', command[command.index('--host') + 1])
        self.assertIn('--confirmed', command)
        flags = spawn.call_args.kwargs['creationflags']
        self.assertTrue(flags & quiet.subprocess.CREATE_NEW_CONSOLE)
        self.assertTrue(flags & quiet.subprocess.CREATE_NEW_PROCESS_GROUP)
        self.assertIn('--stop-request-file', command)
        child.send_signal.assert_not_called()
        child.wait.assert_any_call(timeout=20)
        taskkill.assert_not_called()

    def test_groot_timeout_is_not_force_killed(self):
        child = MagicMock()
        child.poll.return_value = None
        child.wait.side_effect = [subprocess.TimeoutExpired('groot', 20), 0]
        with patch.object(quiet, 'print', create=True) as output:
            quiet._stop_groot_supervisor(child)
        self.assertEqual(2, child.wait.call_count)
        text = ' '.join(
            str(arg)
            for call in output.call_args_list
            for arg in call.args)
        self.assertIn('Keeping this manager open', text)

    def test_file_shutdown_reaches_real_child_without_console_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'groot.stop'
            # Harmless local stand-in: no SDK, SSH, robot code or transport.
            script = ('import pathlib,sys,time\n'
                      'p=pathlib.Path(sys.argv[1])\n'
                      'while not p.is_file(): time.sleep(.02)\n')
            child = subprocess.Popen([sys.executable, '-I', '-B', '-c', script, str(path)],
                                     stdin=subprocess.DEVNULL)
            try:
                self.assertEqual(0, quiet._stop_groot_supervisor(child, path))
                self.assertEqual('stop\n', path.read_text())
                self.assertFalse(path.with_suffix('.tmp').exists())
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)

    def test_receive_hides_only_after_stdout_and_preserves_auth_stdin(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet.observation, 'ssh_executable', return_value='ssh.exe'), \
                patch.object(quiet.subprocess, 'Popen') as spawn, \
                patch.object(quiet.ctypes, 'windll') as win:
            child = spawn.return_value
            child.stdout = iter(['receiver ready\n'])
            child.wait.return_value = 0
            child.poll.return_value = 0
            win.kernel32.GetConsoleWindow.return_value = 42
            self.assertEqual(
                0,
                quiet.receive(
                    'example', str(Path(directory) / 'receive.log')))
            self.assertNotIn('stdin', spawn.call_args.kwargs)
            win.user32.ShowWindow.assert_called_once_with(42, 0)
            self.assertEqual(
                'receiver ready\n',
                (Path(directory) / 'receive.log').read_text())


if __name__ == '__main__':
    unittest.main()
