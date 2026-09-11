"""Strict minimum-error search with unchanged stability/limit constraints.

OFFLINE ONLY: finite-grid minimax, exact observed lower-bound pruning.
Previously seen conditions are calibration, never called independent holdouts.
Do not change live gains, dynamics, motion, XML limits or IK cost parameters.
"""
from __future__ import annotations
import os
for _n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[_n]='1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed,wait,FIRST_COMPLETED
from dataclasses import asdict
import itertools,json,math
from pathlib import Path
import platform
import numpy as np
import mujoco_pd_accuracy_stability as quality
import mujoco_pd_robust_refine as robust
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine
from mujoco_pd_expand_audit import check_case,safe_path
from mujoco_pd_limit_replay import verify_guard_result

S=robust.Scenario
BOUND_EPS=1e-12
SEEDS=((100.,1.3),(100.,1.4),(100.,2.))
FORCE_FULL=SEEDS+((100.,1.25),(100.,1.275),(100.,1.325),(100.,1.35),(100.,1.5))
FINALISTS=8
KNOWN=quality.CALIBRATION+quality.VALIDATION
# Necessary tests most likely to distinguish accuracy and delayed settling.
FIRST=('model/combined_half','motor/new_f000_d2_l9','motor/hold_f000_d1_l8',
       'motor/hold_f000_d3_l3','motor/zero_friction_delay_4ms')
CALIBRATION=tuple(next(s for s in KNOWN if s.identity==name) for name in FIRST)+tuple(s for s in KNOWN if s.identity not in FIRST)

def validation_plan():
    """Reproducible assumed uncertainty, frozen before dynamics evaluation."""
    rng=np.random.default_rng(20260911)
    seen={(s.family,tuple(s.parameters[1:])) for s in KNOWN};out=[]
    while len(out)<12:
        friction=float(rng.choice([0.,.05,.1,.2,.4,.6,.8]))
        delay=float(rng.choice([0.,.001,.002,.003,.004,.005]))
        lag=float(rng.choice([.002,.003,.004,.005,.006,.007,.008,.009]))
        if not .007<=delay+lag<=.011:continue
        dt=.0005 if len(out)%3==0 else .001
        pars=(friction,delay,lag,dt);key=('motor',pars)
        if key in seen:continue
        seen.add(key);out.append(S('motor',(f'fresh_motor_{len(out):02d}',*pars)))
    for i,pars in enumerate(((.001,1.45,.5,.2),(.0005,.55,1.5,.05),
                             (.001,1.15,1.75,.1),(.0005,.85,.5,.125))):
        out.append(S('model',(f'fresh_model_{i:02d}',*pars)))
    return tuple(out)

VALIDATION=validation_plan()

def grid():
    broad=set(itertools.product(range(16,101,4),(.1,.25,.5,.75,1.,1.2,1.3,1.5,2.,3.,5.,7.,10.,15.,20.)))
    fine=set(itertools.product((96.,98.,99.,99.5,100.),(i/1000 for i in range(1200,1351,5))))
    return sorted(broad|fine|set(FORCE_FULL))

def save(path,obj):quality.save(path,obj)
def read(path):return quality.read(path)
def pair(r):return quality.pair(r)
def strict_rank(rows):
    return sorted((r for r in rows if r['all_quality_pass']),key=lambda r:(r['worst_rmse_rad'],r['worst_tail_rms_speed_rad_s'],r['worst_tail_p2p_rad'],*r['pair']))

def job(p,index,s,k,phase,folder):
    return (float(p[0]),float(p[1]),asdict(s),str(folder),f'{phase}_{index:04d}_{k:02d}',phase)

def score(records):
    return max(r['metrics']['reference_rmse_joint22_rad'] for r in records)

def evaluate_pair(task):
    p,index,raw_scenarios,folder,incumbent,force=task
    ss=[S(s['family'],tuple(s['parameters'])) for s in raw_scenarios]
    records=[];kind='fully_evaluated'
    for k,s in enumerate(ss):
        r=quality.run_case(job(p,index,s,k,'calibration',folder));records.append(r)
        if not r['quality_eligible']:
            kind='constraint_rejected';break
        # max over observed subset is a rigorous lower bound on full worst RMSE.
        if not force and incumbent is not None and score(records)>incumbent['score']+BOUND_EPS:
            kind='bound_pruned';break
    decision={'pair':list(p),'index':index,'status':kind,'case_ids':[r['case_id'] for r in records],
              'incumbent':incumbent,'force_full':force,
              'observed_lower_bound_rad':score(records) if all(r['quality_eligible'] for r in records) else None}
    save(Path(folder)/'decisions'/f'{index:04d}.json',decision)
    return decision,records

def expected_selection(ranking,pairs):
    return sorted(set(tuple(r['pair']) for r in strict_rank(ranking)[:FINALISTS]) | (set(SEEDS)&set(map(tuple,pairs))))

def check_decisions(decisions,records,pairs,scenarios):
    """Verify every grid cell is either fully tested or has a sufficient witness."""
    if len(decisions)!=len(pairs) or {tuple(d['pair']) for d in decisions}!=set(map(tuple,pairs)):
        raise ValueError('Grid coverage missing or duplicated')
    index={r['case_id']:r for r in records};seen=set();complete={}
    for d in decisions:
        i=d['index'];p=tuple(d['pair'])
        if i<0 or i>=len(pairs) or p!=tuple(pairs[i]):raise ValueError('Decision index mismatch')
        ids=d['case_ids']
        if not ids or len(ids)>len(scenarios) or seen.intersection(ids):raise ValueError('Bad decision prefix')
        rs=[]
        for k,cid in enumerate(ids):
            r=index[cid];seen.add(cid);rs.append(r)
            if cid!=f'calibration_{i:04d}_{k:02d}' or pair(r)!=p or r['study_phase']!='calibration':raise ValueError('Case/decision mismatch')
            expected=json.loads(json.dumps(asdict(scenarios[k])))
            if json.loads(json.dumps(r['study_scenario_contract']))!=expected:raise ValueError('Decision scenario order differs')
        good=all(r['quality_eligible'] for r in rs)
        observed=score(rs) if good else None
        if observed!=d['observed_lower_bound_rad']:raise ValueError('Wrong lower bound')
        if d['status']=='fully_evaluated':
            if len(rs)!=len(scenarios) or not good:raise ValueError('False fully-tested decision')
            complete[p]=score(rs)
        elif d['status']=='constraint_rejected':
            if rs[-1]['quality_eligible'] or not all(r['quality_eligible'] for r in rs[:-1]):raise ValueError('No failure witness')
        elif d['status']=='bound_pruned':
            if not good or d['force_full'] or d['incumbent'] is None:raise ValueError('Unjustified pruning')
        else:raise ValueError('Unknown decision status')
    if seen!={r['case_id'] for r in records if r['study_phase']=='calibration'}:raise ValueError('Extra/unassigned calibration cases')
    if not complete:raise ValueError('No feasible incumbent established')
    best=min(complete.values())
    for d in decisions:
        inc=d['incumbent']
        if inc is not None:
            p=tuple(inc['pair'])
            if p not in complete or complete[p]!=inc['score']:raise ValueError('Incumbent not fully verified')
        if d['status']=='bound_pruned':
            if not d['observed_lower_bound_rad']>inc['score']+BOUND_EPS or inc['score']<best-BOUND_EPS:
                raise ValueError('Pruning proof fails')
    return complete

def build_summary(records,decisions,manifest,selection,manifest_hash):
    pairs=manifest['pairs'];scenarios=[S(s['family'],tuple(s['parameters'])) for s in manifest['calibration']]
    vs=[S(s['family'],tuple(s['parameters'])) for s in manifest['validation']]
    complete=check_decisions(decisions,records,pairs,scenarios)
    ranks=quality.rank(records,pairs,scenarios,'calibration')
    chosen=expected_selection(ranks,pairs)
    if list(map(tuple,selection['pairs']))!=chosen:raise ValueError('Finalist freeze differs from strict rule')
    val=quality.rank(records,chosen,vs,'validation')
    if not all(r['all_present'] for r in val):raise ValueError('Missing validation condition')
    if len([r for r in records if r['study_phase']=='validation'])!=len(chosen)*len(vs):raise ValueError('Extra validation case')
    passed={tuple(r['pair']) for r in val if r['all_quality_pass']}
    survivors=[r['pair'] for r in strict_rank(ranks) if tuple(r['pair']) in passed]
    status=Counter(d['status'] for d in decisions)
    events=[r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event']]
    return {'schema':'g1.pd.minerror.summary.v1','complete':True,'simulation_only':True,
      'grid_pairs':len(pairs),'total_simulations':len(records),'calibration_simulations':sum(r['study_phase']=='calibration' for r in records),
      'validation_simulations':sum(r['study_phase']=='validation' for r in records),'decision_counts':dict(status),
      'completed_simulations':sum(r['completed'] for r in records),'base_eligible':sum(r['eligible'] for r in records),
      'quality_eligible':sum(r['quality_eligible'] for r in records),
      'base_rejections':dict(Counter(r['reason'] for r in records if not r['eligible'])),
      'quality_rejections':dict(Counter(x for r in records if r['eligible'] for x in r['stability']['rejections'])),
      'guard_events':dict(Counter(e['reason'] for e in events)),
      'minimum_soft_margin_rad':min(x for r in records for x in r['joint_limit_guard']['minimum_soft_margin_rad'] if x is not None),
      'minimum_model_hard_margin_rad':min(x for r in records for x in r['joint_limit_guard']['minimum_hard_margin_rad'] if x is not None),
      'calibration_finite_grid_minimum_verified':True,'calibration_best_pair':strict_rank(ranks)[0]['pair'],
      'calibration_ranking':ranks,'validation_ranking':val,'strict_order_survivors':survivors,
      'manifest_sha256':manifest_hash,'continuous_gain_optimum_proven':False,'physical_stability_proven':False,
      'recommended_hardware_gains':None,'hardware_config_modified':False,
      'limits':['Kp<=100 unchanged','fixed pelvis; joint22 small roundtrip only; gains grouped22..25',
       'hypothetical uncertainty; no measured motor delay/braking','pruned cells not tested under all conditions; valid minimax witnesses retained',
       'validation only for frozen finalists; no whole-grid optimum over unseen conditions',
       'stability means existing finite-horizon quality constraints; no noise/thermal/large-motion/full-body proof']}

def verify_records(folder,source_root=None):
    """Reload all compact/full traces, all29 margins and numerical metrics."""
    folder=Path(folder);m=read(folder/'manifest.json');sel=read(folder/'selection.json');stored=read(folder/'summary.json')
    if m['quality_policy']!=quality.POLICY or m['objective']!='strict_worst_rmse_after_all_quality_constraints':raise ValueError('Policy mismatch')
    expected=grid() if m['full_study'] else [(100.,1.25),(100.,1.3),(100.,2.)]
    if list(map(tuple,m['pairs']))!=expected:raise ValueError('Grid changed')
    cs=CALIBRATION if m['full_study'] else (CALIBRATION[0],)
    vs=VALIDATION if m['full_study'] else (VALIDATION[0],)
    if json.loads(json.dumps([asdict(s) for s in cs]))!=m['calibration'] or json.loads(json.dumps([asdict(s) for s in vs]))!=m['validation']:
        raise ValueError('Scenario manifest changed')
    if source_root:
        for name,digest in m['source_sha256'].items():
            if engine.sha256(safe_path(source_root,name))!=digest:raise ValueError('Source changed: '+name)
        models=Path(source_root)/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in m['asset_sha256'].items():
            root=models if name.replace('\\','/').startswith('meshes/') else source_root
            if engine.sha256(safe_path(root,name))!=digest:raise ValueError('Asset changed')
    records=[];hashes={};rows=[];samples=0
    for path in sorted((folder/'cases').glob('*.json')):
        r,metrics,_=check_case(folder,path);verify_guard_result(r)
        full=safe_path(folder,r['full_state_npz'])
        if engine.sha256(full)!=r['full_state_sha256']:raise ValueError('Full state hash')
        with np.load(full,allow_pickle=False) as f:a={k:f[k] for k in f.files}
        stats=quality.stability(a)
        if stats!=r['stability'] or r['quality_eligible']!=bool(r['eligible'] and stats['passes']):raise ValueError('Quality result changed')
        with np.load(safe_path(folder,r['trace_npz']),allow_pickle=False) as z:
            cols=z['columns'].tolist();v=z['values']
            for n in ('q','dq','ref','cmd'):
                if not np.array_equal(a[n][:,22],v[:,cols.index(n+'_22')]):raise ValueError('Full/compact mismatch')
        e=r['joint_limit_guard']['envelope']
        if r['eligible']:
            for n in ('q','ref','cmd'):
                if np.any(a[n]<=np.array(e['inner_lower'])+1e-10) or np.any(a[n]>=np.array(e['inner_upper'])-1e-10):raise ValueError('Accepted inner limit touch')
            observed=np.minimum(a['q']-np.array(e['soft_lower']),np.array(e['soft_upper'])-a['q']).min(axis=0)
            if np.any(observed+1e-10<np.array(r['joint_limit_guard']['minimum_soft_margin_rad'])):raise ValueError('Extrema contradiction')
        if r['study_phase']=='validation':
            p=pair(r);pi=list(map(tuple,m['pairs'])).index(p)
            si=next((i for i,s in enumerate(vs) if s.identity==r['study_scenario']),None)
            if p not in list(map(tuple,sel['pairs'])) or si is None or r['case_id']!=f'validation_{pi:04d}_{si:02d}':raise ValueError('Validation identity')
            if r['study_scenario_contract']!=json.loads(json.dumps(asdict(vs[si]))):raise ValueError('Validation parameters')
        records.append(r);hashes[r['case_id']]=engine.sha256(path);samples+=len(a['q'])
        rows.append({'case_id':r['case_id'],'phase':r['study_phase'],'kp':r['kp_proximal'],'kd':r['kd_proximal'],
          'scenario':r['study_scenario'],'completed':r['completed'],'base_eligible':r['eligible'],'quality_eligible':r['quality_eligible'],
          'reason':r['reason'],'quality_reasons':';'.join(stats['rejections']),
          'rmse_rad':metrics['reference_rmse_joint22_rad'] if metrics else None,
          'right7_tail_rms_rad_s':stats['max_right7_tail_rms_speed_rad_s'],'right7_tail_p2p_rad':stats['max_right7_tail_p2p_rad'],
          'full_state_sha256':r['full_state_sha256'],'trace_sha256':r['trace_sha256']})
    decisions=[read(p) for p in sorted((folder/'decisions').glob('*.json'))]
    regenerated=build_summary(records,decisions,m,sel,engine.sha256(folder/'manifest.json'))
    if regenerated!=stored:raise ValueError('Regenerated summary differs')
    frozen={r['case_id']:hashes[r['case_id']] for r in records if r['study_phase']=='calibration'}
    if sel['calibration_case_hashes']!=frozen:raise ValueError('Calibration modified after finalist freeze')
    dh={p.name:engine.sha256(p) for p in (folder/'decisions').glob('*.json')}
    if sel['decision_hashes']!=dh:raise ValueError('Pruning records changed')
    import csv
    with (folder/'all_cases.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'schema':'g1.pd.minerror.audit.v1','passed':True,'simulation_only':True,'cases':len(records),
      'grid_decisions_checked':len(decisions),'all29_500hz_rows':samples,'all29_extrema_records':29*len(records),
      'case_hashes':hashes,'source_assets_checked':bool(source_root),'summary_sha256':engine.sha256(folder/'summary.json'),
      'manifest_sha256':engine.sha256(folder/'manifest.json'),'selection_sha256':engine.sha256(folder/'selection.json'),
      'all_cases_sha256':engine.sha256(folder/'all_cases.csv'),'continuous_time_or_hardware_proof':False}
    save(folder/'audit.json',result);return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    p.add_argument('--smoke',action='store_true');p.add_argument('--audit-only',action='store_true')
    args=p.parse_args(argv)
    if not 1<=args.workers<=8:p.error('workers must be1..8')
    folder=args.output.resolve()
    if args.audit_only:
        a=verify_records(folder);print('AUDIT',a['passed'],a['cases']);return 0
    pairs=grid() if not args.smoke else [(100.,1.25),(100.,1.3),(100.,2.)]
    cs=CALIBRATION if not args.smoke else (CALIBRATION[0],)
    vs=VALIDATION if not args.smoke else (VALIDATION[0],)
    for s in cs+vs:s.validate()
    if len({(s.family,tuple(s.parameters[1:])) for s in cs+vs})!=len(cs)+len(vs):raise ValueError('Repeated scenarios')
    contract=engine.load_contract()
    for pair_ in pairs:engine.candidate_gains(contract,*pair_)
    import mujoco
    model,qa,_,_,assets=engine.load_model(engine.MODEL,.001)
    names=['mujoco_pd_minerror.py','mujoco_pd_accuracy_stability.py','mujoco_pd_robust_refine.py','mujoco_pd_sweep.py',
           'mujoco_pd_expand.py','mujoco_pd_motor_stress.py','mujoco_pd_contract.py','mujoco_pd_fixture.py',
           'joint_limit_guard.py','mujoco_pd_expand_audit.py','mujoco_pd_limit_replay.py','pd_small_signal_trial.hpp']
    m={'schema':'g1.pd.minerror.run.v1','full_study':not args.smoke,'simulation_only':True,'pairs':pairs,
       'calibration':[asdict(s) for s in cs],'validation':[asdict(s) for s in vs],'quality_policy':quality.POLICY,
       'objective':'strict_worst_rmse_after_all_quality_constraints','plateau_used':False,'bound_epsilon':BOUND_EPS,
       'seed_pairs':[p for p in SEEDS if p in pairs],'force_full_pairs':[p for p in FORCE_FULL if p in pairs],
       'finalist_count':FINALISTS,'prior_holdouts_now_known':True,'mujoco':mujoco.__version__,'numpy':np.__version__,
       'python':platform.python_version(),'platform':platform.platform(),'validation_rng_seed':20260911,
       'source_sha256':engine.source_hashes([Path(__file__).with_name(n) for n in names]+[engine.REFERENCE]),
       'asset_sha256':assets,'joint_limit_envelope':engine.JointLimitEnvelope.from_model(model,qa,contract).manifest(),
       'recommended_hardware_gains':None,'hardware_config_modified':False}
    folder.mkdir(parents=True,exist_ok=False);save(folder/'manifest.json',m);m=read(folder/'manifest.json')
    records=[];decisions=[];incumbent=None
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        # Seed full-condition feasible bounds; actual simulations, no cached pass flags.
        seeds=[p for p in SEEDS if p in pairs]
        jobs=[job(p,pairs.index(p),s,k,'calibration',folder) for p in seeds for k,s in enumerate(cs)]
        for f in as_completed([pool.submit(quality.run_case,j) for j in jobs]):records.append(f.result())
        for p in seeds:
            rs=sorted([r for r in records if pair(r)==p],key=lambda r:r['case_id'])
            # Seed conditions are all observed even on failure: retain full evidence.
            good=all(r['quality_eligible'] for r in rs)
            if not good:raise RuntimeError('Seed failed; no changed criteria or inferred incumbent')
            d={'pair':list(p),'index':pairs.index(p),'status':'fully_evaluated','case_ids':[r['case_id'] for r in rs],
               'incumbent':None,'force_full':True,'observed_lower_bound_rad':score(rs)}
            decisions.append(d);save(folder/'decisions'/f'{pairs.index(p):04d}.json',d)
            if incumbent is None or score(rs)<incumbent['score']:incumbent={'pair':list(p),'score':score(rs)}
        print('SEED_BOUND',json.dumps(incumbent),flush=True)
        # Good neighborhood first; order is frozen, not tuned after validation.
        remaining=sorted([p for p in pairs if p not in seeds],key=lambda p:(p not in FORCE_FULL,-p[0],abs(p[1]-1.25),p[1]))
        waiting=iter(remaining);pending={}
        def submit_next():
            try:p=next(waiting)
            except StopIteration:return False
            task=(p,pairs.index(p),m['calibration'],str(folder),dict(incumbent),p in FORCE_FULL)
            pending[pool.submit(evaluate_pair,task)]=p;return True
        for _ in range(args.workers):submit_next()
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for f in done:
                pending.pop(f);d,rs=f.result();decisions.append(d);records.extend(rs)
                if d['status']=='fully_evaluated' and score(rs)<incumbent['score']:
                    incumbent={'pair':d['pair'],'score':score(rs)};print('IMPROVED_BOUND',json.dumps(incumbent),flush=True)
                submit_next()
            save(folder/'progress.json',{'complete':False,'grid_done':len(decisions),'grid_total':len(pairs),'simulations':len(records),'incumbent':incumbent})
            if len(decisions)%10==0:print('MINERROR',len(decisions),'/',len(pairs),'simulations',len(records),flush=True)
        ranking=quality.rank(records,pairs,cs,'calibration');selected=expected_selection(ranking,pairs)
        selection={'pairs':selected,'basis':'strict calibration minimax; frozen before validation',
          'calibration_case_hashes':{r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in records},
          'decision_hashes':{p.name:engine.sha256(p) for p in (folder/'decisions').glob('*.json')}}
        save(folder/'selection.json',selection);print('FROZEN_FINALISTS',json.dumps(selected),flush=True)
        jobs=[job(p,pairs.index(p),s,k,'validation',folder) for p in selected for k,s in enumerate(vs)]
        for f in as_completed([pool.submit(quality.run_case,j) for j in jobs]):
            records.append(f.result())
            if len(records)%20==0:print('VALIDATION_SIMULATIONS',len(records),flush=True)
    records.sort(key=lambda r:r['case_id']);decisions.sort(key=lambda d:d['index'])
    summary=build_summary(records,decisions,m,read(folder/'selection.json'),engine.sha256(folder/'manifest.json'))
    save(folder/'summary.json',summary);a=verify_records(folder,engine.ROOT)
    save(folder/'progress.json',{'complete':True,'simulations':len(records),'grid_total':len(pairs),'audited':a['passed']})
    print('MINERROR_RESULT',json.dumps({k:v for k,v in summary.items() if k not in ('calibration_ranking','validation_ranking')}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
