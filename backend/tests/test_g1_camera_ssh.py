"""Insta360 camera transport tests; no SSH or camera hardware."""
import io
import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import g1_camera_ssh as camera

class CameraTransportTests(unittest.TestCase):
    def test_remote_source_is_insta360_mjpeg(self):
        self.assertIn('Insta360_Link_2_Pro-video-index0', camera.REMOTE)
        self.assertIn('pixelformat=MJPG', camera.REMOTE)
        self.assertIn('width=1920,height=1080', camera.REMOTE)
        self.assertIn("'--set-parm=30'", camera.REMOTE)
        self.assertNotIn('VideoClient', camera.REMOTE)
        self.assertNotIn('/dev/video6', camera.REMOTE)

    def test_read_packet_preserves_jpeg(self):
        jpeg = b'\xff\xd8test-jpeg\xff\xd9'
        header = camera.HEADER.pack(b'G1CM', 1, 7, 123456789, len(jpeg))
        packet = camera.read_packet(io.BytesIO(header + jpeg))
        self.assertEqual(packet, header + jpeg)
        self.assertEqual(struct.unpack('!4sIIQI', packet[:camera.HEADER.size])[2], 7)

    def test_invalid_jpeg_is_rejected(self):
        payload = b'not-jpeg'
        header = camera.HEADER.pack(b'G1CM', 1, 0, 0, len(payload))
        with self.assertRaisesRegex(RuntimeError, 'Invalid JPEG'):
            camera.read_packet(io.BytesIO(header + payload))

if __name__ == '__main__':
    unittest.main()
