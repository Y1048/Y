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
            with patch.object(login,'key_path',return_value=key), patch.object(login,'probe',side_effect=[False,True]) as probe, patch.object(login.subprocess,'run') as run:
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
            with patch.object(login,'key_path',return_value=key), patch.object(login,'probe',return_value=False), patch.object(login.subprocess,'run'):
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
        with patch.object(login.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertTrue(login.probe('example'))
            self.assertIn('BatchMode=yes',run.call_args.args[0])
            self.assertIn('StrictHostKeyChecking=yes',run.call_args.args[0])
            self.assertEqual('true',run.call_args.args[0][-1])
    def test_invalid_multiline_public_key_rejected(self):
        with self.assertRaises(RuntimeError):
            login.registration_command('ssh-ed25519 AAAA\ncommand')
