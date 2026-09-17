"""Deterministic C++ queue limits, FIFO, error and stop tests; no sockets."""
import json
import subprocess
import unittest

from test_cpp_upper_target import BASELINE, Packet, ROOT


def Push(payload, at):
    return dict(op='push', payload=payload, at=at)


def Tick(at):
    return dict(op='tick', at=at)


class QueuedInputTests(unittest.TestCase):
    def RunCase(self, events, capacity=64, valid=True, baseline=BASELINE):
        config = dict(baseline=baseline, maximum_delta=.2, capacity=capacity)
        result = subprocess.run([str(ROOT / 'logs/test_results/test_queued_input.exe')],
                                input=''.join(json.dumps(e)+'\n' for e in [config, *events]),
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0 if valid else 2, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_full_capacity_then_drain_and_reuse(self):
        events = [Push(Packet(i), .01) for i in range(1, 65)]
        events += [Tick(.02), Push(Packet(65, [.1]*7), .03), Tick(.04)]
        rows = self.RunCase(events)
        self.assertEqual(rows[63]['depth'], 64)
        self.assertEqual(rows[64]['depth'], 0)
        self.assertEqual(rows[64]['mode'], 'active')
        self.assertEqual(rows[-1]['mode'], 'active')
        self.assertEqual(rows[-1]['peak'], 64)
        self.assertAlmostEqual(rows[64]['q'][22], -.0016)
        self.assertAlmostEqual(rows[-1]['q'][22], 0)

    def test_overflow_clears_queue_and_latches_without_motion(self):
        events = [Push(Packet(), .01), Tick(.02)]
        events += [Push(Packet(i), .03) for i in range(2, 67)]
        events += [Tick(.04), Push(Packet(67), .05), Tick(.06)]
        rows = self.RunCase(events)
        for row in rows[66:]:
            self.assertEqual(row['reason'], 'queue_overflow')
            self.assertEqual(row['depth'], 0)
            self.assertEqual(row['q'], rows[1]['q'])
        self.assertLessEqual(max(r['depth'] for r in rows), 64)

    def test_middle_release_and_error_cannot_be_overwritten(self):
        for bad in ['bad', Packet(3, input_command_mode='pinch_disengaged'),
                    Packet(3, [0]*6+[.201])]:
            with self.subTest(bad=bad):
                rows = self.RunCase([Push(Packet(), .01), Tick(.02),
                                     Push(Packet(2), .025), Push(bad, .03),
                                     Push(Packet(4), .035), Tick(.04),
                                     Push(Packet(5), .05), Tick(.06)])
                self.assertEqual(rows[-1]['mode'], 'stopped')
                self.assertEqual(rows[5]['depth'], 0)
                self.assertEqual(rows[5]['q'], rows[1]['q'])
                self.assertEqual(rows[-1]['q'], rows[1]['q'])

    def test_payload_size_boundary_and_oversize_latch(self):
        packet = Packet()
        rows = self.RunCase([Push(packet+' '*(16384-len(packet)), .01), Tick(.02),
                             Push('x'*16385, .03), Tick(.04)])
        self.assertEqual(rows[1]['mode'], 'active')
        self.assertEqual(rows[2]['reason'], 'datagram_too_large')
        self.assertEqual(rows[2]['q'], rows[1]['q'])
        self.assertEqual(rows[3]['q'], rows[1]['q'])

    def test_bad_receipt_and_future_tick_receipt(self):
        for at in [-1, 'nan', 'inf', '-inf', .009]:
            with self.subTest(at=at):
                rows = self.RunCase([Push(Packet(), .01), Tick(.02),
                                     Push(Packet(2), at), Tick(.04)])
                self.assertEqual(rows[-1]['reason'], 'invalid_receipt_time')
                self.assertEqual(rows[-1]['q'], rows[1]['q'])
        rows = self.RunCase([Push(Packet(), .03), Tick(.02)])
        self.assertEqual(rows[-1]['reason'], 'invalid_receipt_time')
        self.assertEqual(rows[-1]['q'], BASELINE)

    def test_silence_and_queue_delay_timeout(self):
        rows = self.RunCase([Push(Packet(), .01), Tick(.02), Tick(.1), Tick(.261)])
        self.assertEqual(rows[2]['mode'], 'waiting')
        self.assertEqual(rows[3]['reason'], 'receiver_timeout')
        self.assertEqual(rows[3]['q'], rows[1]['q'])
        rows = self.RunCase([Push(Packet(input_packet_age_s=.24), .01), Tick(.03)])
        self.assertEqual(rows[-1]['reason'], 'source_timeout')
        self.assertEqual(rows[-1]['q'], BASELINE)

    def test_external_error_first_reason_wins(self):
        rows = self.RunCase([Push(Packet(), .01), Tick(.02), Push(Packet(2), .03),
                             dict(op='stop', reason='receive_error'),
                             dict(op='stop', reason='output_write_error'),
                             Push(Packet(3), .05), Tick(.06)])
        for row in rows[3:]:
            self.assertEqual(row['reason'], 'receive_error')
            self.assertEqual(row['q'], rows[1]['q'])
            self.assertEqual(row['depth'], 0)

    def test_invalid_capacity(self):
        for capacity in [0, -1, 65]:
            with self.subTest(capacity=capacity):
                self.RunCase([], capacity=capacity, valid=False)

    def test_first_active_baseline_after_idle_then_move_and_release(self):
        from test_cpp_input_contract import Idle
        first = json.loads(Packet())['all_joint_q_rad']
        goal = [q+.05 for q in first[22:]]
        rows = self.RunCase([Push(json.dumps(Idle()), .01), Tick(.02), Tick(1),
                             Push(Packet(), 1.01), Tick(1.02),
                             Push(Packet(2, goal), 1.03), Tick(1.04),
                             Push(Packet(3, input_command_mode='pinch_disengaged'), 1.05),
                             Tick(1.06), Push(Packet(4), 1.07), Tick(1.08)], baseline=None)
        self.assertTrue(all(row['q'] is None for row in rows[:4]))
        self.assertEqual(rows[4]['q'], first)
        self.assertEqual(rows[4]['baseline'], first)
        self.assertEqual(rows[6]['q'][:22], first[:22])
        for before, after in zip(first[22:], rows[6]['q'][22:]):
            self.assertAlmostEqual(after-before, .0016)
        self.assertEqual(rows[-1]['reason'], 'input_disengaged')
        self.assertEqual(rows[-1]['q'], rows[6]['q'])
        self.assertEqual(rows[-1]['baseline'], first)

    def test_first_active_selected_before_latest_in_same_batch(self):
        first = json.loads(Packet())['all_joint_q_rad']
        goal = [q+.05 for q in first[22:]]
        rows = self.RunCase([Push(Packet(), .005), Push(Packet(2, goal), .01), Tick(.02)], baseline=None)
        self.assertEqual(rows[-1]['baseline'], first)
        self.assertNotEqual(rows[-1]['q'][22:], goal)
        self.assertAlmostEqual(rows[-1]['q'][22], first[22]+.0016)

    def test_invalid_first_packet_never_captures_or_recovers(self):
        for payload in ['bad', Packet(input_packet_age_s=.26), Packet(1, [0]*6+[3])]:
            with self.subTest(payload=payload):
                rows = self.RunCase([Push(payload, .01), Tick(.02),
                                     Push(Packet(2), .03), Tick(.04)], baseline=None)
                self.assertEqual(rows[-1]['mode'], 'stopped')
                self.assertTrue(all(row['q'] is None for row in rows))

    def test_overflow_before_baseline_and_release_on_capture_tick(self):
        from test_cpp_input_contract import Idle
        rows = self.RunCase([Push(json.dumps(Idle()), .01), Push(Packet(), .015), Tick(.02)],
                            capacity=1, baseline=None)
        self.assertEqual(rows[-1]['reason'], 'queue_overflow')
        self.assertIsNone(rows[-1]['q'])
        rows = self.RunCase([Push(Packet(), .01),
                             Push(Packet(2, input_command_mode='pinch_disengaged'), .015), Tick(.02)],
                            baseline=None)
        self.assertEqual(rows[-1]['reason'], 'input_disengaged')
        self.assertEqual(rows[-1]['q'], json.loads(Packet())['all_joint_q_rad'])

    def test_previous_inactive_session_waits_only_before_first_active(self):
        from test_cpp_input_contract import Idle
        for mode in ['pinch_disengaged','tracking_disengaged','workspace_exit']:
            with self.subTest(mode=mode):
                old = Idle()
                old.update(input_command_mode=mode, session_id='old', input_packet_age_s=45)
                rows = self.RunCase([Push(json.dumps(old), .01), Tick(.02),
                                     Push(Packet(), .03), Tick(.04),
                                     Push(json.dumps(old), .05), Tick(.06),
                                     Push(Packet(2), .07), Tick(.08)], baseline=None)
                self.assertEqual(rows[1]['mode'], 'waiting')
                self.assertIsNone(rows[1]['q'])
                self.assertEqual(rows[3]['mode'], 'active')
                self.assertEqual(rows[-1]['mode'], 'stopped')
                self.assertEqual(rows[-1]['q'], rows[3]['q'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
