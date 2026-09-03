from __future__ import annotations

import struct
import unittest

from g1_camera_tcp_bridge import (
    FRAME_HEADER,
    FRAME_MAGIC,
    FRAME_VERSION,
    BuildFramePacket,
)


class G1CameraTcpBridgeTest(unittest.TestCase):
    def test_frame_packet_preserves_header_and_jpeg(self):
        jpeg_payload = b"\xff\xd8camera-jpeg\xff\xd9"
        packet = BuildFramePacket(jpeg_payload, 17, 123456789)
        magic, version, sequence, timestamp_ns, payload_size = (
            FRAME_HEADER.unpack(packet[: FRAME_HEADER.size])
        )

        self.assertEqual(magic, FRAME_MAGIC)
        self.assertEqual(version, FRAME_VERSION)
        self.assertEqual(sequence, 17)
        self.assertEqual(timestamp_ns, 123456789)
        self.assertEqual(payload_size, len(jpeg_payload))
        self.assertEqual(packet[FRAME_HEADER.size :], jpeg_payload)

    def test_sequence_wraps_to_unsigned_32_bit(self):
        packet = BuildFramePacket(b"\xff\xd8x\xff\xd9", 0x1_0000_0003, 1)
        sequence = struct.unpack("!I", packet[8:12])[0]
        self.assertEqual(sequence, 3)

    def test_rejects_non_jpeg_payload(self):
        with self.assertRaises(ValueError):
            BuildFramePacket(b"not-a-jpeg", 0, 1)

    def test_rejects_negative_timestamp(self):
        with self.assertRaises(ValueError):
            BuildFramePacket(b"\xff\xd8x\xff\xd9", 0, -1)


if __name__ == "__main__":
    unittest.main()
