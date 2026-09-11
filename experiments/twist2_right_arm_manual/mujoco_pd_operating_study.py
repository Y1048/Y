"""Offline full operating matrix: independent proximal-axis excitation and long runs.

Every declared matrix cell is attempted, including previously failed gains.
No deployment, no SDK/DDS, no live launcher, no post-hoc threshold relaxation.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
import argparse,csv,itertools,json,math,platform
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from pathlib import Path
import numpy as np
import mujoco_pd_operating_core as core
import mujoco_pd_expand as expanded
import mujoco_pd_coupled_stress as coupled
from mujoco_pd_expand_audit import safe_path
engine=core.engine
PAIRS=((80.,1.),(88.,2.),(96.,1.5),(96.,2.),(100.,1.275),(100.,1.3),
       (100.,1.4),(100.,1.5),(100.,1.75),(100.,2.),(100.,2.5),(100.,3.))
SCENARIOS=(core.Coupled('nominal'),core.Coupled('half',dt=.0005),
 core.Coupled('light',.75,.5,.5),core.Coupled('heavy',1.35,1.25,.35,.002,.006),
 core.Coupled('previous_boundary',1.35,.85,.15,.004,.008,.0005),
 core.Coupled('high_friction',1.25,1.5,1.5))

def profiles():
    normal=[];long=[]
    for joint in range(22,26):
        for name,kw in (('standard',{}),('small',{'amplitude_deg':4.,'speed_deg_s':10.,'acceleration_deg_s2':30.}),
          ('large',{'amplitude_deg':12.}),('fast',{'speed_deg_s':30.}),('elbow_plus10',{'elbow_offset_deg':10.})):
            normal.append(core.Profile(f'j{joint}_{name}',joint=joint,**kw))
        for name,kw in (('repeat12',{'cycles':12,'post_hold_s':5.}),('soak30',{'post_hold_s':30.}),
                       ('elbow_minus10_repeat6',{'elbow_offset_deg':-10.,'cycles':6,'post_hold_s':5.})):
            long.append(core.Profile(f'j{joint}_{name}',joint=joint,**kw))
    return normal,long

def make_plan(smoke=False):
    if smoke:
        configs=[('main',core.Profile('j22_standard'),SCENARIOS[0]),
                 ('main',core.Profile('j23_standard',joint=23),SCENARIOS[0])]
        pairs=((100.,1.4),)
    else:
        normal,long=profiles();pairs=PAIRS
        configs=[('main',p,s) for p,s in itertools.product(normal,SCENARIOS)]
        configs += [('long',p,s) for p,s in itertools.product(long,(SCENARIOS[0],SCENARIOS[4]))]
    return [{'case_id':f'case_{i:05d}','kp':p,'kd':d,'phase':phase,'profile':asdict(profile),'scenario':asdict(scenario)}
       for i,((p,d),(phase,profile,scenario)) in enumerate(itertools.product(pairs,configs))]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,r):expanded.save_json(Path(p),r)

def run_case(job,folder):
    p=core.Profile(**job['profile']);s=core.Coupled(**job['scenario'])
    result,arrays=core.simulate(p,job['kp'],job['kd'],s)
    result.update(case_id=job['case_id'],phase=job['phase'])
    dest=Path(folder)/'full_state'/(job['case_id']+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(dest,**arrays)
    result.update(trace=dest.relative_to(folder).as_posix(),trace_sha256=engine.sha256(dest))
    save(Path(folder)/'cases'/(job['case_id']+'.json'),result)
    return result

def summarize(records,plan,manifest_hash):
    expected={p['case_id']:p for p in plan};seen={r['case_id']:r for r in records}
    if len(seen)!=len(records) or set(seen)!=set(expected):raise ValueError('Missing/duplicate matrix cell')
    for k,r in seen.items():
        if any(r[field]!=expected[k][field] for field in ('kp','kd','phase','profile','scenario')):raise ValueError('Matrix cell changed')
    pairs=sorted({(r['kp'],r['kd']) for r in records});ranking=[];axes=[]
    def row(rs,pair,joint=None):
        good=all(r['eligible'] for r in rs)
        return {'pair':list(pair),'joint':joint,'cases':len(rs),'passed':sum(r['eligible'] for r in rs),
          'all_pass':good,'selectable_worst_rmse_rad':max(r['metrics']['active_rmse_rad'] for r in rs) if good else None,
          'partial_worst_rmse_rad':max((r['metrics']['active_rmse_rad'] for r in rs if r['metrics']),default=None),
          'max_tail_error_rad':max((r['metrics']['max_active_tail_error_rad'] for r in rs if r['metrics'] and r['metrics']['max_active_tail_error_rad'] is not None),default=None),
          'failures':dict(Counter(reason for r in rs if not r['eligible'] for reason in r['exclusions']))}
    for pair in pairs:
        rs=[r for r in records if (r['kp'],r['kd'])==pair];ranking.append(row(rs,pair))
        for j in sorted({r['profile']['joint'] for r in rs}):axes.append(row([r for r in rs if r['profile']['joint']==j],pair,j))
    ranking.sort(key=lambda r:(not r['all_pass'],r['selectable_worst_rmse_rad'] if r['all_pass'] else math.inf,r['pair']))
    mins=lambda key:min((v for r in records for v in r['joint_limit_guard'][key] if v is not None),default=None)
    events=[r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event'] is not None]
    return {'schema':'g1.pd.operating.summary.v1','complete':True,'simulation_only':True,
      'actual_runs':len(records),'unique_pairs':len(pairs),'completed':sum(r['completed'] for r in records),
      'eligible':sum(r['eligible'] for r in records),'rejected':sum(not r['eligible'] for r in records),
      'phase_counts':dict(Counter(r['phase'] for r in records)),
      'base_failure_counts':dict(Counter(r['reason'] for r in records if not r['completed'])),
      'exclusion_counts':dict(Counter(x for r in records if not r['eligible'] for x in r['exclusions'])),
      'guard_event_counts':dict(Counter(e['reason'] for e in events)),
      'minimum_soft_margin_rad':mins('minimum_soft_margin_rad'),'minimum_model_hard_margin_rad':mins('minimum_hard_margin_rad'),
      'simulated_seconds':sum(r['final_time_s'] for r in records),
      'ranking':ranking,'per_axis':axes,'minimum_fully_passing_pair':next((r['pair'] for r in ranking if r['all_pass']),None),
      'manifest_sha256':manifest_hash,'all_possible_conditions_tested':False,'continuous_optimum_proven':False,
      'physical_stability_proven':False,'recommended_hardware_gains':None,'hardware_config_modified':False}

def check_guard(r,a):
    g=r['joint_limit_guard'];e=g['envelope'];p=core.Profile(**r['profile']);dt=r['scenario']['dt']
    steps=round(engine.WARMUP/dt)+math.ceil(core.Path(p).total/dt)
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

def check_reference(r,a):
    p=core.Profile(**r['profile']);path=core.Path(p);contract=core.profile_contract(p);dt=r['scenario']['dt']
    kp,kd=engine.candidate_gains(contract,r['kp'],r['kd'])
    if kp.tolist()!=r['gains_kp'] or kd.tolist()!=r['gains_kd'] or contract.baseline.tolist()!=r['initial_q']:raise ValueError('Gain or initial-pose mismatch')
    n=len(a['time_s']);stride=round(.02/dt);writer=round(.002/dt);warm=round(3./dt)
    # Cache each50Hz reference tick and compare every recorded500Hz reference.
    points={};expected=np.tile(contract.baseline,(n,1));segments=[];cycles=[]
    for i in range(n):
        step=i*writer;tick=step//stride*stride
        if tick not in points:points[tick]=path.at(max(0.,(tick-warm)*dt))
        point=points[tick]
        if step>=warm:expected[i,p.joint]+=point.offset
        segments.append(point.segment if step>=warm else 'warmup');cycles.append(point.cycle)
    if not np.array_equal(expected,a['ref']) or not np.array_equal(segments,a['segment']) or not np.array_equal(cycles,a['cycle']):raise ValueError('Recorded reference differs from frozen trajectory')

def audit(folder,source_root=None):
    folder=Path(folder);m=read(folder/'manifest.json');plan=read(folder/'plan.json');summary=read(folder/'summary.json')
    if m['quality_policy']!=core.POLICY or plan!=make_plan(m['smoke']) or m['plan_sha256']!=engine.sha256(folder/'plan.json'):raise ValueError('Frozen plan/policy changed')
    if source_root:
        for name,digest in m['source_sha256'].items():
            if engine.sha256(safe_path(source_root,name))!=digest:raise ValueError('Source changed: '+name)
        model_root=Path(source_root)/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in m['asset_sha256'].items():
            where=model_root if name.replace('\\','/').startswith('meshes/') else source_root
            if engine.sha256(safe_path(where,name))!=digest:raise ValueError('Model/mesh changed')
    records=[];hashes={};rows=[];margins=[];samples=0
    for f in sorted((folder/'cases').glob('*.json')):
        r=read(f);p=core.Profile(**r['profile']);s=core.Coupled(**r['scenario']);s.validate()
        if r['quality_policy']!=core.POLICY or not r['simulation_only'] or r['hardware_config_modified']:raise ValueError('Record policy or hardware claim')
        path=safe_path(folder,r['trace'])
        if engine.sha256(path)!=r['trace_sha256']:raise ValueError('Full-state hash mismatch')
        with np.load(path,allow_pickle=False) as z:a={k:z[k] for k in z.files}
        recomputed=core.evaluate(a,p,r['completed'],r['reason'],r['physics'])
        if any(r[k]!=v for k,v in recomputed.items()):raise ValueError('Stored score/quality differs from trace')
        check_guard(r,a);check_reference(r,a)
        coupled.check_model_evidence({'study_scenario_contract':r['scenario'],'coupled_model_evidence':r['model_evidence'],
          'torque_path':{'delay_s':s.delay_s,'lag_s':s.lag_s}})
        records.append(r);hashes[r['case_id']]=engine.sha256(f);samples+=len(a['time_s'])
        row={k:r[k] for k in ('case_id','phase','kp','kd','completed','eligible','reason')}
        row.update(joint=p.joint,profile=p.name,scenario=s.name,samples=len(a['time_s']),exclusions=';'.join(r['exclusions']))
        for k in ('active_rmse_rad','active_peak_error_rad','max_active_tail_error_rad','max_right7_tail_p2p_rad','max_right7_tail_rms_speed_rad_s','active_peak_torque_nm'):
            row[k]=r['metrics'].get(k) if r['metrics'] else None
        rows.append(row)
        for j in range(29):margins.append({'case_id':r['case_id'],'joint':j,'eligible':r['eligible'],
          **{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}})
    regenerated=summarize(records,plan,engine.sha256(folder/'manifest.json'))
    if regenerated!=summary:raise ValueError('Summary/ranking mismatch')
    for name,data in (('all_cases.csv',rows),('all_joint_margins.csv',margins)):
        with (folder/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    result={'schema':'g1.pd.operating.audit.v1','passed':True,'cases':len(records),'all29_500hz_rows':samples,
      'all29_margin_records':len(margins),'case_hashes':hashes,'source_model_bytes_checked':bool(source_root),
      'manifest_sha256':engine.sha256(folder/'manifest.json'),'summary_sha256':engine.sha256(folder/'summary.json'),
      'all_cases_sha256':engine.sha256(folder/'all_cases.csv'),'all_joint_margins_sha256':engine.sha256(folder/'all_joint_margins.csv'),
      'physical_validation':False,'scope':'recomputed500Hz states/reference/quality and physics extrema; not independent full physics-rate reconstruction'}
    save(folder/'audit.json',result);return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--workers',type=int,default=8);parser.add_argument('--smoke',action='store_true');parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers1..8 required')
    folder=args.output.resolve()
    if args.audit_only:
        r=audit(folder);print('AUDIT',r['passed'],r['cases']);return 0
    plan=make_plan(args.smoke)
    for j in plan:core.Profile(**j['profile']).validate();core.Coupled(**j['scenario']).validate()
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    names=('mujoco_pd_operating_core.py','mujoco_pd_operating_study.py','mujoco_pd_sweep.py','mujoco_pd_contract.py',
      'mujoco_pd_fixture.py','mujoco_pd_coupled_stress.py','mujoco_pd_motor_stress.py','mujoco_pd_expand.py','joint_limit_guard.py')
    folder.mkdir(parents=True,exist_ok=False);save(folder/'plan.json',plan)
    manifest={'schema':'g1.pd.operating.run.v1','smoke':args.smoke,'simulation_only':True,'quality_policy':core.POLICY,
      'plan_sha256':engine.sha256(folder/'plan.json'),'planned_runs':len(plan),'workers':args.workers,
      'source_sha256':engine.source_hashes([Path(__file__).with_name(n) for n in names]+[engine.REFERENCE]),'asset_sha256':assets,
      'python':platform.python_version(),'mujoco':mujoco.__version__,'numpy':np.__version__,'platform':platform.platform(),
      'created_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
      'notes':['full matrix without pruning; no new random noise','operating reference differs explicitly from original C++ small-signal trial',
               'joint22..25 independently excited; group gains22..25','long repetition/soak is not a thermal or infinite-horizon model',
               'hypothetical model/motor parameters; fixed pelvis; no physical G1 proof'],
      'recommended_hardware_gains':None,'hardware_config_modified':False}
    save(folder/'manifest.json',manifest)
    records=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        futures=[pool.submit(run_case,j,str(folder)) for j in plan]
        for future in as_completed(futures):
            r=future.result();records.append(r)
            if len(records)%24==0:
                save(folder/'progress.json',{'complete':False,'count':len(records),'total':len(plan)})
                print('OPERATING',len(records),'/',len(plan),flush=True)
    records.sort(key=lambda r:r['case_id']);summary=summarize(records,plan,engine.sha256(folder/'manifest.json'))
    save(folder/'summary.json',summary);checked=audit(folder,engine.ROOT)
    save(folder/'progress.json',{'complete':True,'count':len(records),'total':len(plan),'audited':checked['passed']})
    print('RESULT',json.dumps({k:v for k,v in summary.items() if k not in ('ranking','per_axis')}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
