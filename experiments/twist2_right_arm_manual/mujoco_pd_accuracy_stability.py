"""Accuracy/stability PD screening, OFFLINE ONLY. No robot I/O or gain deployment.

Prior holdouts are now KNOWN calibration data. A new scenario set is frozen
before any run and never used to retune the finalists. Existing motion,
all29 limit guards, actuator bounds and live/IK paths remain unchanged.
"""
from __future__ import annotations
import os
for _name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_name]='1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
import itertools,json,math
from pathlib import Path
import platform
import numpy as np
import mujoco_pd_robust_refine as previous
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine
from mujoco_pd_expand_audit import check_case,safe_path
from mujoco_pd_limit_replay import verify_guard_result

PAIRS=tuple(sorted({(100.,d) for d in (1.1,1.2,1.3,1.4,1.5,1.6,1.8,2.)}
                  |{(96.,1.3),(96.,1.6),(80.,1.),(56.,3.)}))
CALIBRATION=previous.CALIBRATION+previous.HOLDOUT
S=previous.Scenario
VALIDATION=(
 S('motor',('new_f000_d2_l6',0.,.002,.006,.001)),
 S('motor',('new_f010_d4_l4',.1,.004,.004,.001)),
 S('motor',('new_f050_d3_l5',.5,.003,.005,.001)),
 S('motor',('new_f075_d5_l3',.75,.005,.003,.001)),
 S('motor',('new_f000_d2_l9',0.,.002,.009,.001)),
 S('motor',('new_f025_d4_l3',.25,.004,.003,.001)),
 S('motor',('new_f025_d4_l3_half',.25,.004,.003,.0005)),
 S('model',('new_mass125_damp075_f015',.001,1.25,.75,.15)),
 S('model',('new_mass065_damp150_f005',.001,.65,1.5,.05)),
 S('model',('new_mass135_damp050_f020',.001,1.35,.5,.20)),
)
POLICY={'tail_window_s':.1,'q22_tail_error_rad':.02,'q22_tail_speed_rad_s':.1,
        'right7_tail_p2p_rad':.005,'right7_tail_rms_speed_rad_s':.05,
        'accuracy_plateau_fraction':.02,'finalist_top_count':4}
CONTROLS=((100.,2.),(80.,1.),(56.,3.))
HOLDS=('positive_hold','negative_hold','ready_hold')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):expanded.save_json(Path(path),value)
def pair(r):return previous.pair_of(r)

def collect_arrays(rows):
    n=len(rows)
    arrays={'time_s':np.array([r['time_s'] for r in rows]),
            'trial_time_s':np.array([r['trial_time_s'] for r in rows]),
            'cycle':np.array([r['cycle'] for r in rows],dtype=np.int64),
            'segment':np.array([r['segment'] for r in rows],dtype='U16')}
    for name in ('q','dq','ref','cmd'):
        arrays[name]=np.array([[r[f'{name}_{j}'] for j in range(29)] for r in rows],dtype=np.float64).reshape((n,29))
    return arrays


def stability(arrays,policy=POLICY):
    t,trial,cycle,seg=(arrays[k] for k in ('time_s','trial_time_s','cycle','segment'))
    n=len(t)
    if any(len(arrays[k])!=n for k in ('trial_time_s','cycle','segment')):
        raise ValueError('Full-state array lengths differ')
    for key in ('q','dq','ref','cmd'):
        if arrays[key].shape!=(n,29) or not np.isfinite(arrays[key]).all():
            raise ValueError('Full-state trace must contain finite 29-joint arrays')
    if not np.isfinite(t).all() or not np.isfinite(trial).all() or not np.allclose(np.diff(t),.002,rtol=0,atol=1e-10):
        raise ValueError('Invalid full-state 500Hz clock')
    if not np.allclose(trial,t-engine.WARMUP,rtol=0,atol=1e-10):
        raise ValueError('Full-state warmup clock mismatch')
    holds=[]
    for c,s in itertools.product(range(3),HOLDS):
        ids=np.flatnonzero((trial>=0)&(cycle==c)&(seg==s))
        if not len(ids):continue
        # Exactly the final 50 samples (100ms at500Hz) of each completed hold.
        tail=ids[t[ids]>=t[ids[-1]]-policy['tail_window_s']+1e-9]
        q,dq,ref=(arrays[k][tail] for k in ('q','dq','ref'))
        p2p=np.ptp(q[:,22:29],axis=0)
        rms=np.sqrt(np.mean(dq[:,22:29]**2,axis=0))
        holds.append({'cycle':c,'segment':s,'tail_samples':len(tail),
          'q22_tail_max_error_rad':float(np.max(np.abs(q[:,22]-ref[:,22]))),
          'q22_tail_max_speed_rad_s':float(np.max(np.abs(dq[:,22]))),
          'right7_p2p_rad':p2p.tolist(),'right7_rms_speed_rad_s':rms.tolist()})
    complete=len(holds)==9 and all(h['tail_samples']==50 for h in holds)
    maxima={
      'max_q22_tail_error_rad':max((h['q22_tail_max_error_rad'] for h in holds),default=None),
      'max_q22_tail_speed_rad_s':max((h['q22_tail_max_speed_rad_s'] for h in holds),default=None),
      'max_right7_tail_p2p_rad':max((max(h['right7_p2p_rad']) for h in holds),default=None),
      'max_right7_tail_rms_speed_rad_s':max((max(h['right7_rms_speed_rad_s']) for h in holds),default=None)}
    reasons=[]
    if not complete:reasons.append('incomplete_nine_hold_tails')
    for measured,limit in (('max_q22_tail_error_rad','q22_tail_error_rad'),
       ('max_q22_tail_speed_rad_s','q22_tail_speed_rad_s'),
       ('max_right7_tail_p2p_rad','right7_tail_p2p_rad'),
       ('max_right7_tail_rms_speed_rad_s','right7_tail_rms_speed_rad_s')):
        if maxima[measured] is not None and maxima[measured]>policy[limit]:reasons.append(measured)
    return {'policy':dict(policy),'all_hold_tails_present':complete,'passes':not reasons,
            'rejections':reasons,**maxima,'holds':holds}


def run_case(job):
    captured=[]
    original=engine.run_candidate
    def capture(*args,**kwargs):
        result,rows=original(*args,**kwargs)
        captured.append(collect_arrays(rows))
        return result,rows
    engine.run_candidate=capture
    try:r=previous.run_case(job)
    finally:engine.run_candidate=original
    if len(captured)!=1:raise RuntimeError('Expected exactly one untouched engine call')
    folder=Path(job[3]); arrays=captured[0]
    dest=folder/'full_state'/(r['case_id']+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(dest,**arrays)
    stats=stability(arrays)
    r.update(full_state_npz=dest.relative_to(folder).as_posix(),full_state_sha256=engine.sha256(dest),
             stability=stats,quality_eligible=bool(r['eligible'] and stats['passes']))
    save(folder/'cases'/(r['case_id']+'.json'),r)
    return r


def rank(records,pairs,scenarios,phase):
    required={s.identity for s in scenarios};index={}
    for r in records:
        if r['study_phase']!=phase:continue
        key=(pair(r),r['study_scenario'])
        if key in index:raise ValueError('Duplicate quality evidence')
        index[key]=r
    rows=[]
    for p in pairs:
        rs=[index[(tuple(p),s)] for s in sorted(required) if (tuple(p),s) in index]
        present=len(rs)==len(required)
        good=present and all(r['quality_eligible'] for r in rs)
        rows.append({'pair':list(p),'observed':len(rs),'required':len(required),
          'all_present':present,'all_quality_pass':good,'base_pass_count':sum(r['eligible'] for r in rs),
          'quality_pass_count':sum(r['quality_eligible'] for r in rs),
          'worst_rmse_rad':max(r['metrics']['reference_rmse_joint22_rad'] for r in rs) if good else None,
          'worst_peak_error_rad':max(r['metrics']['peak_reference_error_joint22_rad'] for r in rs) if good else None,
          'worst_tail_rms_speed_rad_s':max(r['stability']['max_right7_tail_rms_speed_rad_s'] for r in rs) if good else None,
          'worst_tail_p2p_rad':max(r['stability']['max_right7_tail_p2p_rad'] for r in rs) if good else None,
          'worst_q22_torque_nm':max(r['metrics']['peak_torque_joint22_nm'] for r in rs) if good else None,
          'failures':[{'scenario':r['study_scenario'],'base_reason':r['reason'],
                       'quality_reasons':r['stability']['rejections']} for r in rs if not r['quality_eligible']]})
    return sorted(rows,key=lambda r:(not r['all_quality_pass'],r['worst_rmse_rad'] if r['all_quality_pass'] else math.inf,*r['pair']))


def preference(ranking,policy=POLICY):
    good=[r for r in ranking if r['all_quality_pass']]
    if not good:return []
    best=min(r['worst_rmse_rad'] for r in good)
    plateau=[r for r in good if r['worst_rmse_rad']<=best*(1+policy['accuracy_plateau_fraction'])]
    plateau.sort(key=lambda r:(r['worst_tail_rms_speed_rad_s'],r['worst_tail_p2p_rad'],r['worst_rmse_rad'],*r['pair']))
    rest=[r for r in good if r not in plateau]
    return [r['pair'] for r in plateau+rest]


def finalists(ranking,pairs):
    ordered=preference(ranking)
    return sorted(set(map(tuple,ordered[:POLICY['finalist_top_count']])) | (set(CONTROLS)&set(map(tuple,pairs))))


def pareto(ranking):
    good=[r for r in ranking if r['all_quality_pass']]
    fields=('worst_rmse_rad','worst_tail_rms_speed_rad_s','worst_q22_torque_nm')
    return [r['pair'] for r in good if not any(
       all(o[k]<=r[k] for k in fields) and any(o[k]<r[k] for k in fields) for o in good)]


def summarize(records,manifest,selection,manifest_hash):
    ss=lambda key:[S(s['family'],tuple(s['parameters'])) for s in manifest[key]]
    pairs=[tuple(p) for p in manifest['pairs']]
    calibration=rank(records,pairs,ss('calibration'),'calibration')
    selected=finalists(calibration,pairs)
    if selected!=list(map(tuple,selection['pairs'])):raise ValueError('Finalists not selected solely on calibration')
    validation=rank(records,selected,ss('validation'),'validation')
    expected=len(pairs)*len(ss('calibration'))+len(selected)*len(ss('validation'))
    if len(records)!=expected or not all(r['all_present'] for r in calibration+validation):
        raise ValueError('Missing prescribed scenario; no complete result')
    passed={tuple(r['pair']) for r in validation if r['all_quality_pass']}
    survivors=[p for p in preference(calibration) if tuple(p) in passed]
    events=[r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event']]
    return {'schema':'g1.pd.accuracy-stability.summary.v1','complete':True,'simulation_only':True,
      'total_cases':expected,'calibration_cases':len(pairs)*len(ss('calibration')),
      'validation_cases':len(selected)*len(ss('validation')),'unique_pairs':len(pairs),
      'completed':sum(r['completed'] for r in records),'base_eligible':sum(r['eligible'] for r in records),
      'quality_eligible':sum(r['quality_eligible'] for r in records),
      'base_rejections':dict(Counter(r['reason'] for r in records if not r['eligible'])),
      'quality_rejection_counts':dict(Counter(x for r in records if r['eligible'] for x in r['stability']['rejections'])),
      'guard_events':dict(Counter(e['reason'] for e in events)),
      'minimum_soft_margin_rad':min(v for r in records for v in r['joint_limit_guard']['minimum_soft_margin_rad'] if v is not None),
      'minimum_model_hard_margin_rad':min(v for r in records for v in r['joint_limit_guard']['minimum_hard_margin_rad'] if v is not None),
      'calibration_ranking':calibration,'calibration_preference':preference(calibration),
      'pareto_calibration':pareto(calibration),'validation_ranking':validation,
      'frozen_order_survivors':survivors,'manifest_sha256':manifest_hash,
      'recommended_hardware_gains':None,'hardware_config_modified':False,'optimum_proven':False,
      'limitations':['fixed pelvis; joint22 only, grouped gains22..25',
        'hypothetical model/torque delay, no real motor identification',
        'bounded finite grid; stability is finite-horizon observed screening',
        'all29 trajectories stored at500Hz, limit extrema checked at physics rate',
        'prior holdouts reused as known calibration, not fresh independent validation',
        'no IK cost adjustment, full-body balance, noise or large-motion validation']}


def audit(folder,source_root=None):
    folder=Path(folder);manifest=read(folder/'manifest.json');selection=read(folder/'selection.json');stored=read(folder/'summary.json')
    if stored['manifest_sha256']!=engine.sha256(folder/'manifest.json'):raise ValueError('Manifest changed')
    if manifest['quality_policy']!=POLICY:raise ValueError('Quality policy changed')
    if source_root:
        for name,digest in manifest['source_sha256'].items():
            if engine.sha256(safe_path(source_root,name))!=digest:raise ValueError('Source changed: '+name)
        model_root=Path(source_root)/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in manifest['asset_sha256'].items():
            root=model_root if name.replace('\\','/').startswith('meshes/') else source_root
            if engine.sha256(safe_path(root,name))!=digest:raise ValueError('Model/mesh changed')
    planned=read(folder/'calibration_plan.json')+read(folder/'validation_plan.json')
    index={j[4]:j for j in planned}
    if len(index)!=len(planned):raise ValueError('Duplicate plan ids')
    # Regenerate plans rather than trusting a mutually modified manifest and case label.
    make=lambda ps,ss,phase:previous.make_jobs(ps,[S(s['family'],tuple(s['parameters'])) for s in ss],phase,folder)
    regenerated=make(manifest['pairs'],manifest['calibration'],'calibration')+make(selection['pairs'],manifest['validation'],'validation')
    normalized=lambda jobs:[(j[0],j[1],j[2],j[4],j[5]) for j in jobs]
    if normalized(planned)!=json.loads(json.dumps(normalized(regenerated))):
        # Python tuple/list normalization is deliberate for cross-platform JSON.
        if json.dumps(normalized(planned),sort_keys=True)!=json.dumps(normalized(regenerated),sort_keys=True):raise ValueError('Plan differs from manifest')
    records=[];hashes={};rows=[];full_hashes={};total_samples=0
    for p in sorted((folder/'cases').glob('*.json')):
        r,metrics,_=check_case(folder,p);verify_guard_result(r)
        job=index.get(r['case_id'])
        if not job or pair(r)!=(job[0],job[1]) or r['study_phase']!=job[5] or r['study_scenario_contract']!=job[2]:raise ValueError('Case identity mismatch')
        if r['study_scenario']!=job[2]['family']+'/'+job[2]['parameters'][0]:raise ValueError('Scenario label mismatch')
        full=safe_path(folder,r['full_state_npz'])
        if engine.sha256(full)!=r['full_state_sha256']:raise ValueError('Full-state trace hash differs')
        with np.load(full,allow_pickle=False) as f:arrays={k:f[k] for k in f.files}
        stats=stability(arrays)
        if stats!=r['stability'] or r['quality_eligible']!=bool(r['eligible'] and stats['passes']):raise ValueError('Stability metrics/decision differs')
        with np.load(safe_path(folder,r['trace_npz']),allow_pickle=False) as z:
            v={c:z['values'][:,i] for i,c in enumerate(z['columns'].tolist())}
            for name in ('q','dq','ref','cmd'):
                if not np.array_equal(arrays[name][:,22],v[name+'_22']):raise ValueError('Full/compact q22 trace mismatch')
        if r['eligible']:
            e=r['joint_limit_guard']['envelope'];q=arrays['q'];cmd=arrays['cmd'];ref=arrays['ref']
            for value in (q,cmd,ref):
                if np.any(value<=np.array(e['inner_lower'])+1e-10) or np.any(value>=np.array(e['inner_upper'])-1e-10):raise ValueError('Accepted sample touches inner limit')
            worst=np.minimum(q-np.array(e['soft_lower']),np.array(e['soft_upper'])-q).min(axis=0)
            if np.any(worst+1e-10<np.array(r['joint_limit_guard']['minimum_soft_margin_rad'])):raise ValueError('500Hz trace contradicts physics extrema')
        records.append(r);hashes[r['case_id']]=engine.sha256(p);full_hashes[r['case_id']]=r['full_state_sha256'];total_samples+=len(arrays['q'])
        row={'case_id':r['case_id'],'phase':r['study_phase'],'kp':r['kp_proximal'],'kd':r['kd_proximal'],
             'scenario':r['study_scenario'],'completed':r['completed'],'base_eligible':r['eligible'],
             'quality_eligible':r['quality_eligible'],'base_reason':r['reason'],'quality_rejections':';'.join(stats['rejections']),
             'rmse_rad':metrics['reference_rmse_joint22_rad'] if metrics else None,
             'tail_error_rad':stats['max_q22_tail_error_rad'],'tail_speed_rad_s':stats['max_q22_tail_speed_rad_s'],
             'right7_tail_rms_speed_rad_s':stats['max_right7_tail_rms_speed_rad_s'],
             'right7_tail_p2p_rad':stats['max_right7_tail_p2p_rad']}
        rows.append(row)
    regenerated=summarize(records,manifest,selection,engine.sha256(folder/'manifest.json'))
    if regenerated!=stored:raise ValueError('Summary or ranking does not match evidence')
    frozen={r['case_id']:hashes[r['case_id']] for r in records if r['study_phase']=='calibration'}
    if frozen!=selection['calibration_case_hashes']:raise ValueError('Calibration changed after selection')
    import csv
    with (folder/'all_cases.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result={'schema':'g1.pd.accuracy-stability.audit.v1','passed':True,'simulation_only':True,
      'cases':len(records),'all29_500hz_state_samples':total_samples,'all29_extrema_records':29*len(records),
      'source_model_hashes_checked':bool(source_root),'case_hashes':hashes,'full_state_hashes':full_hashes,
      'manifest_sha256':engine.sha256(folder/'manifest.json'),'selection_sha256':engine.sha256(folder/'selection.json'),
      'summary_sha256':engine.sha256(folder/'summary.json'),'all_cases_sha256':engine.sha256(folder/'all_cases.csv'),
      'hardware_validated':False,'scope':'all29 sampled500Hz states plus physics-rate extrema/witnesses; not continuous-time proof'}
    save(folder/'audit.json',result);return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--smoke',action='store_true');parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers must be1..8')
    folder=args.output.resolve()
    if args.audit_only:
        result=audit(folder);print('AUDIT',result['passed'],result['cases']);return 0
    pairs=((100.,1.3),(100.,2.)) if args.smoke else PAIRS
    calibration=(CALIBRATION[0],) if args.smoke else CALIBRATION
    validation=VALIDATION[:1] if args.smoke else VALIDATION
    for s in calibration+validation:s.validate()
    if len({s.identity for s in calibration+validation})!=len(calibration+validation):raise ValueError('Overlapping scenario identities')
    contract=engine.load_contract()
    for p in pairs:engine.candidate_gains(contract,*p)
    import mujoco
    model,qa,_,_,assets=engine.load_model(engine.MODEL,.001)
    names=['mujoco_pd_accuracy_stability.py','mujoco_pd_robust_refine.py','mujoco_pd_sweep.py',
      'mujoco_pd_expand.py','mujoco_pd_motor_stress.py','mujoco_pd_contract.py','mujoco_pd_fixture.py',
      'joint_limit_guard.py','mujoco_pd_expand_audit.py','mujoco_pd_limit_replay.py','pd_small_signal_trial.hpp']
    manifest={'schema':'g1.pd.accuracy-stability.run.v1','full_study':not args.smoke,'simulation_only':True,
      'pairs':pairs,'calibration':[asdict(s) for s in calibration],'validation':[asdict(s) for s in validation],
      'quality_policy':POLICY,'baseline_controls':CONTROLS,'prior_holdouts_now_calibration':True,
      'mujoco':mujoco.__version__,'numpy':np.__version__,'python':platform.python_version(),'platform':platform.platform(),
      'source_sha256':engine.source_hashes([Path(__file__).with_name(n) for n in names]+[engine.REFERENCE]),
      'asset_sha256':assets,'joint_limit_envelope':engine.JointLimitEnvelope.from_model(model,qa,contract).manifest(),
      'recommended_hardware_gains':None,'hardware_config_modified':False,
      'selection_rule':'all conditions + endpoint stability, minimum worst RMSE; inside2% plateau prefer lower worst tail RMS speed; freeze before new validation'}
    folder.mkdir(parents=True,exist_ok=False);save(folder/'manifest.json',manifest);manifest=read(folder/'manifest.json')
    records=[]
    def run(pool,jobs):
        for future in as_completed([pool.submit(run_case,j) for j in jobs]):
            records.append(future.result())
            if len(records)%10==0:
                save(folder/'progress.json',{'complete':False,'cases':len(records),'phase':records[-1]['study_phase']})
                print('ACCURACY_STABILITY',len(records),records[-1]['study_phase'],flush=True)
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        jobs=previous.make_jobs(pairs,calibration,'calibration',folder);save(folder/'calibration_plan.json',jobs);run(pool,jobs)
        selected=finalists(rank(records,pairs,calibration,'calibration'),pairs)
        if not selected:raise RuntimeError('No candidate or control available')
        selection={'pairs':selected,'basis':'calibration only; fixed plateau and quality thresholds',
          'calibration_case_hashes':{r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in sorted(records,key=lambda x:x['case_id'])}}
        save(folder/'selection.json',selection);print('FROZEN',json.dumps(selected),flush=True)
        jobs=previous.make_jobs(selected,validation,'validation',folder);save(folder/'validation_plan.json',jobs);run(pool,jobs)
    result=summarize(records,manifest,read(folder/'selection.json'),engine.sha256(folder/'manifest.json'))
    save(folder/'summary.json',result);checked=audit(folder,engine.ROOT)
    save(folder/'progress.json',{'complete':True,'cases':len(records),'audited':checked['passed']})
    print('FINAL',json.dumps({k:v for k,v in result.items() if k not in ('calibration_ranking','validation_ranking')}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
