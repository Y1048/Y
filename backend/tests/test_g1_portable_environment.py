"""Offline portability tests for the current Windows SSH teleop path."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import g1_portable_environment as portable
import SETUP_G1_VR_TELEOP as setup
import g1_camera_ssh as camera


class PortableTests(unittest.TestCase):
    def test_wired_first_fallback_and_explicit_host(self):
        with mock.patch.object(portable.socket, 'create_connection') as connect:
            self.assertEqual('192.168.123.164', portable.select_robot_host())
            connect.assert_called_once_with(('192.168.123.164', 22), timeout=1.5)
        with mock.patch.object(portable.socket, 'create_connection',
                               side_effect=[OSError('timeout'), mock.MagicMock()]) as connect:
            self.assertEqual('192.168.10.165', portable.select_robot_host())
            self.assertEqual(('192.168.10.165', 22), connect.call_args.args[0])
        with mock.patch.object(portable.socket, 'create_connection',
                               side_effect=OSError('timeout')) as connect:
            with self.assertRaises(RuntimeError):
                portable.select_robot_host()
            self.assertEqual(2, connect.call_count)
        with mock.patch.object(portable.socket, 'create_connection') as connect:
            self.assertEqual('192.168.10.165',
                             portable.select_robot_host('192.168.10.165'))
            connect.assert_not_called()

    def test_check_only_missing_environment_never_installs(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(setup, 'ROOT', Path(directory)), \
                mock.patch.object(sys, 'argv', ['setup', '--check-only']), \
                mock.patch.object(setup.subprocess, 'run') as run, \
                mock.patch.object(camera, 'check_environment') as camera_check:
            with self.assertRaises(RuntimeError):
                setup.main()
            run.assert_not_called()
            camera_check.assert_not_called()

    def test_check_only_existing_environment_checks_current_paths_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / '.venv-teleop/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            with mock.patch.object(setup, 'ROOT', root), \
                    mock.patch.object(sys, 'argv', ['setup', '--check-only']), \
                    mock.patch.object(setup.subprocess, 'run') as run, \
                    mock.patch.object(camera, 'check_environment') as camera_check:
                setup.main()
                self.assertEqual(3, run.call_count)
                self.assertIn('g1_portable_environment.py', run.call_args.args[0][-1])
                camera_check.assert_called_once()

    def test_launch_bats_use_own_checkout_environment(self):
        for name in ('START_G1_VR_TELEOP', 'START_G1_CAMERA_TO_UNITY'):
            source = (ROOT / 'tools' / (name + '.bat')).read_text()
            self.assertIn('cd /d "%~dp0.."', source)
            self.assertIn('.venv-teleop\\Scripts\\python.exe', source)
            self.assertNotIn('/mnt/c/Users/', source)

    def test_portable_module_has_no_wsl_camera_fallback(self):
        source = (ROOT / 'tools/g1_portable_environment.py').read_text()
        for token in ('wsl.exe', 'camera_run', 'configure_mirrored_network',
                      'start_camera_tcp_bridge_wsl.sh'):
            self.assertNotIn(token, source)


if __name__ == '__main__':
    unittest.main()
