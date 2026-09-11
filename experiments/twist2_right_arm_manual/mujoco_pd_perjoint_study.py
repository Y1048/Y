"""Bounded offline independent-PD search, full operating verification and fresh validation.

This does NOT alter the live100Kp validator: joint23's1..300 search cap applies
only to the isolated per-joint simulator. No compensation or reference offsets.
A model-optimal candidate is never automatically promoted to a robot setting.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
import argparse,csv,itertools,json,math,platform
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
import mujoco_pd_perjoint as pj

engine=pj.engine
ROLL_PAIRS=tuple(itertools.product((160.,200.,240.,280.,300.),(2.,2.5,3.,3.5,4.,5.,6.,8.)))
AXIS_PAIRS=((72.,1.4),(88.,1.4),(100.,1.),(100.,1.4),(100.,2.),(100.,3.))
AXIS_ORDER=(22,24,25)
BASELINE=pj.Gains()

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):pj.expanded.save_json(Path(path),value)
def normalize(x):return json.loads(json.dumps(x,sort_keys=True))

def change(g,j,p,d):
    kp=list(g.kp);kd=list(g.kd);kp[j-22]=p;kd[j-22]=d
    value=pj.Gains(tuple(kp),tuple(kd));value.validate();return value

def search_conditions(j):
    profiles=[pj.core.Profile(f'j{j}_standard',joint=j),pj.core.Profile(f'j{j}_large',joint=j,amplitude_deg=12.)]
    return [(p,s) for p,s in itertools.product(profiles,(pj.operating.SCENARIOS[0],pj.operating.SCENARIOS[3],pj.operating.SCENARIOS[4]))]

def operating_conditions():
    normal,long=pj.operating.profiles()
    return [(p,s) for p,s in itertools.product(normal,pj.operating.SCENARIOS)]+[(p,s) for p,s in itertools.product(long,(pj.operating.SCENARIOS[0],pj.operating.SCENARIOS[4]))]

def fresh_conditions():
    # This list is frozen before the first full-study dynamics call. The seed
    # selects hypothetical parameters, not observed device uncertainty/noise.
    rng=np.random.default_rng(2026091209);out=[]
    for i in range(12):
        dt=.0005 if i%2==0 else .001
        scenario=pj.core.Coupled(f'new_{i:02d}',float(rng.choice((.8,1.15,1.45))),
          float(rng.choice((.5,.85,1.75))),float(rng.choice((.05,.25,.75,1.25))),
          float(rng.choice((.001,.002,.003))),float(rng.choice((.003,.005,.007))),dt)
        for j in AXIS_ORDER+(23,):
            p=pj.core.Profile(f'new{i:02d}_j{j}',joint=j,amplitude_deg=float((6,10,12)[i%3]),
                speed_deg_s=float((15,25,30)[i%3]),elbow_offset_deg=float((-5,5,0)[i%3]),post_hold_s=5.)
            out.append((p,scenario))
    return out

def jobs(vectors,conditions,phase):
    unique={g.key:g for g in vectors}
    return [{'case_id':f'{phase}_{i:05d}','candidate':normalize(asdict(g)),
      'profile':asdict(p),'scenario':asdict(s),'phase':phase}
      for i,(g,(p,s)) in enumerate(itertools.product(unique.values(),conditions))]

def winner(records,plan):
    ranks=pj.ranking(records,plan)
    return next((pj.Gains(**r['candidate']) for r in ranks if r['all_pass']),None)

def run_phase(pool,folder,plan):
    save(folder/(plan[0]['phase']+'_plan.json'),plan)
    rs=[]
    for f in as_completed([pool.submit(pj.write_case,j,str(folder)) for j in plan]):
        r=f.result();rs.append(r)
        if len(rs)%24==0 or len(rs)==len(plan):
            print('PHASE',plan[0]['phase'],len(rs),'/',len(plan),flush=True)
            save(folder/'progress.json',{'complete':False,'phase':plan[0]['phase'],'done':len(rs),'total':len(plan)})
    return rs

def audit(folder,source_root=None):
    folder=Path(folder);m=read(folder/'manifest.json');summary=read(folder/'summary.json');selection=read(folder/'selection.json')
    if m['quality_policy']!=pj.core.POLICY or m['kp_caps']!=list(pj.KP_CAP):raise ValueError('Policy or research caps changed')
    if engine.sha256(folder/'manifest.json')!=summary['manifest_sha256']:raise ValueError('Manifest mismatch')
    if engine.sha256(folder/'selection.json')!=summary['selection_sha256']:raise ValueError('Frozen selection changed')
    if source_root:
        for name,digest in m['source_sha256'].items():
            if engine.sha256(pj.safe_path(source_root,name))!=digest:raise ValueError('Source bytes changed: '+name)
        mr=Path(source_root)/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in m['asset_sha256'].items():
            if engine.sha256(pj.safe_path(mr if name.replace('\\','/').startswith('meshes/') else source_root,name))!=digest:raise ValueError('Model bytes changed')
    if normalize(m['roll_pairs'])!=normalize(ROLL_PAIRS) or normalize(m['axis_pairs'])!=normalize(AXIS_PAIRS) or tuple(m['axis_order'])!=AXIS_ORDER:raise ValueError('Search grid changed')
    if m['fresh_conditions']!=normalize([{'profile':asdict(p),'scenario':asdict(s)} for p,s in fresh_conditions()]):raise ValueError('Fresh scenarios changed')
    plan=[j for f in sorted(folder.glob('*_plan.json')) for j in read(f)]
    if len(plan)!=len({j['case_id'] for j in plan}):raise ValueError('Duplicate plans')
    if {p.stem for p in (folder/'cases').glob('*.json')}!={j['case_id'] for j in plan}:raise ValueError('Missing or extra cases')
    records=[];rows=[];margins=[];samples=0;hashes={}
    for job in plan:
        r,a=pj.audit_case(folder,job);records.append(r);samples+=len(a['time_s'])
        hashes[r['case_id']]=engine.sha256(folder/'cases'/(r['case_id']+'.json'))
        row={'case_id':r['case_id'],'phase':r['phase'],'kp':json.dumps(r['candidate']['kp']),
          'kd':json.dumps(r['candidate']['kd']),'joint':r['profile']['joint'],'profile':r['profile']['name'],
          'scenario':r['scenario']['name'],'completed':r['completed'],'eligible':r['eligible'],
          'reason':r['reason'],'exclusions':';'.join(r['exclusions'])}
        for k in ('active_rmse_rad','active_peak_error_rad','max_active_tail_error_rad',
                  'max_right7_tail_rms_speed_rad_s','max_right7_tail_p2p_rad','active_peak_torque_nm'):
            row[k]=r['metrics'].get(k) if r['metrics'] else None
        rows.append(row)
        for j in range(29):margins.append({'case_id':r['case_id'],'joint':j,
          **{k:r['joint_limit_guard'][k][j] for k in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad')}})
    recalculated=make_summary(records,plan,selection,summary['manifest_sha256'],summary['selection_sha256'])
    if recalculated!=summary:raise ValueError('Score/count/ranking mismatch')
    # Check every adaptive search decision using ONLY its earlier phase.
    current=BASELINE
    roll_rs=[r for r in records if r['phase']=='roll'];roll_plan=[j for j in plan if j['phase']=='roll']
    if not roll_plan:raise ValueError('Missing roll search')
    if roll_plan:
        expected_roll=jobs([change(BASELINE,23,p,d) for p,d in ROLL_PAIRS],search_conditions(23),'roll')
        if normalize(roll_plan)!=normalize(expected_roll):raise ValueError('Roll grid coverage changed')
        selected=winner(roll_rs,roll_plan)
        if normalize(asdict(selected))!=selection['roll_winner']:raise ValueError('Roll decision changed')
        current=selected
        for joint in AXIS_ORDER:
            phase=f'axis{joint}';rs=[r for r in records if r['phase']==phase];ps=[j for j in plan if j['phase']==phase]
            expected=jobs([change(current,joint,p,d) for p,d in AXIS_PAIRS]+[current],search_conditions(joint),phase)
            if normalize(ps)!=normalize(expected):raise ValueError('Adaptive axis plan changed')
            selected=winner(rs,ps)
            if selected is not None:current=selected
        if normalize(asdict(current))!=selection['coordinate_vector']:raise ValueError('Coordinate winner changed')
        roll_current=pj.Gains(**selection['roll_winner'])
        conservative=pj.Gains(current.kp,tuple(max(d,3.) if j!=1 else max(d,5.) for j,d in enumerate(current.kd)))
        vectors=[current,roll_current,conservative,BASELINE]
        expected_op=jobs(vectors,operating_conditions(),'operating')
        if normalize([j for j in plan if j['phase']=='operating'])!=normalize(expected_op):raise ValueError('Operating coverage changed')
        op_rs=[r for r in records if r['phase']=='operating']
        eligible=[pj.Gains(**r['candidate']) for r in pj.ranking(op_rs,expected_op) if r['all_pass']]
        if selection['fresh_candidates']!=normalize([asdict(g) for g in eligible[:3]]):raise ValueError('Validation used future information')
        if normalize([j for j in plan if j['phase']=='fresh'])!=normalize(jobs(eligible[:3],fresh_conditions(),'fresh')):raise ValueError('Fresh matrix coverage changed')
        initial=read(folder/'operating_selection.json')
        if initial!={k:selection[k] for k in ('roll_winner','coordinate_vector','operating_candidates')}:raise ValueError('Initial vector freeze changed')
        if selection['operating_candidates']!=normalize([asdict(g) for g in {v.key:v for v in vectors}.values()]):raise ValueError('Full matrix candidates changed')
        for r in op_rs:
            if selection['operating_case_hashes'][r['case_id']]!=hashes[r['case_id']]:raise ValueError('Operating result changed after freeze')
    for name,table in (('all_cases.csv',rows),('all_joint_margins.csv',margins)):
        with (folder/name).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    result={'schema':'g1.pd.perjoint.audit.v1','passed':True,'cases':len(records),
      'all29_500hz_rows':samples,'all29_margin_records':len(margins),'case_hashes':hashes,
      'all_cases_sha256':engine.sha256(folder/'all_cases.csv'),'source_model_bytes_checked':bool(source_root),
      'scope':'recomputed full29 sampled states, policy, applied vectors, original references, guard witnesses and adaptive phase decisions',
      'physical_validation':False}
    save(folder/'audit.json',result);return result

def make_summary(records,plan,selection,manifest_hash,selection_hash):
    # Ranking with every planned case also checks candidate identity/completeness.
    pj.ranking(records,plan)
    phases=sorted({r['phase'] for r in records});ranks={}
    for phase in phases:
        ranks[phase]=pj.ranking([r for r in records if r['phase']==phase],[j for j in plan if j['phase']==phase])
    eligible=[r for r in records if r['eligible']]
    minimum=lambda field:min(v for r in records for v in r['joint_limit_guard'][field] if v is not None)
    calibration=[r for r in ranks.get('operating',[]) if r['all_pass']]
    valid={pj.Gains(**r['candidate']).key:r for r in ranks.get('fresh',[])}
    survivors=[r for r in calibration if pj.Gains(**r['candidate']).key in valid and valid[pj.Gains(**r['candidate']).key]['all_pass']]
    return {'schema':'g1.pd.perjoint.summary.v1','complete':True,'simulation_only':True,
      'actual_runs':len(records),'completed':sum(r['completed'] for r in records),'eligible':len(eligible),
      'phase_counts':dict(sorted(Counter(r['phase'] for r in records).items())),
      'base_rejections':dict(sorted(Counter(r['reason'] for r in records if not r['completed']).items())),
      'exclusions':dict(sorted(Counter(x for r in records if not r['eligible'] for x in r['exclusions']).items())),
      'guard_events':dict(sorted(Counter(r['joint_limit_guard']['event']['reason'] for r in records if r['joint_limit_guard']['event']).items())),
      'minimum_soft_margin_rad':minimum('minimum_soft_margin_rad'),'minimum_model_hard_margin_rad':minimum('minimum_hard_margin_rad'),
      'ranking':ranks,'selected_simulation_vector':survivors[0]['candidate'] if survivors else None,
      'manifest_sha256':manifest_hash,'selection_sha256':selection_hash,
      'continuous_or_global_optimum_proven':False,'physical_stability_proven':False,
      'recommended_hardware_gains':None,'hardware_config_modified':False}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=6);parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers must be1..8')
    folder=args.output.resolve()
    if args.audit_only:print('AUDIT',audit(folder)['passed']);return 0
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    fresh=fresh_conditions();folder.mkdir(parents=True,exist_ok=False)
    sources=engine.source_hashes([Path(__file__).with_name(n) for n in ('mujoco_pd_perjoint.py','mujoco_pd_perjoint_study.py',
      'mujoco_pd_operating_core.py','mujoco_pd_operating_study.py','mujoco_pd_sweep.py','mujoco_pd_contract.py',
      'mujoco_pd_fixture.py','mujoco_pd_coupled_stress.py','mujoco_pd_motor_stress.py','joint_limit_guard.py')]+[engine.REFERENCE])
    manifest={'schema':'g1.pd.perjoint.manifest.v1','quality_policy':pj.core.POLICY,'kp_caps':list(pj.KP_CAP),
      'roll_pairs':ROLL_PAIRS,'axis_pairs':AXIS_PAIRS,'axis_order':AXIS_ORDER,
      'fresh_conditions':[{'profile':asdict(p),'scenario':asdict(s)} for p,s in fresh],
      'source_sha256':sources,'asset_sha256':assets,'mujoco':mujoco.__version__,'numpy':np.__version__,
      'python':platform.python_version(),'platform':platform.platform(),'workers':args.workers,
      'simulation_only':True,'limitation':'Kp23 up to300 is research-only, outside live validator; no feedforward, no integral, no control-limit change',
      'recommended_hardware_gains':None,'hardware_config_modified':False}
    save(folder/'manifest.json',manifest);records=[];plan=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=pj.expanded.init_worker) as pool:
        ps=jobs([change(BASELINE,23,p,d) for p,d in ROLL_PAIRS],search_conditions(23),'roll')
        rs=run_phase(pool,folder,ps);records+=rs;plan+=ps
        current=winner(rs,ps)
        if current is None:raise RuntimeError('No feasible roll candidate; do not fabricate a winning PD')
        selection={'roll_winner':normalize(asdict(current))};roll_current=current
        for joint in AXIS_ORDER:
            ps=jobs([change(current,joint,p,d) for p,d in AXIS_PAIRS]+[current],search_conditions(joint),f'axis{joint}')
            rs=run_phase(pool,folder,ps);records+=rs;plan+=ps
            candidate=winner(rs,ps)
            if candidate is not None:current=candidate
        selection['coordinate_vector']=normalize(asdict(current))
        conservative=pj.Gains(current.kp,tuple(max(d,3.) if j!=1 else max(d,5.) for j,d in enumerate(current.kd)))
        vectors=[current,roll_current,conservative,BASELINE]
        selection['operating_candidates']=[normalize(asdict(g)) for g in {v.key:v for v in vectors}.values()]
        save(folder/'operating_selection.json',selection)
        ps=jobs(vectors,operating_conditions(),'operating');rs=run_phase(pool,folder,ps);records+=rs;plan+=ps
        eligible=[pj.Gains(**r['candidate']) for r in pj.ranking(rs,ps) if r['all_pass']]
        selection['fresh_candidates']=[normalize(asdict(g)) for g in eligible[:3]]
        selection['operating_case_hashes']={r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in rs}
        save(folder/'selection.json',selection) # Freeze before fresh, no retuning.
        if eligible:
            ps=jobs(eligible[:3],fresh,'fresh');rs=run_phase(pool,folder,ps);records+=rs;plan+=ps
    summary=make_summary(records,plan,selection,engine.sha256(folder/'manifest.json'),engine.sha256(folder/'selection.json'))
    save(folder/'summary.json',summary);checked=audit(folder,engine.ROOT)
    save(folder/'progress.json',{'complete':True,'actual_runs':len(records),'audited':checked['passed']})
    print('PERJOINT_RESULT',json.dumps({k:v for k,v in summary.items() if k!='ranking'}),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
