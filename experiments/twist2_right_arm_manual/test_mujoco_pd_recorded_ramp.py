"""Causal command-pipeline tests; not actual operator recordings or hardware."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import mujoco_pd_recorded_ramp_core as core
import mujoco_pd_recorded_ramp_study as study
import mujoco_pd_recorded_study as raw_study
from test_mujoco_pd_recorded import fixture_rows,dump,capture


class FilterTest(unittest.TestCase):
    def test_causal_endpoints_and_midpoint(self):
        a=np.zeros(29);b=np.ones(29)
        np.testing.assert_array_equal(core.causal_reference(a,b,0),a)
        np.testing.assert_array_equal(core.causal_reference(a,b,.01),np.full(29,.5))
        np.testing.assert_array_equal(core.causal_reference(a,b,.02),b)
        np.testing.assert_array_equal(a,np.zeros(29))
    def test_invalid_time_or_nonfinite_refused(self):
        for t in (-1,float('nan'),.03):
            with self.assertRaises(ValueError):core.causal_reference(np.zeros(29),np.ones(29),t)
        with self.assertRaises(ValueError):core.causal_reference(np.zeros(29),np.full(29,np.nan),0)
    def test_constant_reference_unchanged(self):
        a=np.arange(29,dtype=float);np.testing.assert_array_equal(core.causal_reference(a,a,.014),a)
    def test_next_goal_does_not_enter_current_interval(self):
        a=np.zeros(29);b=np.ones(29);c=np.ones(29)*9
        first=core.causal_reference(a,b,.018);c[:]=-9
        np.testing.assert_array_equal(first,core.causal_reference(a,b,.018))
        np.testing.assert_array_equal(core.causal_reference(b,c,0),b)
    def test_same_plan_and_frozen_numeric_limits(self):
        c=capture();self.assertEqual(study.jobs([c]),raw_study.jobs([c]))
        for k,v in core.unfiltered.POLICY.items():self.assertEqual(core.POLICY[k],v)
        self.assertFalse(core.POLICY['pd_only_validation'])


class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=capture();cls.r,cls.a=core.simulate(cls.c,study.VECTORS[1],study.SCENARIOS[0],'sample')
    def test_explicitly_different_command_reference(self):
        self.assertTrue(self.r['completed']);self.assertTrue(self.r['eligible'],self.r['exclusions'])
        self.assertTrue(self.r['requires_command_prefilter']);self.assertFalse(self.r['pd_only_optimum_proven'])
        self.assertGreater(np.max(np.abs(self.a['writer_reference']-self.a['ref'])),1e-5)
    def test_scores_use_original_goals(self):
        a=self.a;mask=(a['trial_time_s']>=0)&(a['trial_time_s']<self.c.sample_time_s[-1])
        expected=np.sqrt(np.mean((a['q'][mask,22:]-a['ref'][mask,22:])**2,axis=0))
        np.testing.assert_array_equal(expected,self.r['metrics']['right7_recorded_rmse_rad'])
        modified={k:v.copy() for k,v in a.items()};modified['writer_reference']=a['q'].copy()
        score=core.evaluate(modified,self.c,'sample',self.r['completed'],self.r['reason'],self.r['physics'])
        self.assertEqual(score['metrics'],self.r['metrics'])
    def test_same_guard_and_pure_pd(self):
        study.check_guard(self.r,self.a);self.assertTrue(self.r['joint_limit_guard']['no_intervention'])
        kp=np.array(self.r['gains_kp']);kd=np.array(self.r['gains_kd'])
        np.testing.assert_allclose(self.a['requested'],kp*(self.a['cmd']-self.a['q'])-kd*self.a['dq'],atol=1e-12,rtol=1e-12)
    def test_original_wrist_bias_still_fails(self):
        a={k:v.copy() for k,v in self.a.items()};a['q'][-500:,27]+=.04
        self.assertFalse(core.evaluate(a,self.c,'sample',True,'',self.r['physics'])['eligible'])


class BundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);raw=cls.root/'synthetic_fixture.jsonl'
        dump(raw,fixture_rows());cls.out=cls.root/'result'
        study.main(['--recording',str(raw),'--output',str(cls.out),'--smoke','--workers','1'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_real_filtered_audit_and_separate_claim(self):
        self.assertTrue(study.audit(self.out)['passed']);s=study.read(self.out/'summary.json')
        self.assertTrue(s['requires_command_prefilter']);self.assertFalse(s['pd_only_optimum_proven'])
        self.assertNotIn('selected_simulation_vector',s)
    def test_filter_label_cannot_be_erased(self):
        p=self.out/'cases/case_0000.json';old=p.read_bytes()
        try:
            r=json.loads(old);r['requires_command_prefilter']=False;p.write_text(json.dumps(r))
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old)
    def test_modified_filtered_reference_refused_even_with_new_hash(self):
        p=self.out/'full_state/case_0000.npz';case=self.out/'cases/case_0000.json';old=p.read_bytes();old_case=case.read_bytes()
        try:
            with np.load(p) as z:a={k:z[k] for k in z.files}
            a['writer_reference'][1800,27]+=.0001;np.savez_compressed(p,**a)
            r=json.loads(old_case);r['trace_sha256']=study.engine.sha256(p);case.write_text(json.dumps(r))
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:p.write_bytes(old);case.write_bytes(old_case)
    def test_incomplete_low_error_never_selected(self):
        plan=study.read(self.out/'plan.json');rs=[study.read(self.out/'cases'/(j['case_id']+'.json')) for j in plan]
        for r in rs:r.update(eligible=False,exclusions=['test_failure'])
        s=study.summarize(rs,plan,'x');self.assertIsNone(s['selected_filtered_pipeline_vector'])


if __name__=='__main__':unittest.main()
