"""Exploratory causal command shaping for recorded-target replay. OFFLINE ONLY.
Not a repair or reclassification of the failed unfiltered study. Original goals
remain in ref and in every score. This is a DIFFERENT command-generation pipeline,
not evidence that the unchanged live controller or these PD gains alone pass.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from dataclasses import asdict
import math
import numpy as np
import mujoco_pd_recorded_core as unfiltered
from mujoco_pd_recorded_core import engine,pj,core,POST_HOLD_S,writer_target,RATES
from mujoco_pd_operating_core import TorquePath,apply_model,WRITER_DT,REFERENCE_DT
COMMAND_FILTER=dict(kind='causal_previous_to_current_target',interval_s=REFERENCE_DT,
    input='original50Hzheld_recorded_goals',lookahead=False,applied_at='500Hzwriter',
    scope='adds up to one reference period of command delay; not deployed')
POLICY=dict(unfiltered.POLICY,command_prefilter=dict(COMMAND_FILTER),pd_only_validation=False)


def causal_reference(previous,current,age_s):
    if any(x.shape!=(29,) or not np.isfinite(x).all() for x in (previous,current)):
        raise ValueError('Finite29references required')
    if not math.isfinite(age_s) or not 0<=age_s<=REFERENCE_DT+1e-9:
        raise ValueError('Causal reference age outside one reference period')
    u=min(1.,age_s/REFERENCE_DT)
    return previous+u*(current-previous)


def evaluate(a,capture,clock,completed,reason,physics):
    if a['writer_reference'].shape!=a['ref'].shape or not np.isfinite(a['writer_reference']).all():
        raise ValueError('Invalid filtered reference trace')
    # Deliberately use original ref, NOT writer_reference, for the score.
    return unfiltered.evaluate(a,capture,clock,completed,reason,physics)


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
    arrays['writer_reference']=np.empty((capacity,29),dtype=np.float64)
    reference=contract.baseline.copy();command=reference.copy();limited=np.zeros(29,dtype=bool);slew=limited.copy()
    previous_reference=reference.copy();writer_reference=reference.copy();reference_received_s=0.
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
                previous_reference=reference.copy();reference_received_s=sim_time
                source_index=capture.at(max(0.,trial_time),clock);reference=contract.baseline.copy()
                if trial_time>=0:reference[22:]=capture.joints[source_index]
            if np.max(np.abs(q[12:]-reference[12:]))>.25:reason='upper_reference_error_over_0.25_rad';break
            if step%writer_stride==0:
                monitor.reference(reference,reference,sim_time)
                writer_reference=causal_reference(previous_reference,reference,sim_time-reference_received_s)
                monitor.reference(writer_reference,writer_reference,sim_time)
                old=command.copy();proposed,limited,slew=writer_target(writer_reference,command,q,dq,kp,kd,contract,capture.profile)
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
                arrays['writer_reference'][count]=writer_reference
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
      'simulation_only':True,'hardware_config_modified':False,'quality_policy':dict(POLICY),'command_filter':dict(COMMAND_FILTER),
      'requires_command_prefilter':True,'pd_only_optimum_proven':False}
    result.update(evaluate(arrays,capture,clock,completed,reason,physics))
    result.update(hardware_approved=False,recommended_hardware_gains=None,
        legacy_hardware_gain_compatible=all(x<=100 for x in gains.kp))
    return result,arrays
