"""Remote lifetime script under mocks: no SSH, sockets or hardware."""
import base64
import contextlib
import io
import json
from pathlib import Path
import shlex
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import G1_CAMERA_FOLLOW_LAUNCH as follow

ROOT=Path(__file__).resolve().parents[2]

class FollowTests(unittest.TestCase):
    def test_unity_emits_independent_camera_pose_heartbeat(self):
        source=(ROOT/'Unity_G1_VR/Assets/G1Teleop/G1OmniBodyHeading.cs').read_text(encoding='utf-8')
        self.assertIn('public const int CameraPosePort = 55075;',source)
        self.assertIn('"g1.unity.quest.camera.v1"',source)
        self.assertIn('cameraReady = alignment != null',source)
        self.assertIn('IsCurrentHeadOrientationTracked()',source)
        self.assertIn('cameraPoseEndpoint',source)
        # Locomotion readiness remains separate; cameraReady must not require IsAligned.
        camera_block=source[source.index('bool cameraReady'):source.index('var cameraPacket')]
        self.assertNotIn('IsAligned',camera_block)

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
        udp=MagicMock()
        fake_socket=types.SimpleNamespace(AF_INET=2,SOCK_DGRAM=2,socket=MagicMock(return_value=udp))
        with patch('pathlib.Path',side_effect=path), patch('builtins.open',return_value=fake_lock), \
             patch.dict(sys.modules,{'fcntl':types.SimpleNamespace(flock=MagicMock(),LOCK_EX=1,LOCK_UN=2), 'socket':fake_socket}), \
             patch('subprocess.Popen',return_value=child) as spawn, \
             patch('select.select',return_value=([sys.stdin],[],[])), \
             patch('os.read',return_value=b''), patch('signal.signal'), patch('signal.SIGHUP',1,create=True), patch('sys.stdin') as stdin, \
             contextlib.redirect_stdout(io.StringIO()):
            stdin.fileno.return_value=0
            exec(compile(follow.REMOTE,'remote','exec'),{})
        return spawn,child

    def test_owned_child_stops_on_ssh_eof(self):
        spawn,child=self.execute()
        command=spawn.call_args.args[0]
        self.assertIn('--no-camera-stream',command)  # camera worker owns the stream
        self.assertIn('--camera-follow',command)
        self.assertEqual(command[command.index('--port')+1],'15104')
        self.assertEqual(command[command.index('--quest-port')+1],'15103')
        child.send_signal.assert_called_once()
        child.wait.assert_called_once()

    def test_reused_child_is_never_signalled(self):
        args=['python3','/home/unitree/groot_onboard_runtime/receive_mink_ik_udp.py',
              '--camera-follow','--pan-sign','1','--no-camera-stream',
              '--port','15104','--quest-port','15103']
        spawn,child=self.execute(args)
        spawn.assert_not_called();child.send_signal.assert_not_called()

    def test_non_camera_mink_receiver_can_coexist(self):
        args=['python3','/home/unitree/groot_onboard_runtime/receive_mink_ik_udp.py',
              '--port','5014']
        spawn,child=self.execute(args)
        self.assertIn('--camera-follow',spawn.call_args.args[0])
        child.send_signal.assert_called_once()

    def test_manual_keyboard_or_different_camera_options_are_preserved(self):
        for args in [['python3','/home/unitree/link2_keyboard.py'],
                     ['python3','receive_mink_ik_udp.py','--camera-follow','--dry-run']]:
            with self.assertRaises(RuntimeError):self.execute(args)

    def test_direct_ready_pose_becomes_fresh_camera_observation(self):
        raw=json.dumps(dict(schema=follow.DIRECT_SCHEMA,
            session='a'*32,sequence=7,ready=True,yaw_deg=-21.5,pitch_deg=13.25)).encode()
        packet=json.loads(follow.direct_to_observation(raw))
        omni=packet['payload']['omni']
        self.assertEqual(packet['session'],'a'*32)
        self.assertEqual(packet['sequence'],7)
        self.assertEqual(omni['status'],'FRESH_LIVE')
        self.assertTrue(omni['values']['calibrated'])
        self.assertEqual(omni['values']['unity_alignment_status'],'READY')
        self.assertEqual(omni['values']['unity_quest_yaw_deg'],-21.5)
        self.assertEqual(omni['values']['unity_quest_pitch_deg'],13.25)

    def test_direct_not_ready_pose_is_not_forwarded(self):
        raw=json.dumps(dict(schema=follow.DIRECT_SCHEMA,
            session='b'*32,sequence=1,ready=False,yaw_deg=0.,pitch_deg=0.)).encode()
        self.assertIsNone(follow.direct_to_observation(raw))

    def test_direct_pose_rejects_nonfinite_or_bad_session(self):
        for packet in [
            dict(schema=follow.DIRECT_SCHEMA,session='bad',sequence=1,ready=True,yaw_deg=0.,pitch_deg=0.),
            dict(schema=follow.DIRECT_SCHEMA,session='c'*32,sequence=1,ready=True,yaw_deg=float('nan'),pitch_deg=0.),
        ]:
            with self.assertRaises(ValueError):
                follow.direct_to_observation(json.dumps(packet).encode())

    def test_ssh_shell_quoting_roundtrips_exact_script(self):
        with patch.object(follow,'ssh_executable',return_value='ssh-test.exe'):
            command=follow.ssh_command('192.168.10.165')
        tokens=shlex.split(command[-1]);self.assertEqual(tokens[:3],['python3','-u','-c'])
        captured=[]
        exec(tokens[3],{'exec':captured.append})
        self.assertEqual(captured,[follow.REMOTE.encode()])
        self.assertIn('-T',command)
        with self.assertRaises(ValueError):follow.ssh_command('host; touch bad')

if __name__=='__main__':unittest.main()
