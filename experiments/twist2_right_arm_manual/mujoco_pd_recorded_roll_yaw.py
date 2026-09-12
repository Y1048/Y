"""Coordinate PD research on the fixed causal20ms recorded-input pipeline.
Offline only. No SDK, sockets, live gain editing or relaxation of physical limits.
Only joint23's *separate simulation* search bound extends from300 to350. Restores
that process-local bound on every exit; no concurrent threads use the adapter.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import argparse, csv, json, math, platform, shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_recorded_ramp_study as ramp
import mujoco_pd_independent_study as independent
import mujoco_pd_multiaxis as multi
import mujoco_pd_multiaxis_study as base
from mujoco_pd_expand_audit import safe_path
pj=ramp.pj;engine=ramp.engine
SCHEMA='g1.pd.recorded-roll-yaw.v1'
YAW_KP=(40.,48.,56.,64.,72.,80.)
YAW_KD=(.6,.8,1.,1.2,1.4,1.6)
ROLL_KP=(250.,275.,300.,325.,350.)
ROLL_KD=(3.,4.,5.,6.)
RESEARCH_CAP=(100.,350.,100.,100.)
PHASES=('yaw','roll','validation','regression')
POLICY=dict(simulation_only=True,hardware_approved=False,
    recommended_hardware_gains=None,hardware_config_modified=False,
    requires_command_prefilter=True,pd_only_optimum_proven=False,
    global_optimum_proven=False,command_filter=dict(ramp.core.COMMAND_FILTER),
    objective='minimize worst original-goal all7 RMSE, subject to ALL recorded and regression gates',
    search_method='bounded coordinate search; validation reuses observed recording and models',
    research_kp_cap=list(RESEARCH_CAP),live_kp_cap_unchanged=100.)

def norm(x):return base.norm(x)
def save(p,x):base.save(p,x)
def read(p):return base.read(p)
def require(ok,msg):base.require(ok,msg)
def identity(g):return tuple(g['kp'])+tuple(g['kd'])

def validate_vector(g):
    p,d=g['kp'],g['kd']
    require(len(p)==4 and len(d)==4,'Four proximal gains required')
    require(all(type(v) in (int,float) and math.isfinite(v) and 1<=v<=c for v,c in zip(p,RESEARCH_CAP)),'Research Kp bounds')
    require(all(type(v) in (int,float) and math.isfinite(v) and .1<=v<=20 for v in d),'Research Kd bounds')

@contextmanager
def research_scope():
    old=pj.KP_CAP
    require(old==(100.,300.,100.,100.),'Unexpected existing simulation cap; no nested scope')
    pj.KP_CAP=RESEARCH_CAP
    try:yield
    finally:pj.KP_CAP=old

def vector(yawp=72.,yawd=1.,rollp=300.,rolld=4.):
    g=dict(kp=[100.,float(rollp),float(yawp),100.],kd=[1.4,float(rolld),float(yawd),1.4])
    validate_vector(g);return g

def deduplicate(vectors):
    result=[];seen=set()
    for g in vectors:
        validate_vector(g)
        if identity(g) not in seen:result.append(g);seen.add(identity(g))
    return result

def screen_conditions():
    # Both source clocks and the previously failing send-clock condition.
    return [('send',ramp.SCENARIOS[0]),('send',ramp.SCENARIOS[3]),('sample',ramp.SCENARIOS[3])]

def recorded_plan(stage,vectors,conditions,smoke=False):
    result=[]
    for g in vectors:
        validate_vector(g)
        for clock,s in conditions:
            s.validate()
            result.append(dict(case_id=f'{stage}_{len(result):04d}',stage=stage,kind='recorded',
              candidate=norm(g),episode=0,clock=clock,scenario=asdict(s)))
    return result

def rank(records,plan):
    expected={j['case_id']:j for j in plan};seen={r['case_id']:r for r in records}
    require(len(expected)==len(plan) and len(seen)==len(records) and set(expected)==set(seen),'Missing/duplicate cases')
    for r in records:
        j=expected[r['case_id']]
        require(all(norm(r[k])==norm(v) for k,v in j.items()),'Case identity differs')
        require(r['simulation_only'] is True and r['hardware_approved'] is False and r['recommended_hardware_gains'] is None and r['hardware_config_modified'] is False,'Hardware claim')
    result=[]
    for g in deduplicate([j['candidate'] for j in plan]):
        rs=sorted([r for r in records if identity(r['candidate'])==identity(g)],key=lambda r:r['case_id'])
        good=bool(rs) and all(r['eligible'] for r in rs)
        def score(r):
            return r['metrics'].get('max_right7_recorded_rmse_rad',r['metrics'].get('max_proximal_rmse_rad')) if r['metrics'] else None
        worst=max((score(r) for r in rs if score(r) is not None),default=None)
        result.append(dict(candidate=g,cases=len(rs),passed=sum(r['eligible'] for r in rs),all_pass=good,
           worst_rmse_rad=worst if good else None,partial_worst_rmse_rad=worst,
           failures=[dict(case_id=r['case_id'],reason=r['reason'],exclusions=r['exclusions']) for r in rs if not r['eligible']]))
    return sorted(result,key=lambda r:(not r['all_pass'],r['worst_rmse_rad'] if r['all_pass'] else math.inf,identity(r['candidate'])))

def top(records,plan,count=2):return [r['candidate'] for r in rank(records,plan) if r['all_pass']][:count]

def regression_plan(vectors):
    result=[]
    # A declared subset, NOT all prior individual/simultaneous/independent conditions.
    profiles=independent.motions()
    motions=[profiles[0],profiles[3],profiles[7]]
    for g in vectors:
        for m in motions:
            for s in (ramp.SCENARIOS[0],ramp.SCENARIOS[3]):
                result.append(dict(case_id=f'regression_{len(result):04d}',stage='regression',kind='independent',
                  candidate=norm(g),motion=norm(asdict(m)),scenario=asdict(s)))
        for j in range(22,26):
            for s in (ramp.SCENARIOS[0],ramp.SCENARIOS[3]):
                m=multi.Motion(scales=tuple(1. if i==j-22 else 0. for i in range(4)))
                result.append(dict(case_id=f'regression_{len(result):04d}',stage='regression',phase='regression',kind='single',
                  candidate=norm(g),motion=norm(asdict(m)),scenario=asdict(s)))
    return result

def phase_plan(stage,records,plans,smoke=False):
    require(stage in PHASES,'Unknown phase')
    if stage=='yaw':
        vv=[vector(p,d) for p in YAW_KP for d in YAW_KD]
        if smoke:vv=[vector(64.,1.),vector(72.,1.)]
        return recorded_plan(stage,vv,screen_conditions()[:1] if smoke else screen_conditions())
    yr=[r for r in records if r['stage']=='yaw'];best_yaw=top(yr,plans['yaw'])
    if stage=='roll':
        if not best_yaw:return []
        g=best_yaw[0]
        vv=[vector(g['kp'][2],g['kd'][2],p,d) for p in ROLL_KP for d in ROLL_KD]
        if smoke:vv=[vector(g['kp'][2],g['kd'][2],325.,4.)]
        return recorded_plan(stage,vv,screen_conditions()[:1] if smoke else screen_conditions())
    rr=[r for r in records if r['stage']=='roll'];best_roll=top(rr,plans['roll'])
    if stage=='validation':
        vv=deduplicate(best_roll+best_yaw)
        cc=[(c,s) for c in ramp.CLOCKS for s in ramp.SCENARIOS]
        return recorded_plan(stage,vv[:1] if smoke else vv,cc[:1] if smoke else cc)
    vr=[r for r in records if r['stage']=='validation']
    validated=[r['candidate'] for r in rank(vr,plans['validation']) if r['all_pass']]
    jobs=regression_plan(validated)
    return jobs[:1] if smoke else jobs

def run_case(job,folder):
    folder=Path(folder);validate_vector(job['candidate'])
    with research_scope():
        if job['kind']=='recorded':r=ramp.run_case(job,folder)
        elif job['kind']=='independent':r=independent.run_case(job,folder)
        else:
            g=pj.Gains(**job['candidate']);m=multi.Motion(**job['motion']);s=multi.core.Coupled(**job['scenario'])
            r,a=multi.simulate(m,g,s)
            r['case_id']=job['case_id'];r['phase']=job['phase'];dest=folder/'full_state'/(r['case_id']+'.npz')
            dest.parent.mkdir(parents=True,exist_ok=True);require(not dest.exists(),'Trace exists')
            np.savez_compressed(dest,**a);r.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    r.update(stage=job['stage'],kind=job['kind'],research_kp_cap=list(RESEARCH_CAP))
    save(folder/'cases'/(r['case_id']+'.json'),r);return r

def checked_case(folder,job,capture):
    r0=read(Path(folder)/'cases'/(job['case_id']+'.json'))
    require(r0['stage']==job['stage'] and r0['kind']==job['kind'] and r0['research_kp_cap']==list(RESEARCH_CAP),'Research scope changed')
    with research_scope():
        if job['kind']=='recorded':r,a=ramp.audit_case(folder,job,capture)
        elif job['kind']=='independent':r,a=independent.audit_case(folder,job)
        else:r,a=base.audit_case(folder,job)
    return r,a

def summary(records,plans,manifest_hash,smoke):
    ranks={stage:rank([r for r in records if r['stage']==stage],plans[stage]) for stage in PHASES}
    survivors={identity(r['candidate']) for r in ranks['regression'] if r['all_pass']}
    chosen=next((r['candidate'] for r in ranks['validation'] if r['all_pass'] and identity(r['candidate']) in survivors),None)
    minimum=lambda k:min((v for r in records for v in r['joint_limit_guard'][k] if v is not None),default=None)
    return dict(schema=SCHEMA,complete=True,smoke=smoke,**POLICY,
      actual_runs=len(records),completed=sum(r['completed'] for r in records),eligible=sum(r['eligible'] for r in records),
      stage_counts={k:len(v) for k,v in plans.items()},ranking=ranks,
      selected_filtered_pipeline_vector=None if smoke else chosen,
      base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
      guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
      minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
      minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),
      simulated_seconds=math.fsum(r['final_time_s'] for r in sorted(records,key=lambda r:r['case_id'])),
      manifest_sha256=manifest_hash,regression_scope='14declared cases per validated vector, not inherited previous passes')

def dependencies():return list(dict.fromkeys(ramp.dependencies()+independent.dependencies()+[Path(multi.__file__),Path(__file__)]))

def audit(folder):
    folder=Path(folder);manifest=read(folder/'manifest.json')
    require(manifest['schema']==SCHEMA and manifest['policy']==POLICY,'Manifest policy changed')
    require(type(manifest['smoke']) is bool,'Invalid smoke flag')
    for name,grid in (('yaw_kp',YAW_KP),('yaw_kd',YAW_KD),('roll_kp',ROLL_KP),('roll_kd',ROLL_KD)):
        require(manifest[name]==list(grid),'Manifest grid changed')
    require(engine.source_hashes(dependencies())==manifest['source_sha256'],'Computation sources changed')
    for name,digest in {**manifest['source_sha256'],**manifest['asset_archive_sha256']}.items():
        require(engine.sha256(safe_path(folder/'frozen_source',name))==digest,'Archived source/model changed')
    raw=folder/'inputs/recording.jsonl';require(engine.sha256(raw)==manifest['recording_sha256'],'Raw recording changed')
    captures,info=ramp.recording.extract(raw);require(len(captures)==1,'Exactly one qualified episode required')
    capture=captures[0];require(capture.metadata()==manifest['capture'],'Capture identity changed')
    frozen=ramp.load_capture(folder,0)
    for name in ('joints','send_time_s','sample_time_s','events','sequence'):
        require(np.array_equal(getattr(capture,name),getattr(frozen,name)),'Normalized recording changed')
    records=[];plans={};table=[];margins=[];rows=0
    for phase in PHASES:
        expected=phase_plan(phase,records,plans,manifest['smoke'])
        require(read(folder/'plans'/(phase+'.json'))==expected,'Plan/selection differs:'+phase)
        plans[phase]=expected
        for job in expected:
            r,a=checked_case(folder,job,capture);records.append(r);rows+=len(a['time_s'])
            m=r['metrics'];row=dict(case_id=r['case_id'],stage=phase,kind=r['kind'],kp=json.dumps(r['candidate']['kp']),
              kd=json.dumps(r['candidate']['kd']),clock=r.get('clock',''),scenario=r['scenario']['name'],
              completed=r['completed'],eligible=r['eligible'],reason=r['reason'],exclusions=';'.join(r['exclusions']),samples=len(a['time_s']),
              max_rmse_rad=m.get('max_right7_recorded_rmse_rad',m.get('max_proximal_rmse_rad')) if m else None,
              peak_upper_speed_rad_s=r['physics']['peak_upper_speed_rad_s'],trace_sha256=r['trace_sha256'])
            table.append(row)
            for j in range(29):margins.append(dict(case_id=r['case_id'],joint=j,**{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}))
    ids={j['case_id'] for pp in plans.values() for j in pp}
    for sub,glob in (('cases','*.json'),('full_state','*.npz')):
        require({p.stem for p in (folder/sub).glob(glob)}==ids,'Missing/extra case or trace')
    require(summary(records,plans,engine.sha256(folder/'manifest.json'),manifest['smoke'])==read(folder/'summary.json'),'Summary differs')
    for filename,values in (('all_cases.csv',table),('all_joint_margins.csv',margins)):
        with (folder/filename).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
    result=dict(passed=True,cases=len(records),all29_500hz_rows=rows,all29_margin_records=len(margins),
      all_cases_sha256=engine.sha256(folder/'all_cases.csv'),source_and_recording_checked=True,
      physical_validation=False,scope='full saved traces and guard extrema; not independent continuous dynamics')
    save(folder/'audit.json',result);return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recording',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--smoke',action='store_true');p.add_argument('--audit-only',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.workers<=6:p.error('workers must be1..6')
    folder=a.output.resolve()
    if a.audit_only:print(json.dumps(audit(folder)));return 0
    require(not folder.exists(),'Output exists; no overwrite')
    require(a.recording is not None and a.recording.is_file(),'Explicit existing recording required')
    require(not a.recording.resolve().is_relative_to(folder),'Nested input refused')
    require(shutil.disk_usage(folder.parent if folder.parent.exists() else Path.cwd()).free>4_000_000_000,'At least4GB free required')
    captures,info=ramp.recording.extract(a.recording);require(len(captures)==1,'Exactly one qualified episode required')
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001);archive={}
    for name,digest in assets.items():
        src=safe_path(engine.MODEL.parent if name.replace(chr(92),'/').startswith('meshes/') else engine.ROOT,name)
        require(engine.sha256(src)==digest,'Asset changed');archive[src.relative_to(engine.ROOT).as_posix()]=digest
    sources=engine.source_hashes(dependencies());folder.mkdir(parents=True,exist_ok=False);(folder/'inputs').mkdir()
    shutil.copyfile(a.recording,folder/'inputs/recording.jsonl')
    require(engine.sha256(folder/'inputs/recording.jsonl')==info['source_sha256'],'Recording changed during freeze')
    ramp.write_capture(folder,0,captures[0])
    for name,digest in {**sources,**archive}.items():
        src=safe_path(engine.ROOT,name);dest=safe_path(folder/'frozen_source',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);require(engine.sha256(dest)==digest,'Archive failure')
    manifest=dict(schema=SCHEMA,policy=POLICY,smoke=a.smoke,source_sha256=sources,asset_archive_sha256=archive,
      recording_sha256=info['source_sha256'],capture=captures[0].metadata(),input_name=a.recording.name,
      yaw_kp=YAW_KP,yaw_kd=YAW_KD,roll_kp=ROLL_KP,roll_kd=ROLL_KD,
      mujoco=mujoco.__version__,numpy=np.__version__,python=platform.python_version(),platform=platform.platform(),workers=a.workers)
    save(folder/'manifest.json',manifest);records=[];plans={}
    with ProcessPoolExecutor(max_workers=a.workers,initializer=base.expanded.init_worker) as pool:
        for phase in PHASES:
            plan=phase_plan(phase,records,plans,a.smoke);plans[phase]=plan;save(folder/'plans'/(phase+'.json'),plan)
            futures=[pool.submit(run_case,j,str(folder)) for j in plan]
            for f in as_completed(futures):
                r=f.result();records.append(r)
                progress=dict(complete=False,phase=phase,phase_done=sum(x['stage']==phase for x in records),phase_total=len(plan),total_done=len(records))
                save(folder/'progress.json',progress)
                if progress['phase_done']%6==0 or progress['phase_done']==len(plan):print(json.dumps(progress),flush=True)
            print('PHASE_RANK '+json.dumps(dict(phase=phase,top=rank([r for r in records if r['stage']==phase],plan)[:3])),flush=True)
    result=summary(records,plans,engine.sha256(folder/'manifest.json'),a.smoke);save(folder/'summary.json',result)
    checked=audit(folder);save(folder/'progress.json',dict(complete=True,cases=len(records),audited=checked['passed']))
    print('STUDY_COMPLETE '+json.dumps(dict(cases=len(records),eligible=result['eligible'],candidate=result['selected_filtered_pipeline_vector'])),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
