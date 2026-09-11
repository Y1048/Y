"""Coupled model/actuator uncertainty study. OFFLINE ONLY; never deploy a gain.

Preserve the existing reference, core dynamics, all29 limits and endpoint policy.
All factorial calibration cells are simulated (no pruning). Freeze finalists
before new combined validation conditions. Model perturbations and torque-path
latency are assumptions, not identification of actual G1 hardware.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict,dataclass
import csv,itertools,json,math,platform
from pathlib import Path
import numpy as np
import mujoco_pd_accuracy_stability as quality
import mujoco_pd_robust_refine as previous
import mujoco_pd_motor_stress as motor
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine
from mujoco_pd_expand_audit import check_case,safe_path
from mujoco_pd_limit_replay import verify_guard_result

PAIRS=((80.,1.),(88.,2.),(96.,1.5),(96.,2.),(100.,1.275),(100.,1.3),
       (100.,1.4),(100.,1.5),(100.,1.75),(100.,2.),(100.,2.5),(100.,3.))
CONTROLS=((100.,1.275),(100.,2.),(80.,1.))
TOP_COUNT=6
AXES=((.75,1.25),(.5,1.5),(0.,.5),(0.,.002),(0.,.006),(.001,.0005))

@dataclass(frozen=True)
class Coupled:
    name:str
    mass_scale:float=1.
    damping_scale:float=1.
    friction_scale:float=1.
    delay_s:float=0.
    lag_s:float=0.
    dt:float=.001

    @property
    def identity(self):return 'coupled/'+self.name

    def validate(self):
        if not isinstance(self.name,str) or not self.name or not all(c.isalnum() or c=='_' for c in self.name):
            raise ValueError('Invalid scenario name')
        values=(self.mass_scale,self.damping_scale,self.friction_scale,self.delay_s,self.lag_s,self.dt)
        if not all(math.isfinite(x) for x in values):raise ValueError('Non-finite scenario')
        if not .5<=self.mass_scale<=1.5 or not .25<=self.damping_scale<=2 or not 0<=self.friction_scale<=2:
            raise ValueError('Perturbation outside declared model bounds')
        if self.dt not in (.001,.0005):raise ValueError('Only prescribed physics timesteps')
        motor.TorquePath(self.dt,self.delay_s,self.lag_s)

CALIBRATION=(Coupled('nominal'),)+tuple(Coupled(f'factorial_{i:02d}',*v)
    for i,v in enumerate(itertools.product(*AXES)))
# Deterministic NEW mixtures, written before any simulations. Not random noise.
def new_conditions():
    rng=np.random.default_rng(2026091104)
    result=[]
    for i in range(16):
        dt=.0005 if i%3==0 else .001
        result.append(Coupled(f'validation_{i:02d}',
          float(rng.choice((.65,.9,1.1,1.35))),float(rng.choice((.65,.85,1.25,1.75))),
          float(rng.choice((.05,.15,.35,.75))),float(rng.choice((.001,.003,.004))),
          float(rng.choice((.002,.004,.005,.008))),dt))
    return tuple(result)
VALIDATION=new_conditions()

def read(path):return quality.read(path)
def save(path,data):return quality.save(path,data)
def pair(r):return previous.pair_of(r)

def apply_model(model,qadr,vadr,scenario):
    """Mutate a newly loaded private MjModel, never the XML or any live file."""
    import mujoco
    scenario.validate()
    joints=np.array([mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,engine.JOINTS[j]) for j in range(22,29)])
    if np.any(joints<0):raise ValueError('Missing right-arm joint')
    bodies=np.unique(model.jnt_bodyid[joints])
    def state():
        return {'mass':model.body_mass.copy(),'inertia':model.body_inertia.copy(),
                'damping':model.dof_damping.copy(),'friction':model.dof_frictionloss.copy()}
    before=state();limits=model.jnt_range.copy();margins=model.jnt_margin.copy()
    model.body_mass[bodies]*=scenario.mass_scale
    model.body_inertia[bodies]*=scenario.mass_scale
    model.dof_damping[vadr[22:]]*=scenario.damping_scale
    model.dof_frictionloss[vadr[22:]]*=scenario.friction_scale
    # Official MuJoCo simulation docs require mj_setConst after mass/inertia edits.
    if scenario.mass_scale!=1.:mujoco.mj_setConst(model,mujoco.MjData(model))
    if not np.array_equal(model.jnt_range,limits) or not np.array_equal(model.jnt_margin,margins):
        raise RuntimeError('Model limit unexpectedly changed')
    return {'body_ids':bodies.tolist(),'dof_ids':vadr[22:].tolist(),
      'before':{k:v.tolist() for k,v in before.items()},
      'after':{k:v.tolist() for k,v in state().items()},'limits_unchanged':True}

def run_case(job):
    p,d,raw,folder,identifier,phase=job
    scenario=Coupled(**raw);scenario.validate()
    import mujoco
    old_load,old_step=engine.load_model,mujoco.mj_step
    torque_path=motor.TorquePath(scenario.dt,scenario.delay_s,scenario.lag_s)
    context={}
    def load(xml,dt):
        if dt!=scenario.dt:raise RuntimeError('Timestep composition mismatch')
        model,qa,va,motors,assets=old_load(xml,dt)
        context['motors']=motors[22:].copy()
        context['evidence']=apply_model(model,qa,va,scenario)
        return model,qa,va,motors,assets
    def step(model,data):
        indexes=context['motors']
        data.ctrl[indexes]=torque_path.step(data.ctrl[indexes])
        old_step(model,data)
    engine.load_model=load;mujoco.mj_step=step
    try:
        # Neutral inherited model runner: all modifications happen exactly once above.
        neutral=previous.Scenario('model',(scenario.name,scenario.dt,1.,1.,0.))
        r=quality.run_case((p,d,asdict(neutral),folder,identifier,phase))
    finally:
        engine.load_model=old_load;mujoco.mj_step=old_step
    r.update(study_scenario=scenario.identity,study_scenario_contract=asdict(scenario),
        coupled_model_evidence=context['evidence'],torque_path={'delay_s':scenario.delay_s,'lag_s':scenario.lag_s,
        'scope':'all seven right-arm torques; hypothetical motor path, not measured UDP latency'})
    save(Path(folder)/'cases'/(identifier+'.json'),r)
    return r

def jobs(pairs,scenarios,phase,folder):
    return [(float(p),float(d),asdict(s),str(folder),f'{phase}_{i:05d}',phase)
      for i,((p,d),s) in enumerate(itertools.product(pairs,scenarios))]

def choose(ranking,pairs):
    # Pure worst original-reference RMSE, after all strict quality conditions.
    top=[tuple(r['pair']) for r in ranking if r['all_quality_pass']][:TOP_COUNT]
    return sorted(set(top)|(set(CONTROLS)&set(map(tuple,pairs))))

def summary(records,manifest,selection,manifest_hash):
    calibration=[Coupled(**s) for s in manifest['calibration']]
    validation=[Coupled(**s) for s in manifest['validation']]
    pairs=list(map(tuple,manifest['pairs']))
    train=quality.rank(records,pairs,calibration,'calibration')
    expected=choose(train,pairs)
    if expected!=list(map(tuple,selection['pairs'])):raise ValueError('Calibration-only finalist selection changed')
    valid=quality.rank(records,expected,validation,'validation')
    count=len(pairs)*len(calibration)+len(expected)*len(validation)
    if len(records)!=count or not all(r['all_present'] for r in train+valid):
        raise ValueError('Incomplete prescribed combined study')
    passed={tuple(r['pair']) for r in valid if r['all_quality_pass']}
    survivors=[r['pair'] for r in train if r['all_quality_pass'] and tuple(r['pair']) in passed]
    events=[r['joint_limit_guard']['event'] for r in records if r['joint_limit_guard']['event']]
    minimum=lambda key:min(v for r in records for v in r['joint_limit_guard'][key] if v is not None)
    return {'schema':'g1.pd.coupled.summary.v1','complete':True,'simulation_only':True,
      'total_cases':count,'unique_pairs':len(pairs),'calibration_cases':len(pairs)*len(calibration),
      'validation_cases':len(expected)*len(validation),'completed':sum(r['completed'] for r in records),
      'base_eligible':sum(r['eligible'] for r in records),'quality_eligible':sum(r['quality_eligible'] for r in records),
      'base_rejections':dict(Counter(r['reason'] for r in records if not r['eligible'])),
      'quality_rejections':dict(Counter(reason for r in records if r['eligible'] and not r['quality_eligible'] for reason in r['stability']['rejections'])),
      'guard_events':dict(Counter(e['reason'] for e in events)),
      'minimum_soft_margin_rad':minimum('minimum_soft_margin_rad'),
      'minimum_model_hard_margin_rad':minimum('minimum_hard_margin_rad'),
      'calibration_ranking':train,'validation_ranking':valid,'strict_order_survivors':survivors,
      'manifest_sha256':manifest_hash,'all_possible_cases_tested':False,'optimum_proven':False,
      'recommended_hardware_gains':None,'hardware_config_modified':False,
      'limitations':['fixed pelvis, only joint22 excited, gains grouped22..25',
        'finite combined model and torque-path parameters; not measured robot uncertainty',
        'no other trajectories, sensor noise, payload geometry, full-body or physical validation',
        'all29 states at500Hz plus physics-rate guard witnesses; not continuous-time safety proof']}

def check_model_evidence(r):
    s=Coupled(**r['study_scenario_contract']);s.validate();e=r['coupled_model_evidence']
    if not e['limits_unchanged']:raise ValueError('Model limit changed')
    for key in ('mass','inertia','damping','friction'):
        before=np.asarray(e['before'][key],float);after=np.asarray(e['after'][key],float)
        ids=e['body_ids'] if key in ('mass','inertia') else e['dof_ids']
        scale={'mass':s.mass_scale,'inertia':s.mass_scale,'damping':s.damping_scale,'friction':s.friction_scale}[key]
        expected=before.copy();expected[ids]*=scale
        if not np.isfinite(after).all() or not np.array_equal(expected,after):raise ValueError('Coupled model evidence mismatch: '+key)
    if r['torque_path']['delay_s']!=s.delay_s or r['torque_path']['lag_s']!=s.lag_s:
        raise ValueError('Torque path differs from coupled scenario')

def audit(folder,source_root=None):
    folder=Path(folder);m=read(folder/'manifest.json');selection=read(folder/'selection.json');stored=read(folder/'summary.json')
    if m['quality_policy']!=quality.POLICY or m['selection_rule']!='strict worst RMSE after all unchanged quality/limit conditions':
        raise ValueError('Frozen quality or objective changed')
    if engine.sha256(folder/'manifest.json')!=stored['manifest_sha256']:raise ValueError('Manifest changed')
    if source_root:
        for name,digest in m['source_sha256'].items():
            if engine.sha256(safe_path(source_root,name))!=digest:raise ValueError('Source changed: '+name)
        model_root=Path(source_root)/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1'
        for name,digest in m['asset_sha256'].items():
            source=model_root if name.replace('\\','/').startswith('meshes/') else source_root
            if engine.sha256(safe_path(source,name))!=digest:raise ValueError('Model/mesh changed')
    plans=read(folder/'calibration_plan.json')+read(folder/'validation_plan.json')
    regenerated=jobs(m['pairs'],[Coupled(**s) for s in m['calibration']],'calibration',folder)+jobs(selection['pairs'],[Coupled(**s) for s in m['validation']],'validation',folder)
    norm=lambda data:json.dumps([(j[0],j[1],j[2],j[4],j[5]) for j in data],sort_keys=True)
    if norm(plans)!=norm(regenerated):raise ValueError('Plans differ from declared protocol')
    index={j[4]:j for j in plans}
    if len(index)!=len(plans):raise ValueError('Duplicate planned id')
    records=[];hashes={};rows=[];samples=0
    for file in sorted((folder/'cases').glob('*.json')):
        r,metrics,_=check_case(folder,file);verify_guard_result(r);check_model_evidence(r)
        j=index.get(r['case_id'])
        if not j or pair(r)!=(j[0],j[1]) or r['study_scenario_contract']!=j[2] or r['study_phase']!=j[5]:
            raise ValueError('Case differs from planned coupled parameters')
        if r['study_scenario']!=Coupled(**j[2]).identity:raise ValueError('Scenario label mismatch')
        full=safe_path(folder,r['full_state_npz'])
        if engine.sha256(full)!=r['full_state_sha256']:raise ValueError('Full-state hash changed')
        with np.load(full,allow_pickle=False) as f:a={k:f[k] for k in f.files}
        stats=quality.stability(a)
        if stats!=r['stability'] or r['quality_eligible']!=bool(r['eligible'] and stats['passes']):
            raise ValueError('Endpoint evidence changed')
        with np.load(safe_path(folder,r['trace_npz']),allow_pickle=False) as f:
            v={c:f['values'][:,i] for i,c in enumerate(f['columns'].tolist())}
        for key in ('q','dq','cmd','ref'):
            if not np.array_equal(a[key][:,22],v[key+'_22']):raise ValueError('Compact/full trace mismatch')
        if r['eligible']:
            envelope=r['joint_limit_guard']['envelope']
            for key in ('q','cmd','ref'):
                if np.any(a[key]<=np.array(envelope['inner_lower'])+1e-10) or np.any(a[key]>=np.array(envelope['inner_upper'])-1e-10):
                    raise ValueError('Accepted state touches inner limit')
            observed=np.minimum(a['q']-np.array(envelope['soft_lower']),np.array(envelope['soft_upper'])-a['q']).min(axis=0)
            if np.any(observed+1e-10<r['joint_limit_guard']['minimum_soft_margin_rad']):raise ValueError('Sample contradicts physics minima')
        records.append(r);hashes[r['case_id']]=engine.sha256(file);samples+=len(a['q'])
        rows.append({'case_id':r['case_id'],'phase':r['study_phase'],'kp':r['kp_proximal'],'kd':r['kd_proximal'],
          **r['study_scenario_contract'],'completed':r['completed'],'base_eligible':r['eligible'],
          'quality_eligible':r['quality_eligible'],'base_reason':r['reason'],'quality_reasons':';'.join(stats['rejections']),
          'rmse_rad':metrics['reference_rmse_joint22_rad'] if metrics else None,
          'tail_rms_speed_rad_s':stats['max_right7_tail_rms_speed_rad_s'],'tail_p2p_rad':stats['max_right7_tail_p2p_rad'],
          'trace_sha256':r['trace_sha256'],'full_state_sha256':r['full_state_sha256']})
    recalculated=summary(records,m,selection,engine.sha256(folder/'manifest.json'))
    if recalculated!=stored:raise ValueError('Summary/ranking differs from observed records')
    frozen={r['case_id']:hashes[r['case_id']] for r in records if r['study_phase']=='calibration'}
    if frozen!=selection['calibration_case_hashes']:raise ValueError('Calibration evidence changed after finalist freeze')
    with (folder/'all_cases.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'schema':'g1.pd.coupled.audit.v1','passed':True,'simulation_only':True,'cases':len(records),
      'all29_500hz_rows':samples,'all29_extrema_records':29*len(records),'source_model_hashes_checked':bool(source_root),
      'case_hashes':hashes,'manifest_sha256':engine.sha256(folder/'manifest.json'),
      'selection_sha256':engine.sha256(folder/'selection.json'),'summary_sha256':engine.sha256(folder/'summary.json'),
      'all_cases_sha256':engine.sha256(folder/'all_cases.csv'),'hardware_validated':False,
      'scope':'recomputed compact/full-state metrics and limits; model mutations and frozen selections checked'}
    save(folder/'audit.json',result);return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--workers',type=int,default=6)
    p.add_argument('--smoke',action='store_true');p.add_argument('--audit-only',action='store_true')
    args=p.parse_args(argv)
    if not 1<=args.workers<=8:p.error('workers must be1..8')
    folder=args.output.resolve()
    if args.audit_only:
        result=audit(folder);print('AUDIT',result['passed'],result['cases']);return 0
    if folder.exists():raise FileExistsError('Do not overwrite prior results')
    pairs=((100.,1.275),(100.,2.)) if args.smoke else PAIRS
    calibration=(CALIBRATION[0],) if args.smoke else CALIBRATION
    validation=VALIDATION[:1] if args.smoke else VALIDATION
    for s in calibration+validation:s.validate()
    if len({s.identity for s in calibration+validation})!=len(calibration)+len(validation):raise ValueError('Duplicate scenario')
    for v in pairs:engine.candidate_gains(engine.load_contract(),*v)
    import mujoco
    model,qa,_,_,assets=engine.load_model(engine.MODEL,.001)
    names=['mujoco_pd_coupled_stress.py','mujoco_pd_accuracy_stability.py','mujoco_pd_robust_refine.py',
      'mujoco_pd_sweep.py','mujoco_pd_expand.py','mujoco_pd_motor_stress.py','mujoco_pd_contract.py',
      'mujoco_pd_fixture.py','joint_limit_guard.py','mujoco_pd_expand_audit.py','mujoco_pd_limit_replay.py','pd_small_signal_trial.hpp']
    m={'schema':'g1.pd.coupled.run.v1','full_study':not args.smoke,'simulation_only':True,
      'pairs':pairs,'calibration':[asdict(s) for s in calibration],'validation':[asdict(s) for s in validation],
      'quality_policy':quality.POLICY,'selection_rule':'strict worst RMSE after all unchanged quality/limit conditions',
      'top_count':TOP_COUNT,'controls':CONTROLS,'factorial_axes':AXES,'validation_seed':2026091104,
      'mujoco':mujoco.__version__,'numpy':np.__version__,'python':platform.python_version(),'platform':platform.platform(),
      'source_sha256':engine.source_hashes([Path(__file__).with_name(n) for n in names]+[engine.REFERENCE]),
      'asset_sha256':assets,'joint_limit_envelope':engine.JointLimitEnvelope.from_model(model,qa,engine.load_contract()).manifest(),
      'recommended_hardware_gains':None,'hardware_config_modified':False,'all_possible_cases_tested':False}
    folder.mkdir(parents=True,exist_ok=False);save(folder/'manifest.json',m);m=read(folder/'manifest.json')
    records=[]
    def run(pool,plan):
        for f in as_completed([pool.submit(run_case,j) for j in plan]):
            records.append(f.result())
            if len(records)%20==0:
                save(folder/'progress.json',{'complete':False,'cases':len(records),'phase':records[-1]['study_phase']})
                print('COUPLED',len(records),records[-1]['study_phase'],flush=True)
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        plan=jobs(pairs,calibration,'calibration',folder);save(folder/'calibration_plan.json',plan);run(pool,plan)
        selected=choose(quality.rank(records,pairs,calibration,'calibration'),pairs)
        if not selected:raise RuntimeError('No candidate/control to validate')
        selection={'pairs':selected,'basis':'calibration only, strict error objective',
          'calibration_case_hashes':{r['case_id']:engine.sha256(folder/'cases'/(r['case_id']+'.json')) for r in sorted(records,key=lambda r:r['case_id'])}}
        save(folder/'selection.json',selection);print('FROZEN',json.dumps(selected),flush=True)
        plan=jobs(selected,validation,'validation',folder);save(folder/'validation_plan.json',plan);run(pool,plan)
    result=summary(records,m,read(folder/'selection.json'),engine.sha256(folder/'manifest.json'))
    save(folder/'summary.json',result);checked=audit(folder,engine.ROOT)
    save(folder/'progress.json',{'complete':True,'cases':len(records),'audited':checked['passed']})
    print('FINAL',json.dumps({k:v for k,v in result.items() if k not in ('calibration_ranking','validation_ranking')}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
