"""Compare aligned offline IK traces; no robot, solver, or PD optimization."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def load(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema')!='g1.ik.target_trace.v1':raise ValueError('unsupported trace schema')
    rows=data['samples']
    if len(rows)<3:raise ValueError('at least three samples required')
    previous=-1.;index=-1
    for row in rows:
        t=row['elapsed_s'];seq=row['input_index'];q=row['q_rad']
        if not isinstance(seq,int) or isinstance(seq,bool) or seq<=index:raise ValueError('input indices must increase')
        if not isinstance(t,(int,float)) or not math.isfinite(t) or t<0 or t<=previous:raise ValueError('invalid time')
        if len(q)!=29 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in q):raise ValueError('invalid joint vector')
        previous,index=t,seq
    return data


def compare(a,b,input_sha,speed,acceleration,position_delta):
    for value in (speed,acceleration,position_delta):
        if not math.isfinite(value) or value<=0:raise ValueError('positive thresholds required')
    for key in ('input_sha256','model_sha256','stage','initial_q_rad','right_lower_rad','right_upper_rad'):
        if a[key]!=b[key]:raise ValueError('comparison context differs: '+key)
    if a['input_sha256']!=input_sha:raise ValueError('input file hash mismatch')
    for data in (a,b):
        if not data.get('ik_version'):raise ValueError('IK version missing')
    if len(a['samples'])!=len(b['samples']):raise ValueError('sample count differs')
    for x,y in zip(a['samples'],b['samples']):
        if x['input_index']!=y['input_index'] or abs(x['elapsed_s']-y['elapsed_s'])>1e-9:
            raise ValueError('input/time alignment differs; implicit interpolation forbidden')
    lo,hi=a['right_lower_rad'],a['right_upper_rad']
    if len(lo)!=7 or len(hi)!=7 or not all(math.isfinite(l) and math.isfinite(h) and l<h for l,h in zip(lo,hi)):
        raise ValueError('invalid right-arm limits')
    times=[r['elapsed_s'] for r in a['samples']];dt=[y-x for x,y in zip(times,times[1:])]
    def metrics(data,j):
        q=[r['q_rad'][j] for r in data['samples']]
        v=[(y-x)/d for x,y,d in zip(q,q[1:],dt)]
        accel=[(v[i+1]-v[i])/((dt[i]+dt[i+1])/2) for i in range(len(v)-1)]
        violations=[]
        for i,x in enumerate(v):
            if abs(x)>speed+1e-9:violations.append({'kind':'speed','from_s':times[i],'to_s':times[i+1]})
        for i,x in enumerate(accel):
            if abs(x)>acceleration+1e-8:violations.append({'kind':'acceleration','from_s':times[i],'to_s':times[i+2]})
        return dict(range_rad=max(q)-min(q),travel_rad=sum(abs(y-x) for x,y in zip(q,q[1:])),
                    peak_speed_rad_s=max(map(abs,v)),peak_acceleration_rad_s2=max(map(abs,accel)),
                    minimum_limit_margin_rad=min(min(x-lo[j-22],hi[j-22]-x) for x in q),violations=violations)
    joints=[]
    for j in range(22,29):
        differences=[abs(x['q_rad'][j]-y['q_rad'][j]) for x,y in zip(a['samples'],b['samples'])]
        before,after=metrics(a,j),metrics(b,j)
        changed=[times[i] for i,d in enumerate(differences) if d>position_delta]
        joints.append(dict(joint=j,max_position_difference_rad=max(differences),before=before,after=after,
            changed_sample_times_s=changed,review_required=bool(changed or after['violations'] or after['minimum_limit_margin_rad']<0)))
    return dict(schema='g1.ik.comparison.v1',offline_only=True,versions=[a['ik_version'],b['ik_version']],
        input_sha256=input_sha,samples=len(times),max_gap_s=max(dt),
        thresholds=dict(speed_rad_s=speed,acceleration_rad_s2=acceleration,position_difference_rad=position_delta),
        other_joint_max_difference_rad=max(abs(x['q_rad'][j]-y['q_rad'][j]) for x,y in zip(a['samples'],b['samples']) for j in range(22)),
        joints=joints,limitations='Sample differences only; peaks between samples and collisions untested. Discontinuity is not distinguishable from fast motion at this sampling rate. Review flags do not prove PD retuning is necessary or certify safety. Trace input association is producer-declared; the input file hash is verified.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--speed',required=True,type=float);p.add_argument('--acceleration',required=True,type=float)
    p.add_argument('--position-delta',default=.05,type=float)
    args=p.parse_args();result=compare(load(args.before),load(args.after),hashlib.sha256(args.input.read_bytes()).hexdigest(),args.speed,args.acceleration,args.position_delta)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'samples':result['samples'],'review_joints':[j['joint'] for j in result['joints'] if j['review_required']]}))
