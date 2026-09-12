"""Finite simultaneous-axis comparison, with full-state audit. OFFLINE ONLY.

Two previously accepted research vectors are fixed before any new dynamics.
All declared cells are run; a low partial RMSE can never rescue a failed vector.
This validation does not tune on its own results or deploy a hardware setting.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import argparse,csv,itertools,json,math,platform,shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_multiaxis as multi
import mujoco_pd_operating_study as operating
import mujoco_pd_expand as expanded
from mujoco_pd_expand_audit import safe_path
pj=multi.pj;engine=multi.engine
VECTORS=(pj.Gains((100.,300.,100.,100.),(1.4,4.,1.4,1.4)),
         pj.Gains((100.,300.,100.,100.),(3.,5.,3.,3.)))
SCENARIOS=(multi.core.Coupled('nominal'),multi.core.Coupled('half',dt=.0005),
 multi.core.Coupled('heavy',1.35,1.25,.35,.002,.006),
 multi.core.Coupled('delay_boundary',1.35,.85,.15,.004,.008,.0005))


def norm(x):return json.loads(json.dumps(x,sort_keys=True))
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):expanded.save_json(Path(path),value)
def require(value,message):
    if not value:raise ValueError(message)


def conditions(smoke=False):
    if smoke:return [('smoke',multi.Motion('smoke_all',post_hold_s=2.),SCENARIOS[0])]
    result=[]
    signs=tuple(itertools.product((-1.,1.),repeat=4))
    for i,scales in enumerate(signs):
        for name,amplitude,speed,acceleration in (('small',4.,10.,30.),('standard',8.,20.,60.)):
            p=multi.Motion(f'dir{i:02d}_{name}',scales,amplitude,speed,acceleration)
            result.extend(('main',p,s) for s in SCENARIOS)
    selected=((-1.,-1.,-1.,-1.),(-1.,1.,-1.,1.),(1.,-1.,1.,-1.),(1.,1.,1.,1.))
    for i,scales in enumerate(selected):
        for name,kwargs in (('large',dict(amplitude_deg=12.,post_hold_s=5.)),
             ('long',dict(cycles=12,post_hold_s=30.,elbow_offset_deg=-5.))):
            p=multi.Motion(f'longdir{i}_{name}',scales,**kwargs)
            result.extend(('long',p,s) for s in (SCENARIOS[0],SCENARIOS[3]))
    return result


def plan(smoke=False):
    return [dict(case_id=f'case_{i:05d}',candidate=norm(asdict(g)),phase=phase,
                 motion=norm(asdict(p)),scenario=asdict(s))
       for i,(g,(phase,p,s)) in enumerate(itertools.product(VECTORS,conditions(smoke)))]


def run_case(job,folder):
    r,a=multi.simulate(multi.Motion(**job['motion']),pj.Gains(**job['candidate']),multi.core.Coupled(**job['scenario']))
    r.update(case_id=job['case_id'],phase=job['phase'])
    dest=Path(folder)/'full_state'/(r['case_id']+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
    require(not dest.exists(),'Trace exists; refusing overwrite')
    np.savez_compressed(dest,**a)
    r.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    save(Path(folder)/'cases'/(r['case_id']+'.json'),r);return r


def summary(records,jobs,manifest_hash,smoke=False):
    expected={j['case_id']:j for j in jobs};seen={r['case_id']:r for r in records}
    require(len(expected)==len(jobs) and len(seen)==len(records) and set(expected)==set(seen),'Missing/duplicate matrix cells')
    records=sorted(records,key=lambda r:r['case_id'])
    for r in records:
        require(all(norm(r[k])==norm(expected[r['case_id']][k]) for k in ('candidate','phase','motion','scenario')),'Plan identity changed')
        require(r['simulation_only'] and not r['hardware_config_modified'] and not r['hardware_approved'] and r['recommended_hardware_gains'] is None,'Hardware claim forbidden')
    ranks=[]
    for g in VECTORS:
        rs=[r for r in records if norm(r['candidate'])==norm(asdict(g))];good=bool(rs) and all(r['eligible'] for r in rs)
        maximum=lambda k:max((r['metrics'][k] for r in rs if r['metrics'] and r['metrics'][k] is not None),default=None)
        ranks.append(dict(candidate=norm(asdict(g)),cases=len(rs),passed=sum(r['eligible'] for r in rs),all_pass=good,
          worst_proximal_rmse_rad=maximum('max_proximal_rmse_rad') if good else None,
          partial_worst_proximal_rmse_rad=maximum('max_proximal_rmse_rad'),
          max_tail_error_rad=maximum('max_proximal_tail_error_rad'),
          max_tail_rms_speed_rad_s=maximum('max_right7_tail_rms_speed_rad_s'),
          failures=[dict(case_id=r['case_id'],reason=r['reason'],exclusions=r['exclusions']) for r in rs if not r['eligible']]))
    ranks.sort(key=lambda r:(not r['all_pass'],r['worst_proximal_rmse_rad'] if r['all_pass'] else math.inf,tuple(r['candidate']['kd'])))
    minimum=lambda k:min((v for r in records for v in r['joint_limit_guard'][k] if v is not None),default=None)
    return dict(schema='g1.pd.multiaxis.summary.v1',complete=True,full_study=not smoke,simulation_only=True,
      actual_runs=len(records),completed=sum(r['completed'] for r in records),eligible=sum(r['eligible'] for r in records),
      phase_counts=dict(sorted(Counter(r['phase'] for r in records).items())),
      base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
      exclusions=dict(sorted(Counter(e for r in records if not r['eligible'] for e in r['exclusions']).items())),
      guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
      minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
      minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),simulated_seconds=sum(r['final_time_s'] for r in records),
      ranking=ranks,selected_simulation_vector=next((r['candidate'] for r in ranks if r['all_pass']),None) if not smoke else None,
      manifest_sha256=manifest_hash,global_optimum_proven=False,hardware_approved=False,recommended_hardware_gains=None,
      scope='fixed pelvis; synchronous signed four-axis reference; no arbitrary VR, noise, thermal, wrist tuning or physical validation')


def audit_case(folder,job):
    folder=Path(folder);r=read(folder/'cases'/(job['case_id']+'.json'))
    for k in ('case_id','candidate','phase','motion','scenario'):require(norm(r[k])==norm(job[k]),'Recorded plan changed: '+k)
    m=multi.Motion(**r['motion']);m.validate();g=pj.Gains(**r['candidate']);g.validate()
    s=multi.core.Coupled(**r['scenario']);s.validate();p=m.profile();contract=multi.profile_contract(p)
    require(r['profile']==asdict(p) and r['quality_policy']==multi.POLICY,'Timing/policy changed')
    require(r['simulation_only'] and not r['hardware_approved'] and not r['hardware_config_modified'] and r['recommended_hardware_gains'] is None,'Hardware claim forbidden')
    kp,kd=engine.candidate_gains(contract,*pj.BASE);kp[22:26]=g.kp;kd[22:26]=g.kd
    require(np.array_equal(kp,r['gains_kp']) and np.array_equal(kd,r['gains_kd']),'Applied gain vector changed')
    require(r['initial_q']==contract.baseline.tolist(),'Initial state changed')
    require(r['legacy_hardware_gain_compatible']==all(v<=100 for v in g.kp),'Live compatibility misreported')
    dest=safe_path(folder,r['trace']);require(engine.sha256(dest)==r['trace_sha256'],'Trace hash changed')
    with np.load(dest,allow_pickle=False) as z:a={k:z[k] for k in z.files}
    evaluated=multi.evaluate(a,m,r['completed'],r['reason'],r['physics'])
    require(all(r[k]==v for k,v in evaluated.items()),'Metrics/eligibility changed')
    require(np.allclose(kp*(a['cmd']-a['q'])-kd*a['dq'],a['requested'],rtol=1e-12,atol=1e-12),'PD torque equation differs')
    # Independently reconstruct each held50Hz target, not the achieved command.
    path=multi.Path(p);stride=round(.02/s.dt);writer=round(.002/s.dt);warm=round(engine.WARMUP/s.dt)
    points={};ref=np.tile(contract.baseline,(len(a['time_s']),1));segments=[];cycles=[];phases=[]
    for i in range(len(ref)):
        step=i*writer;tick=step//stride*stride
        if tick not in points:points[tick]=path.at(max(0.,(tick-warm)*s.dt))
        pt=points[tick]
        if step>=warm:
            for j,scale in enumerate(m.scales):ref[i,22+j]+=scale*pt.offset
        segments.append(pt.segment if step>=warm else 'warmup');cycles.append(pt.cycle);phases.append(pt.phase if step>=warm else 0)
    require(np.array_equal(ref,a['ref']) and np.array_equal(segments,a['segment']) and np.array_equal(cycles,a['cycle']) and np.array_equal(phases,a['phase']),'Original vector reference differs')
    operating.check_guard(r,a)
    operating.coupled.check_model_evidence(dict(study_scenario_contract=r['scenario'],coupled_model_evidence=r['model_evidence'],torque_path=dict(delay_s=s.delay_s,lag_s=s.lag_s)))
    return r,a


def audit(folder):
    folder=Path(folder);manifest=read(folder/'manifest.json');jobs=read(folder/'plan.json');stored=read(folder/'summary.json')
    require(engine.source_hashes(dependencies())==manifest['source_sha256'],'Current computation source differs from frozen input')
    require(manifest['quality_policy']==multi.POLICY and manifest['vectors']==norm([asdict(g) for g in VECTORS]),'Policy or fixed candidates changed')
    require(jobs==plan(manifest['smoke']) and engine.sha256(folder/'plan.json')==manifest['plan_sha256'],'Matrix coverage changed')
    for key in ('source_sha256','asset_archive_sha256'):
        for name,digest in manifest[key].items():require(engine.sha256(safe_path(folder/'frozen_source',name))==digest,'Archived input bytes changed')
    require({p.stem for p in (folder/'cases').glob('*.json')}=={j['case_id'] for j in jobs},'Missing or extra case JSON')
    require({p.stem for p in (folder/'full_state').glob('*.npz')}=={j['case_id'] for j in jobs},'Missing or extra trace')
    records=[];rows=[];margins=[];samples=0
    for job in jobs:
        r,a=audit_case(folder,job);records.append(r);samples+=len(a['time_s'])
        row={k:r[k] for k in ('case_id','phase','completed','eligible','reason')}
        row.update(kp=json.dumps(r['candidate']['kp']),kd=json.dumps(r['candidate']['kd']),motion=r['motion']['name'],scales=json.dumps(r['motion']['scales']),scenario=r['scenario']['name'],exclusions=';'.join(r['exclusions']),samples=len(a['time_s']),trace_sha256=r['trace_sha256'])
        for k in ('max_proximal_rmse_rad','max_proximal_tail_error_rad','max_right7_tail_p2p_rad','max_right7_tail_rms_speed_rad_s','torque_limited_ratio','hard_clipped_ratio'):row[k]=r['metrics'][k] if r['metrics'] else None
        rows.append(row)
        for j in range(29):margins.append(dict(case_id=r['case_id'],joint=j,**{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}))
    require(summary(records,jobs,engine.sha256(folder/'manifest.json'),manifest['smoke'])==stored,'Summary/ranking mismatch')
    for filename,table in (('all_cases.csv',rows),('all_joint_margins.csv',margins)):
        with (folder/filename).open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    result=dict(schema='g1.pd.multiaxis.audit.v1',passed=True,cases=len(records),all29_500hz_rows=samples,
      all29_margin_records=len(margins),all_cases_sha256=engine.sha256(folder/'all_cases.csv'),source_archive_bytes_checked=True,
      scope='full29 sampled state/reference/PD equation, per-axis quality, all29 extrema and plans; not independent physics-rate reconstruction',physical_validation=False)
    save(folder/'audit.json',result);return result


def dependencies():
    names=('mujoco_pd_multiaxis.py','mujoco_pd_multiaxis_study.py','mujoco_pd_perjoint.py','mujoco_pd_operating_core.py',
      'mujoco_pd_operating_study.py','mujoco_pd_sweep.py','mujoco_pd_contract.py','mujoco_pd_fixture.py',
      'mujoco_pd_coupled_stress.py','mujoco_pd_motor_stress.py','mujoco_pd_expand.py','mujoco_pd_expand_audit.py','joint_limit_guard.py')
    return [Path(__file__).with_name(n) for n in names]+[engine.REFERENCE]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--smoke',action='store_true');parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers must be1..8')
    folder=args.output.resolve()
    if args.audit_only:print(json.dumps(audit(folder)));return 0
    require(not folder.exists(),'Existing output is never overwritten')
    import mujoco
    jobs=plan(args.smoke);_,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    source_hashes=engine.source_hashes(dependencies());archive={}
    model_base=engine.MODEL.parent
    for name,digest in assets.items():
        path=safe_path(model_base if name.replace('\\','/').startswith('meshes/') else engine.ROOT,name)
        require(engine.sha256(path)==digest,'Asset changed before freeze');archive[path.relative_to(engine.ROOT).as_posix()]=digest
    folder.mkdir(parents=True,exist_ok=False)
    for name,digest in {**source_hashes,**archive}.items():
        src=safe_path(engine.ROOT,name);dest=safe_path(folder/'frozen_source',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);require(engine.sha256(dest)==digest,'Input copy changed')
    save(folder/'plan.json',jobs)
    manifest=dict(schema='g1.pd.multiaxis.manifest.v1',simulation_only=True,smoke=args.smoke,
      source_sha256=source_hashes,asset_archive_sha256=archive,asset_sha256=assets,
      plan_sha256=engine.sha256(folder/'plan.json'),quality_policy=multi.POLICY,vectors=norm([asdict(g) for g in VECTORS]),
      mujoco=mujoco.__version__,numpy=np.__version__,python=platform.python_version(),platform=platform.platform(),workers=args.workers,
      limitations=['fixed pelvis','synchronized targets, not actual VR','hypothetical load/motor delay','research Kp300 is outside unchanged live limit'],hardware_approved=False)
    save(folder/'manifest.json',manifest);records=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        futures=[pool.submit(run_case,job,str(folder)) for job in jobs]
        for future in as_completed(futures):
            r=future.result();records.append(r)
            if len(records)%16==0 or len(records)==len(jobs):
                progress=dict(complete=False,done=len(records),total=len(jobs),eligible=sum(x['eligible'] for x in records));save(folder/'progress.json',progress);print(json.dumps(progress),flush=True)
    result=summary(records,jobs,engine.sha256(folder/'manifest.json'),args.smoke);save(folder/'summary.json',result)
    checked=audit(folder);save(folder/'progress.json',dict(complete=True,done=len(records),audited=checked['passed']))
    print('MULTIAXIS_RESULT '+json.dumps({k:v for k,v in result.items() if k!='ranking'}),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
