"""Read-only writer-frame PD decomposition; hypothetical gains are not a rollout."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def terms(q, target, dq, target_dq, kp, kd, ff):
    values=(q,target,dq,target_dq,kp,kd,ff)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('non-finite PD input')
    p=kp*(target-q)
    d=kd*(target_dq-dq)
    return dict(p_nm=p,d_nm=d,ff_nm=ff,total_nm=p+d+ff)


def review(path,joint=22):
    rows=list(csv.DictReader(Path(path).open(newline='')))
    selected=[];seen=set()
    for row in rows:
        if row['writer_valid']!='1' or row['writer_trial_phase']!='2':continue
        seq=int(row['writer_sequence'])
        if seq in seen:continue
        seen.add(seq)
        v=lambda name:float(row[f'writer_{name}_{joint}'])
        args=[v(n) for n in ('q','target','dq','target_dq','kp','kd','tau_ff')]
        actual=terms(*args)
        proposed=args.copy();proposed[4]=48.
        hypothetical=terms(*proposed)
        selected.append(dict(elapsed_s=float(row['elapsed_s']),q=args[0],target=args[1],
            error_rad=args[1]-args[0],dq=args[2],kp=args[4],kd=args[5],
            tau_est_nm=v('tau_est'),actual=actual,kp48_same_state=hypothetical,
            command_age_ms=1000*(float(row['writer_write_returned_s'])-float(row['writer_desired_created_s'])),
            state_age_ms=1000*(float(row['writer_cycle_started_s'])-float(row['writer_state_received_s'])) ))
    if not selected:raise ValueError('no forward writer samples')
    return dict(source=str(path),sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        joint=joint,samples=len(selected),last=selected[-1],
        peak_abs_p_nm=max(abs(r['actual']['p_nm']) for r in selected),
        peak_abs_d_nm=max(abs(r['actual']['d_nm']) for r in selected),
        peak_abs_total_nm=max(abs(r['actual']['total_nm']) for r in selected),
        max_command_age_ms=max(r['command_age_ms'] for r in selected),
        max_state_age_ms=max(r['state_age_ms'] for r in selected),
        limitation='Kp48 is same-state algebra only, before any changed limiter response; not predicted motion, stability, or optimal gains. Timing ages are local software ages, not end-to-end actuation latency.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('csv',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=review(args.csv)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
