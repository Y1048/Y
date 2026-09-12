"""Simultaneous proximal-axis PD dynamics, OFFLINE ONLY.

Derived from the frozen operating core without changing that core. Shared pure
PD, model mutations, limits, writer and torque-path semantics remain identical.
Only the reference becomes a signed, synchronized four-axis round trip. This
is not replay of actual VR input, full-body balance, or hardware approval.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from dataclasses import dataclass,asdict,replace
import math
import numpy as np
import mujoco_pd_operating_core as core
import mujoco_pd_perjoint as pj
from mujoco_pd_operating_core import Path,profile_contract,TorquePath,apply_model,WRITER_DT,REFERENCE_DT
engine=core.engine
POLICY=dict(core.POLICY)

@dataclass(frozen=True)
class Motion:
    name:str='simultaneous'
    scales:tuple=(1.,1.,1.,1.)
    amplitude_deg:float=8.
    speed_deg_s:float=20.
    acceleration_deg_s2:float=60.
    cycles:int=3
    elbow_offset_deg:float=0.
    post_hold_s:float=0.
    def profile(self,joint=22):
        return core.Profile(self.name,joint,self.amplitude_deg,self.speed_deg_s,
            self.acceleration_deg_s2,self.cycles,self.elbow_offset_deg,self.post_hold_s)
    def validate(self):
        self.profile().validate()
        if len(self.scales)!=4 or not all(math.isfinite(v) and -1<=v<=1 for v in self.scales):
            raise ValueError('Four signed scales within[-1,1] required')
        if not any(self.scales):raise ValueError('No excited axes')
    def extrema(self,baseline):
        offset=np.zeros(29);offset[22:26]=np.abs(self.scales)*math.radians(self.amplitude_deg)
        return baseline-offset,baseline+offset
    def reference(self,baseline,point):
        result=baseline.copy();result[22:26]+=np.asarray(self.scales)*point.offset
        return result

def simulate(motion,gains,scenario):
    """Integrate a fresh private model. No state projection, clipping-to-success or reset."""
    import mujoco
    motion.validate();gains.validate();profile=motion.profile();scenario.validate();contract=profile_contract(profile)
    kp,kd=engine.candidate_gains(contract,*pj.BASE)
    kp[22:26]=gains.kp;kd[22:26]=gains.kd
    model,qa,va,motors,_=engine.load_model(engine.MODEL,scenario.dt)
    evidence=apply_model(model,qa,va,scenario)
    data=mujoco.MjData(model);data.qpos[qa]=contract.baseline;data.qvel[:]=0
    mujoco.mj_forward(model,data)
    trajectory=Path(profile);monitor=engine.JointLimitMonitor(engine.JointLimitEnvelope.from_model(model,qa,contract))
    torque_path=TorquePath(scenario.dt,scenario.delay_s,scenario.lag_s)
    dt=float(model.opt.timestep);writer_stride=round(WRITER_DT/dt);ref_stride=round(REFERENCE_DT/dt)
    warmup_steps=round(engine.WARMUP/dt);total_steps=warmup_steps+math.ceil(trajectory.total/dt)
    capacity=math.ceil(total_steps/writer_stride)
    arrays={k:np.empty((capacity,29),dtype=np.float64) for k in ('q','dq','ref','cmd','requested','actual_tau')}
    arrays.update({k:np.empty(capacity,dtype=np.float64) for k in ('time_s','trial_time_s')})
    arrays.update({k:np.empty(capacity,dtype=np.int64) for k in ('cycle','phase','direction','contacts','torque_limited','hard_clipped','slew_exceeded')})
    arrays['segment']=np.empty(capacity,dtype='U16')
    reference=contract.baseline.copy();command=reference.copy();limited=np.zeros(29,dtype=bool);slew=limited.copy()
    point=trajectory.at(0);count=0;completed=False;reason='';warmup_tail=[]
    physics={'steps':0,'contact_steps':0,'trial_contact_steps':0,'peak_upper_speed_rad_s':0.}
    try:
        lo,hi=motion.extrema(contract.baseline)
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
                point=trajectory.at(max(0.,trial_time));reference=contract.baseline.copy()
                if trial_time>=0:reference=motion.reference(contract.baseline,point)
            if np.max(np.abs(q[12:]-reference[12:]))>.25:reason='upper_reference_error_over_0.25_rad';break
            if step%writer_stride==0:
                monitor.reference(reference,reference,sim_time)
                old=command.copy();proposed,limited,slew=engine.writer_target(reference,command,q,dq,kp,kd,contract)
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
                for key,value in (('time_s',sim_time),('trial_time_s',trial_time),('cycle',point.cycle),
                  ('phase',point.phase if trial_time>=0 else 0),('direction',point.direction),('contacts',data.ncon),
                  ('torque_limited',int(np.any(limited[22:]))),('hard_clipped',int(np.any(np.abs(requested[22:]-ctrl[22:])>1e-7))),
                  ('slew_exceeded',int(np.any(slew[22:]))),('segment',point.segment if trial_time>=0 else 'warmup')):arrays[key][count]=value
                count+=1
        else:completed=True
    except engine.LimitViolation as error:
        reason=error.event['reason'];completed=False
    arrays={k:v[:count].copy() for k,v in arrays.items()}
    result={'completed':completed,'reason':reason,'profile':asdict(profile),'scenario':asdict(scenario),
      'motion':asdict(motion),'candidate':asdict(gains),'gains_kp':kp.tolist(),'gains_kd':kd.tolist(),'initial_q':contract.baseline.tolist(),
      'expected_samples':capacity,'actual_samples':count,'expected_final_time_s':total_steps*dt,
      'final_time_s':float(data.time),'final_q':data.qpos[qa].tolist(),'final_dq':data.qvel[va].tolist(),
      'joint_limit_guard':monitor.summary(),'physics':physics,'model_evidence':evidence,
      'simulation_only':True,'hardware_config_modified':False,'quality_policy':dict(POLICY)}
    result.update(evaluate(arrays,motion,completed,reason,physics))
    result.update(hardware_approved=False,recommended_hardware_gains=None,
        legacy_hardware_gain_compatible=all(x<=100 for x in gains.kp))
    return result,arrays

def evaluate(arrays,motion,completed,reason,physics):
    """Require unchanged endpoint checks for ALL four axes, moving or stationary.

For opposite-direction axes, direction-specific scalar overshoot is not used.
The inherited absolute error/speed/p2p/RMS checks are applied per axis instead.
Every axis shares segment timing; q22 remains screened in every legacy call.
"""
    motion.validate()
    per_axis=[core.evaluate(arrays,motion.profile(j),completed,reason,physics) for j in range(22,26)]
    exclusions=sorted({f'joint{j}:{x}' for j,r in zip(range(22,26),per_axis) for x in r['exclusions']})
    metrics=None
    if all(r['metrics'] is not None for r in per_axis):
        m=[r['metrics'] for r in per_axis]
        metrics={'proximal_rmse_rad':[r['active_rmse_rad'] for r in m],
          'max_proximal_rmse_rad':max(r['active_rmse_rad'] for r in m),
          'proximal_peak_error_rad':[r['active_peak_error_rad'] for r in m],
          'proximal_peak_torque_nm':[r['active_peak_torque_nm'] for r in m],
          'right7_rmse_rad':m[0]['right7_rmse_rad'],
          'max_proximal_tail_error_rad':max(r['max_active_tail_error_rad'] for r in m if r['max_active_tail_error_rad'] is not None) if any(r['max_active_tail_error_rad'] is not None for r in m) else None,
          'max_proximal_tail_speed_rad_s':max(r['max_active_tail_speed_rad_s'] for r in m if r['max_active_tail_speed_rad_s'] is not None) if any(r['max_active_tail_speed_rad_s'] is not None for r in m) else None,
          'max_right7_tail_p2p_rad':m[0]['max_right7_tail_p2p_rad'],
          'max_right7_tail_rms_speed_rad_s':m[0]['max_right7_tail_rms_speed_rad_s'],
          'torque_limited_ratio':m[0]['torque_limited_ratio'],
          'hard_clipped_ratio':m[0]['hard_clipped_ratio']}
    return {'eligible':all(r['eligible'] for r in per_axis),'exclusions':exclusions,
            'metrics':metrics,'axis_evaluations':per_axis}
