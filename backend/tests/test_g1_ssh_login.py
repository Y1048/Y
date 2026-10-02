import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
import g1_ssh_login as login

class LoginTests(unittest.TestCase):
    def pair(self, root):
        key=Path(root)/'key'
        key.write_text('test fixture, not private key')
        Path(str(key)+'.pub').write_text('ssh-ed25519 AAAAFIXTURE comment\n')
        return key
    def test_existing_login_does_not_register_or_prompt(self):
        with tempfile.TemporaryDirectory() as root:
            key=self.pair(root)
            with patch.object(login,'key_path',return_value=key), patch.object(login,'probe',return_value=True), patch.object(login.subprocess,'run') as run:
                login.ensure_login('example')
                run.assert_not_called()
    def test_first_registration_inherits_terminal_and_verifies_key(self):
        with tempfile.TemporaryDirectory() as root:
            key=self.pair(root)
            with patch.object(login,'key_path',return_value=key), patch.object(login,'probe',side_effect=[False,True]) as probe, patch.object(login,'ssh_executable',return_value='ssh-test.exe'), patch.object(login.subprocess,'run') as run:
                login.ensure_login('example')
                self.assertEqual(2,probe.call_count)
                argv=run.call_args.args[0]
                self.assertIn('NumberOfPasswordPrompts=1',argv)
                self.assertIn('StrictHostKeyChecking=accept-new',argv)
                self.assertIn('grep -qxF',argv[-1])
                self.assertNotIn('stdin',run.call_args.kwargs)
                self.assertNotIn('input',run.call_args.kwargs)
    def test_failed_verification_blocks_launch(self):
        with tempfile.TemporaryDirectory() as root:
            key=self.pair(root)
            with patch.object(login,'key_path',return_value=key), patch.object(login,'probe',return_value=False), patch.object(login,'ssh_executable',return_value='ssh-test.exe'), patch.object(login.subprocess,'run'):
                with self.assertRaisesRegex(RuntimeError,'could not be verified'):
                    login.ensure_login('example')
    def test_partial_key_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            key=Path(root)/'key';key.write_text('preserve')
            with patch.object(login,'key_path',return_value=key), patch.object(login.subprocess,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'Incomplete'):
                    login.ensure_login('example')
                run.assert_not_called()
                self.assertEqual('preserve',key.read_text())
    def test_probe_is_noninteractive_and_checks_host_identity(self):
        with patch.object(login,'ssh_executable',return_value='ssh-test.exe'), patch.object(login.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertTrue(login.probe('example'))
            self.assertIn('BatchMode=yes',run.call_args.args[0])
            self.assertIn('StrictHostKeyChecking=yes',run.call_args.args[0])
            self.assertEqual('true',run.call_args.args[0][-1])
    def test_resolver_skips_broken_windows_and_uses_git(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);windows=root/'Windows';program=root/'Program Files'
            broken=windows/'System32/OpenSSH/ssh.exe';working=program/'Git/usr/bin/ssh.exe'
            broken.parent.mkdir(parents=True);working.parent.mkdir(parents=True)
            broken.write_bytes(b'broken');working.write_bytes(b'working')
            env={'WINDIR':str(windows),'PATH':'','ProgramFiles':str(program)}
            with patch.object(login,'_ssh_healthy',side_effect=lambda path: Path(path)==working):
                self.assertEqual(str(working),login.ssh_executable(env))
    def test_explicit_broken_ssh_override_fails_closed(self):
        with patch.object(login,'_ssh_healthy',return_value=False):
            with self.assertRaisesRegex(RuntimeError,'SSH_EXE'):
                login.ssh_executable({'SSH_EXE':r'C:\broken\ssh.exe'})
    def test_keygen_comes_from_selected_ssh_directory(self):
        with tempfile.TemporaryDirectory() as root:
            ssh=Path(root)/'ssh.exe';ssh.write_bytes(b'ssh')
            keygen=ssh.with_name('ssh-keygen.exe' if login.os.name=='nt' else 'ssh-keygen')
            keygen.write_bytes(b'keygen')
            with patch.object(login,'ssh_executable',return_value=str(ssh)):
                self.assertEqual(str(keygen),login.ssh_keygen_executable())
    def test_invalid_multiline_public_key_rejected(self):
        with self.assertRaises(RuntimeError):
            login.registration_command('ssh-ed25519 AAAA\ncommand')
