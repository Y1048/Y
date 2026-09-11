"""Synthetic corrupt-artifact regressions; no physics or hardware imports."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import mujoco_pd_expand_audit as audit

class ExpandedAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'traces').mkdir();(self.root/'cases').mkdir()
        self.path=self.root/'cases/failed.json';self.trace=self.root/'traces/failed.npz'
        self.columns=['time_s','trial_time_s','phase','cycle','direction','ref_22','cmd_22',
          'q_22','dq_22','tau_requested_22','actual_tau_22','contacts',
          'torque_target_limited_arm','hard_clipped_arm','slew_exceeded_arm']
        self.values=np.zeros((2,len(self.columns)));self.values[:,0]=[3,3.002]
        self.values[:,1]=[0,.002];self.values[:,2]=5;self.values[:,4]=1;self.values[:,5]=.1
        metrics={k:0. for k in audit.METRICS}
        metrics['reference_rmse_joint22_rad']=.1;metrics['peak_reference_error_joint22_rad']=.1
        metrics['endpoint_holds']=[]
        self.record={'case_id':'failed','simulation_only':True,'hardware_config_modified':False,
          'trace_rows':2,'samples':2,'trace_npz':'traces\\failed.npz','kp_proximal':40,'kd_proximal':5,
          'gains_kp':[40]*29,'gains_kd':[5]*29,'metrics':metrics,'completed':False,'eligible':False,
          'reason':'injected','scenario':['nominal'],'physics_observation':{'trial_physics_steps':2,'trial_contact_steps':0}}
        self.write()
    def write(self):
        np.savez_compressed(self.trace,columns=np.array(self.columns),values=self.values,
                            segment=np.array(['ready_hold']*len(self.values)))
        self.record['trace_sha256']=audit.sha(self.trace)
        self.path.write_text(json.dumps(self.record),encoding='utf-8')
    def test_valid_failed_partial_retained(self):
        r,m,q=audit.check_case(self.root,self.path)
        self.assertFalse(r['eligible']);self.assertAlmostEqual(m['reference_rmse_joint22_rad'],.1)
        self.assertEqual(len(q),2)
    def test_trace_tampering_rejected(self):
        self.trace.write_bytes(self.trace.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'trace hash'):audit.check_case(self.root,self.path)
    def test_metric_tampering_rejected(self):
        self.record['metrics']['reference_rmse_joint22_rad']=0.;self.write()
        with self.assertRaisesRegex(ValueError,'reference_rmse'):audit.check_case(self.root,self.path)
    def test_time_gap_rejected(self):
        self.values[1,0]+=.002;self.values[1,1]+=.002;self.write()
        with self.assertRaisesRegex(ValueError,'continuity'):audit.check_case(self.root,self.path)
    def test_nonfinite_trace_rejected(self):
        self.values[0,7]=np.nan;self.write()
        with self.assertRaisesRegex(ValueError,'finite'):audit.check_case(self.root,self.path)
    def test_failed_candidate_cannot_be_eligible(self):
        self.record['eligible']=True;self.write()
        with self.assertRaisesRegex(ValueError,'eligibility'):audit.check_case(self.root,self.path)
    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError,'escapes'):audit.safe_path(self.root,'../outside.npz')
    def test_wrong_gain_fields_rejected(self):
        self.record['gains_kp'][22]=56;self.write()
        with self.assertRaisesRegex(ValueError,'Kp fields'):audit.check_case(self.root,self.path)

if __name__=='__main__':unittest.main()
