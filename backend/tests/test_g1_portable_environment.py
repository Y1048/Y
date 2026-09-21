"""Offline portability tests: no network, SDK initialization, or child runtime."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import io
import tarfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import g1_portable_environment as portable
import SETUP_G1_VR_TELEOP as setup
import g1_source_archive_check as archive_check


class PortableTests(unittest.TestCase):
    def test_wired_first_fallback_and_explicit_host(self):
        with mock.patch.object(portable.socket, 'create_connection') as connect:
            self.assertEqual('192.168.123.164', portable.select_robot_host())
            connect.assert_called_once_with(('192.168.123.164', 22), timeout=1.5)
        with mock.patch.object(portable.socket, 'create_connection',
                               side_effect=[OSError('timeout'), mock.MagicMock()]) as connect:
            self.assertEqual('192.168.10.165', portable.select_robot_host())
            self.assertEqual(('192.168.10.165', 22), connect.call_args.args[0])
        with mock.patch.object(portable.socket, 'create_connection', side_effect=OSError('timeout')) as connect:
            with self.assertRaises(RuntimeError):
                portable.select_robot_host()
            self.assertEqual(2, connect.call_count)
        with mock.patch.object(portable.socket, 'create_connection') as connect:
            self.assertEqual('192.168.10.165', portable.select_robot_host('192.168.10.165'))
            connect.assert_not_called()

    def test_source_archive_checks_content_not_owner_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'source.tar'
            data = b'original'
            with tarfile.open(archive, 'w') as output:
                member = tarfile.TarInfo('source.py')
                member.size = len(data)
                member.uid = 9999
                output.addfile(member, io.BytesIO(data))
            (root / 'source.py').write_bytes(data)
            archive_check.verify(archive, root)
            (root / 'source.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Modified source'):
                archive_check.verify(archive, root)
    def test_wsl_merge_preserves_unrelated_settings_and_original_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.wslconfig'
            original = b'[wsl2]\r\nmemory=8GB\r\nnetworkingMode=nat\r\n[experimental]\r\nsparseVhd=true\r\n'
            path.write_bytes(original)
            self.assertTrue(portable.configure_mirrored_network(path))
            text = path.read_text(encoding='utf-8')
            self.assertIn('memory=8GB', text)
            self.assertIn('sparseVhd=true', text)
            self.assertIn('networkingMode=mirrored', text)
            self.assertEqual(original, next(Path(directory).glob('*.g1-backup-*')).read_bytes())
            self.assertFalse(portable.configure_mirrored_network(path))
            self.assertEqual(1, len(list(Path(directory).glob('*.g1-backup-*'))))

    def test_wsl_merge_new_section_utf16_and_ambiguous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.wslconfig'
            path.write_text('[experimental]\nsparseVhd=true\n', encoding='utf-16')
            self.assertTrue(portable.configure_mirrored_network(path))
            self.assertIn('[wsl2]\nnetworkingMode=mirrored', path.read_text(encoding='utf-8'))
            original = b'[wsl2]\nnetworkingMode=nat\nnetworkingMode=none\n'
            path.write_bytes(original)
            with self.assertRaises(RuntimeError):
                portable.configure_mirrored_network(path)
            self.assertEqual(original, path.read_bytes())

    def test_default_and_explicit_wsl_have_no_fixed_distribution(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(['wsl.exe', '--'], portable.wsl_prefix())
        with mock.patch.dict(os.environ, {'G1_WSL_DISTRO': 'Ubuntu-24.04'}):
            self.assertEqual(['wsl.exe', '-d', 'Ubuntu-24.04', '--'], portable.wsl_prefix())

    def test_check_only_camera_does_not_download_sources(self):
        with mock.patch.object(portable, 'prepare_camera_sources') as prepare, \
                mock.patch.object(portable, 'camera_command', return_value=(['mock'], 'echo check\n')), \
                mock.patch.object(portable.subprocess, 'run'):
            portable.camera_run('--check-only', '192.168.10.165')
            prepare.assert_not_called()

    def test_source_cache_wrong_origin_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'logs/setup/camera_sources/cyclonedds').mkdir(parents=True)
            with mock.patch.object(portable, 'ROOT', root), \
                    mock.patch.object(portable.subprocess, 'check_output', return_value='different-origin\n'), \
                    mock.patch.object(portable.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'origin'):
                    portable.prepare_camera_sources()
                run.assert_not_called()

    def test_drive_spaces_unicode_are_one_argument_without_shell_interpolation(self):
        with mock.patch.object(portable.subprocess, 'run', return_value=
                               subprocess.CompletedProcess([], 0, '/mnt/d/다른 PC/project\n')) as run:
            self.assertEqual('/mnt/d/다른 PC/project', portable.wsl_path(r'D:\다른 PC\project'))
            self.assertEqual('D:/다른 PC/project', run.call_args.args[0][-1])
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_crlf_script_is_sent_as_lf_bytes_not_windows_text_pipe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh'
            script.parent.mkdir(parents=True)
            script.write_bytes(b'#!/bin/bash\r\nset -euo pipefail\r\n')
            with mock.patch.object(portable, 'ROOT', root), \
                    mock.patch.object(portable, 'wsl_path', return_value='/mnt/d/a b'), \
                    mock.patch.object(portable.subprocess, 'run') as run:
                portable.camera_run('--check-only', '192.168.123.164')
                self.assertEqual(b'#!/bin/bash\nset -euo pipefail\n', run.call_args.kwargs['input'])
                self.assertEqual(['/mnt/d/a b', '--check-only', '192.168.123.164'],
                                 run.call_args.args[0][-3:])
                self.assertNotIn('text', run.call_args.kwargs)

    def test_failed_path_lookup_and_multiline_output_fail_closed(self):
        with mock.patch.object(portable.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, [])):
            with self.assertRaises(subprocess.CalledProcessError):
                portable.wsl_path('test')
        with mock.patch.object(portable.subprocess, 'run', return_value=
                               subprocess.CompletedProcess([], 0, '/first\n/second')):
            with self.assertRaises(RuntimeError):
                portable.wsl_path('test')

    def test_check_only_missing_environment_never_installs(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(setup, 'ROOT', Path(directory)), \
                mock.patch.object(sys, 'argv', ['setup', '--check-only']), \
                mock.patch.object(setup.subprocess, 'run') as run, \
                mock.patch.object(setup, 'camera_run') as camera:
            with self.assertRaises(RuntimeError):
                setup.main()
            run.assert_not_called()
            camera.assert_not_called()

    def test_check_only_existing_environment_only_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / '.venv-teleop/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            with mock.patch.object(setup, 'ROOT', root), \
                    mock.patch.object(sys, 'argv', ['setup', '--check-only']), \
                    mock.patch.object(setup.subprocess, 'run') as run, \
                    mock.patch.object(setup, 'camera_run') as camera:
                setup.main()
                self.assertEqual(2, run.call_count)
                self.assertIn('g1_portable_environment.py', run.call_args.args[0][-1])
                camera.assert_called_once_with('--check-only', '192.168.123.164')

    def test_launch_bats_use_own_checkout_environment(self):
        for name in ('START_G1_VR_TELEOP', 'START_G1_CAMERA_TO_UNITY', 'START_G1_INPUT_OBSERVATION'):
            source = (ROOT / 'tools' / (name + '.bat')).read_text()
            self.assertIn('cd /d "%~dp0.."', source)
            self.assertIn('.venv-teleop\\Scripts\\python.exe', source)
            self.assertNotIn('/mnt/c/Users/', source)
        shell = (ROOT / 'hardware/g1_arm_bridge/start_camera_tcp_bridge_wsl.sh').read_text()
        self.assertNotIn('192.168.123.99', shell)
        self.assertIn('ip -j route get', shell)
        self.assertIn('"gateway" not in r', shell)
        self.assertIn('9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd', shell)
        self.assertNotIn('ChannelFactoryInitialize(', shell)
        self.assertNotIn('LowCmd', shell)


if __name__ == '__main__':
    unittest.main()
