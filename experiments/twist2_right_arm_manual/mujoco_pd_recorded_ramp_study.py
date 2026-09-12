"""Separate causal20ms command-pipeline comparison, OFFLINE ONLY.
Original raw-study outcomes stay unchanged. This is exploratory, not PD-only validation.

Only an explicit input file is read. No live recording, sockets, robot connection,
model-limit override or automatic deployment. Existing two candidates are frozen.
This is open-loop target replay, not receipt/acceptance/robot-response validation.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
import csv,json,math,platform,shutil
from pathlib import Path
import numpy as np
import mujoco_pd_recorded_ramp_core as core
import mujoco_pd_recording as recording
import mujoco_pd_multiaxis_study as base
import mujoco_pd_operating_study as operating
from mujoco_pd_independent_study import VECTORS, SCENARIOS
from mujoco_pd_expand_audit import safe_path
engine=core.engine;pj=core.pj
CLOCKS=('send','sample')


def save(path,value):base.save(path,value)
def read(path):return base.read(path)
def norm(value):return base.norm(value)
def require(ok,message):base.require(ok,message)


def jobs(captures,smoke=False):
    require(0<len(captures)<=8,'One explicit log must contain1..8qualified episodes')
    plans=[]
    for episode,c in enumerate(captures):
        c.validate()
        for g in VECTORS:
            g.validate()
            for clock in (CLOCKS[:1] if smoke else CLOCKS):
                for s in (SCENARIOS[:1] if smoke else SCENARIOS):
                    s.validate()
                    plans.append(dict(case_id=f'case_{len(plans):04d}',episode=episode,
                        candidate=norm(asdict(g)),clock=clock,scenario=asdict(s)))
    return plans


def write_capture(folder,i,c):
    dest=Path(folder)/'inputs'/f'episode_{i:02d}.npz'
    require(not dest.exists(),'Normalized capture already exists')
    np.savez_compressed(dest,send_time_s=c.send_time_s,sample_time_s=c.sample_time_s,
                        joints=c.joints,sequence=c.sequence,events=np.array(c.events,dtype='U24'))
    save(dest.with_suffix('.json'),c.metadata())


def load_capture(folder,i):
    dest=Path(folder)/'inputs'/f'episode_{i:02d}.npz';m=read(dest.with_suffix('.json'))
    with np.load(dest,allow_pickle=False) as z:
        c=recording.Capture(m['source_sha256'],m['first_line'],m['last_line'],m['profile'],
            z['send_time_s'],z['sample_time_s'],z['joints'],z['sequence'],tuple(z['events'].tolist()),m['ack_records_inside'])
    require(c.metadata()==m,'Normalized recording metadata changed');return c


def run_case(job,folder):
    c=load_capture(folder,job['episode'])
    r,a=core.simulate(c,pj.Gains(**job['candidate']),core.core.Coupled(**job['scenario']),job['clock'])
    r.update(case_id=job['case_id'],episode=job['episode'])
    dest=Path(folder)/'full_state'/(r['case_id']+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
    require(not dest.exists(),'Trace exists')
    np.savez_compressed(dest,**a);r.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    save(Path(folder)/'cases'/(r['case_id']+'.json'),r);return r


def summarize(records,plan,manifest_hash,smoke=False):
    expected={j['case_id']:j for j in plan};seen={r['case_id']:r for r in records}
    require(len(expected)==len(plan) and len(seen)==len(records) and set(seen)==set(expected),'Missing/duplicate matrix cell')
    records=sorted(records,key=lambda r:r['case_id'])
    for r in records:
        require(all(norm(r[k])==expected[r['case_id']][k] for k in ('candidate','episode','clock','scenario')),'Plan mismatch')
        require(r['simulation_only'] is True and r['hardware_approved'] is False and
                r['hardware_config_modified'] is False and r['recommended_hardware_gains'] is None,'Hardware claim forbidden')
    ranking=[]
    for g in VECTORS:
        rs=[r for r in records if norm(r['candidate'])==norm(asdict(g))]
        passed=bool(rs) and all(r['eligible'] for r in rs)
        worst=max((r['metrics']['max_right7_recorded_rmse_rad'] for r in rs if r['metrics']),default=None)
        ranking.append(dict(candidate=norm(asdict(g)),cases=len(rs),passed=sum(r['eligible'] for r in rs),
            all_pass=passed,worst_right7_rmse_rad=worst if passed else None,partial_worst_rmse_rad=worst,
            failures=[dict(case_id=r['case_id'],reason=r['reason'],exclusions=r['exclusions']) for r in rs if not r['eligible']]))
    ranking.sort(key=lambda r:(not r['all_pass'],r['worst_right7_rmse_rad'] if r['all_pass'] else math.inf,tuple(r['candidate']['kp'])))
    minimum=lambda k:min((v for r in records for v in r['joint_limit_guard'][k] if v is not None),default=None)
    return dict(schema='g1.pd.recorded-ramp-study.v1',complete=True,simulation_only=True,smoke=smoke,
        actual_runs=len(records),completed=sum(r['completed'] for r in records),eligible=sum(r['eligible'] for r in records),
        ranking=ranking,selected_filtered_pipeline_vector=next((r['candidate'] for r in ranking if r['all_pass']),None) if not smoke else None,
        base_rejections=dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
        exclusions=dict(sorted(Counter(x for r in records if not r['eligible'] for x in r['exclusions']).items())),
        guard_events=dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
        minimum_soft_margin_rad=minimum('minimum_soft_margin_rad'),minimum_model_hard_margin_rad=minimum('minimum_hard_margin_rad'),
        minimum_stopping_slack_rad=minimum('minimum_stopping_slack_rad'),
        simulated_seconds=math.fsum(r['final_time_s'] for r in records),manifest_sha256=manifest_hash,
        hardware_approved=False,recommended_hardware_gains=None,hardware_config_modified=False,
        global_optimum_proven=False,pd_only_optimum_proven=False,requires_command_prefilter=True,
        command_filter=dict(core.COMMAND_FILTER),scope='exploratory causal20mscommand pipeline; original recorded-goal scores; not the unmodified controller or PD alone')


def check_guard(r,a):
    g=r['joint_limit_guard'];e=g['envelope'];dt=r['scenario']['dt']
    steps=round(engine.WARMUP/dt)+math.ceil((r['common_rest_start_s']+core.POST_HOLD_S)/dt)
    require(e['joints']==29 and e['reserve_rad']>=.05 and not g['hardware_validated'],'Guard contract changed')
    for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad','minimum_soft_witness'):
        require(len(g[k])==29,'Missing joint extrema')
    for j,w in enumerate(g['minimum_soft_witness']):
        if w is not None:
            require(math.isclose(min(w['q']-e['soft_lower'][j],e['soft_upper'][j]-w['q']),g['minimum_soft_margin_rad'][j],abs_tol=1e-12),'Margin witness differs')
    if r['completed']:
        require(g['observations']==2*steps and r['physics']['steps']==steps,'Missing pre/post/final coverage')
        require(len(a['time_s'])==math.ceil(steps/round(.002/dt)),'Missing writer samples')
        require(math.isclose(r['final_time_s'],steps*dt,abs_tol=1e-7),'Wrong final time')
    if r['eligible']:
        require(r['completed'] and g['event'] is None and g['no_intervention'],'Guard intervention cannot pass')
        for k,limit in (('minimum_soft_margin_rad',e['reserve_rad']),('minimum_hard_margin_rad',0),('minimum_stopping_slack_rad',0)):
            require(all(v is not None and math.isfinite(v) and v>limit+1e-10 for v in g[k]),'Insufficient clearance')
        for k in ('q','ref','cmd'):
            require(np.all(a[k]>np.array(e['inner_lower'])+1e-10) and np.all(a[k]<np.array(e['inner_upper'])-1e-10),'At inner limit')
        q=np.array(r['final_q']);require(np.all(q>np.array(e['inner_lower'])+1e-10) and np.all(q<np.array(e['inner_upper'])-1e-10),'Final state at limit')


def audit_case(folder,job,c):
    r=read(Path(folder)/'cases'/(job['case_id']+'.json'))
    require(all(norm(r[k])==job[k] for k in ('case_id','candidate','episode','clock','scenario')),'Case identity changed')
    require(r['recording']==c.metadata() and r['quality_policy']==core.POLICY,'Source mapping or quality changed')
    require(r['common_rest_start_s']==float(c.times(r['clock'])[-1]) and r['synthetic_post_hold_s']==core.POST_HOLD_S,'Tail duration changed')
    require(r['simulation_only'] and not r['hardware_approved'] and not r['hardware_config_modified'] and r['recommended_hardware_gains'] is None,'Hardware claim')
    contract=engine.load_contract();g=pj.Gains(**r['candidate']);g.validate();s=core.core.Coupled(**r['scenario']);s.validate()
    kp,kd=engine.candidate_gains(contract,*pj.BASE);kp[22:26]=g.kp;kd[22:26]=g.kd
    require(r['initial_q']==contract.baseline.tolist() and np.array_equal(kp,r['gains_kp']) and np.array_equal(kd,r['gains_kd']),'Gain/baseline mismatch')
    require(r['legacy_hardware_gain_compatible']==all(v<=100 for v in g.kp),'Live compatibility claim changed')
    path=safe_path(folder,r['trace']);require(engine.sha256(path)==r['trace_sha256'],'Trace hash changed')
    with np.load(path,allow_pickle=False) as z:a={k:z[k] for k in z.files}
    score=core.evaluate(a,c,r['clock'],r['completed'],r['reason'],r['physics'])
    require(all(r[k]==v for k,v in score.items()),'Metrics/eligibility mismatch')
    require(np.allclose(a['requested'],kp*(a['cmd']-a['q'])-kd*a['dq'],rtol=1e-12,atol=1e-12),'PD torque changed')
    n=len(a['time_s']);step=np.arange(n)*round(.002/s.dt);tick=step//round(.02/s.dt)*round(.02/s.dt)
    time=(tick-round(3./s.dt))*s.dt;ids=np.searchsorted(c.times(r['clock']),np.maximum(time,0),side='right')-1
    ids[step<round(3./s.dt)]=-1;reference=np.tile(contract.baseline,(n,1));mask=ids>=0;reference[mask,22:]=c.joints[ids[mask]]
    require(np.array_equal(ids,a['source_index']) and np.array_equal(reference,a['ref']),'Original recorded target or source index changed')
    require(np.array_equal(step*s.dt,a['time_s']),'Writer time changed')
    # Reconstruction includes the captured today/yesterday rate, with no hidden filtering.
    previous=np.vstack((contract.baseline,a['cmd'][:-1])) if n else np.empty((0,29))
    rates=core.RATES.copy()
    if c.profile=='today':rates[22:26]=math.pi/2;rates[26:]=math.pi
    previous_tick=tick-round(.02/s.dt);prior_time=(previous_tick-round(3./s.dt))*s.dt
    prior_ids=np.searchsorted(c.times(r['clock']),np.maximum(prior_time,0),side='right')-1
    prior_ids[previous_tick<round(3./s.dt)]=-1
    prior_ref=np.tile(contract.baseline,(n,1));has_prior=prior_ids>=0;prior_ref[has_prior,22:]=c.joints[prior_ids[has_prior]]
    age=step*s.dt-tick*s.dt;alpha=np.minimum(1.,age/.02)
    filtered=prior_ref+alpha[:,None]*(reference-prior_ref)
    require(np.allclose(filtered,a['writer_reference'],rtol=1e-12,atol=1e-12),'Causal prefilter relation changed')
    require(r['command_filter']==core.COMMAND_FILTER and r['requires_command_prefilter'] is True and r['pd_only_optimum_proven'] is False,'Filtered pipeline misclassified')
    proposed=np.clip(a['writer_reference'],previous-rates*.002,previous+rates*.002)
    proposed=np.clip(proposed,contract.lower,contract.upper);before=proposed.copy();soft=.5*contract.torque
    proposed=np.clip(proposed,a['q']+(-soft+kd*a['dq'])/kp,a['q']+(soft+kd*a['dq'])/kp)
    limited=np.abs(proposed-before)>1e-7;proposed=np.clip(proposed,contract.lower,contract.upper)
    require(np.array_equal(proposed,a['cmd']) and np.array_equal(np.any(limited[:,22:],axis=1),a['torque_limited']),'Writer rate/torque limiter changed')
    check_guard(r,a)
    operating.coupled.check_model_evidence(dict(study_scenario_contract=r['scenario'],coupled_model_evidence=r['model_evidence'],torque_path=dict(delay_s=s.delay_s,lag_s=s.lag_s)))
    return r,a


def dependencies():
    names=('mujoco_pd_recording.py','mujoco_pd_recorded_core.py','mujoco_pd_recorded_study.py',
        'mujoco_pd_independent_study.py','mujoco_pd_independent_timing.py',
        'mujoco_pd_recorded_ramp_core.py','mujoco_pd_recorded_ramp_study.py')
    return list(dict.fromkeys(base.dependencies()+[Path(__file__).with_name(n) for n in names]))


def audit(folder):
    folder=Path(folder);m=read(folder/'manifest.json');plan=read(folder/'plan.json')
    require(engine.source_hashes(dependencies())==m['source_sha256'],'Calculation sources changed')
    require(m.get('simulation_only') is True and m.get('hardware_approved') is False and m.get('schema')=='g1.pd.recorded-ramp.manifest.v1','Manifest hardware/schema claim')
    require(m['clocks']==list(CLOCKS),'Replay clocks changed')
    require(m['quality_policy']==core.POLICY and m['vectors']==norm([asdict(g) for g in VECTORS]),'Policy/vector changed')
    for name,digest in {**m['source_sha256'],**m['asset_archive_sha256']}.items():
        require(engine.sha256(safe_path(folder/'frozen_source',name))==digest,'Archived source/model changed')
    raw=folder/'inputs/recording.jsonl';require(engine.sha256(raw)==m['recording_sha256'],'Original recording changed')
    captures,info=recording.extract(raw);info['file']=m['input_name']
    require(info==m['input_inventory'] and len(captures)==m['episodes'],'Input episode inventory differs')
    for i,c in enumerate(captures):
        frozen=load_capture(folder,i)
        require(c.metadata()==frozen.metadata(),'Input receipt mismatch')
        for key in ('joints','send_time_s','sample_time_s','sequence','events'):
            require(np.array_equal(getattr(c,key),getattr(frozen,key)),'Normalized input changed')
    require(plan==jobs(captures,m['smoke']) and engine.sha256(folder/'plan.json')==m['plan_sha256'],'Frozen matrix differs')
    for sub,ext in (('cases','*.json'),('full_state','*.npz')):
        require({p.stem for p in (folder/sub).glob(ext)}=={j['case_id'] for j in plan},'Missing/extra result')
    records=[];table=[];margins=[];samples=0
    for job in plan:
        r,a=audit_case(folder,job,captures[job['episode']]);records.append(r);samples+=len(a['time_s'])
        row={k:r[k] for k in ('case_id','episode','clock','completed','eligible','reason')}
        row.update(kp=json.dumps(r['candidate']['kp']),kd=json.dumps(r['candidate']['kd']),scenario=r['scenario']['name'],
            exclusions=';'.join(r['exclusions']),samples=len(a['time_s']),trace_sha256=r['trace_sha256'])
        for k in ('max_right7_recorded_rmse_rad','max_proximal_recorded_rmse_rad','torque_limited_ratio','hard_clipped_ratio'):
            row[k]=r['metrics'][k] if r['metrics'] else None
        table.append(row)
        for j in range(29):margins.append(dict(case_id=r['case_id'],joint=j,**{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}))
    require(summarize(records,plan,engine.sha256(folder/'manifest.json'),m['smoke'])==read(folder/'summary.json'),'Summary/ranking differs')
    for name,rows in (('all_cases.csv',table),('all_joint_margins.csv',margins)):
        with (folder/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(passed=True,cases=len(records),all29_500hz_rows=samples,all29_margin_records=len(margins),
        all_cases_sha256=engine.sha256(folder/'all_cases.csv'),recorded_input_reparsed=True,source_model_bytes_checked=True,
        scope='all29sampled traces, source-target timing, gains/PD/limiter, endpoint quality and guard extrema; not independent continuous physics or robot response',physical_validation=False)
    save(folder/'audit.json',result);return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recording',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--smoke',action='store_true');p.add_argument('--audit-only',action='store_true')
    args=p.parse_args(argv)
    if not 1<=args.workers<=6:p.error('workers must be1..6')
    folder=args.output.resolve()
    if args.audit_only:print(json.dumps(audit(folder)));return 0
    require(not folder.exists(),'Output exists; never overwrite')
    require(args.recording is not None and args.recording.is_file(),'An explicit existing recording file is required')
    require(not args.recording.resolve().is_relative_to(folder),'Output cannot contain the source')
    captures,info=recording.extract(args.recording);plan=jobs(captures,args.smoke)
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001);archive={}
    for name,digest in assets.items():
        src=safe_path(engine.MODEL.parent if name.replace(chr(92),'/').startswith('meshes/') else engine.ROOT,name)
        require(engine.sha256(src)==digest,'Asset changed');archive[src.relative_to(engine.ROOT).as_posix()]=digest
    sources=engine.source_hashes(dependencies());folder.mkdir(parents=True,exist_ok=False)
    (folder/'inputs').mkdir();shutil.copyfile(args.recording,folder/'inputs/recording.jsonl')
    require(engine.sha256(folder/'inputs/recording.jsonl')==info['source_sha256'],'Recording changed during freeze')
    for name,digest in {**sources,**archive}.items():
        src=safe_path(engine.ROOT,name);dest=safe_path(folder/'frozen_source',name);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest);require(engine.sha256(dest)==digest,'Source freeze failed')
    for i,c in enumerate(captures):write_capture(folder,i,c)
    save(folder/'plan.json',plan)
    manifest=dict(schema='g1.pd.recorded-ramp.manifest.v1',simulation_only=True,smoke=args.smoke,
        source_sha256=sources,asset_archive_sha256=archive,input_name=args.recording.name,input_inventory=info,
        recording_sha256=info['source_sha256'],episodes=len(captures),vectors=norm([asdict(g) for g in VECTORS]),
        plan_sha256=engine.sha256(folder/'plan.json'),quality_policy=core.POLICY,
        clocks=CLOCKS,mujoco=mujoco.__version__,numpy=np.__version__,python=platform.python_version(),platform=platform.platform(),
        workers=args.workers,hardware_approved=False,limitations=['sent targets are not received/accepted/measured robot states',
        'fixed pelvis and idealized motor with hypothetical delays','no IK or state-machine replay',
        'recorded speed profile; inherited conservative1.5rad/s measured-speed gate','research rollKp300outside unchanged live100bound'])
    save(folder/'manifest.json',manifest);records=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=base.expanded.init_worker) as pool:
        futures=[pool.submit(run_case,j,str(folder)) for j in plan]
        for f in as_completed(futures):
            r=f.result();records.append(r)
            progress=dict(complete=False,done=len(records),total=len(plan),eligible=sum(x['eligible'] for x in records))
            save(folder/'progress.json',progress);print(json.dumps(progress),flush=True)
    result=summarize(records,plan,engine.sha256(folder/'manifest.json'),args.smoke);save(folder/'summary.json',result)
    checked=audit(folder);save(folder/'progress.json',dict(complete=True,done=len(records),audited=checked['passed']))
    print('RECORDED_RESULT '+json.dumps(result),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
