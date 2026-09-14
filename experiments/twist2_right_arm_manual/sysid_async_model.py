"""Timestamp-aware closed-loop first-order baseline; file-only, no hardware gains.

Exact zero-order-hold integration over observed command events, not resampling.
Host timestamps define effective delay; device delay remains unidentifiable.
"""
from pathlib import Path
import numpy as np
from sysid_capture import canonical, decode, digest, read_episode
from sysid_model import load_plan


def freeze(path, plan, delays_s, lags_s):
    for grid, positive in ((delays_s,False),(lags_s,True)):
        if not grid or any(type(x) not in (int,float) or not np.isfinite(x) or
                           x < 0 or (positive and x==0) for x in grid):
            raise ValueError('invalid_time_grid')
    p=dict(plan,async_delays_s=delays_s,async_lags_s=lags_s)
    with Path(path).open('xb') as f:f.write(canonical(p))


def episodes(paths,expected,p):
    out=[]
    for path in paths:
        rows=read_episode(path);first=rows[0]
        base=first['write_begin_ns']
        w=np.array([(r['write_begin_ns']-base)*1e-9 for r in rows])
        selected=[]
        for i,r in enumerate(rows):
            if not selected or r['state_receive_ns']!=rows[selected[-1]]['state_receive_ns']:selected.append(i)
        t=np.array([(rows[i]['state_receive_ns']-base)*1e-9 for i in selected])
        if len(t)<30 or np.any(np.diff(t)>p['max_interval_s']) or np.any(np.diff(w)>p['max_interval_s']):
            raise ValueError('insufficient_samples_or_time_gap')
        u=np.array([r['command_q'] for r in rows]);q=np.array([rows[i]['measured_q'] for i in selected]);dq=np.array([rows[i]['measured_dq'] for i in selected])
        contract=[first[k] for k in ('kp','kd','tau_ff','command_dq')]
        if any([r[k] for k in ('kp','kd','tau_ff','command_dq')]!=contract for r in rows):raise ValueError('changing_gains')
        signature=digest({'w':w.tolist(),'t':t.tolist(),'q':q.tolist(),'dq':dq.tolist(),'u':u.tolist()})
        out.append(dict(id=first['episode'],session=first['session'],kind=first['provenance']['kind'],
                        w=w,t=t,u=u,q=q,dq=dq,signature=signature,contract=contract))
    if sorted(e['id'] for e in out)!=sorted(expected) or len({e['signature'] for e in out})!=len(out):raise ValueError('split_or_duplicate')
    return out


def basis(e,j,delay,lag,start):
    """One initial measured q; thereafter only commands drive prediction."""
    times=e['t'][start:];events=e['w']+delay;cursor=times[0]
    index=int(np.searchsorted(events,cursor,side='right'))-1
    if index<0:raise ValueError('missing_prehistory')
    z=0.;decay=1.;zs=[z];phis=[decay]
    for t in times[1:]:
        while cursor<t:
            boundary=min(t,events[index+1]) if index+1<len(events) else t
            a=np.exp(-(boundary-cursor)/lag)
            z=a*z+(1-a)*e['u'][index,j];decay*=a;cursor=boundary
            if index+1<len(events) and events[index+1]<=cursor:index+=1
        zs.append(z);phis.append(decay)
    phi=np.array(phis);x=np.column_stack((zs,1-phi))
    initial=phi*e['q'][start,j]
    return x,initial,start


def _plan(path):
    p=load_plan(path)
    for name in ('async_delays_s','async_lags_s'):
        xs=p[name]
        if not xs or any(type(x) not in (int,float) or not np.isfinite(x) or x<0 or
                        (name=='async_lags_s' and x==0) for x in xs):raise ValueError('time_grid')
    return p


def fit(path,files):
    p=_plan(path);es=episodes(files,p['train'],p);models=[]
    if any(e['contract']!=es[0]['contract'] for e in es):raise ValueError('contract')
    for j in p['joints']:
        candidates=[]
        if any(np.ptp(e['u'][:,j])<1e-6 for e in es):raise ValueError('insufficient_excitation')
        for delay in p['async_delays_s']:
            for lag in p['async_lags_s']:
                xs=[];ys=[]
                for e in es:
                    start=int(np.searchsorted(e['t'],max(p['async_delays_s']),side='left'))
                    if start>=len(e['t'])-20:raise ValueError('insufficient_common_support')
                    x,initial,_=basis(e,j,delay,lag,start);xs.append(x[1:]);ys.append(e['q'][start+1:,j]-initial[1:])
                x=np.vstack(xs);y=np.concatenate(ys);b,_,rank,_=np.linalg.lstsq(x,y,rcond=None)
                if rank<2 or np.linalg.cond(x)>1e10 or b[0]<=0:continue
                candidates.append(dict(delay_s=delay,lag_s=lag,gain=float(b[0]),bias_rad=float(b[1]),
                    training_q_rmse=float(np.sqrt(np.mean((x@b-y)**2)))))
        if not candidates:raise ValueError('unidentifiable')
        best=min(candidates,key=lambda x:x['training_q_rmse'])
        models.append(dict(joint=j,**best,grid_profile=candidates))
    return dict(schema='g1.sysid.async-model.v1',plan_hash=digest(p),models=models,
        train_signatures=[e['signature'] for e in es],train_sessions=[e['session'] for e in es],
        train_kinds=[e['kind'] for e in es],contract=es[0]['contract'],recommended_hardware_gains=None,
        physical_inertia=None,physical_friction=None,physical_damping=None,actuator_pure_delay=None,
        clock_offset_ns=0,clock_basis='declared same host clock; not independently estimated',
        limitation='effective closed-loop host-time delay/lag; not a torque plant or hardware approval')


def validate(path,m,files):
    p=_plan(path)
    if digest(p)!=m['plan_hash']:raise ValueError('plan_changed')
    canonical(m)  # Reject nonfinite model parameters before calculating scores.
    if m.get('schema')!='g1.sysid.async-model.v1' or sorted(f['joint'] for f in m['models'])!=sorted(p['joints']):
        raise ValueError('model_joint_coverage')
    for f in m['models']:
        if f['delay_s'] not in p['async_delays_s'] or f['lag_s'] not in p['async_lags_s'] or f['gain']<=0:
            raise ValueError('model_parameters')
    scores=[]
    for e in episodes(files,p['validation'],p):
        if e['signature'] in m['train_signatures'] or e['session'] in m['train_sessions']:raise ValueError('leakage')
        if e['contract']!=m['contract']:raise ValueError('contract')
        for fit in m['models']:
            j=fit['joint'];start=int(np.searchsorted(e['t'],max(p['async_delays_s']),side='left'))
            if start>=len(e['t'])-20:raise ValueError('insufficient_common_support')
            x,initial,_=basis(e,j,fit['delay_s'],fit['lag_s'],start)
            pred=x@np.array([fit['gain'],fit['bias_rad']])+initial
            inds=np.searchsorted(e['w']+fit['delay_s'],e['t'][start:],side='right')-1
            pred_dq=(fit['gain']*e['u'][inds,j]+fit['bias_rad']-pred)/fit['lag_s']
            qe=float(np.sqrt(np.mean((pred[1:]-e['q'][start+1:,j])**2)))
            de=float(np.sqrt(np.mean((pred_dq[1:]-e['dq'][start+1:,j])**2)))
            scores.append(dict(episode=e['id'],kind=e['kind'],joint=j,q_rmse_rad=qe,dq_rmse_rad_s=de,
                               passed=bool(qe<=p['q_rmse_rad'] and de<=p['dq_rmse_rad_s'])))
    return dict(plan_hash=digest(p),model_hash=digest(m),scores=scores,passed=all(s['passed'] for s in scores),
                hardware_validated=False,recommended_hardware_gains=None)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['fit','validate'])
    parser.add_argument('--plan',required=True)
    parser.add_argument('--model')
    parser.add_argument('--output',required=True)
    parser.add_argument('episodes',nargs='+')
    args=parser.parse_args()
    if args.action=='validate' and not args.model:parser.error('--model required for validation')
    result=(fit(args.plan,args.episodes) if args.action=='fit' else
            validate(args.plan,decode(Path(args.model).read_bytes()),args.episodes))
    with Path(args.output).open('xb') as output:output.write(canonical(result))
