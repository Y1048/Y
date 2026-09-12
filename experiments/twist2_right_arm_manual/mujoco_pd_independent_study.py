"""Frozen two-candidate independent-timing study, all cells attempted; offline only.
No live/IK/robot settings are imported or changed. No adaptive retuning.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
import argparse,csv,json,math,platform,shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_independent_timing as core
import mujoco_pd_multiaxis_study as base
from mujoco_pd_expand_audit import safe_path
engine=core.engine;pj=core.pj
VECTORS=(pj.Gains((100.,300.,64.,100.),(1.4,4.,1.,1.4)),
         pj.Gains((100.,300.,72.,100.),(1.4,4.,1.,1.4)))
SCENARIOS=base.SCENARIOS+(
 core.core.Coupled('light_delayed',.9,.65,.2,.003,.005,.0005),
 core.core.Coupled('mixed_delayed',1.4,.9,.2,.003,.007,.001))

def motions():
    M=core.Motion
    return (
      M('synchronous_control',delays_s=(0.,)*4),
      M('forward_stagger'),
      M('reverse_mixed',delays_s=(.9,.6,.3,0.),scales=(-1.,1.,-1.,1.)),
      M('different_periods',delays_s=(0.,.18,.54,.82),amplitudes_deg=(4.,8.,6.,10.),speeds_deg_s=(10.,23.,17.,27.),cycles=(3,4,3,5)),
      M('paired_release',delays_s=(0.,.8,0.,.8),scales=(1.,-1.,-1.,1.),amplitudes_deg=(8.,6.,10.,4.),speeds_deg_s=(20.,17.,27.,10.)),
      M('reverse_periods',delays_s=(.76,.24,1.12,0.),scales=(-1.,-1.,1.,1.),amplitudes_deg=(10.,6.,8.,4.),speeds_deg_s=(27.,15.,23.,10.),cycles=(4,3,5,3)),
      M('long_stagger',delays_s=(0.,.3,.6,.9),scales=(1.,-1.,1.,-1.),cycles=(6,6,6,6),post_hold_s=30.),
      M('shifted_start',delays_s=(.4,0.,.8,.2),scales=(-1.,1.,1.,-1.),elbow_offset_deg=-6.,amplitudes_deg=(6.,9.,11.,7.),speeds_deg_s=(17.,23.,27.,19.),post_hold_s=10.))

def jobs(smoke=False):
    mm=motions()[:1] if smoke else motions()
    ss=SCENARIOS[:1] if smoke else SCENARIOS
    result=[]
    for g in VECTORS:
        for m in mm:
            m.validate()
            for s in ss:
                s.validate()
                result.append(dict(case_id=f'case_{len(result):04d}',candidate=base.norm(asdict(g)),
                    motion=base.norm(asdict(m)),scenario=asdict(s)))
    return result

def run_case(job,folder):
    folder=Path(folder)
    r,a=core.simulate(core.Motion(**job['motion']),pj.Gains(**job['candidate']),core.core.Coupled(**job['scenario']))
    r['case_id']=job['case_id']
    dest=folder/'full_state'/(r['case_id']+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
    base.require(not dest.exists(),'Trace exists')
    np.savez_compressed(dest,**a)
    r.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    base.save(folder/'cases'/(r['case_id']+'.json'),r)
    return r

def summarize(records,plan,manifest_hash,smoke=False):
    seen={r['case_id']:r for r in records};expected={j['case_id']:j for j in plan}
    base.require(len(seen)==len(records) and len(expected)==len(plan) and set(seen)==set(expected),'Missing/duplicate cases')
    for r in records:
        base.require(all(base.norm(r[k])==expected[r['case_id']][k] for k in ('candidate','motion','scenario')),'Wrong plan identity')
        base.require(r['simulation_only'] is True and r['hardware_approved'] is False and r['hardware_config_modified'] is False and r['recommended_hardware_gains'] is None,'Hardware claim')
    ranks=[]
    for g in VECTORS:
        rs=sorted((r for r in records if base.norm(r['candidate'])==base.norm(asdict(g))),key=lambda r:r['case_id'])
        good=bool(rs) and all(r['eligible'] for r in rs)
        maximum=max((r['metrics']['max_proximal_rmse_rad'] for r in rs if r['metrics']),default=None)
        ranks.append(dict(candidate=base.norm(asdict(g)),cases=len(rs),passed=sum(r['eligible'] for r in rs),all_pass=good,
          worst_rmse_rad=maximum if good else None,partial_worst_rmse_rad=maximum,
          failures=[dict(case_id=r['case_id'],reason=r['reason'],exclusions=r['exclusions']) for r in rs if not r['eligible']]))
    ranks.sort(key=lambda r:(not r['all_pass'],r['worst_rmse_rad'] if r['all_pass'] else math.inf,tuple(r['candidate']['kp'])))
    minimum=lambda k:min((x for r in records for x in r['joint_limit_guard'][k] if x is not None),default=None)
    return dict(schema='g1.pd.independent.v1',complete=True,simulation_only=True,smoke=smoke,
      actual_runs=len(records),completed=sum(r['completed'] for r in records),eligible=sum(r['eligible'] for r in records),
      ranking=ranks,selected_simulation_vector=next((r['candidate'] for r in ranks if r['all_pass']),None) if not smoke else None,
      base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
      guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
      minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
      minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),simulated_seconds=math.fsum(r['final_time_s'] for r in records),
      manifest_sha256=manifest_hash,hardware_approved=False,recommended_hardware_gains=None,hardware_config_modified=False,
      global_optimum_proven=False,scope='fixed pelvis; four independent synthetic clocks; two frozen vectors; no recorded VR or physical validation')

def check_guard(r,a):
    g=r['joint_limit_guard'];e=g['envelope'];p=core.Motion(**r['motion']);dt=r['scenario']['dt']
    steps=round(engine.WARMUP/dt)+math.ceil(core.Timeline(p).total/dt)
    if e['joints']!=29 or e['reserve_rad']<.05 or g['hardware_validated']:raise ValueError('Invalid limit contract')
    for key in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad','minimum_soft_witness'):
        if len(g[key])!=29:raise ValueError('Missing all29 guard evidence')
    for j,w in enumerate(g['minimum_soft_witness']):
        if w is not None and not math.isclose(min(w['q']-e['soft_lower'][j],e['soft_upper'][j]-w['q']),g['minimum_soft_margin_rad'][j],abs_tol=1e-12):raise ValueError('Guard witness changed')
    if r['completed']:
        if g['observations']!=2*steps or r['physics']['steps']!=steps:raise ValueError('Missing pre/post/final physics coverage')
        if len(a['time_s'])!=math.ceil(steps/round(.002/dt)):raise ValueError('Missing final writer sample')
        if not math.isclose(r['final_time_s'],steps*dt,abs_tol=1e-7):raise ValueError('Incomplete terminal time')
    if r['eligible']:
        if not r['completed'] or g['event'] is not None or not g['no_intervention']:raise ValueError('Unsafe candidate accepted')
        for key,limit in (('minimum_soft_margin_rad',e['reserve_rad']),('minimum_hard_margin_rad',0),('minimum_stopping_slack_rad',0)):
            if any(x is None or not math.isfinite(x) or x<=limit+1e-10 for x in g[key]):raise ValueError('Insufficient measured clearance')
        for k in ('q','ref','cmd'):
            if np.any(a[k]<=np.array(e['inner_lower'])+1e-10) or np.any(a[k]>=np.array(e['inner_upper'])-1e-10):raise ValueError('Accepted sample at inner boundary')
        final=np.asarray(r['final_q'])
        if np.any(final<=np.array(e['inner_lower'])+1e-10) or np.any(final>=np.array(e['inner_upper'])-1e-10):raise ValueError('Final state at inner boundary')

def audit_case(folder,job):
    folder=Path(folder);r=base.read(folder/'cases'/(job['case_id']+'.json'))
    for k in ('case_id','candidate','motion','scenario'):base.require(base.norm(r[k])==job[k],'Changed identity:'+k)
    m=core.Motion(**r['motion']);m.validate();g=pj.Gains(**r['candidate']);g.validate();s=core.core.Coupled(**r['scenario']);s.validate()
    timeline=core.Timeline(m);contract=core.profile_contract(m.profile())
    base.require(r['quality_policy']==core.POLICY and r['profile']==asdict(m.profile()),'Policy/profile differs')
    base.require(r['common_rest_start_s']==timeline.common_rest_start,'Wrong end of motion')
    base.require(r['hardware_approved'] is False and r['hardware_config_modified'] is False and r['recommended_hardware_gains'] is None and r['simulation_only'] is True,'Hardware claim')
    kp,kd=engine.candidate_gains(contract,*pj.BASE);kp[22:26]=g.kp;kd[22:26]=g.kd
    base.require(np.array_equal(kp,r['gains_kp']) and np.array_equal(kd,r['gains_kd']) and r['initial_q']==contract.baseline.tolist(),'Gain/initial state changed')
    base.require(r['legacy_hardware_gain_compatible']==all(x<=100 for x in g.kp),'Wrong gain-cap compatibility')
    dest=safe_path(folder,r['trace']);base.require(engine.sha256(dest)==r['trace_sha256'],'Trace hash')
    with np.load(dest,allow_pickle=False) as z:a={k:z[k] for k in z.files}
    check=core.evaluate(a,m,r['completed'],r['reason'],r['physics'])
    base.require(all(r[k]==v for k,v in check.items()),'Metrics/eligibility differs')
    base.require(np.allclose(kp*(a['cmd']-a['q'])-kd*a['dq'],a['requested'],rtol=1e-12,atol=1e-12),'PD equation')
    # Rebuild each axis from its original scalar path and own clock. This does
    # not call Timeline.at/reference, and never uses cmd as the reference.
    n=len(a['time_s']);ref=np.tile(contract.baseline,(n,1));seg=np.empty((n,4),dtype='U16');cyc=np.zeros((n,4),dtype=np.int64);phase=cyc.copy()
    stride=round(.02/s.dt);writer=round(.002/s.dt);warm=round(3/s.dt)
    for i in range(4):
        path=core.Path(m.profile(22+i));cache={}
        for row in range(n):
            step=row*writer;tick=step//stride*stride
            if tick not in cache:
                t=max(0.,(tick-warm)*s.dt)-m.delays_s[i]
                if t<0:point=core.Point(segment='waiting')
                else:
                    point=path.at(t)
                    if t>=path.motion_total:point=core.replace(point,segment='post_hold')
                cache[tick]=point
            p=cache[tick]
            if step>=warm:ref[row,22+i]+=m.scales[i]*p.offset
            seg[row,i]=p.segment if step>=warm else 'warmup';cyc[row,i]=p.cycle;phase[row,i]=p.phase if step>=warm else 0
    base.require(np.array_equal(ref,a['ref']) and np.array_equal(seg,a['axis_segment']) and np.array_equal(cyc,a['axis_cycle']) and np.array_equal(phase,a['axis_phase']),'Independent reference/metadata mismatch')
    base.require(np.array_equal(a['segment'],seg[:,0]) and np.array_equal(a['cycle'],cyc[:,0]) and np.array_equal(a['phase'],phase[:,0]),'Scalar metadata mismatch')
    base.require(r['actual_samples']==n and r['expected_samples']==math.ceil((round(3/s.dt)+math.ceil(timeline.total/s.dt))/writer),'Sample capacity differs')
    check_guard(r,a)
    base.operating.coupled.check_model_evidence(dict(study_scenario_contract=r['scenario'],coupled_model_evidence=r['model_evidence'],torque_path=dict(delay_s=s.delay_s,lag_s=s.lag_s)))
    return r,a

def dependencies():
    return base.dependencies()+[Path(__file__),Path(core.__file__)]


# This exact archived driver predates deterministic elapsed-time aggregation.
# Its simulator/model/plan inputs remain byte-checked; archived code is never run.
LEGACY_ORDER_DRIVER_SHA = "411ebc009c79c01b58497db472132ae7ced2b4cb7c4b28ac7d27ea031ba089b6"

def check_source_versions(current, frozen):
    base.require(set(current)==set(frozen), 'Source dependency set changed')
    changed=[p for p in current if current[p]!=frozen[p]]
    if changed:
        base.require(len(changed)==1 and changed[0].replace("\\", "/").endswith("/mujoco_pd_independent_study.py")
                     and frozen[changed[0]]==LEGACY_ORDER_DRIVER_SHA, 'Computation source changed')

def check_summary_values(expected, recorded):
    base.require(set(expected)==set(recorded), 'Summary field set differs')
    for k in expected:
        if k=='simulated_seconds':
            base.require(math.isfinite(recorded[k]) and math.isclose(expected[k],recorded[k],rel_tol=0.,abs_tol=1e-9), 'Elapsed-time aggregate differs')
        else:
            base.require(expected[k]==recorded[k], 'Summary/ranking differs: '+k)

def audit(folder):
    folder=Path(folder);manifest=base.read(folder/'manifest.json');plan=base.read(folder/'plan.json')
    check_source_versions(engine.source_hashes(dependencies()),manifest['source_sha256'])
    base.require(manifest['policy']==core.POLICY and manifest['vectors']==base.norm([asdict(g) for g in VECTORS]),'Frozen settings changed')
    base.require(plan==jobs(manifest['smoke']) and engine.sha256(folder/'plan.json')==manifest['plan_sha256'],'Plan/coverage changed')
    for name,h in {**manifest['source_sha256'],**manifest['asset_archive_sha256']}.items():
        base.require(engine.sha256(safe_path(folder/'frozen_source',name))==h,'Frozen source/model changed')
    expected={j['case_id'] for j in plan}
    for sub,suffix in (('cases','*.json'),('full_state','*.npz')):
        base.require({p.stem for p in (folder/sub).glob(suffix)}==expected,'Missing/extra evidence')
    records=[];rows=[];margins=[];count=0
    for job in plan:
        r,a=audit_case(folder,job);records.append(r);count+=len(a['time_s'])
        row=dict(case_id=r['case_id'],candidate=json.dumps(r['candidate'],sort_keys=True),motion=r['motion']['name'],scenario=r['scenario']['name'],completed=r['completed'],eligible=r['eligible'],reason=r['reason'],exclusions=';'.join(r['exclusions']),trace_sha256=r['trace_sha256'])
        for k in ('max_proximal_rmse_rad','max_axis_hold_error_rad','max_axis_hold_speed_rad_s','torque_limited_ratio','hard_clipped_ratio'):row[k]=r['metrics'][k] if r['metrics'] else None
        rows.append(row)
        for j in range(29):margins.append(dict(case_id=r['case_id'],joint=j,**{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}))
    expected_summary=summarize(records,plan,engine.sha256(folder/'manifest.json'),manifest['smoke'])
    check_summary_values(expected_summary,base.read(folder/'summary.json'))
    for name,values in (('all_cases.csv',rows),('all_joint_margins.csv',margins)):
        with (folder/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
    report=dict(passed=True,cases=len(records),all29_500hz_rows=count,margin_records=len(margins),source_model_checked=True,all_cases_sha256=engine.sha256(folder/'all_cases.csv'),physical_validation=False)
    base.save(folder/'audit.json',report);return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--workers',type=int,default=4);parser.add_argument('--smoke',action='store_true');parser.add_argument('--audit-only',action='store_true');args=parser.parse_args(argv)
    if not 1<=args.workers<=6:parser.error('workers1..6 required')
    folder=args.output.resolve()
    if args.audit_only:print(json.dumps(audit(folder)));return 0
    base.require(not folder.exists(),'Output already exists')
    import mujoco
    plan=jobs(args.smoke);source=engine.source_hashes(dependencies());_,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    archive={}
    for name,h in assets.items():
        src=safe_path(engine.MODEL.parent if name.replace('\\','/').startswith('meshes/') else engine.ROOT,name)
        archive[src.relative_to(engine.ROOT).as_posix()]=h
    folder.mkdir(parents=True,exist_ok=False)
    for name,h in {**source,**archive}.items():
        src=safe_path(engine.ROOT,name);dest=safe_path(folder/'frozen_source',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);base.require(engine.sha256(dest)==h,'Freeze mismatch')
    base.save(folder/'plan.json',plan)
    base.save(folder/'manifest.json',dict(schema='g1.pd.independent.manifest.v1',simulation_only=True,smoke=args.smoke,source_sha256=source,asset_archive_sha256=archive,
      plan_sha256=engine.sha256(folder/'plan.json'),policy=core.POLICY,vectors=base.norm([asdict(g) for g in VECTORS]),
      mujoco=mujoco.__version__,numpy=np.__version__,python=platform.python_version(),platform=platform.platform(),workers=args.workers,
      hardware_approved=False,limitations=['synthetic independently timed paths, not recorded VR','fixed pelvis','hypothetical torque-path delay','Kp23=300 outside live cap']))
    records=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=base.expanded.init_worker) as pool:
        for f in as_completed([pool.submit(run_case,j,str(folder)) for j in plan]):
            records.append(f.result())
            if len(records)%8==0 or len(records)==len(plan):
                p=dict(complete=False,done=len(records),total=len(plan),eligible=sum(r['eligible'] for r in records));base.save(folder/'progress.json',p);print(json.dumps(p),flush=True)
    base.save(folder/'summary.json',summarize(records,plan,engine.sha256(folder/'manifest.json'),args.smoke))
    report=audit(folder);base.save(folder/'progress.json',dict(complete=True,done=len(records),audited=report['passed']))
    print('INDEPENDENT_RESULT '+json.dumps(base.read(folder/'summary.json')),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
