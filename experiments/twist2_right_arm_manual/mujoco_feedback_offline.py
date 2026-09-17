"""Local JSONL dynamics fixture. No network, renderer, robot SDK or publisher."""
import hashlib,json,math,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'logs/diagnostics/mujoco_versions/3.12.0'))
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'))
import mujoco
import numpy as np
from g1_right_arm_common import G1_29_JOINTS

class Dynamics:
 def __init__(self,home):
  if mujoco.__version__!='3.12.0':raise RuntimeError('MuJoCo 3.12.0 required')
  source=ROOT/'MuJoCo_G1_Controller/external/unitree_mujoco/unitree_robots/g1/scene_29dof.xml'
  self.model_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,source.with_name('g1_29dof.xml'))}
  self.m=m=mujoco.MjModel.from_xml_path(str(source));self.d=d=mujoco.MjData(m)
  assert m.nq==36 and m.nv==35 and m.nu==29 and m.jnt_type[0]==mujoco.mjtJoint.mjJNT_FREE
  joints=[m.joint(n).id for n in G1_29_JOINTS]
  self.qids=np.array([m.jnt_qposadr[j] for j in joints]);self.vids=np.array([m.jnt_dofadr[j] for j in joints])
  self.aids=np.array([int(np.flatnonzero(m.actuator_trnid[:,0]==j).item()) for j in joints])
  assert len(set(self.aids))==29 and np.allclose(m.actuator_gear[self.aids,0],1)
  header=ROOT/'references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp'
  text=header.read_text();self.header_sha=hashlib.sha256(header.read_bytes()).hexdigest()
  def values(name):
   a=np.array([float(v.strip()) for v in re.search(r'\b'+name+r'\s*=\s*\{([^}]+)\}',text)[1].split(',') if v.strip()])
   assert a.shape==(29,) and np.isfinite(a).all() and (a>0).all();return a
  self.kp=values('kKp');self.kd=values('kKd');self.cap=values('kTorqueLimit')
  self.lo=np.maximum(-self.cap,m.actuator_ctrlrange[self.aids,0]);self.hi=np.minimum(self.cap,m.actuator_ctrlrange[self.aids,1])
  d.qpos[self.qids]=home;mujoco.mj_forward(m,d)
  self.steps=0;self.max_tau=0.;self.clipped=0;self.min_height=float(d.qpos[2]);self.rows=[]
 def sensor(self,name):return self.d.sensor(name).data.copy()
 def snapshot(self):
  d=self.d;w,x,y,z=self.sensor('imu_quat')
  rpy=[math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),math.asin(float(np.clip(2*(w*y-z*x),-1,1))),math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
  return dict(time=float(d.time),q=d.qpos[self.qids].tolist(),dq=d.qvel[self.vids].tolist(),gyro=self.sensor('imu_gyro').tolist(),quat=[w,x,y,z],acc=self.sensor('imu_acc').tolist(),rpy=rpy,root=d.qpos[:7].tolist())
 def advance(self,time,command):
  m,d=self.m,self.d;command=np.array(command,dtype=float)
  if command.shape!=(29,) or not np.isfinite(command).all() or not math.isfinite(time) or time<d.time-1e-9 or time-d.time>.021:raise ValueError('invalid dynamics request')
  while time-d.time>1e-10:
   m.opt.timestep=min(.001,time-d.time)
   tau=self.kp*(command-d.qpos[self.qids])-self.kd*d.qvel[self.vids]
   torque=np.clip(tau,self.lo,self.hi);self.clipped+=int(np.count_nonzero(tau!=torque));self.max_tau=max(self.max_tau,float(np.max(np.abs(torque))))
   d.ctrl[self.aids]=torque;mujoco.mj_step(m,d);self.steps+=1
   if not np.isfinite(d.qpos).all() or not np.isfinite(d.qvel).all() or any(w.number for w in d.warning):raise RuntimeError('dynamics numerical warning')
  mujoco.mj_forward(m,d);state=self.snapshot();self.min_height=min(self.min_height,state['root'][2]);self.rows.append(state);return state
 def report(self):
  return dict(offline_only=True,mujoco_version=mujoco.__version__,steps=self.steps,time=self.d.time,min_root_height=self.min_height,max_applied_torque_nm=self.max_tau,clipped_joint_substeps=self.clipped,gains_sha256=self.header_sha,kp=self.kp.tolist(),kd=self.kd.tolist(),torque_lower=self.lo.tolist(),torque_upper=self.hi.tolist(),model_xml_sha256=self.model_hashes,joint_order=list(G1_29_JOINTS),model='existing unitree scene_29dof.xml; uncalibrated',initialization='XML root height .793m; ready joints; zero velocity; no settled takeover',rows=self.rows,publisher_created=False,physical_safety_validated=False)

def main():
 sim=None
 try:
  for line in sys.stdin:
   request=json.loads(line)
   if sim is None:sim=Dynamics(request['home'])
   print(json.dumps(sim.advance(request['time'],request['command']),allow_nan=False),flush=True)
 finally:
  if sim is not None:(ROOT/'logs/test_results/mink_mujoco_feedback.json').write_text(json.dumps(sim.report(),indent=2),encoding='utf-8')
if __name__=='__main__':main()
