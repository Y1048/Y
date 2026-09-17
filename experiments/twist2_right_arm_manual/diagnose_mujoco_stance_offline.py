"""Controlled stance comparison; no model/gain edits and no robot connection."""
import hashlib,json
from mujoco_feedback_offline import Dynamics,ROOT,mujoco,np

def contact_snapshot(s):
 m,d=s.m,s.d;floor=m.geom('floor').id
 feet=[i for i in range(m.ngeom) if 'ankle_roll' in m.body(m.geom_bodyid[i]).name and m.geom_contype[i]]
 distances=[float(mujoco.mj_geomDistance(m,d,floor,i,1,None)) for i in feet]
 forces={'left':0.,'right':0.};points=[];other=[]
 for i,c in enumerate(d.contact):
  if floor not in c.geom:continue
  g=int(c.geom[1] if c.geom[0]==floor else c.geom[0]);body=m.body(m.geom_bodyid[g]).name
  if g in feet:
   f=np.zeros(6);mujoco.mj_contactForce(m,d,i,f);forces['left' if body.startswith('left') else 'right']+=float(f[0]);points.append(c.pos.tolist())
  else:other.append(body)
 return dict(foot_floor_min_m=min(distances),normal_force_n=forces,foot_contact_points=points,other_floor_bodies=other,com=d.subtree_com[1].tolist())

def run(home,aligned,trace=None):
 s=Dynamics(home);initial=contact_snapshot(s)
 if aligned:
  s.d.qpos[2]-=initial['foot_floor_min_m'];mujoco.mj_forward(s.m,s.d)
 initialized=contact_snapshot(s);rows=[];reason=None;first_contact=None;index=0
 # Same attitude .2rad and speed4rad/s checks as current owner fixture.
 for tick in range(1,2001):
  now=tick*.002
  if trace is not None:
   while index+1<len(trace) and trace[index+1]['time']<=now-.002+1e-10:index+=1
   command=trace[index]['q']
  else:command=home
  state=s.advance(now,command);contact=contact_snapshot(s)
  if first_contact is None and sum(contact['normal_force_n'].values())>1:first_contact=now
  rows.append(dict(**state,contact=contact))
  if max(abs(v) for v in state['rpy'][:2])>.2:reason='attitude_limit'
  elif max(abs(v) for v in state['dq'])>4:reason='velocity_limit'
  if reason:break
 return dict(aligned=aligned,reference='recorded policy commands; open-loop replay' if trace else 'constant ready PD; no policy',initial=initial,initialized=initialized,first_contact_s=first_contact,stop_reason=reason,end_s=rows[-1]['time'],final_rpy=rows[-1]['rpy'],max_pitch_rad=max(abs(r['rpy'][1]) for r in rows),max_dq_rad_s=max(max(abs(v) for v in r['dq']) for r in rows),rows=rows)

def main():
 path=ROOT/'logs/test_results/mink_torch_dynamics_replay.json';raw=path.read_bytes();trial=json.loads(raw)
 home=trial['initial_reference'];default=home.copy();default[15:]=[0,.4,0,1.2,0,0,0,0,-.4,0,1.2,0,0,0]
 cases={}
 for name,q,aligned,trace in [('ready_air',home,False,None),('ready_ground',home,True,None),('default_ground',default,True,None),('recorded_policy_air',home,False,trial['trace']),('recorded_policy_ground',home,True,trial['trace'])]:
  cases[name]=run(q,aligned,trace)
  print(name,json.dumps({k:v for k,v in cases[name].items() if k not in ('rows','initial','initialized')}),flush=True)
 checks=dict(initial_air_gap_detected=cases['ready_air']['initial']['foot_floor_min_m']>.01,
  ground_alignment_residual_small=abs(cases['ready_ground']['initialized']['foot_floor_min_m'])<1e-8,
  ground_contact_precedes_air=cases['ready_ground']['first_contact_s']<cases['ready_air']['first_contact_s'],
  no_policy_also_hits_attitude_limit=cases['ready_ground']['stop_reason']=='attitude_limit',
  recorded_replay_matches_prior_stop=abs(cases['recorded_policy_air']['end_s']-1.442)<.01)
 assert all(checks.values()),checks
 report=dict(checks=checks,offline_only=True,source_sha256=hashlib.sha256(raw).hexdigest(),limits=dict(attitude_rad=.2,velocity_rad_s=4),cases=cases,physical_safety_validated=False,publisher_created=False,note='Recorded policy replay holds its last available reference after trace ends; not closed-loop inference. Ground alignment changes fixture root only, no asset or runtime control edits.')
 (ROOT/'logs/test_results/mink_stance_diagnosis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if __name__=='__main__':main()
