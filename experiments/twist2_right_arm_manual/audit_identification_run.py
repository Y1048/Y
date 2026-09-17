"""Offline provenance and sampling audit. Never fits or certifies a plant model."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(folder,context):
    folder=Path(folder);issues=[]
    run=json.loads((folder/'run.json').read_text())
    result=json.loads((folder/'result.json').read_text())
    if run.get('schema')!='g1.pd.run.v1' or result.get('schema')!='g1.pd.result.v1':
        raise ValueError('unsupported metadata schema')
    if sha(folder/'policy.csv')!=result['csv_sha256'] or sha(folder/'run.json')!=result['run_sha256']:
        raise ValueError('provenance hash mismatch')
    if not result.get('completed_reach') or result.get('reason')!='pd trial completed':
        issues.append('incomplete_trial')
    if run.get('mode')!='pd_reach':issues.append('not_fixed_reach_trial')
    for key in ('robot_id','session_group','support','payload','contact','operator_observations'):
        if not isinstance(context.get(key),str) or not context[key].strip():issues.append('missing_context:'+key)
    if context.get('split') not in ('train','validation','test'):issues.append('missing_dataset_split')
    with (folder/'policy.csv').open(newline='',encoding='utf-8-sig') as stream:
        rows=list(csv.DictReader(stream))
    if len(rows)!=result['policy_samples']:issues.append('row_count_mismatch')
    previous_seq=None;previous_t=None;gaps=[];skips=duplicates=0;phases=set();valid=0
    for row in rows:
        if row['writer_valid']!='1':continue
        seq=int(row['writer_sequence']);t=float(row['writer_write_returned_s'])
        if not math.isfinite(t):raise ValueError('nonfinite writer time')
        if previous_seq is not None:
            if seq<previous_seq:raise ValueError('reversed writer sequence')
            if seq==previous_seq:duplicates+=1;continue
            if t<=previous_t:raise ValueError('reversed writer time')
            gaps.append(t-previous_t);skips+=seq-previous_seq-1
        previous_seq,previous_t=seq,t;valid+=1
        phases.add((int(row['writer_trial_cycle']),int(row['writer_trial_phase'])))
        for i in range(29):
            for field in ('q','dq','target','target_dq','tau_est','tau_ff','kp','kd'):
                value=float(row[f'writer_{field}_{i}'])
                if not math.isfinite(value):raise ValueError('nonfinite joint telemetry')
                if field in ('kp','kd') and abs(value-run[field][i])>1e-5:
                    raise ValueError('effective PD mismatch')
    if not all((cycle,phase) in phases for cycle in range(3) for phase in (2,3,4,5)):
        issues.append('missing_cycle_phase')
    if len(gaps)<2:issues.append('insufficient_samples')
    if gaps and max(gaps)>.06:issues.append('sampling_gap_over_60ms')
    return dict(schema='g1.identification.audit.v1',run_sha256=sha(folder/'run.json'),
        context=context,issues=issues,passes_basic_audit=not issues,
        valid_writer_samples=valid,duplicate_frames=duplicates,skipped_writer_frames=skips,
        effective_sample_hz=(len(gaps)/sum(gaps) if gaps else None),
        max_sample_gap_s=max(gaps,default=None),
        suitable_for_fast_dynamics=False,
        limits='Basic provenance/coverage audit only. Not excitation, phase-duration, sensor accuracy, model-fit or hardware-safety validation. Keep entire session_group in one split; never split neighboring rows randomly.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path)
    p.add_argument('--context',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();report=audit(a.folder,json.loads(a.context.read_text()))
    with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
