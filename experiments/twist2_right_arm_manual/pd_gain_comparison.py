"""Offline candidate design and gated comparison. Never applies gains or runs G1."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidates(joint=22):
    if joint not in range(22,29):raise ValueError('right-arm joint required')
    header=ROOT/'references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp'
    text=header.read_text()
    def gains(name):
        match=re.search(r'\b'+name+r'\s*=\s*\{([^}]+)\}',text)
        values=[float(x.strip()) for x in match[1].split(',') if x.strip()]
        if len(values)!=29 or not all(math.isfinite(x) and x>0 for x in values):raise ValueError('invalid baseline gains')
        return values
    kp,kd=gains('kKp'),gains('kKd')
    reference=Path(__file__).with_name('pd_reach_reference.hpp')
    move=float(re.search(r'move_seconds=([0-9.eE+-]+)',reference.read_text())[1])
    items=[]
    for p in (.8,1.,1.2):
        for d in (.8,1.,1.2):
            pg,dg=kp.copy(),kd.copy();pg[joint]*=p;dg[joint]*=d
            items.append(dict(id=f'p{p:g}_d{d:g}',kp=pg,kd=dg,baseline=p==d==1))
    return dict(schema='pd_gain_plan.v1',offline_only=True,hardware_approved=False,
        joint=joint,source_sha256=sha(header),
        reference_sha256=sha(reference),move_seconds=move,
        speed_cap_deg_s=45,acceleration_cap_rad_s2=10,
        candidates=items,
        limits={'max_error_rad':None,'max_tau_est_nm':None,'max_hold_rms_speed_rad_s':None},
        note='Proposed local grid, not approved hardware gains. Fix limits before collecting trials.')


def evaluate(plan,run):
    limits=plan['limits']
    for key in ('max_error_rad','max_tau_est_nm','max_hold_rms_speed_rad_s'):
        value=limits.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('predeclared positive evaluation limit required: '+key)
    candidate=next(c for c in plan['candidates'] if c['id']==run['candidate_id'])
    if run['reference_sha256']!=plan['reference_sha256']:raise ValueError('reference mismatch')
    if run['termination_reason']!='pd trial completed':raise ValueError('incomplete/stopped trial cannot rank')
    if sha(run['csv'])!=run['csv_sha256']:raise ValueError('CSV hash mismatch')
    move=float(run['move_seconds'])
    if not math.isfinite(move) or move<=0:raise ValueError('invalid move duration')
    if abs(move-plan['move_seconds'])>1e-9:raise ValueError('duration differs from fixed reference')
    groups={};last_sequence=0;last_time=-math.inf
    with Path(run['csv']).open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row['writer_valid']!='1':continue
            sequence=int(row['writer_sequence'])
            if sequence==last_sequence:continue
            if sequence<=last_sequence:raise ValueError('writer sequence reversed')
            t=float(row['writer_write_returned_s'])
            if not math.isfinite(t) or t<=last_time:raise ValueError('writer time invalid')
            last_sequence,last_time=sequence,t
            phase=int(row['writer_trial_phase']);cycle=int(row['writer_trial_cycle'])
            if phase not in (2,3,4,5):continue
            if cycle not in (0,1,2):raise ValueError('unexpected cycle')
            for i in range(29):
                for name in ('kp','kd'):
                    v=float(row[f'writer_{name}_{i}'])
                    if not math.isfinite(v) or abs(v-candidate[name][i])>1e-5:
                        raise ValueError('effective gains differ from candidate')
            i=plan['joint']
            q,target,dq,tau=(float(row[f'writer_{name}_{i}']) for name in ('q','target','dq','tau_est'))
            if not all(math.isfinite(v) for v in (q,target,dq,tau)):raise ValueError('non-finite sample')
            groups.setdefault((cycle,phase),[]).append((t,q-target,dq,tau))
    scores=[];peak_error=peak_tau=hold_rms=0.
    for cycle in range(3):
        integral=duration=0.
        for phase in (2,3,4,5):
            rows=groups.get((cycle,phase),[]);expected=move if phase in (2,4) else 1.
            if len(rows)<2 or rows[-1][0]-rows[0][0]<expected-.06 or rows[-1][0]-rows[0][0]>expected+.06:
                raise ValueError('missing/truncated phase coverage')
            energy=span=0.
            for a,b in zip(rows,rows[1:]):
                dt=b[0]-a[0]
                if dt<=0 or dt>.06:raise ValueError('sampling gap')
                energy+=dt*(a[2]**2+b[2]**2)/2;span+=dt
                if phase in (2,4):integral+=dt*(a[1]**2+b[1]**2)/2;duration+=dt
            if phase in (3,5):hold_rms=max(hold_rms,math.sqrt(energy/span))
            peak_error=max(peak_error,max(abs(r[1]) for r in rows))
            peak_tau=max(peak_tau,max(abs(r[3]) for r in rows))
        scores.append(math.sqrt(integral/duration))
    violations=[]
    for key,value in [('max_error_rad',peak_error),('max_tau_est_nm',peak_tau),('max_hold_rms_speed_rad_s',hold_rms)]:
        if value>limits[key]:violations.append(key)
    return dict(candidate_id=candidate['id'],eligible=not violations,violations=violations,
        cycle_rms_error_rad=scores,mean_cycle_rms_error_rad=sum(scores)/3,
        max_error_rad=peak_error,max_tau_est_nm=peak_tau,max_hold_rms_speed_rad_s=hold_rms,
        limitations='Sampled writer tracking only. tau_est is estimated; trajectory identity relies on run metadata. No stability, lag, clipping or full-body safety certification.')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    draft=sub.add_parser('plan');draft.add_argument('--joint',type=int,default=22);draft.add_argument('--output',type=Path,required=True)
    review=sub.add_parser('evaluate');review.add_argument('plan',type=Path);review.add_argument('run',type=Path)
    args=p.parse_args()
    if args.mode=='plan':
        result=candidates(args.joint)
        with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(args.output)
    else:print(json.dumps(evaluate(json.loads(args.plan.read_text()),json.loads(args.run.read_text())),indent=2))


if __name__=='__main__':main()
