"""Same IK/goal comparison tests, no UDP/viewer/robot."""
import sys,unittest,math,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'logs/diagnostics/mujoco_versions/3.12.0'))
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'))
from g1_mink_speed_profiles import speed_profile,live_joint_bounds
from replay_upstream_mink import build,base,UpstreamMinkTracking
import mink,numpy as np
class Profiles(unittest.TestCase):
 def test_live_bounds_inside_native_contract(self):
  import re
  source=(ROOT/'experiments/twist2_right_arm_manual/offline_twist2_constants.hpp').read_text()
  native=[]
  for name in ('kLower','kUpper'):
   text=re.search(name+r' = \{([^}]+)',source).group(1)
   native.append(np.array([float(x.strip().rstrip('F')) for x in text.split(',') if x.strip()],dtype=np.float32).astype(float)[22:29])
  lo,hi=map(np.array,live_joint_bounds())
  np.testing.assert_allclose(lo,native[0]+.0801,atol=1e-12)
  np.testing.assert_allclose(hi,native[1]-.0801,atol=1e-12)
  self.assertTrue(np.all(lo>native[0]+.05));self.assertTrue(np.all(hi<native[1]-.05))

 def test_exact_units(self):
  a,b=speed_profile('yesterday'),speed_profile('today')
  self.assertEqual(a['velocity_rad_s'],[.7]*7)
  np.testing.assert_allclose(a['acceleration_rad_s2'],np.deg2rad([10]*7))
  np.testing.assert_allclose(b['velocity_rad_s'],np.deg2rad([90]*4+[180]*3))
  np.testing.assert_allclose(b['acceleration_rad_s2'],np.deg2rad([60]*7))
 def test_reject_unknown(self):
  with self.assertRaises(ValueError):speed_profile('fast')
 def test_same_goal_and_ik_respect_both_profiles(self):
  reports={}
  for name in ('yesterday','today'):
   profile=speed_profile(name);m,p,_=build()
   p.limits=[mink.VelocityLimit(m,dict(zip(base.g1.RIGHT_ARM_JOINTS,profile['velocity_rad_s']))) if isinstance(limit,mink.VelocityLimit) else limit for limit in p.limits]
   t=UpstreamMinkTracking(p,p.qpos_ids,profile['velocity_rad_s'],profile['acceleration_rad_s2'],[1.28]*7,base.DT)
   q=base._initial_configuration(m);origin=q.copy();p.configuration.update(q);t.Reset(q)
   pose=p.configuration.get_transform_frame_to_world('right_wrist_yaw_link','body');pos=pose.translation().copy();pos[0]+=.08
   goal=base._matrix_to_se3(pose.rotation().as_matrix(),pos)
   max_v=np.zeros(7);max_a=np.zeros(7);prev=np.zeros(7)
   for _ in range(180):
    step=t.Track(q,goal);self.assertTrue(step.applied,step.status)
    v=np.array(step.velocity_rad_s);a=(v-prev)/base.DT
    self.assertTrue(np.all(abs(v)<=np.array(profile['velocity_rad_s'])+1e-6))
    self.assertTrue(np.all(abs(a)<=np.array(profile['acceleration_rad_s2'])+1e-6))
    q=step.q;prev=v;max_v=np.maximum(max_v,abs(v));max_a=np.maximum(max_a,abs(a))
    fixed=np.ones(len(q),dtype=bool);fixed[p.qpos_ids]=False;np.testing.assert_allclose(q[fixed],origin[fixed],atol=1e-10)
   reports[name]=dict(profile=profile,max_velocity_rad_s=max_v.tolist(),max_acceleration_rad_s2=max_a.tolist(),target_xyz=pos.tolist())
  np.testing.assert_allclose(reports['yesterday']['target_xyz'],reports['today']['target_xyz'])
  (ROOT/'logs/test_results/mink_speed_comparison.json').write_text(json.dumps(dict(offline_only=True,same_ik='mink_position_priority_recovery_v5',cases=reports,physical_safety_validated=False),indent=2),encoding='utf-8')
if __name__=='__main__':unittest.main()
