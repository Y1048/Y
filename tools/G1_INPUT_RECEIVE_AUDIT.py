"""Observation-only PC -> G1 UDP audit. Never uses control ports, SDK or DDS.

Deploy this single file on G1 for `receive`. `send` uses the existing PC log
monitor helper beside this file. `send-live` listens for local, fresh observation
taps; neither mode is an arm/velocity command protocol.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import time
import uuid

PORT = 55070
SOURCE_PORT = 55071
SCHEMA = 'g1.observation.audit.v1'
ACK_SCHEMA = 'g1.observation.audit.ack.v1'
SOURCE_SCHEMA = 'g1.observation.source.v1'
STATUSES = {'WAIT','INVALID','HISTORICAL','CLOCK_MISMATCH','FRESH_LOG','FRESH_LIVE','STALE'}
FRESHNESS_S = .75
JOINT_NAMES = [side+'_'+joint+'_joint' for side in ('left','right') for joint in
               ('shoulder_pitch','shoulder_roll','shoulder_yaw','elbow',
                'wrist_roll','wrist_pitch','wrist_yaw')]


def _stdout_line(line):
    # A blocked OS pipe must not hold Python's buffered stdout lock at shutdown.
    raw=(line+'\n').encode('utf-8',errors='backslashreplace')
    fd=sys.stdout.fileno()
    while raw:
        written=os.write(fd,raw)
        if written<=0:raise OSError('stdout write returned zero')
        raw=raw[written:]


class LatestOutput:
    """Paced latest-value display; repetition never creates a new source sample."""
    def __init__(self, banner='', writer=None, hz=100.):
        if not math.isfinite(hz) or not 1<=hz<=100:raise ValueError('display Hz must be 1..100')
        self.writer=writer or _stdout_line
        self.hz=hz
        self.queue=queue.Queue(maxsize=1)
        self.stop=threading.Event()
        self.dropped=0
        self.written=0
        self.intervals_skipped=0
        self.revision=0
        self.error=None
        self.thread=threading.Thread(target=self._run,args=(banner,),daemon=True)
        self.thread.start()

    def submit(self, snapshot):
        self.revision+=1
        item=(self.revision,time.monotonic(),snapshot)
        try:self.queue.put_nowait(item)
        except queue.Full:
            try:self.queue.get_nowait();self.dropped+=1
            except queue.Empty:pass
            try:self.queue.put_nowait(item)
            except queue.Full:self.dropped+=1

    def stats(self):
        return dict(display_snapshots_dropped=self.dropped,
                    display_snapshots_written=self.written,
                    display_snapshots_pending=self.queue.qsize(),
                    display_intervals_skipped=self.intervals_skipped,
                    display_target_hz=self.hz,display_error=self.error)

    def _run(self, banner):
        try:
            if banner:self.writer(banner)
            deadline=time.perf_counter()
            latest=None
            last_revision=None
            while not self.stop.is_set() or not self.queue.empty():
                delay=deadline-time.perf_counter()
                if delay>0 and not self.stop.is_set():
                    time.sleep(min(delay,.01))
                    continue
                try:latest=self.queue.get_nowait()
                except queue.Empty:pass
                if latest is not None:
                    revision,submitted,snapshot=latest
                    now=time.monotonic()
                    row=display_view(snapshot,now,submitted)
                    row.update(self.stats())
                    row.update(display_sequence=self.written,display_monotonic_s=now,
                               display_repeated_snapshot=revision==last_revision)
                    self.writer(json.dumps(row,allow_nan=False,separators=(',',':')))
                    self.written+=1
                    last_revision=revision
                deadline+=1./self.hz
                finished=time.perf_counter()
                if deadline<=finished:
                    # Skip missed intervals. Never burst stale display frames after a stall.
                    self.intervals_skipped+=int((finished-deadline)*self.hz)+1
                    deadline=finished+1./self.hz
        except (OSError,ValueError) as exc:
            self.error=str(exc)

    def close(self, timeout=.10):
        self.stop.set()
        self.thread.join(timeout)


def _aged_payload(payload, elapsed, local_source_now=None):
    result={}
    for name,stream in payload.items():
        updated=dict(stream)
        for key in ('source_age_s','source_receive_age_s'):
            value=updated.get(key)
            if type(value) in (int,float):updated[key]=value+elapsed
        source_stamp=(updated.get('values') or {}).get('source_monotonic_s')
        if local_source_now is not None and type(source_stamp) in (int,float):
            updated['source_age_s']=local_source_now-source_stamp
        if updated.get('status') in ('FRESH_LOG','FRESH_LIVE'):
            ages=[updated.get(k) for k in ('source_age_s','source_receive_age_s')]
            if any(type(age) in (int,float) and age>FRESHNESS_S for age in ages):
                updated['status']='STALE'
        # Preserve original values/source sequence; annotate Unity age separately.
        values=updated.get('values') or {}
        unity_age=values.get('unity_input_age_s')
        if type(unity_age) in (int,float):
            source_age=updated.get('source_age_s')
            age=unity_age+(max(0.,source_age) if type(source_age) in (int,float) else elapsed)
            updated['display_unity_input_age_s']=age
            updated['display_unity_input_status']='FRESH' if age<=FRESHNESS_S else 'STALE'
        elif 'unity_input_status' in values:
            updated['display_unity_input_status']=values['unity_input_status']
            updated['display_unity_input_age_s']=None
        result[name]=updated
    return result


def display_view(snapshot, now, submitted):
    """Age the display copy only. Received bytes/hash and source logs stay untouched."""
    row=dict(snapshot)
    if 'rx' in row:
        latest=row.get('latest')
        if latest is not None:
            elapsed=max(0.,now-latest['receiver_monotonic_s'])
            row['receiver_age_s']=elapsed
            row['rx']='RECEIVED' if elapsed<=FRESHNESS_S else 'STALE'
            row['display_payload']=_aged_payload(latest['packet']['payload'],elapsed)
            row['display_source_age_basis']='PC_report_plus_G1_elapsed_transport_delay_unmeasured'
    elif 'payload' in row:
        elapsed=max(0.,now-row.get('snapshot_monotonic_s',submitted))
        row['display_payload']=_aged_payload(row['payload'],elapsed,local_source_now=now)
        row['display_source_age_basis']='PC_snapshot_plus_PC_elapsed'
    if 'latest_ack' in row:
        ack=row['latest_ack']
        row['receiver_status']='WAIT_ACK' if ack is None else (
            'ACK_CONFIRMED' if now-ack['ack_at']<=FRESHNESS_S else 'ACK_STALE')
    return row


class AsyncLog:
    """Bounded log queue; receipt ACK does not imply durable log persistence."""
    def __init__(self, path, capacity=256, sink=None):
        self.sink=sink or path.open('x',encoding='utf-8')
        self.queue=queue.Queue(maxsize=capacity)
        self.stop=threading.Event()
        self.dropped=0
        self.written=0
        self.error=None
        self.thread=threading.Thread(target=self._run,daemon=True)
        self.thread.start()

    def submit(self, row):
        if self.error is not None:
            self.dropped+=1
            return
        try:self.queue.put_nowait(row)
        except queue.Full:self.dropped+=1

    def stats(self):
        return dict(log_records_dropped=self.dropped,log_records_written=self.written,
                    log_records_pending=self.queue.qsize(),log_error=self.error)

    def _run(self):
        last_flush=time.monotonic()
        unflushed=0
        try:
            while not self.stop.is_set() or not self.queue.empty():
                try:row=self.queue.get(timeout=.02)
                except queue.Empty:row=None
                if row is not None:
                    self.sink.write(json.dumps(row,allow_nan=False)+'\n')
                    self.written+=1
                    unflushed+=1
                if unflushed and (unflushed>=64 or time.monotonic()-last_flush>=.10):
                    self.sink.flush();last_flush=time.monotonic();unflushed=0
            if self.dropped:
                self.sink.write(json.dumps(dict(kind='log_summary',**self.stats()),allow_nan=False)+'\n')
            self.sink.flush()
        except (OSError,ValueError) as exc:
            self.error=str(exc)
        finally:
            try:self.sink.close()
            except (OSError,ValueError):pass

    def close(self, timeout=.50):
        self.stop.set()
        self.thread.join(timeout)


def exclusive_bind(sock, address):
    if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
    try:sock.bind(address)
    except OSError as exc:
        raise OSError('Cannot bind observation UDP %s:%d. Check the existing owner; '
                      'do not launch duplicate receivers or terminate unrelated processes. %s'
                      % (address[0],address[1],exc)) from exc


def encode(packet):
    return json.dumps(packet,allow_nan=False,separators=(',',':')).encode('utf-8')


def parse(raw):
    if len(raw)>6000:
        raise ValueError('packet_size')
    def constant(_):
        raise ValueError('nonfinite')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate_key')
            result[k]=v
        return result
    result=json.loads(raw,parse_constant=constant,object_pairs_hook=pairs)
    if not isinstance(result,dict):raise ValueError('object_required')
    def check(x,depth=0):
        if depth>8:raise ValueError('depth')
        if isinstance(x,float) and not math.isfinite(x):raise ValueError('nonfinite')
        if isinstance(x,dict):
            for value in x.values():check(value,depth+1)
        if isinstance(x,list):
            for value in x:check(value,depth+1)
    check(result)
    return result


def validate(packet):
    if packet.get('schema')!=SCHEMA or packet.get('observation_only') is not True:
        raise ValueError('observation_schema')
    session=packet.get('session')
    if not isinstance(session,str) or len(session)!=32 or any(c not in '0123456789abcdef' for c in session):
        raise ValueError('session')
    seq=packet.get('sequence')
    if type(seq) is not int or not 0<=seq<2**53:raise ValueError('sequence')
    payload=packet.get('payload')
    if not isinstance(payload,dict):raise ValueError('payload')
    for key in ('arm','omni'):
        stream=payload.get(key)
        if not isinstance(stream,dict) or stream.get('status') not in STATUSES:
            raise ValueError('stream_status')
        values=stream.get('values')
        if values is None:
            if stream['status'] not in ('WAIT','INVALID'):raise ValueError('missing_values')
            continue
        if not isinstance(values,dict):raise ValueError('values')
        fields=('left_q_rad','right_q_rad') if key=='arm' else ('vx','vy','yaw_rate')
        for field in fields:
            v=values.get(field)
            array=v if key=='arm' else [v]
            if (not isinstance(array,list) or len(array)!=(7 if key=='arm' else 1)
                    or any(type(x) not in (int,float) or not math.isfinite(x) for x in array)):
                raise ValueError('invalid_'+field)
    return packet


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def _sequence(value):
    return type(value) is int and 0<=value<2**53


def validate_source(packet):
    if (packet.get('schema')!=SOURCE_SCHEMA or packet.get('observation_only') is not True
            or packet.get('stream') not in ('arm','omni')):
        raise ValueError('source_schema')
    session=packet.get('session')
    if (not isinstance(session,str) or len(session)!=32
            or any(c not in '0123456789abcdef' for c in session)):
        raise ValueError('source_session')
    if not _sequence(packet.get('sequence')):raise ValueError('source_sequence')
    stamp=packet.get('source_monotonic_s')
    if not _finite(stamp) or stamp<0:raise ValueError('source_timestamp')
    values=packet.get('values')
    if not isinstance(values,dict):raise ValueError('source_values')
    if packet['stream']=='arm':
        if values.get('joint_names')!=JOINT_NAMES:
            raise ValueError('source_joint_names')
        indices=values.get('joint_indices')
        if (indices!=list(range(15,29)) or any(type(x) is not int for x in indices)):
            raise ValueError('source_joint_indices')
        for key in ('left_q_rad','right_q_rad'):
            q=values.get(key)
            if not isinstance(q,list) or len(q)!=7 or not all(_finite(x) for x in q):
                raise ValueError('source_'+key)
        if values.get('state') not in ('ready','tracking','returning','blocked'):
            raise ValueError('source_arm_state')
        if not isinstance(values.get('reason'),str) or len(values['reason'])>512:
            raise ValueError('source_arm_reason')
        source_session=values.get('session')
        waiting=(values['state']=='ready' and source_session is None
                 and type(values.get('sequence')) is int and values['sequence']==-1
                 and values.get('unity_input_status')=='WAIT'
                 and 'unity_input_age_s' in values and values['unity_input_age_s'] is None)
        identity=(isinstance(source_session,str) and 1<=len(source_session)<=128
                  and _sequence(values.get('sequence')))
        if not (waiting or identity) or not _sequence(values.get('feedback_sequence')):
            raise ValueError('source_arm_identity')
    else:
        for key in ('mx','my','arm_yaw_deg','omni_yaw_rate_deg_s','vx','vy',
                    'yaw_rate','yaw_diff_deg','yaw_step_diff_deg'):
            if not _finite(values.get(key)):raise ValueError('source_'+key)
        if type(values.get('calibrated')) is not bool:raise ValueError('source_calibrated')
    return packet


class LiveSources:
    """Local source clocks only. Snapshot resends never refresh source age."""
    def __init__(self):
        self.latest={}
        self.retired={stream:set() for stream in ('arm','omni')}
        self.accepted={stream:0 for stream in ('arm','omni')}
        self.rejected=0
        self.last_rejection=None

    def accept(self, raw, peer, now):
        try:
            if peer[0]!='127.0.0.1':raise ValueError('source_peer')
            packet=validate_source(parse(raw))
            stream=packet['stream'];stamp=packet['source_monotonic_s']
            if stamp>now:raise ValueError('source_future_clock')
            previous=self.latest.get(stream)
            if packet['session'] in self.retired[stream]:
                raise ValueError('source_retired_session')
            if previous is not None:
                old=previous['packet']
                # Windows source clocks may quantize distinct samples to one tick.
                # Sequence still advances; unchanged source time cannot renew freshness.
                if stamp<old['source_monotonic_s']:
                    raise ValueError('source_nonmonotonic_timestamp')
                if packet['session']==old['session']:
                    if peer!=previous['peer']:raise ValueError('source_session_peer_changed')
                    if packet['sequence']<=old['sequence']:raise ValueError('source_reordered')
                else:
                    if len(self.retired[stream])>=64:raise ValueError('source_session_capacity')
                    self.retired[stream].add(old['session'])
            self.latest[stream]=dict(packet=packet,peer=peer,accepted_at=now)
            self.accepted[stream]+=1
            return True
        except (ValueError,TypeError,RecursionError,UnicodeError) as exc:
            self.rejected+=1;self.last_rejection=str(exc)
            return False

    def snapshot(self, stream, now):
        latest=self.latest.get(stream)
        if latest is None:
            return dict(status='WAIT',source_age_s=None,values=None)
        packet=latest['packet']
        source_age=now-packet['source_monotonic_s']
        receive_age=now-latest['accepted_at']
        status=('CLOCK_MISMATCH' if min(source_age,receive_age)<0 else
                'FRESH_LIVE' if max(source_age,receive_age)<=FRESHNESS_S else 'STALE')
        values=dict(packet['values'],source_monotonic_s=packet['source_monotonic_s'])
        return dict(status=status,source_age_s=source_age,source_receive_age_s=receive_age,
                    source_session=packet['session'],source_sequence=packet['sequence'],
                    source_accepted_count=self.accepted[stream],values=values)


def matching_ack(raw, peer, target, session, pending):
    ack=parse(raw)
    seq=ack.get('sequence')
    if (peer!=target or ack.get('schema')!=ACK_SCHEMA or ack.get('session')!=session
            or type(seq) is not int or seq not in pending):
        return None
    sent, digest=pending[seq]
    if ack.get('received_sha256')!=digest or ack.get('motor_acceptance')!='NOT_CHECKED':
        return None
    return seq,sent,ack


def receiver_view(**fields):
    """The mock observes external targets; it never reads G1 q or commands C++."""
    return dict(fields,controller_role='INPUT_RECEIVER_MOCK',initial_g1_q_rad=None,
                initial_g1_q_status='NOT_MEASURED',cpp_command_sent=False)


def receive(args, output_writer=None):
    log_path=args.log or Path('input_receive_'+time.strftime('%Y%m%d_%H%M%S')+'.jsonl')
    log_path.parent.mkdir(parents=True,exist_ok=True)
    start=last_packet=time.monotonic()
    latest=None
    sessions={}
    count=rejected=0
    print_hz=getattr(args,'print_hz',100.)
    reported=None
    output=log=None
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        exclusive_bind(sock,(args.bind,PORT))
        sock.settimeout(.002)
        log=AsyncLog(log_path)
        if print_hz:
            output=LatestOutput('RECEIVE ONLY UDP 55070; no SDK/DDS/motor output. '
                                'Ctrl+C exits safely.\nLOG '+str(log_path.resolve()),output_writer,hz=print_hz)
        try:
            while not args.seconds or time.monotonic()-start<args.seconds:
                try:
                    raw,peer=sock.recvfrom(6001)
                    now=time.monotonic()
                    try:
                        if args.allow_peer and peer[0]!=args.allow_peer:raise ValueError('peer')
                        packet=validate(parse(raw))
                        key=(peer,packet['session'])
                        if key not in sessions:
                            if len(sessions)>=16:raise ValueError('session_capacity_restart_receiver')
                            sessions[key]=-1
                        previous=sessions[key]
                        sequence=packet['sequence']
                        gap=max(0,sequence-previous-1)
                        ordered=sequence>previous
                        sessions[key]=max(previous,sequence)
                        count+=1
                        digest=hashlib.sha256(raw).hexdigest()
                        latest=receiver_view(kind='received_observation',receiver_monotonic_s=now,
                            peer=list(peer),receive_count=count,ordered=ordered,
                            missing_before_this_packet=gap,received_sha256=digest,packet=packet,
                            motor_acceptance='NOT_CHECKED',**log.stats())
                        log.submit(latest)
                        # ACK proves receipt of exactly these bytes, never persistence/actuation.
                        ack=dict(schema=ACK_SCHEMA,session=packet['session'],sequence=sequence,
                            received_sha256=digest,receive_count=count,receiver_monotonic_s=now,
                            motor_acceptance='NOT_CHECKED',**log.stats())
                        if output:ack.update(output.stats())
                        sock.sendto(encode(ack),peer)
                        last_packet=now
                    except (ValueError,TypeError,RecursionError,UnicodeError) as exc:
                        rejected+=1
                        log.submit(receiver_view(kind='reject',reason=str(exc),peer=list(peer)))
                except socket.timeout:
                    pass
                now=time.monotonic()
                revision=(count,rejected,log.dropped,log.error)
                if output and revision!=reported:
                    output.submit(receiver_view(rx='WAIT' if latest is None else
                        ('RECEIVED' if now-last_packet<=FRESHNESS_S else 'STALE'),
                        receiver_age_s=None if latest is None else now-last_packet,
                        rejected=rejected,latest=latest,**log.stats()))
                    reported=revision
        finally:
            log.close()
            if output:output.close()
    return dict(received=count,rejected=rejected,**log.stats(),
                **(output.stats() if output else {}))


def _send_snapshots(args, snapshot, banner, source_stats=None, default_send_hz=50.):
    target=(socket.gethostbyname(args.host),PORT)
    session=uuid.uuid4().hex
    pending={}
    sequence=confirmed=0
    last_ack=None
    print_hz=getattr(args,'print_hz',100.)
    send_hz=getattr(args,'send_hz',None) or default_send_hz
    start=time.monotonic()
    deadline=time.perf_counter()
    output=LatestOutput(banner+' -> %s:%d; not a motor command. ACK proves this receiver only.'%target,
                        hz=print_hz) if print_hz else None
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.bind(('0.0.0.0',0));sock.setblocking(False)
            while not args.seconds or time.monotonic()-start<args.seconds:
                now=time.monotonic()
                payload=snapshot(now)
                now=time.monotonic()
                packet=dict(schema=SCHEMA,observation_only=True,session=session,sequence=sequence,
                    payload=payload)
                validate(packet)
                raw=encode(packet)
                if len(raw)>6000:raise ValueError('packet_budget')
                sock.sendto(raw,target)
                pending[sequence]=(now,hashlib.sha256(raw).hexdigest())
                pending={k:v for k,v in pending.items() if now-v[0]<2}
                for _ in range(128):
                    try:ack_raw,peer=sock.recvfrom(6001)
                    except (BlockingIOError,ConnectionResetError):break
                    try:match=matching_ack(ack_raw,peer,target,session,pending)
                    except (ValueError,TypeError,RecursionError,UnicodeError):continue
                    if match:
                        seq,sent,ack=match
                        pending.pop(seq,None);confirmed+=1
                        last_ack=dict(sequence=seq,rtt_ms=(time.monotonic()-sent)*1000,
                            ack_at=time.monotonic(),received_sha256=ack['received_sha256'],
                            receiver_log_records_dropped=ack.get('log_records_dropped'),
                            receiver_display_snapshots_dropped=ack.get('display_snapshots_dropped'))
                if output:
                    report=dict(tx_sequence=sequence,ack_verified_count=confirmed,
                        receiver_status='WAIT_ACK' if last_ack is None else
                            ('ACK_CONFIRMED' if now-last_ack['ack_at']<=FRESHNESS_S else 'ACK_STALE'),
                        latest_ack=last_ack,payload=packet['payload'],motor_acceptance='NOT_CHECKED',
                        snapshot_monotonic_s=now,send_target_hz=send_hz)
                    if source_stats:report.update(source_stats())
                    output.submit(report)
                sequence+=1
                deadline+=1./send_hz
                current=time.perf_counter()
                if deadline<=current:deadline=current+1./send_hz
                time.sleep(max(0.,deadline-time.perf_counter()))
    finally:
        if output:output.close()
    return dict(sent=sequence,ack_verified_count=confirmed,latest_ack=last_ack,send_target_hz=send_hz)


def send(args):
    spec=importlib.util.spec_from_file_location('console_monitor',Path(__file__).with_name('PRINT_G1_INPUTS_50HZ.py'))
    monitor=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(monitor)
    arm,omni=monitor.LogTail('arm'),monitor.LogTail('omni')
    scan=[-math.inf]
    def snapshot(now):
        if now-scan[0]>=1:
            arm.select(monitor.newest(args.root,('logs/test_results/bimanual/unity_*.jsonl',)))
            omni.select(monitor.newest(args.root,('logs/test_results/omni_timeseries/*.csv',
                                                'logs/test_results/omni_gateway_readonly/*.csv')))
            scan[0]=now
        arm.poll(now);omni.poll(now)
        now=time.monotonic()
        return dict(arm=arm.snapshot(now),omni=omni.snapshot(now))
    try:return _send_snapshots(args,snapshot,'OBSERVATION LOG COPY ONLY')
    finally:arm.close();omni.close()


def send_live(args):
    sources=LiveSources()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as inbound:
        exclusive_bind(inbound,('127.0.0.1',SOURCE_PORT))
        inbound.setblocking(False)
        if hasattr(socket,'SIO_UDP_CONNRESET'):
            inbound.ioctl(socket.SIO_UDP_CONNRESET,False)
        def snapshot(now):
            # Bound work even if a faulty local producer floods the observation tap.
            for _ in range(256):
                try:raw,peer=inbound.recvfrom(6001)
                except (BlockingIOError,ConnectionResetError):break
                sources.accept(raw,peer,time.monotonic())
            now=time.monotonic()
            return {stream:sources.snapshot(stream,now) for stream in ('arm','omni')}
        def stats():
            return dict(source_packets_rejected=sources.rejected,
                        last_source_rejection=sources.last_rejection)
        return _send_snapshots(args,snapshot,
            'LIVE OBSERVATION ONLY; source taps 127.0.0.1:55071',stats,default_send_hz=60.)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('send','send-live','receive'))
    parser.add_argument('--host',default='192.168.123.164')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bind',default='0.0.0.0')
    parser.add_argument('--allow-peer')
    parser.add_argument('--log',type=Path)
    parser.add_argument('--seconds',type=float,default=0)
    parser.add_argument('--print-hz',type=float,default=100.,
                        help='independent display target 1..100 Hz, or 0 to disable stdout')
    parser.add_argument('--send-hz',type=float,default=None,
                        help='observation UDP target 1..100 Hz; send-live default 60, log-copy default 50')
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<0:parser.error('invalid seconds')
    if not math.isfinite(args.print_hz) or not (args.print_hz==0 or 1<=args.print_hz<=100):
        parser.error('print-hz must be 0 or between 1 and 100')
    if args.send_hz is not None and (not math.isfinite(args.send_hz) or not 1<=args.send_hz<=100):
        parser.error('send-hz must be between 1 and 100')
    try:
        {'send':send,'send-live':send_live,'receive':receive}[args.mode](args)
    except KeyboardInterrupt:
        # Do not synchronously write into the same blocked terminal on shutdown.
        if args.print_hz:
            output=LatestOutput('Observation audit stopped; no motor controller was changed.')
            output.close()


if __name__=='__main__':main()
