import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import g1_quiet_observation as quiet

class QuietTests(unittest.TestCase):
    def test_local_workers_hidden_and_own_children_stopped(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(quiet.subprocess, 'Popen') as spawn, patch('builtins.input', return_value=''):
            child = MagicMock()
            child.poll.return_value = None
            spawn.return_value = child
            quiet.run_workers(Path(directory), ['send', 'omni', 'arm'], 'example', {})
            self.assertEqual(3, spawn.call_count)
            for call in spawn.call_args_list:
                self.assertEqual(quiet.subprocess.CREATE_NO_WINDOW, call.kwargs['creationflags'])
                self.assertEqual(quiet.subprocess.DEVNULL, call.kwargs['stdin'])
                self.assertIn('stdout', call.kwargs)
            self.assertEqual(3, child.terminate.call_count)
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
