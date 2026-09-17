"""Windows MSVC memory-only tests; no sockets, WSL, DDS, policy or robot calls.

Build in a VS x64 developer shell before running pytest (see README).
"""
import json
import random
from pathlib import Path
import subprocess
import unittest

from test_vr_input_offline import MakePacket
from arm_sdk_hold_contract import RIGHT_ARM_LIMITS_RAD

ROOT = Path(__file__).resolve().parents[2]
BASELINE = [i / 100 for i in range(22)] + [0.0] * 7


def Packet(sequence=1, arm=None, **changes):
    value = json.loads(MakePacket(sequence, **changes))
    if arm is not None:
        value['right_arm']['joints'] = arm
        value['all_joint_q_rad'][22:] = arm
    return json.dumps(value)


def Event(now, payload=None):
    return dict(now=now, **({'payload': payload} if payload is not None else {}))


class UpperTargetTests(unittest.TestCase):
    def RunCase(self, events, baseline=None, maximum_delta=.2, valid=True):
        config = dict(baseline=BASELINE if baseline is None else baseline,
                      maximum_delta=maximum_delta, now=0)
        result = subprocess.run([str(ROOT / 'logs/test_results/test_upper_target_offline.exe')],
                                input=''.join(json.dumps(x)+'\n' for x in [config, *events]),
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0 if valid else 2, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_rate_convergence_no_overshoot_and_preserved_joints(self):
        goal = [-.1, .1, -.0001, .0016, 0, -.034, .12345]
        rows = self.RunCase([Event(i*.02, Packet(i, goal)) for i in range(1, 121)])
        previous = BASELINE
        for row in rows:
            self.assertEqual(row['mode'], 'active')
            self.assertEqual(row['q'][:22], BASELINE[:22])
            self.assertFalse(row['hardware_output_authorized'])
            for old, new, desired in zip(previous[22:], row['q'][22:], goal):
                self.assertLessEqual(abs(new-old), .0016+1e-14)
                self.assertTrue(min(old, desired) <= new <= max(old, desired))
            previous = row['q']
        self.assertEqual(previous[22:], goal)

    def test_small_dt_long_dt_and_reversal(self):
        rows = self.RunCase([Event(.001, Packet(1)), Event(.101, Packet(2)),
                             Event(.111, Packet(3, [.1]*7))])
        self.assertAlmostEqual(rows[0]['q'][22], -.00008)
        self.assertAlmostEqual(rows[1]['q'][22], -.00168)
        self.assertAlmostEqual(rows[2]['q'][22], -.00088)

    def test_idle_wait_and_missing_packet_freeze(self):
        idle = json.loads(Packet())
        idle.update(input_command_mode='idle', session_id=None, input_packet_age_s=None)
        idle['right_arm'].update(active=False, command_state='idle', minimum_clearance_m=None)
        rows = self.RunCase([Event(1), Event(2, json.dumps(idle)), Event(3),
                             Event(3.01, Packet()), Event(3.1), Event(3.2, Packet(2))])
        self.assertEqual([r['mode'] for r in rows], ['waiting']*3+['active','waiting','active'])
        for row in rows[:3]:
            self.assertEqual(row['q'], BASELINE)
        self.assertEqual(rows[3]['q'], rows[4]['q'])

    def test_errors_release_and_timeout_latch_without_partial_update(self):
        bad_events = [Event(.04, 'bad'), Event(.04, '{}'), Event(.04, Packet(1)),
                      Event(.04, Packet(2, session_id='other')),
                      Event(.04, Packet(2, input_command_mode='pinch_disengaged')),
                      Event(.04, Packet(2, input_packet_age_s=.251)),
                      Event(.04, Packet(2, [0]*6+[.201])),
                      Event(.271), Event(.271, Packet(2)),
                      Event(.02, Packet(2)), Event(.01, Packet(2)),
                      Event('nan'), Event('inf'), Event('-inf')]
        for bad in bad_events:
            with self.subTest(bad=bad):
                rows = self.RunCase([Event(.02, Packet()), bad, Event(.3, Packet(3)), Event(.32)])
                self.assertEqual([r['mode'] for r in rows], ['active']+['stopped']*3)
                for row in rows[1:]:
                    self.assertEqual(row['q'], rows[0]['q'])
                    self.assertEqual(row['reason'], rows[1]['reason'])

    def test_all_model_joint_boundaries_and_atomic_rejection(self):
        for index, limits in enumerate(RIGHT_ARM_LIMITS_RAD):
            for bound, direction in zip(limits, [-1, 1]):
                with self.subTest(index=index, bound=bound):
                    arm = [0]*7
                    arm[index] = bound
                    good = Packet(2, arm.copy())
                    arm[index] += direction*1e-6
                    rows = self.RunCase([Event(.02, Packet()), Event(.04, good),
                                         Event(.06, Packet(3, arm)), Event(.08, Packet(4))],
                                        maximum_delta=4)
                    self.assertEqual(rows[1]['mode'], 'active')
                    self.assertEqual(rows[2]['reason'], 'right_arm_joint_limit')
                    self.assertEqual(rows[1]['q'], rows[2]['q'])
                    self.assertEqual(rows[1]['q'], rows[3]['q'])

    def test_timeout_boundary(self):
        rows = self.RunCase([Event(.125, Packet()), Event(.375), Event(.375001)])
        self.assertEqual([r['mode'] for r in rows], ['active','waiting','stopped'])
        self.assertEqual(rows[2]['reason'], 'receiver_timeout')
        self.assertEqual(rows[0]['q'], rows[2]['q'])

    def test_invalid_initialization(self):
        for baseline in ([0]*28, [0]*28+[2], [None]*29):
            with self.subTest(baseline=baseline):
                self.RunCase([], baseline=baseline, valid=False)
        for limit in [0, -1]:
            self.RunCase([], maximum_delta=limit, valid=False)

    def test_varying_goals_from_nonzero_baseline(self):
        rng = random.Random(22028)
        baseline = BASELINE[:22] + [.05, -.1, .2, .3, -.2, .1, -.05]
        now = 0
        events, cases = [], []
        for sequence in range(1, 501):
            dt = rng.choice([.001, .01, .02, .05])
            goal = [q + rng.uniform(-.19, .19) for q in baseline[22:]]
            now += dt
            events.append(Event(now, Packet(sequence, goal)))
            cases.append((dt, goal))
        previous = baseline
        for row, (dt, goal) in zip(self.RunCase(events, baseline=baseline), cases):
            self.assertEqual(row['mode'], 'active')
            self.assertEqual(row['q'][:22], baseline[:22])
            for old, new, desired in zip(previous[22:], row['q'][22:], goal):
                self.assertTrue(min(old, desired) <= new <= max(old, desired))
                self.assertLessEqual(abs(new-old), .08*min(dt, .02)+1e-14)
            previous = row['q']


if __name__ == '__main__':
    unittest.main(verbosity=2)
