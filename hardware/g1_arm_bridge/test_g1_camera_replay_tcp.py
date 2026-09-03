from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from g1_camera_replay_tcp import (
    BuildReplayJpeg,
    ValidateArguments,
    WriteResult,
)
from g1_camera_tcp_bridge import BuildFramePacket, FRAME_HEADER, FRAME_MAGIC


class G1CameraReplayTcpTest(unittest.TestCase):
    def test_replay_jpeg_is_decodable_and_nonblank(self):
        jpeg_payload = BuildReplayJpeg(17, 1.25, width=320, height=240)

        self.assertTrue(jpeg_payload.startswith(b"\xff\xd8"))
        self.assertTrue(jpeg_payload.endswith(b"\xff\xd9"))
        with Image.open(io.BytesIO(jpeg_payload)) as image:
            self.assertEqual(image.size, (320, 240))
            self.assertEqual(image.mode, "RGB")
            extrema = image.getextrema()
            self.assertTrue(any(maximum > minimum for minimum, maximum in extrema))

    def test_replay_uses_exact_camera_packet_contract(self):
        jpeg_payload = BuildReplayJpeg(3, 0.5, width=320, height=240)
        packet = BuildFramePacket(jpeg_payload, 3, 99)
        magic, _version, sequence, timestamp_ns, payload_size = (
            FRAME_HEADER.unpack(packet[: FRAME_HEADER.size])
        )

        self.assertEqual(magic, FRAME_MAGIC)
        self.assertEqual(sequence, 3)
        self.assertEqual(timestamp_ns, 99)
        self.assertEqual(payload_size, len(jpeg_payload))
        self.assertEqual(packet[FRAME_HEADER.size :], jpeg_payload)

    def test_replay_rejects_non_loopback_output(self):
        args = argparse.Namespace(
            host="192.168.123.164",
            port=5011,
            fps=20.0,
            quality=82,
            duration=0.0,
            connect_timeout=1.0,
            reconnect_delay=1.0,
        )
        with self.assertRaises(SystemExit):
            ValidateArguments(args)

    def test_result_file_preserves_offline_safety_flags(self):
        result = {
            "schema": "g1.camera.offline_replay.result.v1",
            "passed": True,
            "robot_connected": False,
            "dds_created": False,
            "command_output_enabled": False,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            result_path = WriteResult(result, Path(temporary_directory))
            saved = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(saved, result)
        self.assertIn("camera_offline_replay_", result_path.name)


if __name__ == "__main__":
    unittest.main()
