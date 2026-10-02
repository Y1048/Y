import signal
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import g1_quiet_observation as quiet


class QuietTests(unittest.TestCase):
    def test_local_workers_hidden_and_own_children_stopped(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet.subprocess, 'Popen') as spawn, \
                patch('builtins.input', return_value=''), \
                patch.object(quiet, 'bind_session_lifetime'), \
                patch.object(quiet.subprocess, 'run') as kill:
            child = MagicMock()
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
            quiet.run_workers(Path(directory), ['camera'], 'example', {})
            bind.assert_called_once()
            self.assertEqual(
                spawn.call_args.args[0][-2:],
                ['--robot-host', 'example'])
            self.assertEqual(
                spawn.call_args.kwargs['creationflags'],
                quiet.subprocess.CREATE_NEW_CONSOLE)

    def test_groot_gets_own_process_group_and_controlled_stop(self):
        child = MagicMock()
        child.poll.return_value = None
        child.wait.return_value = 0
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(quiet, 'bind_session_lifetime') as bind, \
                patch.object(quiet.subprocess, 'Popen', return_value=child) as spawn, \
                patch.object(quiet.subprocess, 'run') as taskkill, \
                patch('builtins.input', return_value=''):
            quiet.run_workers(Path(directory), ['groot'], 'example', {})
        bind.assert_called_once()
        command = spawn.call_args.args[0]
        self.assertIn('G1_GROOT_REMOTE_LAUNCH.py', ' '.join(command))
        self.assertEqual('example', command[command.index('--host') + 1])
        self.assertIn('--confirmed', command)
        flags = spawn.call_args.kwargs['creationflags']
        self.assertTrue(flags & quiet.subprocess.CREATE_NEW_CONSOLE)
        self.assertTrue(flags & quiet.subprocess.CREATE_NEW_PROCESS_GROUP)
        expected_signal = getattr(
            signal, 'CTRL_BREAK_EVENT', signal.SIGINT)
        child.send_signal.assert_called_once_with(expected_signal)
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
