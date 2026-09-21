"""Real loopback WebSocket recovery; ephemeral TCP only, no Omni/G1/UDP."""
import asyncio
import json
import socket
import threading
import time
import unittest

import websocket
from websockets.asyncio.server import serve

from hardware.g1_arm_bridge.g1_omni_velocity_gateway import LatestOmniReader


class LocalOmniServer:
    """Reserve a local ephemeral port before allowing the server to listen."""
    def __init__(self, handshake_delay=.3):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(('127.0.0.1', 0))
        self.port = self.socket.getsockname()[1]
        self.handshake_delay = handshake_delay
        self.ready = threading.Event()
        self.release_more = threading.Event()
        self.error = None
        self.loop = self.async_stop = None
        self.thread = None

    @property
    def url(self):
        return 'ws://127.0.0.1:%d' % self.port

    async def handshake(self, connection, request):
        await asyncio.sleep(self.handshake_delay)

    async def handler(self, connection):
        await connection.send(json.dumps(dict(movementXY=[.1, .2], armYaw=112.)))
        while not self.release_more.is_set():
            await asyncio.sleep(.005)
        for values, yaw in (([.2, .3], 113.), ([.3, .4], 114.)):
            await connection.send(json.dumps(dict(movementXY=values, armYaw=yaw)))
            await asyncio.sleep(.02)
        await connection.wait_closed()

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.async_stop = asyncio.Event()
        async with serve(self.handler, sock=self.socket, process_request=self.handshake,
                         ping_interval=None, close_timeout=.1):
            self.ready.set()
            await self.async_stop.wait()

    def _run(self):
        try:
            asyncio.run(self.run())
        except Exception as error:
            self.error = error
            self.ready.set()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(2):
            raise AssertionError('local WebSocket server startup timed out')
        if self.error is not None:
            raise AssertionError('local WebSocket server failed: %r' % self.error)

    def close(self):
        self.release_more.set()
        if self.loop is not None and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.async_stop.set)
        if self.thread is not None:
            self.thread.join(2)
            if self.thread.is_alive():
                raise AssertionError('local WebSocket server did not close')
        self.socket.close()


class OmniTransportRecoveryTests(unittest.TestCase):
    def wait_for(self, condition, timeout=3.):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if condition():
                return
            time.sleep(.005)
        self.fail('timed out waiting for local WebSocket condition')

    def close_reader(self, reader):
        started = time.perf_counter()
        reader.close()
        self.assertLess(time.perf_counter() - started, .7)
        self.assertFalse(reader.thread.is_alive())

    def test_delayed_handshake_and_silent_receive_polling_recover_without_fake_samples(self):
        server = LocalOmniServer(handshake_delay=.3)
        reader = None
        try:
            server.start()
            reader = LatestOmniReader(server.url, websocket)
            started = time.perf_counter()
            reader.thread.start()
            self.wait_for(lambda: reader.snapshot()[1] == 1)
            self.assertGreaterEqual(time.perf_counter() - started, .28)
            first, count, error = reader.snapshot()
            self.assertEqual(count, 1)
            self.assertEqual(first.sequence, 0)
            self.assertEqual(first.values, (.1, .2, 112.))
            self.assertIsNone(error)
            self.wait_for(lambda: reader.transport_status()['receive_timeouts'] >= 2)
            silent, count, error = reader.snapshot()
            self.assertEqual(count, 1)
            self.assertEqual(silent, first)  # Polling timeout never refreshes source time.
            self.assertIsNone(error)
            server.release_more.set()
            self.wait_for(lambda: reader.snapshot()[1] == 3)
            last, count, error = reader.snapshot()
            self.assertEqual((count, last.sequence), (3, 2))
            self.assertEqual(last.values, (.3, .4, 114.))
            self.assertGreater(last.received_monotonic_s, first.received_monotonic_s)
            self.assertEqual(reader.transport_status()['connect_attempts'], 1)
            self.assertIsNone(error)
            self.close_reader(reader)
            self.assertIsNone(server.error)
        finally:
            if reader is not None:
                reader.close()
            server.close()

    def test_reader_started_before_listener_recovers_when_ephemeral_server_starts(self):
        server = LocalOmniServer(handshake_delay=0.)
        reader = LatestOmniReader(server.url, websocket)
        try:
            reader.thread.start()  # The reserved port is intentionally not listening yet.
            self.wait_for(lambda: reader.transport_status()['status'] == 'RETRY_WAIT')
            self.assertEqual(reader.snapshot(), (None, 0, None))
            self.assertIsNotNone(reader.transport_status()['last_transport_error'])
            server.release_more.set()
            server.start()
            self.wait_for(lambda: reader.snapshot()[1] == 3, timeout=4.)
            latest, count, error = reader.snapshot()
            self.assertEqual((count, latest.sequence), (3, 2))
            self.assertEqual(latest.values, (.3, .4, 114.))
            self.assertGreaterEqual(reader.transport_status()['connect_attempts'], 2)
            self.assertIsNone(error)
            self.close_reader(reader)
            self.assertIsNone(server.error)
        finally:
            reader.close()
            server.close()


if __name__ == '__main__':
    unittest.main()
