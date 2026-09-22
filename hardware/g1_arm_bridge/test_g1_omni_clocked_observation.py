"""Generated WS fixtures for opt-in scheduling; no Omni/G1 network connection."""
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import g1_omni_velocity_gateway as gateway


class CaptureTap:
    def __init__(self):
        self.samples = []
        self.closed = False

    def publish(self, values, raw_time):
        self.samples.append((dict(values), raw_time, time.perf_counter()))

    def close(self):
        self.closed = True


class SyntheticTimeout(Exception):
    pass


class BurstyConnection:
    """Four generated samples per 1/30 s batch, equivalent to 120 raw samples/s."""
    def __init__(self):
        self.started = time.perf_counter()
        self.index = 0
        self.closed = False

    def recv(self):
        batch = self.index // 4
        deadline = self.started + batch / 30.
        time.sleep(max(0., deadline - time.perf_counter()))
        moving = self.index >= 32
        yaw = 110. + max(0, self.index - 32) * .5
        theta = math.radians((yaw - 110.) + 120.)
        movement = ([.35 * math.sin(theta) + .6 * math.cos(theta),
                     .35 * math.cos(theta) - .6 * math.sin(theta)]
                    if moving else [0., 0.])
        raw = json.dumps(dict(fixture_sequence=self.index,
                             movementXY=movement, armYaw=yaw))
        self.index += 1
        return raw

    def close(self, timeout=0):
        self.closed = True

    def settimeout(self, timeout):
        self.receive_timeout = timeout


class ScriptedConnection:
    def __init__(self, actions):
        self.actions = list(actions)
        self.closed = False
        self.receive_timeout = None

    def settimeout(self, timeout):
        self.receive_timeout = timeout

    def recv(self):
        time.sleep(.005)
        if not self.actions:
            raise SyntheticTimeout()
        action = self.actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return action() if callable(action) else action

    def close(self, timeout=0):
        self.closed = True


class ClockedOmniObservationTests(unittest.TestCase):
    def processor(self):
        mapper = gateway.OmniVelocityMapper(gateway.OmniVelocityConfig(
            calibration_s=.1, yaw_deadzone_deg_s=0., yaw_output_deadzone_rad_s=0.,
            yaw_filter_alpha=1.))
        return gateway.ClockedOmniProcessor(mapper, 60., 0.)

    def sample(self, sequence, stamp, yaw=110.):
        raw = json.dumps(dict(movementXY=[0., 0.], armYaw=yaw))
        return gateway.ReceivedOmniSample(sequence, stamp, (0., 0., yaw), raw)

    def test_original_sample_time_drives_yaw_and_repeats_do_not_publish(self):
        processor = self.processor()
        processor.process(self.sample(0, 0.), 0, 10., 0)
        processor.process(self.sample(1, .1), 6, 10.1, 0)
        moving = self.sample(2, .2, 116.)
        values = processor.process(moving, 12, 10.2, 0)
        self.assertAlmostEqual(values['omni_yaw_rate_deg_s'], 60.)
        self.assertAlmostEqual(values['yaw_rate'], math.radians(60.))
        self.assertEqual(values['raw_sample_sequence'], 2)
        self.assertEqual(values['processed_monotonic_s'], 10.2)
        for tick in range(13, 100):
            self.assertIsNone(processor.process(moving, tick, 10. + tick / 60., 0))
        self.assertEqual(processor.processed_samples, 3)
        self.assertEqual(processor.mapper.previous_time_s, .2)

    def test_latest_only_sampling_exposes_skipped_raw_sequences(self):
        processor = self.processor()
        processor.process(self.sample(0, 0.), 0, 0., 0)
        values = processor.process(self.sample(4, .1), 6, .105, 2)
        self.assertEqual(values['raw_samples_skipped'], 3)
        self.assertEqual(values['process_tick'], 6)
        self.assertEqual(values['processing_deadlines_missed'], 2)
        self.assertIsNone(processor.process(self.sample(2, .05), 7, .12, 2))

    def test_scheduler_skips_deadlines_without_catchup(self):
        period = 1. / 60.
        deadline, missed = gateway.next_processing_deadline(1., 1.002, period)
        self.assertAlmostEqual(deadline, 1. + period)
        self.assertEqual(missed, 0)
        deadline, missed = gateway.next_processing_deadline(1., 1.051, period)
        self.assertAlmostEqual(deadline, 1.051 + period)
        self.assertGreaterEqual(missed, 3)
        self.assertGreater(deadline, 1.051)

    def test_invalid_or_unauthorized_process_rate_rejected_before_socket(self):
        cases = [(['--dry-run', '--process-hz', value], {'G1_OBSERVATION_TAP': '1'})
                 for value in ('nan', 'inf', '-1', '9', '121')]
        cases += [(['--dry-run', '--process-hz', '60'], {}),
                  (['--process-hz', '60'], {'G1_OBSERVATION_TAP': '1'})]
        for arguments, environment in cases:
            with self.subTest(arguments=arguments, environment=environment), \
                    patch.dict(gateway.os.environ, environment, clear=True), \
                    patch('sys.argv', ['gateway', *arguments]), \
                    patch.object(gateway.socket, 'socket') as factory:
                with self.assertRaises(ValueError):
                    gateway.main()
                factory.assert_not_called()

    def test_60_hz_processing_of_bursty_120_hz_generated_ws(self):
        connection = BurstyConnection()
        websocket = SimpleNamespace(create_connection=lambda *a, **k: connection,
                                    WebSocketTimeoutException=SyntheticTimeout)
        tap = CaptureTap()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'generated_processed_samples.csv'
            args = SimpleNamespace(process_hz=60., calibration_seconds=.1, start_delay_seconds=0.,
                                   duration_seconds=.75, max_samples=0, csv=output,
                                   omni_url='synthetic://no-network')
            with contextlib.redirect_stdout(io.StringIO()), \
                    patch.object(gateway, 'make_listener') as discovery, \
                    patch.object(gateway.socket, 'socket') as command_socket:
                result = gateway.run_clocked_observation(args, tap, websocket)
            discovery.assert_not_called()
            command_socket.assert_not_called()
            self.assertTrue(result['reader_thread_stopped'])
            self.assertTrue(connection.closed)
            self.assertTrue(tap.closed)
            self.assertGreaterEqual(result['process_ticks'], 30)
            self.assertLessEqual(result['process_ticks'], 48)
            self.assertGreater(result['raw_samples_received'], result['process_ticks'])
            self.assertGreater(result['raw_samples_skipped'], 10)
            self.assertLessEqual(len(tap.samples), result['process_ticks'])
            raw_sequences = [v['raw_sample_sequence'] for v, _, _ in tap.samples]
            self.assertEqual(raw_sequences, sorted(set(raw_sequences)))
            self.assertTrue(any(v['vx'] > .1 and v['vy'] < -.1 for v, _, _ in tap.samples))
            with output.open(encoding='utf-8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(tap.samples))
            for row, (values, stamp, _) in zip(rows, tap.samples):
                self.assertAlmostEqual(float(row['receive_monotonic_s']), stamp, places=8)
                self.assertEqual(int(row['sample_sequence']), values['raw_sample_sequence'])
                self.assertEqual(json.loads(row['raw_json_text'])['fixture_sequence'], values['raw_sample_sequence'])
                self.assertEqual(row['csv_row_kind'], 'processed_new_raw_sample')
                self.assertEqual(float(row['processing_hz']), 60.)
                self.assertGreaterEqual(values['processed_monotonic_s'], stamp)

    def test_no_samples_duration_expires_and_reader_closes(self):
        class SilentConnection:
            closed = False

            def recv(self):
                time.sleep(.02)
                raise SyntheticTimeout()

            def close(self, timeout=0):
                self.closed = True

            def settimeout(self, timeout):
                self.receive_timeout = timeout

        connection = SilentConnection()
        websocket = SimpleNamespace(create_connection=lambda *a, **k: connection,
                                    WebSocketTimeoutException=SyntheticTimeout)
        args = SimpleNamespace(process_hz=60., calibration_seconds=.1, start_delay_seconds=0.,
                               duration_seconds=.15, max_samples=0, csv=None,
                               omni_url='synthetic://no-network')
        tap = CaptureTap()
        started = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            result = gateway.run_clocked_observation(args, tap, websocket)
        self.assertLess(time.perf_counter() - started, .7)
        self.assertGreaterEqual(result['process_ticks'], 6)
        self.assertEqual(result['processed_samples'], 0)
        self.assertEqual(tap.samples, [])
        self.assertTrue(result['reader_thread_stopped'])
        self.assertTrue(connection.closed)

    def wait_for(self, predicate, timeout=1.):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if predicate():
                return
            time.sleep(.002)
        self.fail('synthetic reader condition did not become true')

    def raw(self, yaw=110.):
        return json.dumps(dict(movementXY=[.1, .2], armYaw=yaw))

    def test_builtin_startup_timeout_retries_then_uses_separate_receive_timeout(self):
        connection = ScriptedConnection([self.raw()])
        calls = []

        def connect(url, timeout):
            calls.append((url, timeout))
            if len(calls) == 1:
                raise TimeoutError('synthetic handshake timeout')
            return connection

        websocket = SimpleNamespace(create_connection=connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'RECONNECT_DELAY_S', .01):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            try:
                self.wait_for(lambda: reader.snapshot()[1] == 1)
                sample, received, error = reader.snapshot()
                self.assertIsNone(error)
                self.assertEqual((sample.sequence, received), (0, 1))
                self.assertEqual(len(calls), 2)
                self.assertTrue(all(timeout == 2. for _, timeout in calls))
                self.assertEqual(connection.receive_timeout, .1)
                self.assertTrue(reader.thread.is_alive())
                status = reader.transport_status()
                self.assertEqual(status['connect_attempts'], 2)
                self.assertEqual(status['reconnect_count'], 0)
                self.assertIn(status['status'], ('RECEIVING', 'WAIT_SAMPLE'))
                self.assertIn('synthetic handshake timeout', status['last_transport_error'])
            finally:
                reader.close()
        self.assertTrue(connection.closed)
        self.assertFalse(reader.thread.is_alive())

    def test_builtin_receive_timeout_is_idle_without_reconnect(self):
        connection = ScriptedConnection([TimeoutError('idle receive'), self.raw()])
        calls = []

        def connect(*args, **kwargs):
            calls.append(1)
            return connection

        websocket = SimpleNamespace(create_connection=connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
        reader.thread.start()
        try:
            self.wait_for(lambda: reader.snapshot()[1] == 1)
            self.assertEqual(len(calls), 1)
            self.assertIsNone(reader.snapshot()[2])
            self.assertTrue(reader.thread.is_alive())
            self.assertGreaterEqual(reader.transport_status()['receive_timeouts'], 1)
        finally:
            reader.close()
        self.assertTrue(connection.closed)

    def test_websocket_handshake_timeout_and_refusal_both_retry(self):
        connection = ScriptedConnection([self.raw()])
        failures = [SyntheticTimeout('synthetic WS handshake timeout'),
                    ConnectionRefusedError('synthetic Omni not started')]
        calls = []

        def connect(*args, **kwargs):
            calls.append(1)
            if failures:
                raise failures.pop(0)
            return connection

        websocket = SimpleNamespace(create_connection=connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'RECONNECT_DELAY_S', .01):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            try:
                self.wait_for(lambda: reader.snapshot()[1] == 1)
                self.assertIsNone(reader.snapshot()[2])
                self.assertEqual(len(calls), 3)
                status = reader.transport_status()
                self.assertEqual(status['connect_attempts'], 3)
                self.assertEqual(status['reconnect_count'], 0)
                self.assertIn('Omni not started', status['last_transport_error'])
            finally:
                reader.close()
        self.assertTrue(connection.closed)

    def test_disconnect_reconnect_keeps_raw_sequence_and_never_republishes_stale_sample(self):
        release_disconnect = threading.Event()
        release_reconnect = threading.Event()

        def disconnect_after_first_observation():
            release_disconnect.wait(.8)
            return ''

        first = ScriptedConnection([self.raw(), disconnect_after_first_observation])
        second = ScriptedConnection([self.raw(111.)])
        calls = []

        def connect(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return first
            release_reconnect.wait(.8)
            return second

        websocket = SimpleNamespace(create_connection=connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'RECONNECT_DELAY_S', .01):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            try:
                self.wait_for(lambda: reader.snapshot()[1] == 1)
                first_sample = reader.snapshot()[0]
                processor = self.processor()
                self.assertIsNotNone(processor.process(first_sample, 0, time.monotonic(), 0))
                release_disconnect.set()
                self.wait_for(lambda: len(calls) == 2)
                for tick in range(1, 8):
                    held_sample, received, error = reader.snapshot()
                    self.assertIsNone(error)
                    self.assertEqual(received, 1)
                    self.assertIs(held_sample, first_sample)
                    self.assertEqual(held_sample.received_monotonic_s, first_sample.received_monotonic_s)
                    self.assertIsNone(processor.process(held_sample, tick, time.monotonic(), 0))
                release_reconnect.set()
                self.wait_for(lambda: reader.snapshot()[1] == 2)
                second_sample, received, error = reader.snapshot()
                self.assertEqual((second_sample.sequence, received), (1, 2))
                self.assertGreaterEqual(second_sample.received_monotonic_s, first_sample.received_monotonic_s)
                self.assertIsNotNone(processor.process(second_sample, 8, time.monotonic(), 0))
                self.assertEqual(processor.processed_samples, 2)
                self.assertIsNone(error)
                self.assertEqual(len(calls), 2)
                status = reader.transport_status()
                self.assertEqual(status['connect_attempts'], 2)
                self.assertEqual(status['reconnect_count'], 1)
            finally:
                release_disconnect.set()
                release_reconnect.set()
                reader.close()
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)

    def test_malformed_samples_remain_fatal_and_are_not_retried(self):
        for raw in ('{', '{"movementXY":[0,0],"armYaw":"invalid"}'):
            with self.subTest(raw=raw):
                connection = ScriptedConnection([raw])
                calls = []

                def connect(*args, **kwargs):
                    calls.append(1)
                    return connection

                websocket = SimpleNamespace(create_connection=connect,
                                            WebSocketTimeoutException=SyntheticTimeout)
                reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
                reader.thread.start()
                try:
                    self.wait_for(lambda: reader.snapshot()[2] is not None)
                    reader.thread.join(timeout=.5)
                    self.assertFalse(reader.thread.is_alive())
                    self.assertEqual(reader.snapshot()[1], 0)
                    self.assertIsNone(reader.snapshot()[0])
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(reader.transport_status()['status'], 'ERROR')
                finally:
                    reader.close()
                self.assertTrue(connection.closed)

    def test_shutdown_interrupts_retry_backoff(self):
        attempted = threading.Event()
        calls = []

        def unavailable(*args, **kwargs):
            calls.append(1)
            attempted.set()
            raise ConnectionRefusedError('synthetic no listener')

        websocket = SimpleNamespace(create_connection=unavailable,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'RECONNECT_DELAY_S', 5.):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            self.assertTrue(attempted.wait(.5))
            started = time.perf_counter()
            reader.close()
        self.assertLess(time.perf_counter() - started, .3)
        self.assertFalse(reader.thread.is_alive())
        self.assertEqual(len(calls), 1)

    def test_shutdown_during_bounded_inflight_connect_does_not_retry(self):
        connecting = threading.Event()
        calls = []

        def slow_connect(url, timeout):
            calls.append(timeout)
            connecting.set()
            time.sleep(timeout)
            raise TimeoutError('synthetic bounded handshake timeout')

        websocket = SimpleNamespace(create_connection=slow_connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'CONNECT_TIMEOUT_S', .05):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            self.assertTrue(connecting.wait(.5))
            started = time.perf_counter()
            reader.close()
        self.assertLess(time.perf_counter() - started, .3)
        self.assertFalse(reader.thread.is_alive())
        self.assertEqual(calls, [.05])
        self.assertEqual(reader.snapshot()[1], 0)

    def test_late_successful_connection_is_closed_after_shutdown_without_reading(self):
        connecting = threading.Event()
        connection = ScriptedConnection([self.raw()])

        def slow_connect(url, timeout):
            connecting.set()
            time.sleep(timeout)
            return connection

        websocket = SimpleNamespace(create_connection=slow_connect,
                                    WebSocketTimeoutException=SyntheticTimeout)
        with patch.object(gateway.LatestOmniReader, 'CONNECT_TIMEOUT_S', .05):
            reader = gateway.LatestOmniReader('synthetic://no-network', websocket)
            reader.thread.start()
            self.assertTrue(connecting.wait(.5))
            reader.close()
        self.assertFalse(reader.thread.is_alive())
        self.assertTrue(connection.closed)
        self.assertEqual(reader.snapshot()[1], 0)
        self.assertEqual(len(connection.actions), 1)


if __name__ == '__main__':
    unittest.main()
