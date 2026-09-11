"""SDK-free all-joint envelope regressions and headless MuJoCo injection tests."""
import math
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_sweep as engine
from joint_limit_guard import JointLimitEnvelope, JointLimitMonitor, LimitViolation, DOFS


def envelope():
    return JointLimitEnvelope(np.full(29,-1.1),np.full(29,1.1),np.full(29,-1.),np.full(29,1.))


class EnvelopeTest(unittest.TestCase):
    def test_bounds_are_copied_and_immutable(self):
        e=envelope()
        with self.assertRaises(ValueError):e.soft_lower[0]=0
    def test_bad_limits_and_relaxed_reserve_refused(self):
        for kwargs in ({'reserve':.01},{'reaction':0},{'brake':0},{'soft_lower':np.ones(29)},
                       {'hard_lower':np.full(29,math.nan)}, {'outward_acceleration':-1}):
            with self.assertRaises(ValueError):replace(envelope(),**kwargs)
    def test_all_29_lower_and_upper_boundaries_are_strict(self):
        for j in range(29):
            for bound in (-1.1,-1.,-.95,.95,1.,1.1):
                monitor=JointLimitMonitor(envelope());q=np.zeros(29);q[j]=bound
                with self.assertRaises(LimitViolation):monitor.state(q,np.zeros(29),0,'test')
                self.assertIn(j,monitor.event['joints'])
    def test_near_soft_limit_refuses_before_crossing(self):
        m=JointLimitMonitor(envelope());q=np.zeros(29);q[28]=.94;dq=np.zeros(29);dq[28]=.2
        with self.assertRaises(LimitViolation):m.state(q,dq,0,'test')
        self.assertEqual(m.event['reason'],'joint_stopping_envelope_exhausted')
        self.assertGreater(m.minimum_soft[28],.05)
    def test_inward_motion_is_not_treated_as_outward(self):
        m=JointLimitMonitor(envelope());q=np.zeros(29);q[28]=.94;dq=np.zeros(29);dq[28]=-.2
        m.state(q,dq,0,'test');self.assertIsNone(m.event)
    def test_stop_distance_increases_with_speed_and_delay(self):
        e=envelope();values=e.stop_distance(np.array([0,.1,.5,1]))
        self.assertTrue(np.all(np.diff(values)>0))
        self.assertGreater(replace(e,reaction=.04).stop_distance(.5),e.stop_distance(.5))
    def test_nonfinite_fails_closed_and_json_event_is_finite(self):
        import json
        for bad in (math.nan,math.inf):
            m=JointLimitMonitor(envelope());q=np.zeros(29);q[12]=bad
            with self.assertRaises(LimitViolation):m.state(q,np.zeros(29),0,'test')
            json.dumps(m.summary(),allow_nan=False)
    def test_latched_failure_cannot_resume(self):
        m=JointLimitMonitor(envelope());q=np.zeros(29);q[5]=1
        with self.assertRaises(LimitViolation):m.state(q,q*0,0,'test')
        with self.assertRaises(LimitViolation):m.state(np.zeros(29),np.zeros(29),.01,'test')
    def test_reference_extrema_outside_corridor_refused(self):
        m=JointLimitMonitor(envelope());low=np.zeros(29);high=low.copy();high[7]=.99
        with self.assertRaises(LimitViolation):m.reference(low,high)
    def test_governor_slows_before_boundary_without_mutating_input(self):
        e=envelope();p=np.zeros(29);q=p.copy();q[22]=10;vel=[]
        for _ in range(5000):
            out,changed=e.command_step(q,p,.002)
            self.assertTrue(np.all(out>e.inner_lower) and np.all(out<e.inner_upper))
            vel.append((out[22]-p[22])/.002);p=out
        self.assertLess(vel[-1],vel[0]/100)
        self.assertEqual(q[22],10)
        self.assertGreater(1-p[22],.05)
    def test_governor_intervention_is_not_rankable(self):
        m=JointLimitMonitor(envelope())
        with self.assertRaises(LimitViolation):m.command(np.ones(29)*10,np.zeros(29),.002,0)
        self.assertEqual(m.event['reason'],'joint_limit_command_intervention')
    def test_random_governed_commands_remain_strictly_inside(self):
        rng=np.random.default_rng(420);e=envelope();p=np.zeros(29)
        for _ in range(2000):
            q=rng.uniform(-10,10,29);next_q,_=e.command_step(q,p,.002)
            self.assertTrue(np.all(next_q>e.inner_lower) and np.all(next_q<e.inner_upper));p=next_q


class DynamicsLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model,cls.qa,cls.va,cls.motors,_=engine.load_model(engine.MODEL,.001)
        cls.contract=engine.load_contract()
    def run_case(self,**kw):
        return engine.run_candidate(self.model,self.qa,self.va,self.motors,self.contract,56,3,**kw)
    def test_nominal_all_joints_include_final_integrated_step(self):
        result,rows=self.run_case();g=result['joint_limit_guard']
        self.assertTrue(result['eligible']);self.assertIsNone(g['event'])
        self.assertEqual(len(g['minimum_soft_margin_rad']),29)
        self.assertTrue(all(x>.05 for x in g['minimum_soft_margin_rad']))
        self.assertTrue(all(x>0 for x in g['minimum_stopping_slack_rad']))
        steps=round(engine.WARMUP/.001)+math.ceil(engine.RoundTrip().total/.001)
        self.assertEqual(g['observations'],2*steps)
    def test_reference_outside_inner_range_never_integrates(self):
        class BadPath(engine.RoundTrip):offset=10.
        with patch.object(engine,'RoundTrip',BadPath),patch.object(mujoco,'mj_step') as step:
            result,rows=self.run_case()
        self.assertFalse(result['eligible']);step.assert_not_called();self.assertEqual(rows,[])
    def test_unsafe_start_refused_without_integrating(self):
        c=replace(self.contract,baseline=self.contract.baseline.copy());c.baseline[5]=c.upper[5]-.01
        with patch.object(mujoco,'mj_step') as step:
            r,_=engine.run_candidate(self.model,self.qa,self.va,self.motors,c,56,3)
        step.assert_not_called();self.assertFalse(r['eligible'])
    def test_post_step_violation_catches_non_arm_joint(self):
        real=mujoco.mj_step
        def injected(m,d):
            real(m,d);d.qpos[self.qa[5]]=self.contract.upper[5]+.001
        with patch.object(mujoco,'mj_step',side_effect=injected):r,_=self.run_case()
        self.assertFalse(r['eligible']);g=r['joint_limit_guard'];self.assertEqual(g['event']['stage'],'post_step')
        self.assertIn(5,g['event']['joints']);self.assertLess(g['minimum_soft_margin_rad'][5],0)
    def test_final_step_violation_cannot_be_reported_complete(self):
        real=mujoco.mj_step;count=0;last=round(engine.WARMUP/.001)+math.ceil(engine.RoundTrip().total/.001)
        def injected(m,d):
            nonlocal count
            real(m,d);count+=1
            if count==last:d.qpos[self.qa[28]]=self.contract.upper[28]
        with patch.object(mujoco,'mj_step',side_effect=injected):r,_=self.run_case()
        self.assertEqual(count,last);self.assertFalse(r['completed']);self.assertFalse(r['eligible'])
        self.assertIn(28,r['joint_limit_guard']['event']['joints'])
    def test_torque_limiter_cannot_silently_put_command_on_soft_limit(self):
        def unsafe_writer(ref,prev,q,dq,kp,kd,c):return c.upper.copy(),np.zeros(29,bool),np.zeros(29,bool)
        with patch.object(engine,'writer_target',side_effect=unsafe_writer),patch.object(mujoco,'mj_step') as step:
            r,_=self.run_case()
        step.assert_not_called();self.assertEqual(r['reason'],'joint_limit_command_intervention')
    def test_disabled_model_limit_refused(self):
        m,qa,va,motors,_=engine.load_model(engine.MODEL,.001);m.jnt_limited[0]=0
        with self.assertRaises(ValueError):engine.run_candidate(m,qa,va,motors,self.contract,56,3)
    def test_model_limit_activation_margin_respected(self):
        e=envelope();fake=type('M',(),{})();fake.jnt_qposadr=np.arange(29);fake.jnt_limited=np.ones(29)
        fake.jnt_range=np.tile([-1.1,1.1],(29,1));fake.jnt_margin=np.full(29,.2)
        c=type('C',(),{'lower':e.soft_lower,'upper':e.soft_upper})()
        actual=JointLimitEnvelope.from_model(fake,np.arange(29),c)
        np.testing.assert_allclose(actual.soft_lower,-.9);np.testing.assert_allclose(actual.soft_upper,.9)


if __name__=='__main__':unittest.main()
