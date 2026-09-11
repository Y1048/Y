"""Replay the fixed, recorded 718-case plan with all-29-joint limit screening.

This does NOT reuse the old success flags as new validation. Every selected
case is simulated again. No model limit change, robot connection or DDS.
"""
from __future__ import annotations
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import csv
import json
import math
from pathlib import Path
import platform
import numpy as np
import mujoco_pd_expand as expanded
import mujoco_pd_motor_stress as motor
import mujoco_pd_sweep as engine
from joint_limit_guard import RESERVE_RAD,EPS

PLAN=engine.ROOT/'docs/validation/g1_pd_expanded_20260911/all_cases.csv'


def load_plan(path=PLAN):
    with Path(path).open(newline='',encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    identities={(r['dataset'],r['case_id']) for r in rows}
    if len(rows)!=718 or len(identities)!=718:raise ValueError('Expected the complete unique historical 718-case plan')
    for r in rows:
        p,d=float(r['kp']),float(r['kd'])
        engine.candidate_gains(engine.load_contract(),p,d)
        pars=json.loads(r['scenario_parameters'])
        if r['dataset']=='motor_results':
            r['replay_scenario']=[r['scenario'],pars['friction_scale'],pars['torque_delay_s'],pars['torque_lag_s'],pars['timestep_s']]
        elif r['dataset']=='results_v2':r['replay_scenario']=pars
        else:raise ValueError('Unknown historical dataset')
    return rows


def run_case(job):
    record,folder,number=job
    p,d=float(record['kp']),float(record['kd']);scenario=record['replay_scenario'];identifier=f'case_{number:04d}'
    if record['dataset']=='motor_results':r=motor.simulate((p,d,scenario,folder,identifier))
    else:r=expanded.simulate((p,d,scenario,folder,identifier,'limits'))
    r.update({'historical_dataset':record['dataset'],'historical_case_id':record['case_id'],
      'historical_eligible':record['eligible']=='True','historical_reason':record['reason']})
    expanded.save_json(Path(folder)/'cases'/(identifier+'.json'),r)
    return r


def verify_guard_result(r):
    g=r['joint_limit_guard'];e=g['envelope']
    if e['joints']!=29 or e['reserve_rad']<RESERVE_RAD or g['hardware_validated']:
        raise ValueError('Bad guard contract or hardware claim')
    for key in ('minimum_soft_margin_rad','minimum_hard_margin_rad','minimum_stopping_slack_rad','minimum_soft_witness'):
        if len(g[key])!=29:raise ValueError('All 29 joints must be recorded')
    for j,w in enumerate(g['minimum_soft_witness']):
        if w is None:continue
        expected=min(w['q']-e['soft_lower'][j],e['soft_upper'][j]-w['q'])
        if not math.isclose(expected,g['minimum_soft_margin_rad'][j],abs_tol=1e-12):
            raise ValueError('Minimum-clearance witness mismatch')
    if r['eligible']:
        if not r['completed'] or g['event'] is not None or not g['no_intervention']:
            raise ValueError('Intervened/incomplete candidate cannot be eligible')
        for key,threshold in (('minimum_soft_margin_rad',e['reserve_rad']),('minimum_hard_margin_rad',0),('minimum_stopping_slack_rad',0)):
            if any(x is None or not math.isfinite(x) or x<=threshold+EPS for x in g[key]):
                raise ValueError('Eligible candidate lacks strict measured margin')
        dt=r['scenario'][1]
        steps=round(engine.WARMUP/dt)+math.ceil(engine.RoundTrip().total/dt)
        if g['observations']!=2*steps:raise ValueError('Pre/post/final-step coverage missing')
    return True


def summarize(folder,results):
    from collections import Counter
    for r in results:verify_guard_result(r)
    accepted=[r for r in results if r['eligible']]
    events=[r['joint_limit_guard']['event'] for r in results if r['joint_limit_guard']['event'] is not None]
    return {'schema':'g1.pd.limit-screen.v1','simulation_only':True,'total':len(results),
      'completed':sum(r['completed'] for r in results),'eligible':len(accepted),
      'rejected':len(results)-len(accepted),'rejection_reasons':dict(Counter(r['reason'] for r in results if not r['eligible'])),
      'guard_events':dict(Counter(e['reason'] for e in events)),
      'previously_eligible_now_rejected':sum(r['historical_eligible'] and not r['eligible'] for r in results),
      'accepted_minimum_soft_margin_rad':min((min(r['joint_limit_guard']['minimum_soft_margin_rad']) for r in accepted),default=None),
      'accepted_minimum_hard_margin_rad':min((min(r['joint_limit_guard']['minimum_hard_margin_rad']) for r in accepted),default=None),
      'accepted_minimum_stopping_slack_rad':min((min(r['joint_limit_guard']['minimum_stopping_slack_rad']) for r in accepted),default=None),
      'case_json_sha256':{r['case_id']:engine.sha256(Path(folder)/'cases'/(r['case_id']+'.json')) for r in results},
      'scope':'29 joints at all actual physics pre/post states; witnesses and minima, not stored full-state trajectories',
      'recommended_hardware_gains':None,'hardware_config_modified':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--cases',type=int,default=718,help='Explicit prefix subset for smoke checks, default all718')
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8 or not 1<=args.cases<=718:parser.error('workers1..8 and cases1..718 required')
    rows=load_plan()[:args.cases];folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    import mujoco
    model,qa,_,_,assets=engine.load_model(engine.MODEL,.001)
    dependencies=['mujoco_pd_limit_replay.py','joint_limit_guard.py','mujoco_pd_sweep.py','mujoco_pd_expand.py',
        'mujoco_pd_motor_stress.py','mujoco_pd_contract.py','mujoco_pd_fixture.py','pd_small_signal_trial.hpp']
    sources=engine.source_hashes([Path(__file__).with_name(n) for n in dependencies]+[engine.REFERENCE,PLAN])
    manifest={'schema':'g1.pd.limit-replay.run.v1','simulation_only':True,'plan_count':len(rows),
      'mujoco':mujoco.__version__,'numpy':np.__version__,'python':platform.python_version(),
      'platform':platform.platform(),'source_sha256':sources,'asset_sha256':assets,
      'joint_limit_envelope':engine.JointLimitEnvelope.from_model(model,qa,engine.load_contract()).manifest(),
      'hardware_config_modified':False,'physical_braking_validated':False}
    expanded.save_json(folder/'manifest.json',manifest)
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers,initializer=expanded.init_worker) as pool:
        futures=[pool.submit(run_case,(r,str(folder),i)) for i,r in enumerate(rows)]
        for f in as_completed(futures):
            r=f.result();results.append(r);verify_guard_result(r)
            expanded.save_json(folder/'progress.json',{'complete':False,'count':len(results),'total':len(rows)})
            if len(results)%20==0:print('LIMIT_REPLAY',len(results),'/',len(rows),flush=True)
    results.sort(key=lambda r:r['case_id']);summary=summarize(folder,results)
    summary.update(complete=len(results)==len(rows),full_plan=len(rows)==718,manifest_sha256=engine.sha256(folder/'manifest.json'))
    expanded.save_json(folder/'summary.json',summary)
    expanded.save_json(folder/'progress.json',{'complete':True,'count':len(results),'total':len(rows)})
    print('LIMIT_RESULT '+json.dumps({k:v for k,v in summary.items() if k!='case_json_sha256'}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
