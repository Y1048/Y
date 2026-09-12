"""Independent-timing proximal PD trajectories. OFFLINE ONLY; no SDK or sockets.
The dynamics loop is copied from the unchanged simultaneous core. Only reference
timing/metadata and the corresponding per-axis rest-window evaluation differ.
Synthetic paths are NOT recorded VR. Research gains are NOT robot configuration.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from dataclasses import dataclass,asdict,replace
import math
import numpy as np
import mujoco_pd_multiaxis as sync
core=sync.core;pj=sync.pj;engine=sync.engine
from mujoco_pd_operating_core import Path,profile_contract,TorquePath,apply_model,WRITER_DT,REFERENCE_DT
from mujoco_pd_contract import Point
POLICY=dict(core.POLICY, independent_axis_hold_windows=True,
            common_rest_right7=True, common_rest_last_second=True,
            no_score_after_failure=True)

@dataclass(frozen=True)
class Motion:
    name:str='independent'
    delays_s:tuple=(0.,.3,.6,.9)
    amplitudes_deg:tuple=(8.,8.,8.,8.)
    speeds_deg_s:tuple=(20.,20.,20.,20.)
    scales:tuple=(1.,1.,1.,1.)
    cycles:tuple=(3,3,3,3)
    elbow_offset_deg:float=0.
    post_hold_s:float=5.
    def profile(self,joint=22):
        i=joint-22
        return core.Profile(self.name,joint,self.amplitudes_deg[i],self.speeds_deg_s[i],
                            60.,self.cycles[i],self.elbow_offset_deg,0.)
    def validate(self):
        for seq in (self.delays_s,self.amplitudes_deg,self.speeds_deg_s,self.scales,self.cycles):
            if len(seq)!=4:raise ValueError('Four axis settings required')
        if not all(math.isfinite(x) and 0<=x<=2 for x in self.delays_s):
            raise ValueError('Delays outside0..2s')
        if not all(math.isfinite(x) and abs(x)==1 for x in self.scales):
            raise ValueError('Four unit signed scales required')
        if not math.isfinite(self.post_hold_s) or not 2<=self.post_hold_s<=30:
            raise ValueError('Common hold must be2..30s')
        for j in range(22,26):self.profile(j).validate()
    def extrema(self,baseline):
        offset=np.zeros(29);offset[22:26]=np.deg2rad(self.amplitudes_deg)
        return baseline-offset,baseline+offset

class Timeline:
    def __init__(self,motion):
        motion.validate();self.motion=motion
        self.paths=tuple(Path(motion.profile(j)) for j in range(22,26))
        self.ends=tuple(d+p.motion_total for d,p in zip(motion.delays_s,self.paths))
        self.common_rest_start=max(self.ends)
        self.total=self.common_rest_start+motion.post_hold_s
    def at(self,elapsed):
        if not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid reference time')
        result=[]
        for i,p in enumerate(self.paths):
            t=elapsed-self.motion.delays_s[i]
            if t<0:point=Point(segment='waiting')
            else:
                point=p.at(t)
                if t>=p.motion_total:point=replace(point,segment='post_hold')
            result.append(point)
        return tuple(result)
    def reference(self,baseline,points):
        q=baseline.copy()
        for i,point in enumerate(points):q[22+i]+=self.motion.scales[i]*point.offset
        return q

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
    trajectory=Timeline(motion);monitor=engine.JointLimitMonitor(engine.JointLimitEnvelope.from_model(model,qa,contract))
    torque_path=TorquePath(scenario.dt,scenario.delay_s,scenario.lag_s)
    dt=float(model.opt.timestep);writer_stride=round(WRITER_DT/dt);ref_stride=round(REFERENCE_DT/dt)
    warmup_steps=round(engine.WARMUP/dt);total_steps=warmup_steps+math.ceil(trajectory.total/dt)
    capacity=math.ceil(total_steps/writer_stride)
    arrays={k:np.empty((capacity,29),dtype=np.float64) for k in ('q','dq','ref','cmd','requested','actual_tau')}
    arrays.update({k:np.empty(capacity,dtype=np.float64) for k in ('time_s','trial_time_s')})
    arrays.update({k:np.empty(capacity,dtype=np.int64) for k in ('cycle','phase','direction','contacts','torque_limited','hard_clipped','slew_exceeded')})
    arrays['segment']=np.empty(capacity,dtype='U16')
    arrays['axis_segment']=np.empty((capacity,4),dtype='U16')
    arrays['axis_cycle']=np.empty((capacity,4),dtype=np.int64)
    arrays['axis_phase']=np.empty((capacity,4),dtype=np.int64)
    reference=contract.baseline.copy();command=reference.copy();limited=np.zeros(29,dtype=bool);slew=limited.copy()
    points=trajectory.at(0);point=points[0];count=0;completed=False;reason='';warmup_tail=[]
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
                points=trajectory.at(max(0.,trial_time));point=points[0];reference=contract.baseline.copy()
                if trial_time>=0:reference=trajectory.reference(contract.baseline,points)
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
                arrays['axis_segment'][count]=[p.segment if trial_time>=0 else 'warmup' for p in points]
                arrays['axis_cycle'][count]=[p.cycle for p in points]
                arrays['axis_phase'][count]=[p.phase if trial_time>=0 else 0 for p in points]
                count+=1
        else:completed=True
    except engine.LimitViolation as error:
        reason=error.event['reason'];completed=False
    arrays={k:v[:count].copy() for k,v in arrays.items()}
    result={'completed':completed,'reason':reason,'profile':asdict(profile),'scenario':asdict(scenario),
      'motion':asdict(motion),'common_rest_start_s':trajectory.common_rest_start,'candidate':asdict(gains),'gains_kp':kp.tolist(),'gains_kd':kd.tolist(),'initial_q':contract.baseline.tolist(),
      'expected_samples':capacity,'actual_samples':count,'expected_final_time_s':total_steps*dt,
      'final_time_s':float(data.time),'final_q':data.qpos[qa].tolist(),'final_dq':data.qvel[va].tolist(),
      'joint_limit_guard':monitor.summary(),'physics':physics,'model_evidence':evidence,
      'simulation_only':True,'hardware_config_modified':False,'quality_policy':dict(POLICY)}
    result.update(evaluate(arrays,motion,completed,reason,physics))
    result.update(hardware_approved=False,recommended_hardware_gains=None,
        legacy_hardware_gain_compatible=all(x<=100 for x in gains.kp))
    return result,arrays

def evaluate(a,motion,completed,reason,physics):
    """Same numeric thresholds, matching each axis's own declared rest windows.
    A moving *other* axis is not residual motion. All right7 must be quiet during
    the shared final hold; stopped individual axes are checked at their own holds.
    """
    motion.validate();n=len(a['time_s']);fail=[]
    for name in ('q','dq','ref','cmd','requested','actual_tau'):
        if a[name].shape!=(n,29) or not np.isfinite(a[name]).all():raise ValueError('Invalid all29:'+name)
    for name in ('axis_cycle','axis_phase','axis_segment'):
        if a[name].shape!=(n,4):raise ValueError('Invalid axis metadata:'+name)
    if any(len(v)!=n for v in a.values()):raise ValueError('Trace length mismatch')
    if not np.isfinite(a['time_s']).all() or not np.isfinite(a['trial_time_s']).all():raise ValueError('Nonfinite time')
    if not np.allclose(np.diff(a['time_s']),WRITER_DT,rtol=0,atol=1e-10):raise ValueError('Writer clock gap')
    if not np.allclose(a['trial_time_s'],a['time_s']-engine.WARMUP,rtol=0,atol=1e-10):raise ValueError('Warmup clock')
    if not completed:fail.append(reason or 'incomplete')
    trial=a['trial_time_s']>=0
    if not trial.any():return dict(eligible=False,exclusions=sorted(set(fail or ['no_trial_samples'])),metrics=None,holds=[])
    if physics['contact_steps']:fail.append('contact_including_warmup')
    errors=a['ref'][trial]-a['q'][trial]
    metrics=dict(proximal_rmse_rad=np.sqrt(np.mean(errors[:,22:26]**2,axis=0)).tolist(),
      proximal_peak_error_rad=np.max(np.abs(errors[:,22:26]),axis=0).tolist(),
      right7_rmse_rad=np.sqrt(np.mean(errors[:,22:]**2,axis=0)).tolist(),
      proximal_peak_torque_nm=np.max(np.abs(a['actual_tau'][trial,22:26]),axis=0).tolist(),
      torque_limited_ratio=float(np.mean(a['torque_limited'][trial])),
      hard_clipped_ratio=float(np.mean(a['hard_clipped'][trial])))
    metrics['max_proximal_rmse_rad']=max(metrics['proximal_rmse_rad'])
    if max(metrics['torque_limited_ratio'],metrics['hard_clipped_ratio'])>POLICY['max_torque_limit_ratio']:
        fail.append('excessive_torque_limiting')
    holds=[]
    for i,j in enumerate(range(22,26)):
        for cycle in range(motion.cycles[i]):
            for segment in ('positive_hold','negative_hold','ready_hold'):
                ids=np.flatnonzero(trial & (a['axis_cycle'][:,i]==cycle) & (a['axis_segment'][:,i]==segment))
                if len(ids)<50:fail.append(f'joint{j}:incomplete_hold');continue
                ids=ids[-50:];q=a['q'][ids,j];dq=a['dq'][ids,j];ref=a['ref'][ids,j]
                h=dict(joint=j,cycle=cycle,segment=segment,samples=50,
                  error_rad=float(np.max(np.abs(q-ref))),speed_rad_s=float(np.max(np.abs(dq))),
                  p2p_rad=float(np.ptp(q)),rms_speed_rad_s=float(np.sqrt(np.mean(dq*dq))))
                for k,bound in (('error_rad',.02),('speed_rad_s',.1),('p2p_rad',.005),('rms_speed_rad_s',.05)):
                    if h[k]>bound:fail.append(f'joint{j}:{k}')
                holds.append(h)
    timeline=Timeline(motion)
    ids=np.flatnonzero(trial & (a['trial_time_s']>=timeline.common_rest_start) &
                        np.all(a['axis_segment']=='post_hold',axis=1))
    common=None
    if len(ids)<500:fail.append('common_final_second_missing')
    else:
        last=ids[-500:];tail=ids[-50:]
        common=dict(error_rad=float(np.max(np.abs(a['q'][last,22:26]-a['ref'][last,22:26]))),
          speed_rad_s=float(np.max(np.abs(a['dq'][last,22:26]))),
          right7_p2p_rad=float(np.max(np.ptp(a['q'][tail,22:],axis=0))),
          right7_rms_speed_rad_s=float(np.max(np.sqrt(np.mean(a['dq'][tail,22:]**2,axis=0)))))
        for k,bound in (('error_rad',.02),('speed_rad_s',.1),('right7_p2p_rad',.005),('right7_rms_speed_rad_s',.05)):
            if common[k]>bound:fail.append('common:'+k)
    metrics.update(max_axis_hold_error_rad=max((h['error_rad'] for h in holds),default=None),
      max_axis_hold_speed_rad_s=max((h['speed_rad_s'] for h in holds),default=None),
      common_rest=common,expected_axis_holds=sum(motion.cycles)*3,observed_axis_holds=len(holds))
    return dict(eligible=not fail,exclusions=sorted(set(fail)),metrics=metrics,holds=holds)
