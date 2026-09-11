"""Complete every pair x condition of a frozen coupled study; OFFLINE ONLY.

This consumes all validation conditions as a complete descriptive matrix; do
not label subsequent selection against these conditions a new independent test.
The original selected-candidate study and its frozen ordering are preserved.
"""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,csv,itertools,json
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_coupled_stress as study

read,save=study.read,study.save
engine=study.engine

def source_records(base):
    return [read(p) for p in sorted((Path(base)/'cases').glob('*.json'))]

def missing_jobs(records,manifest,folder):
    lookup={}
    for r in records:
        key=(study.pair(r),r['study_scenario'])
        if key in lookup:raise ValueError('Duplicate pair/condition in base study')
        lookup[key]=r
    required=[(tuple(p),study.Coupled(**s)) for p,s in itertools.product(manifest['pairs'],manifest['validation'])]
    return [(float(p),float(d),asdict(s),str(folder),f'extra_{i:05d}','validation')
      for i,((p,d),s) in enumerate((v for v in required if (v[0],v[1].identity) not in lookup))]

def summarize(records,manifest):
    pairs=list(map(tuple,manifest['pairs']))
    scenarios=[study.Coupled(**s) for s in manifest['calibration']+manifest['validation']]
    all_records=[dict(r,study_phase='combined') for r in records]
    ranked=study.quality.rank(all_records,pairs,scenarios,'combined')
    if len(records)!=len(pairs)*len(scenarios) or not all(r['all_present'] for r in ranked):
        raise ValueError('Complete matrix still has missing/extra conditions')
    good=[r['pair'] for r in ranked if r['all_quality_pass']]
    events=[r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event']]
    minimum=lambda key:min(v for r in records for v in r['joint_limit_guard'][key] if v is not None)
    from collections import Counter
    return {'schema':'g1.pd.coupled.matrix.v1','complete':True,'full_study':manifest['full_study'],
      'simulation_only':True,'pairs':len(pairs),'conditions_per_pair':len(scenarios),'total_cases':len(records),
      'completed':sum(r['completed'] for r in records),'base_eligible':sum(r['eligible'] for r in records),
      'quality_eligible':sum(r['quality_eligible'] for r in records),'fully_passing_pairs':good,
      'minimum_tested_pair':good[0] if good else None,'ranking':ranked,
      'base_rejections':dict(Counter(r['reason'] for r in records if not r['eligible'])),
      'quality_rejections':dict(Counter(x for r in records if r['eligible'] and not r['quality_eligible'] for x in r['stability']['rejections'])),
      'guard_events':dict(Counter(e['reason'] for e in events)),
      'minimum_soft_margin_rad':minimum('minimum_soft_margin_rad'),
      'minimum_model_hard_margin_rad':minimum('minimum_hard_margin_rad'),
      'all_possible_cases_tested':False,'physical_stability_proven':False,'continuous_optimum_proven':False,
      'recommended_hardware_gains':None,'hardware_config_modified':False,
      'interpretation':'Complete descriptive finite matrix; new conditions now observed, not independent retuning evidence'}

def verify_extra(folder,file,job):
    r,_,_=study.check_case(folder,file);study.verify_guard_result(r);study.check_model_evidence(r)
    if study.pair(r)!=(job[0],job[1]) or r['case_id']!=job[4] or r['study_scenario_contract']!=job[2]:
        raise ValueError('Supplemental case differs from frozen plan')
    if r['study_phase']!=job[5] or r['study_scenario']!=study.Coupled(**job[2]).identity:raise ValueError('Supplemental identity mismatch')
    full=study.safe_path(folder,r['full_state_npz'])
    if engine.sha256(full)!=r['full_state_sha256']:raise ValueError('Supplemental full-state hash mismatch')
    with np.load(full,allow_pickle=False) as f:a={k:f[k] for k in f.files}
    stats=study.quality.stability(a)
    if stats!=r['stability'] or r['quality_eligible']!=bool(r['eligible'] and stats['passes']):
        raise ValueError('Supplemental quality mismatch')
    with np.load(study.safe_path(folder,r['trace_npz']),allow_pickle=False) as f:
        v={c:f['values'][:,i] for i,c in enumerate(f['columns'].tolist())}
    for key in ('q','dq','ref','cmd'):
        if not np.array_equal(a[key][:,22],v[key+'_22']):raise ValueError('Supplemental compact/full parity mismatch')
    if r['eligible']:
        envelope=r['joint_limit_guard']['envelope']
        for key in ('q','ref','cmd'):
            if np.any(a[key]<=np.array(envelope['inner_lower'])+1e-10) or np.any(a[key]>=np.array(envelope['inner_upper'])-1e-10):
                raise ValueError('Supplemental accepted limit touch')
        observed=np.minimum(a['q']-np.array(envelope['soft_lower']),np.array(envelope['soft_upper'])-a['q']).min(axis=0)
        if np.any(observed+1e-10<r['joint_limit_guard']['minimum_soft_margin_rad']):raise ValueError('Supplemental extrema mismatch')
    return r,len(a['q'])

def audit(base,folder):
    base,folder=Path(base),Path(folder);m=read(base/'manifest.json');own=read(folder/'manifest.json')
    old_audit=study.audit(base,engine.ROOT)
    for name,digest in own['base_artifact_sha256'].items():
        if engine.sha256(base/name)!=digest:raise ValueError('Base evidence changed: '+name)
    for name,digest in own['source_sha256'].items():
        if engine.sha256(study.safe_path(engine.ROOT,name))!=digest:raise ValueError('Matrix source changed')
    original=source_records(base);plan=read(folder/'plan.json')
    normalized=lambda x:json.dumps([(j[0],j[1],j[2],j[4],j[5]) for j in x],sort_keys=True)
    if normalized(plan)!=normalized(missing_jobs(original,m,folder)):raise ValueError('Missing-cell plan changed')
    index={j[4]:j for j in plan};extras=[];samples=0;hashes={}
    for path in sorted((folder/'cases').glob('*.json')):
        if path.stem not in index:raise ValueError('Unplanned matrix case')
        r,n=verify_extra(folder,path,index[path.stem]);extras.append(r);samples+=n;hashes[r['case_id']]=engine.sha256(path)
    if len(extras)!=len(plan):raise ValueError('Missing supplemental execution')
    all_records=original+extras;result=summarize(all_records,m)
    if result!=read(folder/'summary.json'):raise ValueError('Full matrix summary mismatch')
    rows=[]
    for r in sorted(all_records,key=lambda r:(study.pair(r),r['study_scenario'])):
        s=r['stability']
        rows.append({'case_id':r['case_id'],'dataset':'supplement' if r['case_id'].startswith('extra_') else 'base',
          'kp':r['kp_proximal'],'kd':r['kd_proximal'],**r['study_scenario_contract'],
          'completed':r['completed'],'base_eligible':r['eligible'],'quality_eligible':r['quality_eligible'],
          'base_reason':r['reason'],'quality_reasons':';'.join(s['rejections']),
          'rmse_rad':r['metrics']['reference_rmse_joint22_rad'] if r['metrics'] else None,
          'tail_rms_speed_rad_s':s['max_right7_tail_rms_speed_rad_s'],'tail_p2p_rad':s['max_right7_tail_p2p_rad'],
          'trace_sha256':r['trace_sha256'],'full_state_sha256':r['full_state_sha256']})
    with (folder/'all_cases.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    evidence={'schema':'g1.pd.coupled.matrix.audit.v1','passed':True,'total_cases':len(all_records),
      'base_cases':len(original),'extra_cases':len(extras),'all29_500hz_rows':old_audit['all29_500hz_rows']+samples,
      'all29_extrema_records':len(all_records)*29,'all_cells_present':True,
      'source_model_hashes_checked':True,'extra_case_hashes':hashes,
      'matrix_summary_sha256':engine.sha256(folder/'summary.json'),'matrix_manifest_sha256':engine.sha256(folder/'manifest.json'),
      'matrix_all_cases_sha256':engine.sha256(folder/'all_cases.csv'),'base_audit_sha256':engine.sha256(base/'audit.json'),
      'simulation_only':True,'hardware_validated':False}
    save(folder/'audit.json',evidence);return evidence

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6);p.add_argument('--audit-only',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.workers<=8:p.error('workers must be1..8')
    base,folder=a.base_run.resolve(),a.output.resolve()
    if a.audit_only:print(audit(base,folder));return 0
    if folder.exists():raise FileExistsError('Never overwrite matrix results')
    if folder.is_relative_to(base) or base.is_relative_to(folder):raise ValueError('Use separate sibling artifact roots')
    if not read(base/'progress.json')['complete']:raise ValueError('Base study must finish first')
    original=source_records(base);m=read(base/'manifest.json');plan=missing_jobs(original,m,folder)
    sources=engine.source_hashes([Path(__file__)])
    sources.update(m['source_sha256'])
    folder.mkdir(parents=True,exist_ok=False)
    save(folder/'manifest.json',{'schema':'g1.pd.coupled.matrix.run.v1','source_sha256':sources,
      'base_artifact_sha256':{n:engine.sha256(base/n) for n in ('manifest.json','summary.json','selection.json','audit.json')},
      'extra_count':len(plan),'intent':'Fill every missing pair x validation cell, without pruning or rescue',
      'recommended_hardware_gains':None,'hardware_config_modified':False,'simulation_only':True})
    save(folder/'plan.json',plan);extras=[]
    with ProcessPoolExecutor(max_workers=a.workers,initializer=study.expanded.init_worker) as pool:
        for f in as_completed([pool.submit(study.run_case,j) for j in plan]):
            extras.append(f.result())
            if len(extras)%20==0:print('MATRIX_EXTRA',len(extras),'/',len(plan),flush=True)
    result=summarize(original+extras,m);save(folder/'summary.json',result)
    checked=audit(base,folder)
    save(folder/'progress.json',{'complete':True,'audited':checked['passed'],'total_cases':len(original)+len(extras)})
    print('MATRIX_FINAL',json.dumps({k:v for k,v in result.items() if k!='ranking'}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
