"""Memory-only torque-path tests and headless simulation regressions."""
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_motor_stress as motor
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine

class MotorStressTest(unittest.TestCase):
    def test_exact_zero_delay_identity_and_no_input_mutation(self):
        p=motor.TorquePath(.001,0,0)
        u=np.arange(7,dtype=float)
        np.testing.assert_array_equal(p.step(u),u)
        np.testing.assert_array_equal(u,np.arange(7))
    def test_exact_fifo_delay(self):
        p=motor.TorquePath(.001,.002,0)
        for u,expected in ((1,0),(2,0),(3,1),(4,2)):
            np.testing.assert_array_equal(p.step(np.ones(7)*u),np.ones(7)*expected)
    def test_first_order_exact_discretization_and_reset(self):
        a=motor.TorquePath(.001,0,.002)
        b=motor.TorquePath(.001,0,.002)
        for i in range(1,11):
            x=a.step(np.ones(7));y=b.step(np.ones(7))
            np.testing.assert_array_equal(x,y)
            np.testing.assert_allclose(x,1-math.exp(-i*.001/.002),rtol=1e-12,atol=1e-12)
    def test_invalid_parameters_and_input(self):
        for args in ((0,0,0),(.001,-1,0),(.001,.0005,0),(.001,0,math.nan)):
            with self.assertRaises(ValueError):motor.TorquePath(*args)
        with self.assertRaises(ValueError):motor.TorquePath(.001,0,0).step(np.zeros(6))
    def test_nominal_matches_unchanged_dynamics(self):
        with tempfile.TemporaryDirectory() as d:
            a=expanded.simulate((56.,3.,expanded.SCENARIOS[0],d,'base','test'))
            b=motor.simulate((56.,3.,motor.SCENARIOS[0],d,'motor'))
            self.assertEqual(a['metrics'],b['metrics'])
            with np.load(Path(d)/a['trace_npz']) as x,np.load(Path(d)/b['trace_npz']) as y:
                np.testing.assert_array_equal(x['values'],y['values'])
    def test_friction_zero_is_explicit_and_changes_response(self):
        with tempfile.TemporaryDirectory() as d:
            r=motor.simulate((56.,3.,motor.SCENARIOS[1],d,'zero'))
            self.assertEqual(r['frictionloss_modified_nm'],[0.]*7)
            self.assertTrue(all(v>0 for v in r['frictionloss_source_nm']))
    def test_callbacks_restored_on_failure(self):
        load,step=engine.load_model,mujoco.mj_step
        with tempfile.TemporaryDirectory() as d,patch.object(expanded,'simulate',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):motor.simulate((56.,3.,motor.SCENARIOS[0],d,'fail'))
        self.assertIs(engine.load_model,load);self.assertIs(mujoco.mj_step,step)
    def test_missing_scenarios_not_accepted(self):
        self.assertTrue(all(not r['all_eligible'] for r in motor.summarize([])))
    def test_worker_import_and_real_socket_creation_denied(self):
        code="import sys;sys.path.insert(0,"+repr(str(Path(__file__).parent))+ ");import mujoco_pd_expand as e;e.init_worker();import mujoco;import socket\ntry:\n socket.socket()\nexcept RuntimeError:\n print('blocked')\nelse:\n raise SystemExit(3)\n"
        p=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('blocked',p.stdout)

if __name__=='__main__':unittest.main()
