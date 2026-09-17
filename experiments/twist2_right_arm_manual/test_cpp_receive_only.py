"""Windows transport integration test; loopback only, no robot runtime."""
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import unittest


class ReceiveOnlyTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows transport probe")
    def test_exact_datagrams(self):
        executable = Path(__file__).resolve().parents[2] / "logs/test_results/twist2_receive_only.exe"
        self.assertTrue(executable.is_file(), "Build receive_only.cpp first")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packets.bin"
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            process = subprocess.Popen([str(executable), str(port), "1", str(output)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True)
            try:
                self.assertTrue(process.stdout.readline().startswith("READY"))
                payloads = [b'{"sequence":1}', b'{"sequence":2,"active":false}', b'bad json', b'']
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    for payload in payloads:
                        sender.sendto(payload, ("127.0.0.1", port))
                process.communicate(timeout=4)
                self.assertEqual(process.returncode, 0)
                expected = b''.join(struct.pack('!I', len(p)) + p for p in payloads)
                self.assertEqual(output.read_bytes(), expected)
                # Existing captures must not be overwritten.
                retry = subprocess.run([str(executable), str(port), "1", str(output)], timeout=3)
                self.assertEqual(retry.returncode, 2)
                self.assertEqual(output.read_bytes(), expected)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
