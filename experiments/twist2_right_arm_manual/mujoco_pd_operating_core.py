"""Offline operating-envelope PD dynamics. Never imports SDK or opens robot I/O.

Derived from the guarded engine at4b9dde3. Original engine/live paths stay intact.
Default profile must match every inherited q/dq/ref/cmd sample exactly. Extensions
are declared excitation axes, amplitudes, speeds, starts and repetition/soak time.
"""
from __future__ import annotations
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from dataclasses import dataclass,asdict,replace
import math
import numpy as np
import mujoco_pd_sweep as engine
from mujoco_pd_contract import Point,RoundTrip,WRITER_DT,REFERENCE_DT
from mujoco_pd_motor_stress import TorquePath
from mujoco_pd_coupled_stress import Coupled,apply_model

POLICY={'tail_window_s':.1,'active_tail_error_rad':.02,'active_tail_speed_rad_s':.1,
        'right7_tail_p2p_rad':.005,'right7_tail_rms_speed_rad_s':.05,
        'max_torque_limit_ratio':.05,'no_contact':True,'unchanged_joint_guard':True}

@dataclass(frozen=True)
class Profile:
    name:str='standard'
    joint:int=22
    amplitude_deg:float=8.
    speed_deg_s:float=20.
    acceleration_deg_s2:float=60.
    cycles:int=3
    elbow_offset_deg:float=0.
    post_hold_s:float=0.
    def validate(self):
        if not self.name or not all(c.isalnum() or c=='_' for c in self.name):raise ValueError('Invalid profile name')
        if self.joint not in range(22,26):raise ValueError('Only the four declared proximal axes')
        values=(self.amplitude_deg,self.speed_deg_s,self.acceleration_deg_s2,self.elbow_offset_deg,self.post_hold_s)
        if not all(math.isfinite(x) for x in values):raise ValueError('Nonfinite profile')
        if not 0<self.amplitude_deg<=12 or not 0<self.speed_deg_s<=30 or not 0<self.acceleration_deg_s2<=60:raise ValueError('Declared excitation bounds exceeded')
        if type(self.cycles) is not int or not 3<=self.cycles<=12:raise ValueError('Cycles must be3..12')
        if not -10<=self.elbow_offset_deg<=10 or not 0<=self.post_hold_s<=30:raise ValueError('Pose/soak outside study bounds')

class Path:
    def __init__(self,profile):
        profile.validate();self.profile=profile
        self.offset=math.radians(profile.amplitude_deg)
        self.speed=math.radians(profile.speed_deg_s)
        self.acceleration=math.radians(profile.acceleration_deg_s2)
        duration=lambda x:max(1.875*x/self.speed,math.sqrt((10/math.sqrt(3))*x/self.acceleration))
        self.outbound=duration(self.offset);self.cross=duration(2*self.offset)
        self.period=2*self.outbound+self.cross+1.5
        self.motion_total=1+profile.cycles*self.period
        self.total=self.motion_total+profile.post_hold_s
    def at(self,elapsed):
        if not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid reference time')
        if elapsed<1:return Point()
        if elapsed>=self.motion_total:
            return Point(phase=6,cycle=self.profile.cycles,segment='post_hold' if elapsed<self.total else 'done')
        active=elapsed-1;cycle=int(active/self.period);t=active-cycle*self.period
        segments=((self.outbound,0.,self.offset,2,'out',1),(.5,self.offset,self.offset,3,'positive_hold',1),
          (self.cross,self.offset,-self.offset,4,'cross',-1),(.5,-self.offset,-self.offset,3,'negative_hold',-1),
          (self.outbound,-self.offset,0.,4,'return',1),(.5,0.,0.,5,'ready_hold',1))
        for duration,start,end,phase,segment,direction in segments:
            if t<duration:
                u=max(0.,min(1.,t/duration));delta=end-start
                return Point(start+delta*u**3*(10+u*(-15+6*u)),delta/duration*30*u*u*(1-u)**2,
                  delta/duration**2*60*u*(1-u)*(1-2*u),phase,cycle,segment,direction)
            t-=duration
        return Point(phase=5,cycle=cycle,segment='ready_hold',direction=1)

def profile_contract(profile):
    contract=engine.load_contract();q=contract.baseline.copy();q[25]+=math.radians(profile.elbow_offset_deg)
    return replace(contract,baseline=q)

def simulate(profile,p,d,scenario):
    """Integrate a fresh private model. No state projection, clipping-to-success or reset."""
    import mujoco
    profile.validate();scenario.validate();contract=profile_contract(profile)
    kp,kd=engine.candidate_gains(contract,p,d)
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
        lo,hi=contract.baseline.copy(),contract.baseline.copy();lo[profile.joint]-=trajectory.offset;hi[profile.joint]+=trajectory.offset
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
                if trial_time>=0:reference[profile.joint]+=point.offset
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
      'kp':p,'kd':d,'gains_kp':kp.tolist(),'gains_kd':kd.tolist(),'initial_q':contract.baseline.tolist(),
      'expected_samples':capacity,'actual_samples':count,'expected_final_time_s':total_steps*dt,
      'final_time_s':float(data.time),'final_q':data.qpos[qa].tolist(),'final_dq':data.qvel[va].tolist(),
      'joint_limit_guard':monitor.summary(),'physics':physics,'model_evidence':evidence,
      'simulation_only':True,'hardware_config_modified':False,'quality_policy':dict(POLICY)}
    result.update(evaluate(arrays,profile,completed,reason,physics))
    return result,arrays

def evaluate(a,profile,completed,reason,physics):
    """Generalized endpoint screening, same tolerances as prior study, for each active axis."""
    profile.validate();n=len(a['time_s']);reasons=[]
    for name in ('q','dq','ref','cmd','requested','actual_tau'):
        if a[name].shape!=(n,29) or not np.isfinite(a[name]).all():raise ValueError('Invalid full29 trace: '+name)
    if any(len(v)!=n for v in a.values()):raise ValueError('Trace length mismatch')
    if not np.isfinite(a['time_s']).all() or not np.isfinite(a['trial_time_s']).all() or not np.allclose(np.diff(a['time_s']),WRITER_DT,rtol=0,atol=1e-10):raise ValueError('Invalid writer clock')
    if not np.allclose(a['trial_time_s'],a['time_s']-engine.WARMUP,rtol=0,atol=1e-10):raise ValueError('Warmup clock mismatch')
    mask=a['trial_time_s']>=0;j=profile.joint
    if not completed:reasons.append(reason or 'incomplete')
    if not mask.any():return {'eligible':False,'exclusions':reasons or ['no_trial_samples'],'metrics':None,'holds':[]}
    error=a['ref'][mask]-a['q'][mask]
    metric={'active_rmse_rad':float(np.sqrt(np.mean(error[:,j]**2))),
      'active_peak_error_rad':float(np.max(np.abs(error[:,j]))),
      'right7_rmse_rad':np.sqrt(np.mean(error[:,22:]**2,axis=0)).tolist(),
      'active_peak_torque_nm':float(np.max(np.abs(a['actual_tau'][mask,j]))),
      'active_rms_torque_nm':float(np.sqrt(np.mean(a['actual_tau'][mask,j]**2))),
      'active_peak_speed_rad_s':float(np.max(np.abs(a['dq'][mask,j]))),
      'torque_limited_ratio':float(np.mean(a['torque_limited'][mask])),
      'hard_clipped_ratio':float(np.mean(a['hard_clipped'][mask]))}
    if physics['contact_steps']:reasons.append('contact_influenced_including_warmup')
    if metric['torque_limited_ratio']>POLICY['max_torque_limit_ratio'] or metric['hard_clipped_ratio']>POLICY['max_torque_limit_ratio']:reasons.append('excessive_torque_limiting')
    holds=[]
    windows=[(c,s) for c in range(profile.cycles) for s in ('positive_hold','negative_hold','ready_hold')]
    if profile.post_hold_s:windows.append((profile.cycles,'post_hold'))
    for c,s in windows:
        ids=np.flatnonzero(mask&(a['cycle']==c)&(a['segment']==s))
        if len(ids)<50:continue
        ids=ids[-50:];q=a['q'][ids];dq=a['dq'][ids];ref=a['ref'][ids]
        # Preserve q22 tolerance and additionally screen the actually excited joint.
        axes=sorted({22,j})
        holds.append({'cycle':c,'segment':s,'samples':len(ids),
          'active_tail_error_rad':float(np.max(np.abs(q[:,axes]-ref[:,axes]))),
          'active_tail_speed_rad_s':float(np.max(np.abs(dq[:,axes]))),
          'right7_tail_p2p_rad':float(np.max(np.ptp(q[:,22:],axis=0))),
          'right7_tail_rms_speed_rad_s':float(np.max(np.sqrt(np.mean(dq[:,22:]**2,axis=0))))})
    if len(holds)!=len(windows):reasons.append('incomplete_hold_tails')
    for key in ('active_tail_error_rad','active_tail_speed_rad_s','right7_tail_p2p_rad','right7_tail_rms_speed_rad_s'):
        metric['max_'+key]=max((h[key] for h in holds),default=None)
        if metric['max_'+key] is not None and metric['max_'+key]>POLICY[key]:reasons.append(key)
    # Whole final second of a long post-hold, not only a favorable100ms slice.
    if profile.post_hold_s>=1 and completed:
        ids=np.flatnonzero(mask&(a['segment']=='post_hold'))[-500:]
        metric['post_hold_last_second_error_rad']=float(np.max(np.abs(a['q'][ids,j]-a['ref'][ids,j])))
        metric['post_hold_last_second_speed_rad_s']=float(np.max(np.abs(a['dq'][ids,j])))
        if len(ids)!=500 or metric['post_hold_last_second_error_rad']>.02 or metric['post_hold_last_second_speed_rad_s']>.1:reasons.append('post_hold_last_second_not_settled')
    return {'eligible':not reasons,'exclusions':reasons,'metrics':metric,'holds':holds}
