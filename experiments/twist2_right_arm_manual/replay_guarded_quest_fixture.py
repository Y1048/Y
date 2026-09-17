"""Saved Quest datagrams + explicitly SYNTHETIC frozen state and policy fixtures."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
from replay_cpp_receiver_log import Replay, ROOT

EXE=ROOT/'logs/test_results/test_guarded_replay.exe'
CAPTURE=ROOT/'logs/test_results/twist2_cpp_quest_raw_20260907_152430/ticks.jsonl'


def F32(x):
    return struct.unpack('f',struct.pack('f',x))[0]


def Run(path=CAPTURE,scenario='normal'):
    if scenario not in ('normal','disconnect','tilt','policy_stale','state_stale','alignment'):
        raise ValueError('unknown scenario')
    original=Replay(path)  # Reject incomplete or corrupted source evidence first.
    rows=[json.loads(x) for x in Path(path).read_text().splitlines()]
    ticks=[r for r in rows if r['event']=='tick']
    baseline=next(r['baseline'] for r in ticks if r['baseline'] is not None)
    baseline=list(baseline)
    if scenario=='alignment': baseline[22]+=.05
    config=dict(fixture_source='synthetic_state_and_policy_not_g1',baseline=baseline)
    events=[]; expected=[]; pending=[]; started=False; fault_index=None
    for row in rows:
        if row['event']=='packet':
            pending.append(dict(hex=row['payload_hex'],at=row['received_at_s']))
        elif row['event']=='tick':
            index=len(events)
            action=[.02*math.sin(index*.05+i) for i in range(29)]
            event=dict(now=row['now_s'],action=action,packets=pending,fault='')
            pending=[]
            if started and fault_index is None and scenario in ('disconnect','tilt','policy_stale','state_stale'):
                fault_index=index
            if fault_index is not None:
                if scenario=='disconnect': event['packets']=[]
                elif index==fault_index: event['fault']=scenario
            events.append(event);expected.append(row)
            started=started or row['mode']=='active'
    result=subprocess.run([str(EXE)],input=''.join(json.dumps(x)+'\n' for x in [config,*events]),
                          text=True,capture_output=True,check=True,timeout=20)
    actual=[json.loads(x) for x in result.stdout.splitlines()]
    if len(actual)!=len(events): raise ValueError('output count')
    reasons=dict(normal='input_disengaged',disconnect='receiver_timeout',tilt='attitude_limit',
                 policy_stale='policy_time',state_stale='stale_or_invalid_state_time',alignment='initial_arm_mismatch')
    latched=None; active_count=0; legs_changed=False; previous=baseline; last_time=0
    default=[-.2,0,0,.4,-.2,0]*2
    lower=[-2.5307,-.5236,-2.7576,-.087267,-.87267,-.2618,-2.5307,-2.9671,-2.7576,-.087267,-.87267,-.2618]
    upper=[2.8798,2.9671,2.7576,2.8798,.5236,.2618,2.8798,.5236,2.7576,2.8798,.5236,.2618]
    for event,row,source in zip(events,actual,expected):
        if latched is not None and (row['reason']!=latched or row['candidate'] is not None):
            raise ValueError('resumed after stop')
        if row['mode']=='stopped': latched=row['reason']
        q=row['candidate']
        if q is not None:
            if not all(math.isfinite(x) for x in q) or q[12:22]!=baseline[12:22]:
                raise ValueError('held joints/finite')
            for i in range(12):
                decoded=F32(F32(default[i])+F32(F32(.5)*F32(event['action'][i])))
                goal=max(F32(F32(lower[i])+F32(.05)),min(F32(F32(upper[i])-F32(.05)),decoded))
                if q[i]!=goal: raise ValueError('policy motor mapping')
            legs_changed=legs_changed or q[:12]!=previous[:12]
            if scenario=='normal' and q[12:]!=source['q'][12:]:
                raise ValueError('recorded upper candidate mismatch')
            if row['mode']=='active':
                active_count+=1
                goal=source['validated_goal']
                bound=.08*min(event['now']-last_time,.02)+1e-12
                for a,b,g in zip(previous[22:],q[22:],goal):
                    if abs(b-a)>bound or not min(a,g)-1e-12<=b<=max(a,g)+1e-12:
                        raise ValueError('rate/overshoot')
            elif q[22:]!=previous[22:]: raise ValueError('arm moved without input')
            previous=q
        last_time=event['now']
    for event,row in zip(events,actual):
        row.update(now_s=event['now'],fixture_source=config['fixture_source'],hardware_output_authorized=False)
    if latched!=reasons[scenario]: raise ValueError(f'unexpected stop {latched}')
    if scenario=='normal' and (active_count!=original['active_ticks'] or not legs_changed):
        raise ValueError('missing active motion or leg composition')
    return dict(passed=True,scenario=scenario,active_ticks=active_count,reason=latched,
                source_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                fixture_source=config['fixture_source'],state_model='frozen_virtual_baseline',
                crc_source='synthetic_true_assertion_not_raw_crc',policy_source='synthetic_sine_not_inference',
                recorded_upper_match_checked=scenario=='normal',hardware_output_authorized=False,
                robot_safety_validated=False),actual


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    reports=[]
    for scenario in ('normal','disconnect','tilt','policy_stale','state_stale','alignment'):
        report,rows=Run(scenario=scenario)
        (args.output/(scenario+'.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
        reports.append(report)
    (args.output/'result.json').write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(reports,indent=2))
