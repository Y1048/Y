import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import g1_quiet_observation as quiet

class QuietTests(unittest.TestCase):
    def test_local_workers_hidden_and_own_children_stopped(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(quiet.subprocess, 'Popen') as spawn, patch('builtins.input', return_value=''), patch.object(quiet, 'bind_session_lifetime'), patch.object(quiet.subprocess, 'run') as kill:
            child = MagicMock()
            child.poll.return_value = None
            spawn.return_value = child
            quiet.run_workers(Path(directory), ['send', 'omni', 'arm'], 'example', {})
            self.assertEqual(3, spawn.call_count)
            for call in spawn.call_args_list:
                self.assertEqual(quiet.subprocess.CREATE_NO_WINDOW, call.kwargs['creationflags'])
                self.assertEqual(quiet.subprocess.DEVNULL, call.kwargs['stdin'])
                self.assertIn('stdout', call.kwargs)
            self.assertEqual(3, kill.call_count)
            self.assertEqual(0, child.terminate.call_count)
            for call in kill.call_args_list:
                self.assertIn('/T', call.args[0])
    def test_lifetime_failure_prevents_all_worker_launches(self):
        with patch.object(quiet, 'bind_session_lifetime', side_effect=OSError('job failed')), patch.object(quiet.subprocess, 'Popen') as spawn:
            with self.assertRaises(OSError):
                quiet.run_workers(Path('unused'), ['send', 'camera'], 'example', {})
            spawn.assert_not_called()

    def test_camera_is_owned_by_same_supervisor(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(quiet, 'bind_session_lifetime') as bind, patch.object(quiet.subprocess, 'Popen') as spawn, patch.object(quiet.subprocess, 'run'), patch('builtins.input', return_value=''):
            spawn.return_value.poll.return_value = None
            quiet.run_workers(Path(directory), ['camera'], 'example', {})
            bind.assert_called_once()
            self.assertEqual(spawn.call_args.args[0][-2:], ['--robot-host', 'example'])
            self.assertEqual(spawn.call_args.kwargs['creationflags'], quiet.subprocess.CREATE_NEW_CONSOLE)

    def test_receive_hides_only_after_stdout_and_preserves_auth_stdin(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(quiet.subprocess, 'Popen') as spawn, patch.object(quiet.ctypes, 'windll') as win:
            child=spawn.return_value
            child.stdout=iter(['receiver ready\n'])
            child.wait.return_value=0
            child.poll.return_value=0
            win.kernel32.GetConsoleWindow.return_value=42
            self.assertEqual(0, quiet.receive('example', str(Path(directory)/'receive.log')))
            self.assertNotIn('stdin', spawn.call_args.kwargs)
            win.user32.ShowWindow.assert_called_once_with(42, 0)
            self.assertEqual('receiver ready\n', (Path(directory)/'receive.log').read_text())
