"""Targeted joint24 refinement AFTER the failed simultaneous validation.

Only joint24 Kp/Kd changes, within the pre-existing research AND live numeric
bounds. All other research gains remain fixed, including non-deployable Kp23=300.
Known failures are now calibration, not unseen evidence. Final conditions are
frozen before this study, and cannot tune or reorder the operating selection.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
import argparse,csv,itertools,json,math,platform,shutil
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_multiaxis_study as base
multi=base.multi;pj=base.pj;engine=base.engine
YAW_PAIRS=tuple(itertools.product((32.,48.,64.,72.,80.,88.,100.),(.4,.7,1.,1.4,2.,3.)))


def vectors():
    result=[]
    for p,d in YAW_PAIRS:
        g=base.VECTORS[0];kp=list(g.kp);kd=list(g.kd);kp[2]=p;kd[2]=d
        result.append(pj.Gains(tuple(kp),tuple(kd)))
    return result


def screen_conditions():
    return [('screen',multi.Motion('screen_nominal'),base.SCENARIOS[0]),
      ('screen',multi.Motion('screen_negative',(-1.,-1.,-1.,-1.),4.,10.,30.),base.SCENARIOS[3]),
      ('screen',multi.Motion('screen_mixed',(1.,-1.,1.,-1.),12.,post_hold_s=5.),base.SCENARIOS[3])]


def validation_conditions():
    result=[]
    factors=((1.2,.7,.2,.003,.006,.0005),(1.45,1.,.1,.003,.007,.001),
             (.85,.6,.4,.002,.004,.0005),(1.3,1.1,.25,.004,.006,.001),
             (1.1,1.6,1.3,.001,.003,.001),(1.4,.8,.15,.003,.009,.0005))
    signs=((-1.,-1.,1.,1.),(-1.,1.,1.,-1.),(1.,-1.,-1.,1.),(1.,1.,-1.,-1.))
    for i,f in enumerate(factors):
        s=multi.core.Coupled(f'validation_{i}',*f)
        for j,scale in enumerate(signs):
            p=multi.Motion(f'validation_{i}_{j}',scale,float((6,9,11)[i%3]),float((15,23,27)[i%3]),60.,
                           6 if i%2 else 3,float((-4,4,0)[i%3]),5.)
            result.append(('validation',p,s))
    return result


def jobs(gains,conditions,phase):
    require=base.require;require(len({g.key for g in gains})==len(gains),'Duplicate gain vectors')
    return [dict(case_id=f'{phase}_{i:05d}',phase=phase,candidate=base.norm(asdict(g)),motion=base.norm(asdict(m)),scenario=asdict(s))
      for i,(g,(_,m,s)) in enumerate(itertools.product(gains,conditions))]


def ranking(records,plan):
    expected={j['case_id']:j for j in plan};seen={r['case_id']:r for r in records}
    base.require(len(expected)==len(plan) and len(seen)==len(records) and set(seen)==set(expected),'Incomplete or duplicate phase')
    for key,r in seen.items():
        base.require(all(base.norm(r[k])==base.norm(expected[key][k]) for k in ('phase','candidate','motion','scenario')),'Candidate/condition mismatch')
    keys=sorted({pj.Gains(**r['candidate']).key for r in records});rows=[]
    for key in keys:
        rs=sorted((r for r in records if pj.Gains(**r['candidate']).key==key),key=lambda r:r['case_id'])
        good=all(r['eligible'] for r in rs)
        maximum=max((r['metrics']['max_proximal_rmse_rad'] for r in rs if r['metrics']),default=None)
        rows.append(dict(candidate=rs[0]['candidate'],cases=len(rs),passed=sum(r['eligible'] for r in rs),all_pass=good,
          selectable_worst_rmse_rad=maximum if good else None,partial_worst_rmse_rad=maximum,
          failures=[dict(case_id=r['case_id'],reason=r['reason'],exclusions=r['exclusions']) for r in rs if not r['eligible']]))
    return sorted(rows,key=lambda r:(not r['all_pass'],r['selectable_worst_rmse_rad'] if r['all_pass'] else math.inf,tuple(r['candidate']['kp']),tuple(r['candidate']['kd'])))


def passing(records,plan):return [pj.Gains(**r['candidate']) for r in ranking(records,plan) if r['all_pass']]


def block(pool,folder,plan):
    if not plan:return []
    records=[]
    for future in as_completed([pool.submit(base.run_case,j,str(folder)) for j in plan]):
        records.append(future.result())
        if len(records)%16==0 or len(records)==len(plan):
            base.save(folder/'progress.json',dict(complete=False,phase=plan[0]['phase'],done=len(records),total=len(plan)))
            print('YAW_PHASE',plan[0]['phase'],len(records),'/',len(plan),flush=True)
    return records


def make_summary(records,plans,manifest_hash):
    ranks={p:ranking([r for r in records if r['phase']==p],plans[p]) for p in plans}
    valid={pj.Gains(**r['candidate']).key for r in ranks['validation'] if r['all_pass']}
    selected=next((r['candidate'] for r in ranks['operating'] if r['all_pass'] and pj.Gains(**r['candidate']).key in valid),None)
    minimum=lambda key:min((v for r in records for v in r['joint_limit_guard'][key] if v is not None),default=None)
    return dict(schema='g1.pd.multiaxis-yaw.summary.v1',complete=True,simulation_only=True,actual_runs=len(records),
       completed=sum(r['completed'] for r in records),eligible=sum(r['eligible'] for r in records),phase_counts={p:len(v) for p,v in plans.items()},
       selected_simulation_vector=selected,ranking=ranks,
       base_rejections=dict(sorted(base.Counter(r['reason'] for r in records if not r['completed']).items())),
       guard_events=dict(sorted(base.Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
       minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
       manifest_sha256=manifest_hash,hardware_approved=False,recommended_hardware_gains=None,hardware_config_modified=False,
       global_optimum_proven=False,scope='only joint24 tuned; other research gains fixed; known simultaneous cases then frozen new finite conditions')


def audit(folder):
    folder=Path(folder);m=base.read(folder/'manifest.json');stored=base.read(folder/'summary.json')
    deps=base.dependencies()+[Path(__file__)]
    base.require(engine.source_hashes(deps)==m['source_sha256'],'Computational source changed')
    base.require(m['quality_policy']==multi.POLICY and m['yaw_pairs']==base.norm(YAW_PAIRS),'Frozen search changed')
    base.require(m['validation_conditions']==base.norm([dict(motion=asdict(p),scenario=asdict(s)) for _,p,s in validation_conditions()]),'Validation conditions changed')
    for name,digest in {**m['source_sha256'],**m['asset_archive_sha256']}.items():
        base.require(engine.sha256(base.safe_path(folder/'frozen_source',name))==digest,'Frozen source/model archive changed')
    plans={phase:base.read(folder/(phase+'_plan.json')) for phase in ('screen','operating','validation')}
    records=[];rows=[];margins=[];samples=0;case_hashes={}
    expected=[j for p in plans.values() for j in p]
    base.require({f.stem for f in (folder/'cases').glob('*.json')}=={j['case_id'] for j in expected},'Missing/extra raw cases')
    base.require({f.stem for f in (folder/'full_state').glob('*.npz')}=={j['case_id'] for j in expected},'Missing/extra raw traces')
    for j in expected:
        r,a=base.audit_case(folder,j);records.append(r);samples+=len(a['time_s']);case_hashes[r['case_id']]=engine.sha256(folder/'cases'/(r['case_id']+'.json'))
        row=dict(case_id=r['case_id'],phase=r['phase'],kp=json.dumps(r['candidate']['kp']),kd=json.dumps(r['candidate']['kd']),motion=r['motion']['name'],scenario=r['scenario']['name'],completed=r['completed'],eligible=r['eligible'],reason=r['reason'],exclusions=';'.join(r['exclusions']),trace_sha256=r['trace_sha256'])
        for k in ('max_proximal_rmse_rad','max_proximal_tail_error_rad','max_right7_tail_rms_speed_rad_s','max_right7_tail_p2p_rad','torque_limited_ratio','hard_clipped_ratio'):row[k]=r['metrics'][k] if r['metrics'] else None
        rows.append(row)
        for joint in range(29):margins.append(dict(case_id=r['case_id'],joint=joint,**{k:r['joint_limit_guard'][k][joint] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}))
    base.require(plans['screen']==jobs(vectors(),screen_conditions(),'screen'),'Screen plan mismatch')
    sr=[r for r in records if r['phase']=='screen'];best=passing(sr,plans['screen'])[:2]
    base.require(plans['operating']==jobs(best,base.conditions(),'operating'),'Operating shortlist or matrix changed')
    freeze=base.read(folder/'screen_selection.json')
    base.require(freeze['vectors']==base.norm([asdict(g) for g in best]),'Operating freeze differs')
    base.require(freeze['case_hashes']=={r['case_id']:case_hashes[r['case_id']] for r in sr},'Screen outcomes changed after freeze')
    op=[r for r in records if r['phase']=='operating'];survivors=passing(op,plans['operating'])
    base.require(plans['validation']==jobs(survivors,validation_conditions(),'validation'),'Validation plan changed')
    freeze=base.read(folder/'validation_selection.json')
    base.require(freeze['vectors']==base.norm([asdict(g) for g in survivors]),'Validation freeze differs')
    base.require(freeze['case_hashes']=={r['case_id']:case_hashes[r['case_id']] for r in op},'Operating outcomes changed after freeze')
    base.require(make_summary(records,plans,engine.sha256(folder/'manifest.json'))==stored,'Summary changed')
    for name,table in (('all_cases.csv',rows),('all_joint_margins.csv',margins)):
        with (folder/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    result=dict(schema='g1.pd.multiaxis-yaw.audit.v1',passed=True,cases=len(records),all29_500hz_rows=samples,
       all29_margin_records=len(margins),all_cases_sha256=engine.sha256(folder/'all_cases.csv'),source_model_bytes_checked=True,physical_validation=False)
    base.save(folder/'audit.json',result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=6);parser.add_argument('--audit-only',action='store_true');args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers1..8 required')
    folder=args.output.resolve()
    if args.audit_only:print(json.dumps(audit(folder)));return 0
    base.require(not folder.exists(),'Output exists')
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001);source=engine.source_hashes(base.dependencies()+[Path(__file__)])
    archive={}
    for name,digest in assets.items():
        src=base.safe_path(engine.MODEL.parent if name.replace('\\','/').startswith('meshes/') else engine.ROOT,name)
        archive[src.relative_to(engine.ROOT).as_posix()]=digest
    folder.mkdir(parents=True,exist_ok=False)
    for name,digest in {**source,**archive}.items():
        src=base.safe_path(engine.ROOT,name);dest=base.safe_path(folder/'frozen_source',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);base.require(engine.sha256(dest)==digest,'Input freeze mismatch')
    base.save(folder/'manifest.json',dict(schema='g1.pd.multiaxis-yaw.manifest.v1',source_sha256=source,asset_archive_sha256=archive,
      yaw_pairs=base.norm(YAW_PAIRS),quality_policy=multi.POLICY,
      validation_conditions=base.norm([dict(motion=asdict(p),scenario=asdict(s)) for _,p,s in validation_conditions()]),
      mujoco=mujoco.__version__,numpy=np.__version__,python=platform.python_version(),platform=platform.platform(),workers=args.workers,
      simulation_only=True,hardware_approved=False,scope='known 24yaw failures motivate bounded isolated refinement; no live change'))
    records=[];plans={}
    with ProcessPoolExecutor(max_workers=args.workers,initializer=base.expanded.init_worker) as pool:
        plans['screen']=jobs(vectors(),screen_conditions(),'screen');base.save(folder/'screen_plan.json',plans['screen'])
        sr=block(pool,folder,plans['screen']);records+=sr;best=passing(sr,plans['screen'])[:2]
        base.save(folder/'screen_selection.json',dict(vectors=base.norm([asdict(g) for g in best]),case_hashes={r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in sr}))
        plans['operating']=jobs(best,base.conditions(),'operating');base.save(folder/'operating_plan.json',plans['operating'])
        op=block(pool,folder,plans['operating']);records+=op;survivors=passing(op,plans['operating'])
        base.save(folder/'validation_selection.json',dict(vectors=base.norm([asdict(g) for g in survivors]),case_hashes={r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in op}))
        plans['validation']=jobs(survivors,validation_conditions(),'validation');base.save(folder/'validation_plan.json',plans['validation'])
        records+=block(pool,folder,plans['validation'])
    result=make_summary(records,plans,engine.sha256(folder/'manifest.json'));base.save(folder/'summary.json',result)
    checked=audit(folder);base.save(folder/'progress.json',dict(complete=True,done=len(records),audited=checked['passed']))
    print('YAW_RESULT '+json.dumps({k:v for k,v in result.items() if k!='ranking'}),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
