import hashlib
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

PATH=Path(__file__).resolve().parents[2]/'tools/G1_INPUT_RECEIVE_AUDIT.py'
spec=importlib.util.spec_from_file_location('audit',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def packet():
    return dict(schema=m.SCHEMA,observation_only=True,session='a'*32,sequence=0,
                payload={s:dict(status='WAIT',values=None) for s in ('arm','omni')})


def source_packet(stream='arm', sequence=0, stamp=1., session='b'*32):
    if stream=='arm':
        values=dict(left_q_rad=[i*.01 for i in range(7)],right_q_rad=[-i*.02 for i in range(7)],
            joint_names=m.JOINT_NAMES,joint_indices=list(range(15,29)),state='tracking',reason='',
            session='unity-session',sequence=sequence,feedback_sequence=sequence,
            unity_input_status='FRESH',unity_input_age_s=.01)
    else:
        values=dict(mx=.1,my=.2,arm_yaw_deg=112.,omni_yaw_rate_deg_s=2.,
            vx=.4,vy=-.2,yaw_rate=.3,yaw_diff_deg=10.,yaw_step_diff_deg=.2,
            sample_sequence=sequence,calibrated=True)
    return dict(schema=m.SOURCE_SCHEMA,observation_only=True,stream=stream,session=session,
                sequence=sequence,source_monotonic_s=stamp,values=values)


class AuditTests(unittest.TestCase):
    def test_100hz_display_repeats_one_snapshot_ages_it_and_never_bursts_after_slow_write(self):
        rows=[];times=[];enough=threading.Event()
        now=time.monotonic()
        stream=dict(status='FRESH_LIVE',source_age_s=.60,source_sequence=9,
                    values=dict(source_monotonic_s=now-.60,left_q_rad=[.1]*7,right_q_rad=[.2]*7))
        snapshot=dict(tx_sequence=4,payload=dict(arm=stream,omni=dict(status='WAIT',values=None)),
                      snapshot_monotonic_s=now)
        original=copy.deepcopy(snapshot)
        def writer(line):
            times.append(time.perf_counter());rows.append(json.loads(line))
            if len(rows)==3:time.sleep(.04)
            if len(rows)>=24:enough.set()
        output=m.LatestOutput(writer=writer,hz=100.)
        try:
            output.submit(snapshot)
            self.assertTrue(enough.wait(2),'independent display did not continue without new source samples')
        finally:output.close()
        self.assertGreaterEqual(len(rows),24)
        self.assertTrue(all(row['tx_sequence']==4 for row in rows))
        self.assertTrue(all(row['display_payload']['arm']['source_sequence']==9 for row in rows))
        self.assertEqual([row['display_sequence'] for row in rows],list(range(len(rows))))
        self.assertTrue(all(row['display_repeated_snapshot'] for row in rows[1:]))
        intervals=[b-a for a,b in zip(times,times[1:])]
        self.assertGreaterEqual(min(intervals),.006)
        self.assertLess(sorted(intervals)[len(intervals)//2],.014)
        self.assertGreater(intervals[2],.045)
        self.assertGreater(output.stats()['display_intervals_skipped'],0)
        self.assertEqual(rows[-1]['display_payload']['arm']['status'],'STALE')
        self.assertGreater(rows[-1]['display_payload']['arm']['source_age_s'],
                           rows[0]['display_payload']['arm']['source_age_s'])
        self.assertEqual(snapshot,original)  # Original packet/hash/log payload is unchanged.

    def test_receiver_display_ages_wait_and_packet_without_cross_host_clock_subtraction(self):
        stream=dict(status='FRESH_LIVE',source_age_s=.20,source_sequence=5,
                    values=dict(source_monotonic_s=999999.,vx=.4,vy=0.,yaw_rate=.2))
        latest=dict(receiver_monotonic_s=10.,packet=dict(payload=dict(omni=stream)))
        view=m.display_view(m.receiver_view(rx='RECEIVED',receiver_age_s=0.,latest=latest),10.6,10.)
        self.assertAlmostEqual(view['receiver_age_s'],.6)
        self.assertAlmostEqual(view['display_payload']['omni']['source_age_s'],.8)
        self.assertEqual(view['display_payload']['omni']['status'],'STALE')
        self.assertEqual(view['latest']['packet']['payload']['omni']['source_age_s'],.2)
        later=m.display_view(m.receiver_view(rx='RECEIVED',latest=latest),11.,10.)
        self.assertEqual(later['rx'],'STALE')
        wait=m.display_view(m.receiver_view(rx='WAIT',latest=None,receiver_age_s=None),11.,10.)
        self.assertEqual(wait['rx'],'WAIT');self.assertIsNone(wait['receiver_age_s'])

    def test_display_rate_validation_accepts_100_and_rejects_outside_range_before_binding(self):
        for value in ('101','-1','nan'):
            done=subprocess.run([sys.executable,str(PATH),'receive','--print-hz',value],
                                capture_output=True,text=True,timeout=3)
            self.assertEqual(done.returncode,2)
            self.assertIn('print-hz must be',done.stderr)
        with self.assertRaises(ValueError):m.LatestOutput(hz=101)

    def test_receiver_mock_never_labels_external_ik_as_measured_g1_or_cpp_output(self):
        external=source_packet()['values']
        row=m.receiver_view(values=external,initial_g1_q_rad=external['left_q_rad'],
                            initial_g1_q_status='MEASURED',cpp_command_sent=True)
        self.assertEqual(row['controller_role'],'INPUT_RECEIVER_MOCK')
        self.assertIsNone(row['initial_g1_q_rad'])
        self.assertEqual(row['initial_g1_q_status'],'NOT_MEASURED')
        self.assertIs(row['cpp_command_sent'],False)
        self.assertEqual(row['values'],external)
        self.assertNotIn('initial_g1_q_rad',external)

    def test_contract_separate_from_control(self):
        m.validate(packet())
        self.assertNotIn(m.PORT,(5008,5014,5017,5020))
        for schema in ('g1.velocity.command.v1','g1.mink.cycle.live.v1'):
            p=packet();p['schema']=schema
            with self.assertRaises(ValueError):m.validate(p)
        with self.assertRaises(ValueError):m.parse(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError):m.parse(b'{"x":NaN}')

    def test_bad_values_and_wrong_order_size(self):
        p=packet();p['payload']['arm']=dict(status='FRESH_LOG',values=dict(left_q_rad=[0]*7,right_q_rad=[0]*6))
        with self.assertRaises(ValueError):m.validate(p)
        p['payload']['arm']['values']['right_q_rad']=[float('inf')]*7
        with self.assertRaises(ValueError):m.validate(p)

    def test_ack_requires_peer_session_sequence_and_exact_digest(self):
        raw=m.encode(packet());target=('127.0.0.1',m.PORT)
        digest=hashlib.sha256(raw).hexdigest();pending={0:(1.,digest)}
        ack=dict(schema=m.ACK_SCHEMA,session='a'*32,sequence=0,received_sha256=digest,motor_acceptance='NOT_CHECKED')
        self.assertIsNotNone(m.matching_ack(m.encode(ack),target,target,'a'*32,pending))
        for field,value in [('session','b'*32),('sequence',1),('received_sha256','wrong')]:
            changed=dict(ack);changed[field]=value
            self.assertIsNone(m.matching_ack(m.encode(changed),target,target,'a'*32,pending))
        self.assertIsNone(m.matching_ack(m.encode(ack),('127.0.0.2',m.PORT),target,'a'*32,pending))

    def test_loopback_real_udp_ack_and_recorded_packet_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);console=root/'receiver.txt';log=root/'received.jsonl'
            with console.open('w') as out:
                process=subprocess.Popen([sys.executable,str(PATH),'receive','--bind','127.0.0.1',
                    '--seconds','2','--log',str(log)],stdout=out,stderr=out)
                try:
                    for _ in range(100):
                        if 'RECEIVE ONLY' in console.read_text():break
                        if process.poll() is not None:self.fail(console.read_text())
                        time.sleep(.02)
                    else:self.fail('receiver startup timeout')
                    sent=subprocess.run([sys.executable,str(PATH),'send','--host','127.0.0.1',
                        '--root',d,'--seconds','.6'],capture_output=True,text=True,timeout=5,check=True)
                    rows=[json.loads(x) for x in sent.stdout.splitlines() if x.startswith('{')]
                    self.assertGreater(rows[-1]['ack_verified_count'],10)
                    self.assertEqual(rows[-1]['receiver_status'],'ACK_CONFIRMED')
                    process.wait(timeout=4)
                    self.assertEqual(process.returncode,0)
                    received=[json.loads(x) for x in log.read_text().splitlines()]
                    self.assertGreater(len(received),10)
                    for row in received:
                        self.assertEqual(row['received_sha256'],hashlib.sha256(m.encode(row['packet'])).hexdigest())
                        self.assertEqual(row['motor_acceptance'],'NOT_CHECKED')
                        self.assertEqual(row['packet']['payload']['arm']['status'],'WAIT')
                finally:
                    if process.poll() is None:process.terminate();process.wait(timeout=3)

    def test_live_source_strict_contract_and_exact_joint_order(self):
        original=source_packet()
        m.validate_source(original)
        m.validate_source(source_packet('omni'))
        bad=[]
        for key,value in [('observation_only',False),('session','wrong'),('sequence',True),
                          ('source_monotonic_s',float('inf')),('source_monotonic_s',-1),
                          ('stream','command')]:
            p=copy.deepcopy(original);p[key]=value;bad.append(p)
        for key,value in [('joint_names',list(reversed(m.JOINT_NAMES))),('joint_indices',list(range(14))),
                          ('left_q_rad',[0]*6),('right_q_rad',[float('nan')]*7),
                          ('state','actuate'),('feedback_sequence',False)]:
            p=copy.deepcopy(original);p['values'][key]=value;bad.append(p)
        p=source_packet('omni');p['values']['calibrated']=1;bad.append(p)
        p=source_packet('omni');p['values']['vx']=float('nan');bad.append(p)
        for p in bad:
            with self.subTest(packet=p):
                with self.assertRaises(ValueError):m.validate_source(p)
        waiting=source_packet()
        waiting['values'].update(state='ready',session=None,sequence=-1,
                                  unity_input_status='WAIT',unity_input_age_s=None)
        m.validate_source(waiting)
        waiting['values']['state']='tracking'
        with self.assertRaises(ValueError):m.validate_source(waiting)

    def test_source_order_restart_clock_and_freshness_cannot_be_refreshed_by_resend(self):
        sources=m.LiveSources();peer=('127.0.0.1',61000)
        p=source_packet(stamp=10.,sequence=4)
        self.assertTrue(sources.accept(m.encode(p),peer,10.01))
        first=sources.snapshot('arm',10.02)
        self.assertEqual(first['status'],'FRESH_LIVE')
        self.assertEqual(sources.snapshot('omni',10.02)['status'],'WAIT')
        self.assertFalse(sources.accept(m.encode(p),peer,10.7))  # duplicate cannot refresh age
        self.assertEqual(sources.snapshot('arm',10.8)['status'],'STALE')
        for p in (source_packet(sequence=3,stamp=10.9),source_packet(sequence=5,stamp=9.9),
                  source_packet(sequence=5,stamp=12.)):
            self.assertFalse(sources.accept(m.encode(p),peer,11.))
        restart=source_packet(sequence=0,stamp=11.,session='c'*32)
        self.assertTrue(sources.accept(m.encode(restart),('127.0.0.1',61001),11.01))
        self.assertFalse(sources.accept(m.encode(source_packet(sequence=99,stamp=11.1)),peer,11.2))
        self.assertEqual(sources.last_rejection,'source_retired_session')
        self.assertFalse(sources.accept(m.encode(source_packet('omni',stamp=11.)),('192.0.2.1',1),11.1))
        self.assertEqual(sources.snapshot('arm',11.2)['source_sequence'],0)
        self.assertEqual(sources.snapshot('arm',11.8)['status'],'STALE')
        # An old but increasing source sample is not fresh simply because it just arrived.
        self.assertTrue(sources.accept(m.encode(source_packet(sequence=1,stamp=11.2,session='c'*32)),
                                       ('127.0.0.1',61001),13.))
        self.assertEqual(sources.snapshot('arm',13.)['status'],'STALE')

    def test_equal_source_clock_tick_allows_new_sequence_without_renewing_source_age(self):
        sources=m.LiveSources();peer=('127.0.0.1',61000)
        self.assertTrue(sources.accept(m.encode(source_packet(sequence=0,stamp=10.)),peer,10.))
        self.assertTrue(sources.accept(m.encode(source_packet(sequence=1,stamp=10.)),peer,10.5))
        snapshot=sources.snapshot('arm',10.8)
        self.assertEqual(snapshot['source_sequence'],1)
        self.assertAlmostEqual(snapshot['source_age_s'],.8)
        self.assertEqual(snapshot['status'],'STALE')
        self.assertFalse(sources.accept(m.encode(source_packet(sequence=1,stamp=10.)),peer,10.81))
        self.assertFalse(sources.accept(m.encode(source_packet(sequence=2,stamp=9.9)),peer,10.82))

    def test_blocked_stdout_does_not_block_real_udp_ack_or_grow_display_queue(self):
        entered=threading.Event();release=threading.Event();result={};errors=[]
        def blocked_output(line):
            entered.set();release.wait(5)
        with tempfile.TemporaryDirectory() as d:
            args=SimpleNamespace(log=Path(d)/'blocked.jsonl',bind='127.0.0.1',allow_peer=None,
                                 seconds=.8,print_hz=50.)
            def run():
                try:result.update(m.receive(args,output_writer=blocked_output))
                except Exception as exc:errors.append(exc);entered.set()
            worker=threading.Thread(target=run,daemon=True);worker.start()
            try:
                self.assertTrue(entered.wait(2));self.assertFalse(errors)
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                    sock.bind(('127.0.0.1',0));sock.settimeout(.15)
                    acks=[]
                    for sequence in range(30):
                        p=packet();p['sequence']=sequence;raw=m.encode(p)
                        sock.sendto(raw,('127.0.0.1',m.PORT))
                        response,_=sock.recvfrom(6001);ack=m.parse(response);acks.append(ack)
                        self.assertEqual(ack['sequence'],sequence)
                        self.assertEqual(ack['received_sha256'],hashlib.sha256(raw).hexdigest())
                        time.sleep(.01)
                worker.join(2)
                self.assertFalse(worker.is_alive());self.assertFalse(errors)
                self.assertEqual(result['received'],30)
                self.assertGreater(result['display_snapshots_dropped'],5)
                self.assertLessEqual(result['display_snapshots_pending'],1)
                self.assertEqual(result['log_records_dropped'],0)
                self.assertGreater(acks[-1]['display_snapshots_dropped'],0)
                self.assertEqual(len(args.log.read_text().splitlines()),30)
            finally:release.set();worker.join(2)

    def test_slow_log_sink_is_bounded_and_reports_drops(self):
        entered=threading.Event();release=threading.Event()
        class SlowSink:
            def __init__(self):self.rows=[]
            def write(self,row):entered.set();release.wait(3);self.rows.append(json.loads(row))
            def flush(self):pass
            def close(self):pass
        sink=SlowSink();log=m.AsyncLog(None,capacity=2,sink=sink)
        try:
            log.submit(dict(n=0));self.assertTrue(entered.wait(1))
            for i in range(1,11):log.submit(dict(n=i))
            self.assertEqual(log.stats()['log_records_pending'],2)
            self.assertEqual(log.stats()['log_records_dropped'],8)
        finally:release.set();log.close(1)
        self.assertFalse(log.thread.is_alive())
        self.assertEqual([r['n'] for r in sink.rows if 'n' in r],[0,1,2])
        self.assertEqual(sink.rows[-1]['log_records_dropped'],8)

    def test_live_loopback_pairs_both_sources_then_marks_old_values_stale(self):
        # Real observation producers may still be sending to localhost:55071.
        # Use two ephemeral fixture ports; never mix live operator samples in.
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as rx_port, \
             socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as tap_port:
            rx_port.bind(('127.0.0.1',0));tap_port.bind(('127.0.0.1',0))
            fixture_port=rx_port.getsockname()[1]
            fixture_source_port=tap_port.getsockname()[1]
        bootstrap=("import importlib.util; "
            "s=importlib.util.spec_from_file_location('fixture_audit',%r); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "m.PORT=%d; m.SOURCE_PORT=%d; m.main()" %
            (str(PATH),fixture_port,fixture_source_port))
        fixture_command=[sys.executable,'-B','-c',bootstrap]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=root/'receive.jsonl';console=root/'receive.txt';sent=root/'send.txt'
            receiver=sender=None
            with console.open('w') as rout,sent.open('w') as sout:
                try:
                    receiver=subprocess.Popen(fixture_command+['receive','--bind','127.0.0.1',
                        '--seconds','3.2','--log',str(log)],stdout=rout,stderr=rout)
                    for _ in range(100):
                        if 'RECEIVE ONLY' in console.read_text():break
                        if receiver.poll() is not None:self.fail(console.read_text())
                        time.sleep(.01)
                    else:self.fail('receiver did not start')
                    sender=subprocess.Popen(fixture_command+['send-live','--host','127.0.0.1',
                        '--seconds','2.5'],stdout=sout,stderr=sout)
                    for _ in range(100):
                        if 'LIVE OBSERVATION ONLY' in sent.read_text():break
                        if sender.poll() is not None:self.fail(sent.read_text())
                        time.sleep(.01)
                    else:self.fail('live sender did not start')
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as tap:
                        for sequence in range(30):
                            for stream in ('arm','omni'):
                                p=source_packet(stream,sequence,time.monotonic())
                                tap.sendto(m.encode(p),('127.0.0.1',fixture_source_port))
                            time.sleep(.02)
                    sender.wait(4);receiver.wait(4)
                    self.assertEqual(sender.returncode,0,sent.read_text())
                    self.assertEqual(receiver.returncode,0,console.read_text())
                    rows=[json.loads(x) for x in log.read_text().splitlines()]
                    pairs=[r['packet']['payload'] for r in rows if r['kind']=='received_observation']
                    fresh=[p for p in pairs if all(p[s]['status']=='FRESH_LIVE' for s in ('arm','omni'))]
                    self.assertGreater(len(fresh),10)
                    self.assertEqual(fresh[-1]['arm']['values']['joint_indices'],list(range(15,29)))
                    self.assertEqual(fresh[-1]['arm']['values']['left_q_rad'],source_packet()['values']['left_q_rad'])
                    self.assertEqual(fresh[-1]['omni']['values']['vx'],.4)
                    self.assertTrue(all(pairs[-1][s]['status']=='STALE' for s in ('arm','omni')))
                    self.assertEqual(pairs[-1]['arm']['source_sequence'],29)
                    self.assertGreater(pairs[-1]['arm']['source_age_s'],.75)
                    sender_rows=[json.loads(x) for x in sent.read_text().splitlines() if x.startswith('{')]
                    self.assertGreater(sender_rows[-1]['ack_verified_count'],50)
                    self.assertEqual(sender_rows[-1]['source_packets_rejected'],0)
                finally:
                    for process in (sender,receiver):
                        if process is not None and process.poll() is None:
                            process.terminate();process.wait(timeout=3)


if __name__=='__main__':unittest.main()
