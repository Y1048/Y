"""Numerical adapter checks, not robot safety tests."""
import unittest
from mujoco_feedback_offline import Dynamics,np,mujoco
class FeedbackTests(unittest.TestCase):
 def setUp(self):self.s=Dynamics([0.]*29)
 def test_joint_mapping(self):
  s=self.s;q=np.linspace(-.12,.12,29);v=np.linspace(-.3,.3,29)
  s.d.qpos[s.qids]=q;s.d.qvel[s.vids]=v;mujoco.mj_forward(s.m,s.d)
  state=s.snapshot();np.testing.assert_allclose(state['q'],q);np.testing.assert_allclose(state['dq'],v)
  for i,j in enumerate(s.qids):self.assertEqual(s.m.actuator_trnid[s.aids[i],0],s.m.dof_jntid[s.vids[i]])
 def test_pelvis_imu_frame(self):
  s=self.s;angle=.3;s.d.qpos[3:7]=[np.cos(angle/2),np.sin(angle/2),0,0]
  s.d.qvel[3:6]=[.1,.2,.3];mujoco.mj_forward(s.m,s.d);state=s.snapshot()
  np.testing.assert_allclose(state['rpy'],[angle,0,0],atol=1e-12)
  np.testing.assert_allclose(state['gyro'],[.1,.2,.3],atol=1e-12)
 def test_torque_does_not_teleport(self):
  s=self.s;command=np.zeros(29);command[22]=.1;state=s.advance(.002,command)
  self.assertGreater(abs(state['dq'][22]),0);self.assertGreater(abs(state['q'][22]-.1),.05)
  self.assertAlmostEqual(state['time'],.002);self.assertLessEqual(s.max_tau,max(s.cap))
 def test_reject_invalid_command(self):
  for command in ([0.]*28,[float('nan')]*29):
   with self.assertRaises(ValueError):self.s.advance(.002,command)
 def test_reject_time_jump(self):
  with self.assertRaises(ValueError):self.s.advance(.1,[0.]*29)
  self.s.advance(.002,[0.]*29)
  with self.assertRaises(ValueError):self.s.advance(0,[0.]*29)
if __name__=='__main__':unittest.main()
