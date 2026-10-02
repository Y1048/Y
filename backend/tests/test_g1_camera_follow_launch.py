"""Remote lifetime script under mocks: no SSH, sockets or hardware."""
import base64
import contextlib
import io
from pathlib import Path
import shlex
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import G1_CAMERA_FOLLOW_LAUNCH as follow

class FollowTests(unittest.TestCase):
    def execute(self, args=None):
        proc=MagicMock();proc.name='123'
        proc.joinpath.return_value.read_bytes.return_value=('\0'.join(args)+'\0').encode() if args else b''
        root=MagicMock();root.__truediv__.return_value=root
        root.resolve.return_value=root
        root.is_file.return_value=True
        root.name='receive_mink_ik_udp.py'
        root.__str__.return_value='/home/unitree/groot_onboard_runtime/receive_mink_ik_udp.py'
        def path(value,*rest):
            if value=='/proc':
                result=MagicMock();result.iterdir.return_value=[proc] if args else []
                result.exists.return_value=True;return result
            if value=='/home/unitree/groot_onboard_runtime':return root
            result=MagicMock();result.name=value.rsplit('/',1)[-1]
            result.is_absolute.return_value=True;result.resolve.return_value=root
            return result
        fake_lock=MagicMock();child=MagicMock();child.poll.side_effect=[None,None]
        with patch('pathlib.Path',side_effect=path), patch('builtins.open',return_value=fake_lock), \
             patch.dict(sys.modules,{'fcntl':types.SimpleNamespace(flock=MagicMock(),LOCK_EX=1,LOCK_UN=2)}), \
             patch('subprocess.Popen',return_value=child) as spawn, \
             patch('select.select',return_value=([sys.stdin],[],[])), \
             patch('os.read',return_value=b''), patch('signal.signal'), patch('signal.SIGHUP',1,create=True), patch('sys.stdin') as stdin, \
             contextlib.redirect_stdout(io.StringIO()):
            stdin.fileno.return_value=0
            exec(compile(follow.REMOTE,'remote','exec'),{})
        return spawn,child

    def test_owned_child_stops_on_ssh_eof(self):
        spawn,child=self.execute()
        self.assertNotIn('--no-camera-stream',spawn.call_args.args[0])  # follower keeps Link 2 Pro awake
        self.assertIn('--camera-follow',spawn.call_args.args[0])
        child.send_signal.assert_called_once()
        child.wait.assert_called_once()

    def test_reused_child_is_never_signalled(self):
        args=['python3','/home/unitree/groot_onboard_runtime/receive_mink_ik_udp.py',
              '--camera-follow','--pan-sign','1']
        spawn,child=self.execute(args)
        spawn.assert_not_called();child.send_signal.assert_not_called()

    def test_manual_keyboard_or_different_options_are_preserved(self):
        for args in [['python3','/home/unitree/link2_keyboard.py'],
                     ['python3','receive_mink_ik_udp.py','--camera-follow','--dry-run']]:
            with self.assertRaises(RuntimeError):self.execute(args)

    def test_ssh_shell_quoting_roundtrips_exact_script(self):
        command=follow.ssh_command('192.168.10.165')
        tokens=shlex.split(command[-1]);self.assertEqual(tokens[:3],['python3','-u','-c'])
        captured=[]
        exec(tokens[3],{'exec':captured.append})
        self.assertEqual(captured,[follow.REMOTE.encode()])
        self.assertIn('-T',command)
        with self.assertRaises(ValueError):follow.ssh_command('host; touch bad')

if __name__=='__main__':unittest.main()
