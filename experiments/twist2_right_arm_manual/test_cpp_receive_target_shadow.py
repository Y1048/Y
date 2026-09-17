"""Windows loopback synthetic-input tests. Never contact G1/WSL/DDS."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest

from test_cpp_upper_target import BASELINE, Packet, ROOT
from replay_cpp_receiver_log import Replay

EXE = ROOT / 'logs/test_results/receive_target_shadow.exe'


def ReadRows(path):
    if not path.exists():
        return []
    # The receiver may still be writing the last line when polled.
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    return [json.loads(line) for line in lines if line.endswith('\n')]


@unittest.skipUnless(os.name == 'nt', 'Windows Winsock shadow')
class ReceiveTargetShadowTests(unittest.TestCase):
    @contextmanager
    def Receiver(self, *, capacity=64, duration=2, port=None, changes=None,
                 existing_output=False, expect_ready=True, first_active=False):
        with tempfile.TemporaryDirectory(prefix='cpp_shadow_test_', dir=ROOT / 'logs/test_results') as directory:
            folder = Path(directory)
            config = dict(schema='g1.twist2.cpp_receive_shadow.v1',
                          baseline_source='explicit_simulation_baseline',
                          baseline=BASELINE, maximum_delta_rad=.2, queue_capacity=capacity)
            if first_active:
                config['baseline_source'] = 'first_active_mink_simulation_not_g1'
                del config['baseline']
            config.update(changes or {})
            config_path = folder / 'config.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')
            output = folder / 'ticks.jsonl'
            if existing_output:
                output.write_text('preserve existing log', encoding='utf-8')
            if port is None:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
                    reservation.bind(('127.0.0.1', 0))
                    port = reservation.getsockname()[1]
            stdout_path = folder / 'stdout.txt'
            with stdout_path.open('w') as stdout, (folder / 'stderr.txt').open('w') as stderr:
                process = subprocess.Popen([str(EXE), str(port), str(duration),
                                            str(config_path), str(output)], stdout=stdout, stderr=stderr)
                try:
                    if expect_ready:
                        deadline = time.monotonic()+5
                        while not stdout_path.read_text().startswith('READY'):
                            self.assertIsNone(process.poll(), (folder / 'stderr.txt').read_text())
                            self.assertLess(time.monotonic(), deadline, 'receiver readiness timeout')
                            time.sleep(.005)
                    yield process, output, port
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=3)

    def WaitRows(self, path, predicate):
        deadline = time.monotonic()+3
        while True:
            rows = ReadRows(path)
            if predicate(rows):
                return rows
            self.assertLess(time.monotonic(), deadline, 'expected shadow state not observed')
            time.sleep(.005)

    def CheckCandidates(self, rows):
        previous = BASELINE
        previous_time = 0
        latched = None
        for row in rows:
            if 'q' not in row:
                continue
            self.assertEqual(row['q'][:22], BASELINE[:22])
            self.assertFalse(row['hardware_output_authorized'])
            self.assertFalse(row['publisher_created'])
            if row['mode'] != 'active':
                self.assertEqual(row['q'], previous)
            else:
                bound = .08*min(row['now_s']-previous_time, .02)+1e-12
                self.assertLessEqual(max(abs(a-b) for a, b in zip(row['q'], previous)), bound)
                goal = json.loads(Packet())['right_arm']['joints']
                for old, new, target in zip(previous[22:], row['q'][22:], goal):
                    self.assertTrue(min(old, target) <= new <= max(old, target))
            if latched is not None:
                self.assertEqual(row['mode'], 'stopped')
                self.assertEqual(row['reason'], latched)
            if row['mode'] == 'stopped':
                latched = row['reason']
            previous, previous_time = row['q'], row['now_s']

    def test_idle_active_release_and_no_outgoing_datagram(self):
        with self.Receiver() as (process, output, port), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            # Silence before first engage must not trigger the active watchdog.
            self.WaitRows(output, lambda rows: any(row.get('now_s', 0) > .3 for row in rows))
            sender.sendto(Packet().encode(), ('127.0.0.1', port))
            self.WaitRows(output, lambda rows: any(row.get('active_ticks', 0) >= 1 for row in rows))
            sender.settimeout(.03)
            with self.assertRaises(socket.timeout):
                sender.recvfrom(65536)
            sender.sendto(Packet(2).encode(), ('127.0.0.1', port))
            self.WaitRows(output, lambda rows: any(row.get('active_ticks', 0) >= 2 for row in rows))
            sender.sendto(Packet(3, input_command_mode='pinch_disengaged').encode(), ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 0)
            rows = ReadRows(output)
            self.assertEqual(rows[-1]['event'], 'final')
            self.assertEqual(rows[-1]['reason'], 'input_disengaged')
            self.assertGreaterEqual(rows[-1]['active_ticks'], 2)
            self.assertTrue(Replay(output)["passed"])
            self.CheckCandidates(rows)

    def test_silence_after_active_times_out_and_holds(self):
        with self.Receiver() as (process, output, port), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(Packet().encode(), ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 2)
            rows = ReadRows(output)
            self.assertEqual(rows[-1]['reason'], 'receiver_timeout')
            self.assertEqual(rows[-1]['active_ticks'], 1)
            self.assertTrue(Replay(output)["passed"])
            self.CheckCandidates(rows)

    def test_invalid_empty_stale_and_oversized_datagrams_stop(self):
        for payload, reason in [(b'bad', 'parse_error'), (b'\xff\x00\xfe', 'parse_error'), (b'', 'parse_error'),
                                (Packet(input_packet_age_s=.251).encode(), 'source_timeout'),
                                (b'x'*16385, 'datagram_too_large'),
                                (b'x'*20000, 'datagram_too_large')]:
            with self.subTest(reason=reason, size=len(payload)), self.Receiver() as (process, output, port):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                    sender.sendto(payload, ('127.0.0.1', port))
                self.assertEqual(process.wait(timeout=3), 2)
                rows = ReadRows(output)
                self.assertIn(reason, rows[-1]['reason'])
                self.assertEqual(next(row for row in rows if row['event'] == 'packet')['payload_hex'], payload.hex())
                self.assertEqual(rows[-1]['active_ticks'], 0)
                self.assertTrue(Replay(output)["passed"])
                self.CheckCandidates(rows)

    def test_small_queue_burst_overflow(self):
        payloads = [Packet(i).encode() for i in range(1, 201)]
        with self.Receiver(capacity=1) as (process, output, port):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                for payload in payloads:
                    sender.sendto(payload, ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 2)
            rows = ReadRows(output)
            self.assertEqual(rows[-1]['reason'], 'queue_overflow')
            self.assertEqual(rows[-1]['queue_peak'], 1)
            self.assertTrue(Replay(output)["passed"])
            self.CheckCandidates(rows)

    def test_existing_output_and_port_conflict(self):
        with self.Receiver(existing_output=True, expect_ready=False) as (process, output, _):
            self.assertEqual(process.wait(timeout=3), 2)
            self.assertEqual(output.read_text(), 'preserve existing log')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as owner:
            owner.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            owner.bind(('127.0.0.1', 0))
            with self.Receiver(port=owner.getsockname()[1], expect_ready=False) as (process, output, _):
                self.assertEqual(process.wait(timeout=3), 2)
                self.assertFalse(output.exists())

    def test_invalid_configuration_before_socket_or_log(self):
        for changes in [dict(queue_capacity=65), dict(queue_capacity=1.5),
                        dict(baseline=[0]*28), dict(baseline_source='measured_g1'),
                        dict(maximum_delta_rad=0)]:
            with self.subTest(changes=changes), self.Receiver(changes=changes, expect_ready=False) as (process, output, _):
                self.assertEqual(process.wait(timeout=3), 2)
                self.assertFalse(output.exists())

    def test_no_input_has_bounded_duration(self):
        with self.Receiver(duration=1) as (process, output, _):
            self.assertEqual(process.wait(timeout=3), 2)
            rows = ReadRows(output)
            self.assertEqual(rows[-1]['reason'], 'duration_limit')
            self.assertEqual(rows[-1]['packets'], 0)
            self.assertEqual(rows[-1]['active_ticks'], 0)
            self.assertTrue(Replay(output)["passed"])
            self.CheckCandidates(rows)

    def test_first_active_simulation_baseline_loopback(self):
        with self.Receiver(first_active=True) as (process, output, port), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            rows = self.WaitRows(output, lambda rows: any(row.get('now_s', 0) > .3 for row in rows))
            self.assertTrue(all(row.get('q') is None for row in rows))
            sender.sendto(Packet().encode(), ('127.0.0.1', port))
            rows = self.WaitRows(output, lambda rows: any(row.get('baseline_captured') for row in rows))
            baseline = json.loads(Packet())['all_joint_q_rad']
            self.assertEqual(rows[-1]['baseline'], baseline)
            self.assertEqual(rows[-1]['q'], baseline)
            sender.sendto(Packet(2, [q+.05 for q in baseline[22:]]).encode(), ('127.0.0.1', port))
            rows = self.WaitRows(output, lambda rows: any(row.get('active_ticks', 0) >= 2 for row in rows))
            held = rows[-1]['q']
            self.assertEqual(held[:22], baseline[:22])
            self.assertGreater(held[22], baseline[22])
            sender.sendto(Packet(3, input_command_mode='pinch_disengaged').encode(), ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 0)
            self.assertTrue(Replay(output)['passed'])
            final = ReadRows(output)[-1]
            self.assertEqual(final['q'], held)
            self.assertEqual(final['baseline'], baseline)

    def test_near_goal_snap_and_reversal_replay(self):
        with self.Receiver() as (process, output, port), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            goals = [[.0005]*7, [-.0005]*7, [.05]*7, [-.05]*7]
            for sequence, goal in enumerate(goals, 1):
                sender.sendto(Packet(sequence, goal).encode(), ('127.0.0.1', port))
                rows = self.WaitRows(output, lambda rows: any(row.get('active_ticks', 0) >= sequence for row in rows))
                active_row = next(row for row in reversed(rows) if row.get('mode') == 'active')
                self.assertEqual(active_row['validated_goal'], goal)
                if sequence <= 2:
                    self.assertEqual(active_row['q'][22:], goal)
            sender.sendto(Packet(5, input_command_mode='pinch_disengaged').encode(), ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 0)
            report = Replay(output)
            self.assertEqual(report['active_ticks'], 4)
            self.assertTrue(report['overshoot_checked'])

    def test_replay_detects_missing_tampered_and_incomplete_evidence(self):
        with self.Receiver() as (process, output, port), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(Packet().encode(), ('127.0.0.1', port))
            self.WaitRows(output, lambda rows: any(row.get('active_ticks', 0) >= 1 for row in rows))
            sender.sendto(Packet(2, input_command_mode='pinch_disengaged').encode(), ('127.0.0.1', port))
            self.assertEqual(process.wait(timeout=3), 0)
            rows = ReadRows(output)
            self.assertTrue(Replay(output)['passed'])
            # Preserve one reproducible synthetic run and its report outside the temporary fixture.
            folder = Path(tempfile.mkdtemp(prefix='cpp_raw_replay_', dir=ROOT / 'logs/test_results'))
            (folder / 'ticks.jsonl').write_bytes(output.read_bytes())
            (folder / 'result.json').write_text(json.dumps(Replay(output), indent=2), encoding='utf-8')
            mutations = []
            import copy
            wrong_goal = copy.deepcopy(rows)
            next(row for row in wrong_goal if row.get('mode') == 'active')['validated_goal'][0] += .01
            mutations.append(wrong_goal)
            wrong_q = copy.deepcopy(rows)
            next(row for row in wrong_q if row.get('mode') == 'active')['q'][0] += .01
            mutations.append(wrong_q)
            mutations.append([row for row in rows if row.get('packet') != 1])
            mutations.append(rows[:-1])
            mutations.append([dict(event='config')] + rows[1:])
            for candidate in mutations:
                output.write_text(''.join(json.dumps(row)+'\n' for row in candidate), encoding='utf-8')
                with self.assertRaises(ValueError):
                    Replay(output)
            output.write_text(json.dumps(rows[0]), encoding='utf-8')
            with self.assertRaises(ValueError):
                Replay(output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
