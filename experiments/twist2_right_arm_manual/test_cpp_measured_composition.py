"""Synthetic state samples only; no LowState connection or policy runtime."""
import json
import subprocess
import unittest
from test_cpp_upper_target import ROOT, BASELINE, Packet

LIMITS = dict(state_age=.021, settle_seconds=.039, settle_velocity=.1, settle_drift=.01,
              initial_arm_error=.025, tracking_error=.25, maximum_arm_delta=.17)


def Event(n, payload=None, q=None):
    now=n*.02
    return dict(now=now, state=dict(q=list(BASELINE if q is None else q), dq=[0]*29,
        sequence=n, received_at=now), legs=[i*.01 for i in range(12)],
        packets=[] if payload is None else [dict(payload=payload, at=now)])


class CompositionTests(unittest.TestCase):
    def Run(self, events, limits=None):
        result=subprocess.run([str(ROOT/'logs/test_results/test_measured_composition.exe')],
            input=''.join(json.dumps(x)+'\n' for x in [limits or LIMITS,*events]),
            text=True,capture_output=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        return [json.loads(x) for x in result.stdout.splitlines()]

    def Ready(self):
        return [Event(1),Event(2),Event(3),Event(4,Packet(1,[.01]*7))]

    def test_measured_capture_and_motor_order_composition(self):
        rows=self.Run(self.Ready()+[Event(5,Packet(2,[.05]*7))])
        self.assertEqual(rows[0]['mode'],'settling')
        self.assertIsNone(rows[0]['baseline'])
        self.assertEqual(rows[2]['mode'],'awaiting_alignment')
        self.assertIsNone(rows[2]['candidate'])
        self.assertEqual(rows[-1]['baseline'],BASELINE)
        self.assertEqual(rows[-1]['candidate'][:12],Event(5)['legs'])
        self.assertEqual(rows[-1]['candidate'][12:22],BASELINE[12:22])
        for q in rows[-1]['candidate'][22:]: self.assertAlmostEqual(q,.0032)

    def test_mismatch_stops_without_rebase_or_resume(self):
        events=[Event(1),Event(2),Event(3),Event(4,Packet(1,[.1]*7)),Event(5,Packet(2,[0]*7))]
        rows=self.Run(events)
        for row in rows[-2:]:
            self.assertEqual(row['reason'],'initial_arm_mismatch')
            self.assertIsNone(row['candidate'])
            self.assertEqual(row['baseline'],BASELINE)

    def test_state_faults_latch_and_suppress_candidate(self):
        for fault in ('missing','stale','future','repeat','gap','tracking','clock'):
            with self.subTest(fault=fault):
                event=Event(5,Packet(2,[.01]*7))
                if fault=='missing': event['state']=None
                if fault=='stale': event['state']['received_at']-=.03
                if fault=='future': event['state']['received_at']+=.01
                if fault=='repeat': event['state']['sequence']=4
                if fault=='gap': event=Event(7,Packet(2,[.01]*7))
                if fault=='tracking': event['state']['q'][12]+=.3
                if fault=='clock': event['now']=.08
                rows=self.Run(self.Ready()+[event,Event(8,Packet(3,[.01]*7))])
                for row in rows[-2:]:
                    self.assertEqual(row['mode'],'stopped')
                    self.assertIsNone(row['candidate'])

    def test_settling_restarts_on_velocity_or_drift(self):
        for key in ('dq','q'):
            events=[Event(i) for i in range(1,8)]
            events[1]['state'][key][0]=.2
            rows=self.Run(events)
            self.assertIsNone(rows[3]['baseline'])
            self.assertEqual(rows[-1]['baseline'],BASELINE)

    def test_release_invalid_batch_and_timeout(self):
        for fault in ('release','invalid','limit','timeout'):
            with self.subTest(fault=fault):
                events=self.Ready()
                if fault=='timeout': events += [Event(i) for i in range(5,19)]
                else:
                    payload=Packet(2,input_command_mode='pinch_disengaged') if fault=='release' else ('bad' if fault=='invalid' else Packet(2,[.3]*7))
                    events += [Event(5,payload),Event(6,Packet(3,[.01]*7))]
                rows=self.Run(events)
                self.assertEqual(rows[-1]['mode'],'stopped')
                self.assertIsNone(rows[-1]['candidate'])

    def test_silence_freezes_arm_but_composes_new_policy_legs(self):
        event=Event(5); event['legs']=[.2]*12
        rows=self.Run(self.Ready()+[event])
        self.assertEqual(rows[-1]['mode'],'waiting')
        self.assertEqual(rows[-1]['candidate'][12:],rows[-2]['candidate'][12:])
        self.assertEqual(rows[-1]['candidate'][:12],[.2]*12)

    def test_same_batch_release_never_returns_candidate(self):
        events=[Event(1),Event(2),Event(3),Event(4,Packet(1,[.01]*7))]
        events[-1]['packets'].append(dict(payload=Packet(2,input_command_mode='pinch_disengaged'),at=.08))
        rows=self.Run(events)
        self.assertEqual(rows[-1]['reason'],'input_disengaged')
        self.assertIsNone(rows[-1]['candidate'])

    def test_idle_before_active_and_invalid_later_packet(self):
        events=self.Ready()
        idle=json.loads(Packet(1,[0]*7))
        idle.update(input_command_mode='idle')
        idle['right_arm'].update(active=False,command_state='idle')
        events[-1]['packets'].insert(0,dict(payload=json.dumps(idle),at=.08))
        self.assertEqual(self.Run(events)[-1]['mode'],'active')
        events[-1]['packets'].append(dict(payload='bad',at=.08))
        row=self.Run(events)[-1]
        self.assertEqual(row['mode'],'stopped')
        self.assertIsNone(row['candidate'])

    def test_invalid_baseline_and_input_envelopes(self):
        for fault in ('joint_limit','oversize','overflow','future_input','old_input'):
            with self.subTest(fault=fault):
                events=self.Ready()
                if fault=='joint_limit':
                    for event in events: event['state']['q'][22]=4
                elif fault=='oversize': events[-1]['packets'][0]['payload']='x'*16385
                elif fault=='overflow': events[-1]['packets']*=65
                elif fault=='future_input': events[-1]['packets'][0]['at']=.09
                else:
                    events += [Event(5,Packet(2,[.01]*7))]
                    events[-1]['packets'][0]['at']=.07
                row=self.Run(events)[-1]
                self.assertEqual(row['mode'],'stopped')
                self.assertIsNone(row['candidate'])


if __name__=='__main__': unittest.main()
