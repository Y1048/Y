"""Offline transport/codec tests. No SSH, SDK, G1, or Unity process is started."""
import io
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import g1_camera_h264 as h
import g1_camera_ssh as legacy
import G1_CAMERA_LAUNCH as launch


class H264Tests(unittest.TestCase):
    def test_remote_source_cannot_publish_motor_commands(self):
        source = h.remote_source(3)
        compile(source, '<remote>', 'exec')
        for forbidden in ('unitree_sdk', 'ChannelPublisher', 'LowCmd', '15100',
                          '55070', 'pan_absolute', 'tilt_absolute'):
            self.assertNotIn(forbidden, source)
        self.assertIn("ctl(restore,'--set-parm='+fps[1])", source)
        self.assertIn('Camera is already owned', source)
        self.assertIn('Camera capture timeout', source)

    def test_probe_duration_is_bounded_before_ssh(self):
        for value in (-1, 301, float('inf'), float('nan')):
            with self.assertRaises(ValueError):h.remote_source(value)

    def test_chunk_roundtrip_and_short_reads(self):
        class Short(io.BytesIO):
            def read(self,n):return super().read(min(n,3))
        raw=b'\0\0\0\1\x65abc'
        packet=h.HEADER.pack(b'G1H4',1,4,123,len(raw))+raw
        self.assertEqual(h.read_chunk(Short(packet)),(4,123,raw))
        self.assertIsNone(h.read_chunk(io.BytesIO()))

    def test_bad_header_and_truncation_rejected(self):
        for magic,version,size in ((b'NOPE',1,2),(b'G1H4',2,2),(b'G1H4',1,0),
                                   (b'G1H4',1,65537)):
            with self.assertRaises(RuntimeError):
                h.read_chunk(io.BytesIO(h.HEADER.pack(magic,version,0,1,size)))
        for raw in (b'G1',h.HEADER.pack(b'G1H4',1,0,1,10)+b'a'):
            with self.assertRaisesRegex(RuntimeError,'Truncated'):
                h.read_chunk(io.BytesIO(raw))

    def test_only_latest_decoded_frame_retained_and_stale_discarded(self):
        slot=h.LatestFrame();slot.put((1.,b'a'));slot.put((1.1,b'b'))
        self.assertEqual(slot.overwritten,1)
        self.assertTrue(slot.ready.is_set())
        self.assertEqual(slot.take(1.2),(1.1,b'b'))
        self.assertFalse(slot.ready.is_set())
        self.assertIsNone(slot.take(1.2))
        slot.put((1.,b'old'));self.assertIsNone(slot.take(2.))

    def test_encoded_chunk_gap_fails_instead_of_dropping_interframes(self):
        raw=b'\0\0\1\x09'
        stream=io.BytesIO(b''.join(h.HEADER.pack(b'G1H4',1,i,1,len(raw))+raw for i in (0,2)))
        metrics=dict(wire_bytes=0,decode_encode_s=0,frames=0)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(h,'Decoder') as decoder:
            decoder.return_value.feed.return_value=[]
            done=threading.Event()
            h.receive(stream,h.LatestFrame(),done,metrics,Path(tmp)/'frames.jsonl')
            self.assertTrue(done.is_set())
            self.assertIn('sequence gap',metrics['error'])

    def test_decoder_setup_failure_unblocks_receiver(self):
        metrics={};done=threading.Event()
        with mock.patch.object(h,'Decoder',side_effect=RuntimeError('codec missing')):
            h.receive(io.BytesIO(),h.LatestFrame(),done,metrics,Path('unused'))
        self.assertTrue(done.is_set());self.assertIn('codec missing',metrics['error'])

    def test_real_generated_h264_decodes_to_unchanged_unity_protocol(self):
        import av
        import numpy as np
        enc=av.CodecContext.create('libx264','w')
        enc.width=1920;enc.height=1080;enc.pix_fmt='yuv420p'
        enc.time_base=Fraction(1,30);enc.framerate=Fraction(30,1)
        enc.options={'preset':'ultrafast','tune':'zerolatency','crf':'24'}
        data=bytearray()
        for i in range(6):
            image=np.zeros((1080,1920,3),dtype=np.uint8);image[:,:,1]=60+i*20
            f=av.VideoFrame.from_ndarray(image,format='rgb24');f.pts=i
            for packet in enc.encode(f):data.extend(bytes(packet))
        for packet in enc.encode(None):data.extend(bytes(packet))
        decoder=h.Decoder();converted=[]
        for n in range(0,len(data),101):converted.extend(decoder.feed(data[n:n+101]))
        self.assertGreaterEqual(len(converted),4)
        for seq,jpeg in converted:
            packet=h.HEADER.pack(b'G1CM',1,seq,123,len(jpeg))+jpeg
            self.assertEqual(legacy.read_packet(io.BytesIO(packet)),packet)
            image=av.CodecContext.create('mjpeg','r').decode(av.Packet(jpeg))[0]
            self.assertEqual((image.width,image.height),(1920,1080))

    def test_mjpeg_fallback_dispatch_preserved(self):
        with mock.patch.object(legacy,'run_mjpeg') as run:
            legacy.run('example',codec='mjpeg');run.assert_called_once_with('example')
        with self.assertRaises(ValueError):legacy.run('example',codec='mjpeg',probe_seconds=1)

    def test_camera_cli_default_and_explicit_legacy(self):
        with mock.patch.object(legacy,'run') as run, mock.patch.object(legacy,'check_environment'), \
                mock.patch.object(launch,'select_robot_host',return_value='example'):
            launch.main(['--robot-host','example'])
            run.assert_called_with('example',codec='h264',probe_seconds=0)
            launch.main(['--robot-host','example','--camera-codec','mjpeg'])
            run.assert_called_with('example',codec='mjpeg',probe_seconds=0)


if __name__=='__main__':unittest.main()
