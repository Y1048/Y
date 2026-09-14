"""Offline first-order closed-loop response/delay baseline, never hardware gains.

Explicitly uniform, shared-clock episodes only. Pure actuator delay and physical
friction/inertia cannot be separated from closed-loop/sensor effects here.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from sysid_capture import canonical, decode, digest, read_episode


def create_plan(path, train_ids, validation_ids, joints, delays, q_rmse, dq_rmse,
                threshold_basis, max_interval_s=.05):
    """Freeze BEFORE validation is read. Never opens episode files."""
    if not train_ids or not validation_ids or set(train_ids) & set(validation_ids):
        raise ValueError('split_overlap_or_empty')
    if len(set(train_ids + validation_ids)) != len(train_ids + validation_ids):
        raise ValueError('duplicate_ids')
    if not joints or any(type(j) is not int or j not in range(29) for j in joints):
        raise ValueError('joints')
    if not delays or any(type(d) is not int or d < 0 for d in delays): raise ValueError('delays')
    for x in (q_rmse, dq_rmse, max_interval_s):
        if type(x) not in (int, float) or not np.isfinite(x) or x <= 0: raise ValueError('threshold')
    if not threshold_basis: raise ValueError('threshold_basis_required')
    plan = dict(schema='g1.sysid.plan.v1', train=train_ids, validation=validation_ids,
                joints=joints, delay_samples=delays, q_rmse_rad=q_rmse,
                dq_rmse_rad_s=dq_rmse, threshold_basis=threshold_basis,
                max_interval_s=max_interval_s)
    with Path(path).open('xb') as f: f.write(canonical(plan))
    return plan


def load_set(paths, expected, plan):
    episodes = []
    for path in paths:
        rows = read_episode(path)
        t = np.array([r['state_receive_ns'] for r in rows], dtype=np.int64)
        w = np.array([r['write_begin_ns'] for r in rows], dtype=np.int64)
        dt_ns = np.diff(t)
        if len(rows) < max(plan['delay_samples']) + 30: raise ValueError('too_short')
        # This narrow baseline rejects timing ambiguity; never silently resamples.
        if np.any(dt_ns <= 0) or np.max(dt_ns)*1e-9 > plan['max_interval_s']:
            raise ValueError('state_gap_or_repeated_state')
        if np.max(abs(dt_ns-np.median(dt_ns))) > 1 or np.any(w != t):
            raise ValueError('requires_uniform_aligned_shared_clock')
        for field in ('kp', 'kd', 'command_dq', 'tau_ff'):
            if any(r[field] != rows[0][field] for r in rows): raise ValueError('changing_control_contract')
        q = np.array([r['measured_q'] for r in rows]); dq = np.array([r['measured_dq'] for r in rows])
        u = np.array([r['command_q'] for r in rows])
        # Normalize absolute clock/session labels to reject relabelled duplicates.
        signature = digest({'t': (t-t[0]).tolist(), 'q': q.tolist(), 'u': u.tolist(), 'dq': dq.tolist()})
        episodes.append(dict(id=rows[0]['episode'], session=rows[0]['session'],
                             kind=rows[0]['provenance']['kind'], signature=signature,
                             clock=rows[0]['clock'], q=q, dq=dq, u=u,
                             dt=float(np.median(dt_ns))*1e-9,
                             contract=[rows[0][k] for k in ('kp','kd','command_dq','tau_ff')]))
    if sorted(e['id'] for e in episodes) != sorted(expected): raise ValueError('unexpected_split')
    if len({e['signature'] for e in episodes}) != len(episodes): raise ValueError('duplicate_data')
    return episodes


def load_plan(path):
    plan=decode(Path(path).read_bytes())
    if plan.get('schema')!='g1.sysid.plan.v1': raise ValueError('plan_schema')
    train=plan['train']; val=plan['validation']
    if not train or not val or len(set(train+val))!=len(train+val):
        raise ValueError('split_overlap_or_empty')
    if not all(isinstance(x,str) and x for x in train+val): raise ValueError('episode_ids')
    if not plan['joints'] or len(set(plan['joints']))!=len(plan['joints']) or any(
        type(x) is not int or x not in range(29) for x in plan['joints']): raise ValueError('joints')
    if not plan['delay_samples'] or any(type(x) is not int or x<0 for x in plan['delay_samples']):
        raise ValueError('delays')
    for k in ('q_rmse_rad','dq_rmse_rad_s','max_interval_s'):
        if type(plan[k]) not in (int,float) or not np.isfinite(plan[k]) or plan[k]<=0:
            raise ValueError('threshold')
    if not isinstance(plan['threshold_basis'],str) or not plan['threshold_basis']:
        raise ValueError('threshold_basis')
    return plan


def fit(plan_path, paths):
    plan = load_plan(plan_path)
    episodes = load_set(paths, plan['train'], plan)
    dt = episodes[0]['dt']
    if any(e['dt'] != dt or e['contract'] != episodes[0]['contract'] for e in episodes):
        raise ValueError('mixed_training_contract')
    models = []
    start = max(plan['delay_samples'])
    for j in plan['joints']:
        if any(np.ptp(e['u'][:, j]) < 1e-6 for e in episodes): raise ValueError('insufficient_excitation')
        candidates = []
        for delay in plan['delay_samples']:
            x = np.vstack([np.column_stack((e['q'][start:-1,j],
                 e['u'][start-delay:len(e['u'])-1-delay,j], np.ones(len(e['q'])-1-start))) for e in episodes])
            y = np.concatenate([e['q'][start+1:,j] for e in episodes])
            beta, _, rank, _ = np.linalg.lstsq(x,y,rcond=None)
            if rank < 3 or np.linalg.cond(x) > 1e10: continue
            a,b,c = map(float,beta)
            if not 0 < a < 1 or b <= 0: continue
            candidates.append(dict(delay_samples=delay, coefficients=[a,b,c],
                                   training_one_step_rmse=float(np.sqrt(np.mean((x@beta-y)**2))),
                                   condition_number=float(np.linalg.cond(x))))
        if not candidates: raise ValueError('no_identifiable_stable_model')
        best=min(candidates,key=lambda c:c['training_one_step_rmse'])
        a,b,c=best['coefficients']
        models.append(dict(joint=j, **best, effective_delay_s=best['delay_samples']*dt,
                           effective_lag_s=-dt/np.log(a), steady_gain=b/(1-a),
                           steady_bias_rad=c/(1-a), delay_profile=candidates))
    return dict(schema='g1.sysid.model.v1', plan_hash=digest(plan), models=models,dt_s=dt,
                training_ids=[e['id'] for e in episodes],
                training_sessions=[e['session'] for e in episodes],
                training_signatures=[e['signature'] for e in episodes],
                training_kinds=[e['kind'] for e in episodes],contract=episodes[0]['contract'],
                recommended_hardware_gains=None, clock_offset_ns=0,
                clock_offset_basis='required shared aligned clock; not estimated',
                actuator_pure_delay_s=None, physical_damping=None, friction=None,
                effective_inertia=None, load_scale=None,
                limitations=['closed-loop phenomenological q response, not torque plant',
                             'delay includes observation and command effects',
                             'physical parameters need calibrated torque/excitation',
                             'delay profile is sensitivity, not confidence interval'])


def validate_model(plan_path, model, paths):
    plan=load_plan(plan_path)
    if digest(plan)!=model['plan_hash']: raise ValueError('plan_changed')
    episodes=load_set(paths,plan['validation'],plan)
    scores=[]
    for e in episodes:
        if e['signature'] in model['training_signatures'] or e['session'] in model['training_sessions']:
            raise ValueError('train_validation_leakage')
        if e['dt']!=model['dt_s'] or e['contract']!=model['contract']: raise ValueError('contract_changed')
        for m in model['models']:
            j=m['joint'];delay=m['delay_samples'];a,b,c=m['coefficients']
            pred=e['q'][:,j].copy()
            for k in range(delay,len(pred)-1): pred[k+1]=a*pred[k]+b*e['u'][k-delay,j]+c
            q_error=pred[delay+1:]-e['q'][delay+1:,j]
            # Interval-average velocity is compared with endpoint sensor dq;
            # approximation is explicit, not an independent velocity state model.
            dq_error=np.diff(pred[delay:])/e['dt']-e['dq'][delay+1:,j]
            qrmse=float(np.sqrt(np.mean(q_error**2)));drmse=float(np.sqrt(np.mean(dq_error**2)))
            scores.append(dict(episode=e['id'],kind=e['kind'],joint=j,q_rmse_rad=qrmse,
                               dq_rmse_rad_s=drmse,passed=bool(qrmse<=plan['q_rmse_rad'] and drmse<=plan['dq_rmse_rad_s'])))
    return dict(schema='g1.sysid.validation.v1',plan_hash=digest(plan),model_hash=digest(model),
                scores=scores,passed=all(s['passed'] for s in scores),hardware_validated=False,
                recommended_hardware_gains=None,
                note='No physical approval; thresholds must be justified by independent noise/repeatability.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['fit','validate'])
    parser.add_argument('--plan',required=True)
    parser.add_argument('--model')
    parser.add_argument('--output',required=True)
    parser.add_argument('episodes',nargs='+')
    a=parser.parse_args()
    result=fit(a.plan,a.episodes) if a.operation=='fit' else validate_model(
        a.plan,decode(Path(a.model).read_bytes()),a.episodes)
    with Path(a.output).open('xb') as f:f.write(canonical(result))


if __name__=='__main__': main()
