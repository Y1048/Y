import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import g1_camera_ssh as camera
import g1_ssh_login as login
import G1_CAMERA_LAUNCH as launcher

class CameraTests(unittest.TestCase):
    def test_low_bandwidth_remote_rate_without_reencoding(self):
        self.assertIn('frame_period_s = 0.5', camera.REMOTE)
        self.assertIn('frame_period_s-(time.monotonic()-start)', camera.REMOTE)
        self.assertNotIn('cv2', camera.REMOTE)

    def test_ssh_setup_and_check_never_use_wsl_or_robot(self):
        for flag in ('--setup', '--check-only'):
            with self.subTest(flag=flag), patch.object(sys, 'argv', ['camera', flag]), patch.object(launcher, 'camera_run', side_effect=AssertionError('WSL')), patch.object(camera, 'run', side_effect=AssertionError('Robot')), patch.object(camera, 'check_environment') as check:
                launcher.main()
                check.assert_called_once()

    def test_explicit_wsl_check_still_uses_legacy_path(self):
        with patch.object(sys, 'argv', ['camera','--transport','wsl','--check-only']), patch.object(launcher, 'camera_run') as run:
            launcher.main()
            run.assert_called_once_with('--check-only','auto')

    def test_valid_packet_roundtrip(self):
        jpeg=b'\xff\xd8data\xff\xd9'
        raw=camera.HEADER.pack(b'G1CM',1,1,123,len(jpeg))+jpeg
        self.assertEqual(raw,camera.read_packet(io.BytesIO(raw)))
    def test_bad_header_jpeg_and_truncation_rejected(self):
        for raw in [b'',camera.HEADER.pack(b'BAD!',1,1,0,4)+b'abcd',camera.HEADER.pack(b'G1CM',1,1,0,4)+b'abcd',camera.HEADER.pack(b'G1CM',1,1,0,5000000)]:
            with self.assertRaises(RuntimeError):camera.read_packet(io.BytesIO(raw))
    def test_remote_script_is_python36_compatible_and_read_only(self):
        import ast
        ast.parse(camera.REMOTE,feature_version=(3,6))
        self.assertIn('GetImageSample',camera.REMOTE)
        for token in ['LowCmd','SportClient','MotionSwitcher','ChannelPublisher']:
            self.assertNotIn(token,camera.REMOTE)
    def test_remote_receiver_free_recognized_unknown(self):
        expected='/home/unitree/audit'
        good={'cwd':expected,'args':['python3','-u','G1_INPUT_RECEIVE_AUDIT.py','receive','--print-hz','100']}
        with patch.object(login.subprocess,'run') as run:
            for rows,answer in [([],False),([good],True)]:
                run.return_value=subprocess.CompletedProcess([],0,json.dumps(rows))
                self.assertEqual(answer,login.remote_receiver_running('host',expected))
            for rows in [[dict(good,cwd='/other')],[good,good],[dict(good,args=['other'])]]:
                run.return_value=subprocess.CompletedProcess([],0,json.dumps(rows))
                with self.assertRaises(RuntimeError):login.remote_receiver_running('host',expected)
