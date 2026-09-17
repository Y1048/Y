"""Queue-to-tick tests of the memory-only C++ harness."""
import json
import unittest

from test_cpp_upper_target import BASELINE, Event, Packet
import test_cpp_upper_target as target_tests
from replay_cpp_input_tick import BuildTicks, Replay, ROOT


def Received(payload, at):
    return dict(payload=payload, received_at=at)


def Tick(now, *packets):
    return dict(now=now, packets=list(packets))


class InputTickTests(unittest.TestCase):
    RunCase = target_tests.UpperTargetTests.RunCase

    def test_batch_moves_once_to_latest_goal(self):
        rows = self.RunCase([Tick(.02, Received(Packet(1), .005),
                                 Received(Packet(2, [.1]*7), .01),
                                 Received(Packet(3, [-.1]*7), .015)), Tick(.04)])
        self.assertEqual(rows[0]['mode'], 'active')
        self.assertEqual(rows[0]['q'], BASELINE[:22]+[-.0016]*7)
        self.assertEqual(rows[1]['q'], rows[0]['q'])
        self.assertEqual(rows[1]['mode'], 'waiting')

    def test_stop_inside_batch_is_never_hidden_by_later_valid_packet(self):
        for bad in ['bad', Packet(3, input_command_mode='pinch_disengaged'),
                    Packet(3, [0]*6+[.201]), Packet(2),
                    Packet(3, session_id='other')]:
            with self.subTest(bad=bad):
                rows = self.RunCase([Event(.02, Packet()),
                                     Tick(.04, Received(Packet(2), .025),
                                          Received(bad, .03), Received(Packet(4), .035)),
                                     Event(.06, Packet(5))])
                self.assertEqual([r['mode'] for r in rows], ['active','stopped','stopped'])
                self.assertEqual(rows[0]['q'], rows[1]['q'])
                self.assertEqual(rows[0]['q'], rows[2]['q'])

    def test_source_age_includes_queue_delay_and_boundary(self):
        for age, expected in [(.125, 'active'), (.125001, 'stopped')]:
            with self.subTest(age=age):
                rows = self.RunCase([Tick(.25, Received(Packet(input_packet_age_s=age), .125))])
                self.assertEqual(rows[0]['mode'], expected)
                if expected == 'stopped':
                    self.assertEqual(rows[0]['reason'], 'source_timeout')
                    self.assertEqual(rows[0]['q'], BASELINE)
        rows = self.RunCase([Tick(.3, Received(Packet(), .01)), Event(.32, Packet(2))])
        self.assertEqual([r['mode'] for r in rows], ['stopped']*2)
        self.assertEqual(rows[1]['q'], BASELINE)

    def test_timeout_uses_receipt_not_processing_time(self):
        rows = self.RunCase([Tick(.125, Received(Packet(), .0625)), Tick(.3125), Tick(.313)])
        self.assertEqual([r['mode'] for r in rows], ['active','waiting','stopped'])
        self.assertEqual(rows[-1]['reason'], 'receiver_timeout')
        self.assertEqual(rows[0]['q'], rows[-1]['q'])

    def test_invalid_receipt_times_and_order(self):
        for received in [-.01, .05, 'nan', 'inf', '-inf', .009]:
            with self.subTest(received=received):
                rows = self.RunCase([Tick(.02, Received(Packet(), .01)),
                                     Tick(.04, Received(Packet(2), received)), Event(.06, Packet(3))])
                self.assertEqual(rows[1]['reason'], 'invalid_receipt_time')
                self.assertEqual(rows[0]['q'], rows[1]['q'])
                self.assertEqual(rows[0]['q'], rows[2]['q'])
        rows = self.RunCase([Tick(.02, Received(Packet(), .015), Received(Packet(2), .01))])
        self.assertEqual(rows[0]['reason'], 'invalid_receipt_time')
        self.assertEqual(rows[0]['q'], BASELINE)

    def test_idle_then_active_same_tick_and_same_receipt_time(self):
        idle = json.loads(Packet())
        idle.update(input_command_mode='idle', session_id=None, input_packet_age_s=None)
        idle['right_arm'].update(active=False, command_state='idle', minimum_clearance_m=None)
        rows = self.RunCase([Tick(.02, Received(json.dumps(idle), .01),
                                 Received(Packet(), .01), Received(Packet(2), .01))])
        self.assertEqual(rows[0]['mode'], 'active')
        self.assertAlmostEqual(rows[0]['q'][22], -.0016)

    def test_stalled_tick_does_not_resume_from_fresh_queue(self):
        rows = self.RunCase([Event(.02, Packet()),
                             Tick(.3, Received(Packet(2), .1), Received(Packet(3), .2)),
                             Event(.32, Packet(4))])
        self.assertEqual(rows[1]['reason'], 'receiver_timeout')
        self.assertEqual(rows[0]['q'], rows[1]['q'])
        self.assertEqual(rows[0]['q'], rows[2]['q'])


class ReplayTests(unittest.TestCase):
    def test_tick_grouping_keeps_release_and_all_packets(self):
        packets = [Received(Packet(1), 0),
                   Received(Packet(2, input_command_mode='pinch_disengaged'), .001),
                   Received(Packet(3), .02), Received(Packet(4), .020001)]
        ticks = BuildTicks(packets)
        self.assertEqual(ticks[0]['packets'], packets[:3])
        self.assertEqual(ticks[1]['packets'], packets[3:])
        self.assertEqual([p for tick in ticks for p in tick['packets']], packets)
        rows = target_tests.UpperTargetTests().RunCase(ticks)
        self.assertTrue(all(row['mode'] == 'stopped' for row in rows))
        self.assertTrue(all(row['q'] == BASELINE for row in rows))

    def test_bad_capture_clocks_are_rejected(self):
        for times in [[], [-.01], [float('nan')], [float('inf')], [181], [.02, .01]]:
            with self.subTest(times=times), self.assertRaises(ValueError):
                BuildTicks([Received(Packet(i+1), at) for i, at in enumerate(times)])

    def test_recorded_quest_replay(self):
        capture = ROOT / 'logs/test_results/twist2_vr_shadow_20260907_140851_282afca4/samples.jsonl'
        if not capture.exists():
            self.skipTest('Local Quest capture not present')
        report, trace = Replay(capture, ROOT / 'logs/test_results/test_upper_target_offline.exe')
        self.assertEqual(report['violations'], [])
        self.assertEqual(report['stop_reason'], 'input_disengaged')
        self.assertGreaterEqual(report['tick_counts']['active'], 100)
        self.assertGreater(report['tick_counts']['waiting'], 0)
        self.assertGreater(report['tick_counts']['stopped'], 1)
        self.assertGreater(report['maximum_observed_rate_rad_s'], 0)
        self.assertLessEqual(report['maximum_observed_rate_rad_s'], .08+1e-12)
        self.assertEqual(trace[-1]['mode'], 'stopped')


if __name__ == '__main__':
    unittest.main(verbosity=2)
