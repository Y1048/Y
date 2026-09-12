"""Recorded seven-axis target dynamics; OFFLINE ONLY.
Raw recorded goals, not recorded robot response, drive a fixed-pelvis model.
No protocol acceptance, network delivery, IK, full-body or hardware claim.
The existing PD/model/guard loop is retained; the input and endpoint mapping differ.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from dataclasses import asdict
import math
import numpy as np
import mujoco_pd_multiaxis as sync
core=sync.core;pj=sync.pj;engine=sync.engine
from mujoco_pd_operating_core import TorquePath,apply_model,WRITER_DT,REFERENCE_DT
from mujoco_pd_contract import RATES
from mujoco_pd_recording import Capture
POST_HOLD_S=5.
POLICY=dict(core.POLICY,all_seven_endpoint_error=True,common_rest_last_second=True,
            recorded_input_no_scaling=True,measured_upper_velocity_rad_s=1.5,
            synthetic_post_hold_s=POST_HOLD_S)


def writer_target(reference,previous,q,dq,kp,kd,contract,profile):
    """Existing writer equations with the recorded yesterday/today speed profile.
    This changes only the new replay. The live code and its old tests are untouched.
    The inherited1.5rad/s observed-speed guard remains stricter than live today.
    """
    if profile not in ('yesterday','today'):raise ValueError('Unknown recorded profile')
    arrays=(reference,previous,q,dq,kp,kd)
    if any(a.shape!=(29,) or not np.isfinite(a).all() for a in arrays) or np.any(kp<=0):
        raise ValueError('Finite29array and positiveKp required')
    rates=RATES.copy()
    if profile=='today':rates[22:26]=math.pi/2;rates[26:]=math.pi
    target=np.clip(reference,previous-rates*WRITER_DT,previous+rates*WRITER_DT)
    target=np.clip(target,contract.lower,contract.upper);before=target.copy();soft=.5*contract.torque
    target=np.clip(target,q+(-soft+kd*dq)/kp,q+(soft+kd*dq)/kp)
    limited=np.abs(target-before)>1e-7;target=np.clip(target,contract.lower,contract.upper)
    slew=np.abs(target-previous)>rates*WRITER_DT+1e-7
    return target,limited,slew


def simulate(capture,gains,scenario,clock="send"):
    """Integrate a fresh private model. No state projection, clipping-to-success or reset."""
    import mujoco
    capture.validate();gains.validate();scenario.validate();contract=engine.load_contract()
    if not np.allclose(capture.joints[0],contract.baseline[22:],atol=1e-6,rtol=0):
        raise ValueError("Recorded episode must start at the unchanged ready target")
    duration=float(capture.times(clock)[-1]);total=duration+POST_HOLD_S
    kp,kd=engine.candidate_gains(contract,*pj.BASE)
    kp[22:26]=gains.kp;kd[22:26]=gains.kd
    model,qa,va,motors,_=engine.load_model(engine.MODEL,scenario.dt)
    evidence=apply_model(model,qa,va,scenario)
    data=mujoco.MjData(model);data.qpos[qa]=contract.baseline;data.qvel[:]=0
    mujoco.mj_forward(model,data)
    monitor=engine.JointLimitMonitor(engine.JointLimitEnvelope.from_model(model,qa,contract))
    torque_path=TorquePath(scenario.dt,scenario.delay_s,scenario.lag_s)
    dt=float(model.opt.timestep);writer_stride=round(WRITER_DT/dt);ref_stride=round(REFERENCE_DT/dt)
    warmup_steps=round(engine.WARMUP/dt);total_steps=warmup_steps+math.ceil(total/dt)
    capacity=math.ceil(total_steps/writer_stride)
    arrays={k:np.empty((capacity,29),dtype=np.float64) for k in ('q','dq','ref','cmd','requested','actual_tau')}
    arrays.update({k:np.empty(capacity,dtype=np.float64) for k in ('time_s','trial_time_s')})
    arrays.update({k:np.empty(capacity,dtype=np.int64) for k in ('cycle','phase','direction','contacts','torque_limited','hard_clipped','slew_exceeded')})
    arrays['segment']=np.empty(capacity,dtype='U16')
    arrays['source_index']=np.empty(capacity,dtype=np.int64)
    reference=contract.baseline.copy();command=reference.copy();limited=np.zeros(29,dtype=bool);slew=limited.copy()
    source_index=0;count=0;completed=False;reason='';warmup_tail=[]
    physics={'steps':0,'contact_steps':0,'trial_contact_steps':0,'peak_upper_speed_rad_s':0.}
    try:
        lo,hi=contract.baseline.copy(),contract.baseline.copy()
        lo[22:]=np.min(capture.joints,axis=0);hi[22:]=np.max(capture.joints,axis=0)
        monitor.reference(lo,hi,stage='preflight')
        for step in range(total_steps):
            sim_time=step*dt;trial_time=(step-warmup_steps)*dt
            q,dq=data.qpos[qa].copy(),data.qvel[va].copy()
            monitor.state(q,dq,sim_time,'pre_step')
            if not np.isfinite(q).all() or not np.isfinite(dq).all():reason='nonfinite_state';break
            if np.any(q<contract.lower) or np.any(q>contract.upper):reason='joint_soft_limit';break
            if np.max(np.abs(dq[12:]))>1.5 or np.max(np.abs(dq[:12]))>12:reason='measured_velocity_limit';break
            if step==warmup_steps and (not warmup_tail or not all(warmup_tail)):
                reason='ready_pose_not_settled_in_final_warmup_second';break
            if step%ref_stride==0:
                source_index=capture.at(max(0.,trial_time),clock);reference=contract.baseline.copy()
                if trial_time>=0:reference[22:]=capture.joints[source_index]
            if np.max(np.abs(q[12:]-reference[12:]))>.25:reason='upper_reference_error_over_0.25_rad';break
            if step%writer_stride==0:
                monitor.reference(reference,reference,sim_time)
                old=command.copy();proposed,limited,slew=writer_target(reference,command,q,dq,kp,kd,contract,capture.profile)
                command=monitor.command(proposed,old,WRITER_DT,sim_time)
            requested=kp*(command-q)-kd*dq
            ctrl=np.clip(requested,model.actuator_ctrlrange[motors,0],model.actuator_ctrlrange[motors,1])
            data.ctrl[motors]=ctrl
            data.ctrl[motors[22:]]=torque_path.step(data.ctrl[motors[22:]])
            mujoco.mj_step(model,data)
            physics['steps']+=1;physics['contact_steps']+=int(data.ncon>0)
            physics['trial_contact_steps']+=int(trial_time>=0 and data.ncon>0)
            physics['peak_upper_speed_rad_s']=max(physics['peak_upper_speed_rad_s'],float(np.max(np.abs(data.qvel[va[12:]]))))
            if np.any(data.warning.number) or not math.isclose(data.time,sim_time+dt,abs_tol=1e-7):reason='mujoco_warning_or_state_reset';break
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():reason='nonfinite_integrated_state';break
            monitor.state(data.qpos[qa],data.qvel[va],float(data.time),'post_step')
            if np.max(np.abs(data.qvel[va[12:]]))>1.5 or np.max(np.abs(data.qvel[va[:12]]))>12:
                reason='post_step_measured_velocity_limit';break
            if np.any(data.efc_type[:data.nefc]==mujoco.mjtConstraint.mjCNSTR_LIMIT_JOINT):
                monitor.fail('joint_model_limit_constraint_active','post_step',float(data.time),data.qpos[qa],data.qvel[va])
            if engine.WARMUP-1<=sim_time<engine.WARMUP:
                warmup_tail.append(bool(np.max(np.abs(q[15:]-reference[15:]))<=.1 and np.max(np.abs(dq[15:]))<=.1))
            if step%writer_stride==0:
                for key,value in (('q',q),('dq',dq),('ref',reference),('cmd',command),('requested',requested),('actual_tau',data.actuator_force[motors])):arrays[key][count]=value
                for key,value in (('time_s',sim_time),('trial_time_s',trial_time),('cycle',0),
                  ('phase',0 if trial_time<0 else (6 if trial_time>=duration else 2)),('direction',0),('contacts',data.ncon),
                  ('torque_limited',int(np.any(limited[22:]))),('hard_clipped',int(np.any(np.abs(requested[22:]-ctrl[22:])>1e-7))),
                  ('slew_exceeded',int(np.any(slew[22:]))),('segment','warmup' if trial_time<0 else ('post_hold' if trial_time>=duration else 'recorded'))):arrays[key][count]=value
                arrays['source_index'][count]=source_index if trial_time>=0 else -1
                count+=1
        else:completed=True
    except engine.LimitViolation as error:
        reason=error.event['reason'];completed=False
    arrays={k:v[:count].copy() for k,v in arrays.items()}
    result={'completed':completed,'reason':reason,'recording':capture.metadata(),'clock':clock,'scenario':asdict(scenario),
      'common_rest_start_s':duration,'synthetic_post_hold_s':POST_HOLD_S,'candidate':asdict(gains),'gains_kp':kp.tolist(),'gains_kd':kd.tolist(),'initial_q':contract.baseline.tolist(),
      'expected_samples':capacity,'actual_samples':count,'expected_final_time_s':total_steps*dt,
      'final_time_s':float(data.time),'final_q':data.qpos[qa].tolist(),'final_dq':data.qvel[va].tolist(),
      'joint_limit_guard':monitor.summary(),'physics':physics,'model_evidence':evidence,
      'simulation_only':True,'hardware_config_modified':False,'quality_policy':dict(POLICY)}
    result.update(evaluate(arrays,capture,clock,completed,reason,physics))
    result.update(hardware_approved=False,recommended_hardware_gains=None,
        legacy_hardware_gain_compatible=all(x<=100 for x in gains.kp))
    return result,arrays

def evaluate(a,capture,clock,completed,reason,physics):
    """Score original seven goals; do not interpret moving recorded targets as rest.
    Whole last1s after the explicitly appended5s hold checks all seven errors/speeds;
    last100ms checks the same seven-axis residual p2p/RMS bounds as earlier work.
    Report moving-only RMSE separately so the appended hold cannot dilute it.
    """
    capture.validate();duration=float(capture.times(clock)[-1]);n=len(a['time_s']);fail=[]
    for key in ('q','dq','ref','cmd','requested','actual_tau'):
        if a[key].shape!=(n,29) or not np.isfinite(a[key]).all():raise ValueError('Invalid full29:'+key)
    if any(len(v)!=n for v in a.values()):raise ValueError('Trace length mismatch')
    if not np.isfinite(a['time_s']).all() or not np.isfinite(a['trial_time_s']).all():raise ValueError('Nonfinite clock')
    if not np.allclose(np.diff(a['time_s']),WRITER_DT,rtol=0,atol=1e-10):raise ValueError('Writer clock gap')
    if not np.allclose(a['trial_time_s'],a['time_s']-engine.WARMUP,rtol=0,atol=1e-10):raise ValueError('Warmup clock')
    if not completed:fail.append(reason or 'incomplete')
    mask=(a['trial_time_s']>=0)&(a['trial_time_s']<duration)
    if not mask.any():return dict(eligible=False,exclusions=sorted(set(fail or ['no_recorded_samples'])),metrics=None)
    if physics['contact_steps']:fail.append('contact_including_warmup')
    err=a['ref'][mask,22:]-a['q'][mask,22:]
    metric=dict(right7_recorded_rmse_rad=np.sqrt(np.mean(err**2,axis=0)).tolist(),
        right7_recorded_peak_error_rad=np.max(np.abs(err),axis=0).tolist(),
        right7_peak_torque_nm=np.max(np.abs(a['actual_tau'][:,22:]),axis=0).tolist(),
        right7_peak_speed_rad_s=np.max(np.abs(a['dq'][:,22:]),axis=0).tolist(),
        torque_limited_ratio=float(np.mean(a['torque_limited'][mask])),
        hard_clipped_ratio=float(np.mean(a['hard_clipped'][mask])),
        recorded_samples=int(mask.sum()),final_hold=None)
    metric['max_right7_recorded_rmse_rad']=max(metric['right7_recorded_rmse_rad'])
    metric['max_proximal_recorded_rmse_rad']=max(metric['right7_recorded_rmse_rad'][:4])
    if max(metric['torque_limited_ratio'],metric['hard_clipped_ratio'])>POLICY['max_torque_limit_ratio']:
        fail.append('excessive_torque_limiting')
    # Never use the last1s of an early-aborted replay as a successful final hold.
    ids=np.flatnonzero((a['trial_time_s']>=duration+POST_HOLD_S-1)&(a['segment']=='post_hold'))
    if len(ids)<500 or not completed:fail.append('final_hold_incomplete')
    else:
        last=ids[-500:];tail=ids[-50:]
        final=dict(error_rad=float(np.max(np.abs(a['q'][last,22:]-a['ref'][last,22:]))),
            speed_rad_s=float(np.max(np.abs(a['dq'][last,22:]))),
            p2p_rad=float(np.max(np.ptp(a['q'][tail,22:],axis=0))),
            rms_speed_rad_s=float(np.max(np.sqrt(np.mean(a['dq'][tail,22:]**2,axis=0)))))
        metric['final_hold']=final
        for key,bound in (('error_rad',.02),('speed_rad_s',.1),('p2p_rad',.005),('rms_speed_rad_s',.05)):
            if final[key]>bound:fail.append('final_right7:'+key)
    return dict(eligible=not fail,exclusions=sorted(set(fail)),metrics=metric)
