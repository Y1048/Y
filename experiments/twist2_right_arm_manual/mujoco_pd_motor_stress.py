"""Offline-only actuator uncertainty screen; no SDK/DDS, ports, or robot commands.
The delay is in the simulated ideal TORQUE path, not a model of measured UDP latency.
Friction factors are hypothetical. No production/live file is modified or imported.
"""
from __future__ import annotations
import argparse
import os
for _var in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[_var]="1"
from collections import deque
from concurrent.futures import ProcessPoolExecutor,as_completed
import math
from pathlib import Path
import time
import numpy as np
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine

PAIRS=((40,5),(56,3),(64,1),(72,1),(80,.1),(80,.5),(80,1),(80,2),(80,3),
       (100,.1),(100,.5),(100,1),(100,2),(100,3),(100,5))
# name, friction factor, pure torque delay(s), torque first-order time constant(s), dt(s)
SCENARIOS=(('nominal',1,0,0,.001),('friction_zero',0,0,0,.001),
 ('friction_025',.25,0,0,.001),('friction_050',.5,0,0,.001),
 ('delay_1ms',1,.001,0,.001),('delay_2ms',1,.002,0,.001),
 ('delay_4ms',1,.004,0,.001),('delay_8ms',1,.008,0,.001),
 ('lag_2ms',1,0,.002,.001),('lag_5ms',1,0,.005,.001),('lag_10ms',1,0,.010,.001),
 ('zero_friction_lag_2ms',0,0,.002,.001),('zero_friction_lag_5ms',0,0,.005,.001),
 ('zero_friction_delay_2ms',0,.002,0,.001),('zero_friction_delay_4ms',0,.004,0,.001),
 ('combined',.25,.002,.002,.001),('dt_half',1,0,0,.0005),
 ('combined_half',0,.002,.002,.0005))

class TorquePath:
    def __init__(self,dt,delay_s,lag_s):
        if not all(math.isfinite(x) for x in (dt,delay_s,lag_s)) or dt<=0 or not 0<=delay_s<=.02 or not 0<=lag_s<=.02:
            raise ValueError('Invalid offline actuator parameters')
        n=round(delay_s/dt)
        if not math.isclose(n,delay_s/dt,abs_tol=1e-9):
            raise ValueError('Delay must be integer physics steps')
        self.queue=deque([np.zeros(7) for _ in range(n)])
        self.delay_steps=n
        self.alpha=1. if lag_s==0 else -math.expm1(-dt/lag_s)
        self.value=np.zeros(7)
    def step(self,request):
        if np.shape(request)!=(7,) or not np.isfinite(request).all():
            raise ValueError('Expected finite right-arm torque vector')
        u=np.array(request,copy=True)
        if self.delay_steps:
            self.queue.append(u);u=self.queue.popleft()
        self.value=u.copy() if self.alpha==1. else self.value+self.alpha*(u-self.value)
        return self.value.copy()

def simulate(job):
    import mujoco
    kp,kd,scenario,folder,identifier=job
    name,friction,delay,lag,dt=scenario
    if not math.isfinite(friction) or not 0<=friction<=2:
        raise ValueError("Friction scale outside offline bounds")
    path=TorquePath(dt,delay,lag)
    original_load=engine.load_model
    original_step=mujoco.mj_step
    info={}
    def load_model(xml,timestep):
        model,qa,va,motors,assets=original_load(xml,timestep)
        info['motors']=motors[22:].copy()
        info['source_frictionloss_nm']=model.dof_frictionloss[va[22:]].tolist()
        model.dof_frictionloss[va[22:]]*=friction
        info['modified_frictionloss_nm']=model.dof_frictionloss[va[22:]].tolist()
        return model,qa,va,motors,assets
    def actuator_step(model,data):
        motors=info['motors']
        data.ctrl[motors]=path.step(data.ctrl[motors])
        original_step(model,data)
    engine.load_model=load_model
    mujoco.mj_step=actuator_step
    try:
        r=expanded.simulate((kp,kd,(name,dt,1.,1.,0.),folder,identifier,'motor'))
    finally:
        engine.load_model=original_load
        mujoco.mj_step=original_step
    r['actuator_scenario']={'friction_scale':friction,'torque_delay_s':delay,'torque_lag_s':lag,'timestep_s':dt}
    r['frictionloss_source_nm']=info['source_frictionloss_nm']
    r['frictionloss_modified_nm']=info['modified_frictionloss_nm']
    r['motor_model_limitation']='hypothetical torque-path delay/lag, not measured hardware or UDP semantics'
    expanded.save_json(Path(folder)/'cases'/(identifier+'.json'),r)
    return r

def summarize(results):
    required={s[0] for s in SCENARIOS}; ranks=[]
    for pair in PAIRS:
        cases={r['scenario'][0]:r for r in results if expanded.key(r)==pair}
        complete=required<=set(cases)
        good=complete and all(cases[s]['eligible'] for s in required)
        errs=[r['metrics']['reference_rmse_joint22_rad'] for r in cases.values() if r['metrics']]
        ranks.append({'pair':pair,'all_present':complete,'all_eligible':good,
          'eligible_count':sum(r['eligible'] for r in cases.values()),'required':len(required),
          'worst_rmse':max(errs) if errs else None,
          'failures':[{'scenario':s,'reason':r['reason'],'exclusions':r['exclusion_reasons']} for s,r in cases.items() if not r['eligible']]})
    return sorted(ranks,key=lambda r:(not r['all_eligible'],-r['eligible_count'],r['worst_rmse'] or math.inf,r['pair']))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8:parser.error('workers must be 1..8')
    folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    import mujoco
    _,_,_,_,assets=engine.load_model(engine.MODEL,.001)
    sources=engine.source_hashes([Path(__file__),Path(__file__).with_name("joint_limit_guard.py"),Path(expanded.__file__),Path(engine.__file__),
       Path(__file__).with_name('mujoco_pd_contract.py'),Path(__file__).with_name('mujoco_pd_fixture.py'),
       Path(__file__).with_name('pd_small_signal_trial.hpp'),engine.REFERENCE])
    expanded.save_json(folder/'manifest.json',{'schema':'g1.pd.motor-stress.v1','simulation_only':True,
      'source_sha256':sources,'asset_sha256':assets,'mujoco':mujoco.__version__,'numpy':np.__version__,
      'pairs':PAIRS,'scenarios':SCENARIOS,'workers':args.workers,'recommended_hardware_gains':None,
      'hardware_config_modified':False,'limitation':'hypothetical torque-path uncertainty, not real motor identification'})
    jobs=[(p,d,s,str(folder),f'motor_{i:04d}') for i,((p,d),s) in enumerate(expanded.itertools.product(PAIRS,SCENARIOS))]
    expanded.save_json(folder/'plan.json',jobs)
    results=[];start=time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        futures=[pool.submit(simulate,j) for j in jobs]
        for future in as_completed(futures):
            r=future.result();results.append(r)
            print(engine.json.dumps({'done':len(results),'pair':expanded.key(r),'scenario':r['scenario'][0],
                  'eligible':r['eligible'],'reason':r['reason']}),flush=True)
            expanded.save_json(folder/'progress.json',{'complete':False,'count':len(results)})
    summary={'schema':'g1.pd.motor-stress.summary.v1','complete':True,'simulation_only':True,
       'count':len(results),'completed_count':sum(r['completed'] for r in results),
       'eligible_count':sum(r['eligible'] for r in results),'ranking':summarize(results),
       'manifest_sha256':engine.sha256(folder/'manifest.json'),'wall_seconds':time.monotonic()-start,
       'recommended_hardware_gains':None,'hardware_config_modified':False}
    expanded.save_json(folder/'summary.json',summary)
    expanded.save_json(folder/'progress.json',{'complete':True,'count':len(results)})
    print('MOTOR_STRESS_RESULT '+engine.json.dumps(summary),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
