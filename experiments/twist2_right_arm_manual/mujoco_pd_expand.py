"""Expanded fixed-pelvis MuJoCo PD search; simulation ONLY, no SDK/DDS/robot I/O.
Existing engine, live launcher, reference, limits and hardware gains are unchanged.
All changes of model parameters exist only in newly loaded MjModel instances.
"""
from __future__ import annotations
import os
for _var in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_var] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import sys
import time
import numpy as np
import mujoco_pd_sweep as engine

KP = (16,24,32,40,48,56,64,72,80,88,96,100)
KD = (.1,.25,.5,.75,1,1.25,1.5,2,2.5,3,4,5,7,10,15,20)
# name, physics timestep, right-arm mass+inertia scale, passive damping scale,
# added right-arm frictionloss in Nm. These are assumptions, NOT measured G1 errors.
SCENARIOS = (
 ('nominal',.001,1.,1.,0.), ('dt_half',.0005,1.,1.,0.),
 ('mass_075',.001,.75,1.,0.), ('mass_125',.001,1.25,1.,0.),
 ('damping_050',.001,1.,.5,0.), ('damping_200',.001,1.,2.,0.),
 ('friction_add_010',.001,1.,1.,.1), ('friction_add_025',.001,1.,1.,.25),
 ('combined_low',.001,.75,.5,.1), ('combined_high',.001,1.25,2.,.25),
 ('combined_half',.0005,1.25,2.,.25))

def block_network(event,args):
    if event.startswith('socket.'):
        raise RuntimeError('OFFLINE worker forbids '+event)

def init_worker():
    # Windows platform.system() otherwise lazily calls local gethostname.
    # Cache OS metadata before the hook; keep every socket audit event blocked.
    platform.uname()
    sys.addaudithook(block_network)

def save_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    temp.replace(path)

def key(r):
    return (r['kp_proximal'],r['kd_proximal'])

def nominal_rank(results):
    return sorted((r for r in results if r['scenario'][0]=='nominal' and r['eligible']),
                  key=lambda r:(r['metrics']['reference_rmse_joint22_rad'],*key(r)))

def fine_pairs(results):
    seen={key(r) for r in results if r['scenario'][0]=='nominal'}
    pairs=set()
    for r in nominal_rank(results)[:6]:
        for dp,dd in itertools.product((-6,-4,-2,0,2,4,6),(-.3,-.15,0,.15,.3)):
            p,d=round(key(r)[0]+dp,6),round(key(r)[1]+dd,6)
            if 1<=p<=100 and .1<=d<=20 and (p,d) not in seen:
                pairs.add((p,d))
    return sorted(pairs)

def validation_pairs(results):
    pairs={key(r) for r in nominal_rank(results)[:12]}
    pairs.update(((40.,5.),(56.,3.),(80.,1.),(80.,2.),(100.,.5),
                  (100.,1.),(100.,2.),(100.,3.),(100.,5.)))
    return sorted(pairs)

def simulate(job):
    import mujoco
    kp,kd,scenario,folder,identifier,stage=job
    name,dt,mass,damping,friction=scenario
    model,qadr,vadr,motors,_=engine.load_model(engine.MODEL,dt)
    contract=engine.load_contract()
    engine.candidate_gains(contract,kp,kd)
    ids=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,engine.JOINTS[j]) for j in range(22,29)]
    bodies=np.unique(model.jnt_bodyid[ids])
    original={'mass_kg':model.body_mass[bodies].tolist(),
              'inertia':model.body_inertia[bodies].tolist(),
              'damping':model.dof_damping[vadr[22:]].tolist(),
              'frictionloss_nm':model.dof_frictionloss[vadr[22:]].tolist()}
    model.body_mass[bodies]*=mass
    model.body_inertia[bodies]*=mass
    model.dof_damping[vadr[22:]]*=damping
    model.dof_frictionloss[vadr[22:]]+=friction
    if mass!=1.:
        mujoco.mj_setConst(model,mujoco.MjData(model))
    observation={'trial_physics_steps':0,'trial_contact_steps':0,
                 'peak_arm_speed_rad_s':0.,'peak_arm_actuator_torque_nm':0.}
    real_step=mujoco.mj_step
    def observe(m,data):
        trial=float(data.time)>=engine.WARMUP-dt/2
        real_step(m,data)
        if trial:
            observation['trial_physics_steps']+=1
            observation['trial_contact_steps']+=int(data.ncon>0)
            observation['peak_arm_speed_rad_s']=max(observation['peak_arm_speed_rad_s'],float(np.max(np.abs(data.qvel[vadr[22:]]))))
            observation['peak_arm_actuator_torque_nm']=max(observation['peak_arm_actuator_torque_nm'],float(np.max(np.abs(data.actuator_force[motors[22:]]))))
    start=time.monotonic()
    mujoco.mj_step=observe
    try:
        result,rows=engine.run_candidate(model,qadr,vadr,motors,contract,kp,kd)
    finally:
        mujoco.mj_step=real_step
    result.update(case_id=identifier,stage=stage,scenario=list(scenario),
                  simulation_only=True,hardware_config_modified=False,
                  physics_observation=observation,original_model_parameters=original,
                  wall_seconds=time.monotonic()-start)
    if observation['trial_contact_steps']:
        result['eligible']=False
        result['exclusion_reasons'].append('physics_step_contact')
    # Full-rate joint22 trace for EVERY run, including failures; no cherry-picked traces.
    columns=['time_s','trial_time_s','phase','cycle','direction','ref_22','cmd_22',
             'q_22','dq_22','tau_requested_22','actual_tau_22','contacts',
             'torque_target_limited_arm','hard_clipped_arm','slew_exceeded_arm']
    values=np.array([[r[c] for c in columns] for r in rows],dtype=np.float64).reshape((-1,len(columns)))
    dest=Path(folder)/'traces'/(identifier+'.npz'); dest.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(dest,columns=np.array(columns),values=values,segment=np.array([r['segment'] for r in rows]))
    with np.load(dest,allow_pickle=False) as trace:
        v=trace['values']; trial=v[:,1]>=0
        if trial.any():
            rmse=float(np.sqrt(np.mean((v[trial,5]-v[trial,7])**2)))
            if not math.isclose(rmse,result['metrics']['reference_rmse_joint22_rad'],rel_tol=1e-12,abs_tol=1e-12):
                raise RuntimeError('Saved-trace independent RMSE mismatch')
    result['trace_npz']=str(dest.relative_to(Path(folder)))
    result['trace_sha256']=engine.sha256(dest)
    result['trace_rows']=len(rows)
    save_json(Path(folder)/'cases'/(identifier+'.json'),result)
    return result

def jobs_for(pairs,scenarios,folder,stage,existing=()):
    seen={(key(r),r['scenario'][0]) for r in existing}
    jobs=[]
    for pair,scenario in itertools.product(pairs,scenarios):
        if (pair,scenario[0]) not in seen:
            jobs.append((*pair,scenario,str(folder),f'{stage}_{len(jobs):04d}',stage))
    return jobs

def run_batch(pool,jobs,results,folder):
    futures={pool.submit(simulate,j):j for j in jobs}
    for future in as_completed(futures):
        r=future.result() # Infrastructure errors abort; never classify them as good candidates.
        results.append(r)
        print(json.dumps({'done':len(results),'case':r['case_id'],'pair':key(r),
                          'scenario':r['scenario'][0],'eligible':r['eligible'],'reason':r['reason'],
                          'rmse':r['metrics']['reference_rmse_joint22_rad'] if r['metrics'] else None}),flush=True)
        save_json(folder/'progress.json',{'complete':False,'count':len(results),
            'top':[{'pair':key(x),'rmse':x['metrics']['reference_rmse_joint22_rad']} for x in nominal_rank(results)[:5]]})

def robust_rank(results,pairs):
    required={s[0] for s in SCENARIOS}; rank=[]
    for pair in pairs:
        cases={r['scenario'][0]:r for r in results if key(r)==pair}
        present=required<=set(cases)
        eligible=present and all(cases[s]['eligible'] for s in required)
        errors=[cases[s]['metrics']['reference_rmse_joint22_rad'] for s in required if s in cases and cases[s]['metrics']]
        rank.append({'pair':pair,'all_scenarios_present':present,'all_scenarios_eligible':eligible,
          'eligible_count':sum(cases[s]['eligible'] for s in required if s in cases),'required':len(required),
          'worst_rmse':max(errors) if errors else None,'mean_rmse':float(np.mean(errors)) if errors else None,
          'failures':[{'scenario':s,'reason':cases[s]['reason'],'exclusions':cases[s]['exclusion_reasons']}
                      for s in sorted(required) if s in cases and not cases[s]['eligible']]})
    return sorted(rank,key=lambda r:(not r['all_scenarios_eligible'],-r['eligible_count'],r['worst_rmse'] or math.inf,r['pair']))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8: parser.error('workers must be 1..8')
    folder=args.output.resolve(); folder.mkdir(parents=True,exist_ok=False)
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    sources=engine.source_hashes([Path(__file__),Path(__file__).with_name("joint_limit_guard.py"),Path(engine.__file__),Path(__file__).with_name('mujoco_pd_contract.py'),
        Path(__file__).with_name('mujoco_pd_fixture.py'),Path(__file__).with_name('pd_small_signal_trial.hpp'),engine.REFERENCE])
    save_json(folder/'manifest.json',{'schema':'g1.pd.expanded.v1','simulation_only':True,
      'mujoco':mujoco.__version__,'numpy':np.__version__,'python':platform.python_version(),'platform':platform.platform(),
      'source_sha256':sources,'asset_sha256':assets,'coarse_kp':KP,'coarse_kd':KD,'scenarios':SCENARIOS,
      'workers':args.workers,'reference':'unchanged joint22 +/-8deg three cycles; gains grouped on22..25',
      'trace_scope':'joint22 at500Hz; seven-joint scalar metrics; contacts and arm peaks monitored every physics step',
      'limitations':['fixed pelvis','ideal motor; no actuator or communication delay model',
                     'hypothetical mass/inertia/passive damping/friction perturbations','no VR/IK or hardware validation'],
      'recommended_hardware_gains':None,'hardware_config_modified':False})
    results=[]; start=time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=init_worker) as pool:
        jobs=jobs_for(list(itertools.product(KP,KD)),[SCENARIOS[0]],folder,'coarse')
        save_json(folder/'coarse_plan.json',jobs); run_batch(pool,jobs,results,folder)
        pairs=fine_pairs(results); jobs=jobs_for(pairs,[SCENARIOS[0]],folder,'fine',results)
        save_json(folder/'fine_plan.json',jobs); run_batch(pool,jobs,results,folder)
        checked=validation_pairs(results); jobs=jobs_for(checked,SCENARIOS,folder,'stress',results)
        save_json(folder/'stress_plan.json',jobs); run_batch(pool,jobs,results,folder)
    summary={'schema':'g1.pd.expanded.summary.v1','complete':True,'simulation_only':True,
       'count':len(results),'completed_count':sum(r['completed'] for r in results),'eligible_count':sum(r['eligible'] for r in results),
       'stage_counts':{s:sum(r['stage']==s for r in results) for s in ('coarse','fine','stress')},
       'nominal_ranking':[{'pair':key(r),'rmse':r['metrics']['reference_rmse_joint22_rad'],'case_id':r['case_id']} for r in nominal_rank(results)],
       'robust_ranking':robust_rank(results,checked),'wall_seconds':time.monotonic()-start,
       'manifest_sha256':engine.sha256(folder/'manifest.json'),'recommended_hardware_gains':None,'hardware_config_modified':False}
    save_json(folder/'summary.json',summary)
    save_json(folder/'progress.json',{'complete':True,'count':len(results)})
    print('EXPANDED_RESULT '+json.dumps(summary),flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
