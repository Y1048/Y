"""Offline-only pitch/wrist adapter, selection and actual-state evidence tests.
Generated recording fixtures are not operator data and never formal study runs.
"""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import mujoco_pd_recorded_pitch_wrist as study
from test_mujoco_pd_recorded import capture, fixture_rows, dump


def mock_result(job, good=True, error=.01):
    return dict(job, simulation_only=True, hardware_approved=False,
        recommended_hardware_gains=None, hardware_config_modified=False,
        completed=good, eligible=good, reason='' if good else 'speed',
        exclusions=[] if good else ['speed'],
        metrics={'max_right7_recorded_rmse_rad':error})


class PlanTest(unittest.TestCase):
    def test_pitch_grid_45_equal_conditions(self):
        jobs=study.phase_plan('pitch',[],{})
        self.assertEqual(len(jobs),45)
        self.assertEqual(len({study.identity(j) for j in jobs}),15)
        self.assertEqual(len({j['case_id'] for j in jobs}),45)
        for g in study.deduplicate(jobs):
            cells={(j['clock'],j['scenario']['name']) for j in jobs if study.identity(j)==study.identity(g)}
            self.assertEqual(len(cells),3)
    def test_wrist_grid_36_equal_conditions(self):
        p=study.phase_plan('pitch',[],{});records=[mock_result(j,error=.01+j['candidate']['kp'][0]*1e-6) for j in p]
        jobs=study.phase_plan('wrist',records,{'pitch':p})
        self.assertEqual(len(jobs),36)
        self.assertEqual({j['wrist_pitch']['kp'] for j in jobs},set(study.WRIST_KP))
    def test_all_failed_pitch_no_wrist_search(self):
        p=study.phase_plan('pitch',[],{})
        self.assertEqual(study.phase_plan('wrist',[mock_result(j,False) for j in p],{'pitch':p}),[])
    def test_validation_contains_baseline_and_same16cells(self):
        p=study.phase_plan('pitch',[],{});rs=[mock_result(j,error=.02-j['candidate']['kp'][0]*1e-5) for j in p]
        w=study.phase_plan('wrist',rs,{'pitch':p});rs += [mock_result(j,error=.01-j['wrist_pitch']['kp']*1e-6) for j in w]
        v=study.phase_plan('validation',rs,{'pitch':p,'wrist':w})
        self.assertIn(study.specification(),study.deduplicate(v))
        self.assertLessEqual(len(v),64)
        for g in study.deduplicate(v):
            self.assertEqual(sum(study.identity(j)==study.identity(g) for j in v),16)
        for scenario in study.EXTRA_SCENARIOS:scenario.validate()
    def test_wrist_identity_is_not_lost(self):
        a,b=study.specification(),study.specification(wrist_kp=30.)
        self.assertNotEqual(study.identity(a),study.identity(b))
        self.assertEqual(len(study.deduplicate([a,b,a])),2)
    def test_boolean_nonfinite_or_out_of_bounds_refused(self):
        for changes in ({'pitch_kp':True},{'pitch_kp':float('nan')},{'pitch_kp':161.},
                        {'wrist_kp':41.},{'wrist_kd':float('inf')},{'wrist_kd':0.}):
            with self.assertRaises(ValueError):study.specification(**changes)
    def test_unrelated_gain_mutation_refused(self):
        for field,index in (('kp',1),('kd',2),('kp',3)):
            g=study.specification();g['candidate'][field][index]+=.1
            with self.assertRaises(ValueError):study.validate(g)
    def test_unknown_field_or_phase_refused(self):
        g=study.specification();g['bias']=.01
        with self.assertRaises(ValueError):study.validate(g)
        with self.assertRaises(ValueError):study.phase_plan('invalid',[],{})
    def test_failed_small_error_not_selected(self):
        p=study.recorded_plan('pitch',[study.specification(),study.specification(120.)],study.previous.screen_conditions()[:1])
        r=[mock_result(p[0],False,.001),mock_result(p[1],True,.02)]
        self.assertEqual(study.passing(r,p),[study.spec_of(p[1])])
    def test_missing_or_duplicate_case_refused(self):
        p=study.phase_plan('pitch',[],{});r=[mock_result(j) for j in p]
        with self.assertRaises(ValueError):study.rank(r[:-1],p)
        with self.assertRaises(ValueError):study.rank(r+[r[0]],p)
    def test_rank_independent_of_completion_order(self):
        p=study.phase_plan('pitch',[],{});r=[mock_result(j) for j in p]
        self.assertEqual(study.rank(r,p),study.rank(r[::-1],p))
    def test_hardware_claim_refused(self):
        p=study.phase_plan('pitch',[],{});r=[mock_result(j) for j in p];r[0]['hardware_approved']=True
        with self.assertRaises(ValueError):study.rank(r,p)
    def test_unchanged_numeric_guard_and_filter(self):
        self.assertEqual(study.POLICY['command_filter'],study.ramp.core.COMMAND_FILTER)
        e=study.engine.JointLimitEnvelope
        model,qa,_,_,_=study.engine.load_model(study.engine.MODEL,.001)
        guard=e.from_model(model,qa,study.engine.load_contract())
        self.assertEqual(guard.reserve,.05)
        self.assertEqual(guard.reaction,.02)
        self.assertEqual(guard.brake,1.)
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):study.main(['--output',d])
    def test_invalid_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):study.main(['--output',str(Path(d)/'none'),'--workers','5'])
            self.assertFalse((Path(d)/'none').exists())
    def test_low_disk_refuses_before_simulation(self):
        with tempfile.TemporaryDirectory() as d,patch.object(study.shutil,'disk_usage',return_value=SimpleNamespace(free=1)):
            job=study.phase_plan('pitch',[],{})[0]
            with patch.object(study.ramp,'run_case') as run:
                with self.assertRaises(ValueError):study.run_case(job,d)
                run.assert_not_called()


class ScopeTest(unittest.TestCase):
    def test_only_wrist27_changed_by_adapter(self):
        c=study.engine.load_contract();p,d=study.engine.candidate_gains(c,*study.pj.BASE)
        with study.research_scope(study.specification(120.,2.,30.,1.4)):
            pp,dd=study.engine.candidate_gains(c,*study.pj.BASE)
            self.assertEqual(study.pj.KP_CAP,study.RESEARCH_CAP)
        p[27],d[27]=30.,1.4
        np.testing.assert_array_equal(p,pp);np.testing.assert_array_equal(d,dd)
        self.assertEqual(c.kp[27],20.)
    def test_restore_on_exception(self):
        cap,assign=study.pj.KP_CAP,study.engine.candidate_gains
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with study.research_scope(study.specification()):raise RuntimeError('injected')
        self.assertEqual(study.pj.KP_CAP,cap);self.assertIs(study.engine.candidate_gains,assign)
        self.assertFalse(study._ACTIVE_SCOPE)
    def test_nested_scope_and_bad_sentinel_refused(self):
        with study.research_scope(study.specification()):
            with self.assertRaises(ValueError):
                with study.research_scope(study.specification()):pass
            with self.assertRaises(ValueError):study.engine.candidate_gains(study.engine.load_contract(),40.,5.)
    def test_original_validator_still_refuses_extended_pitch(self):
        g=study.pj.Gains(**study.specification(120.)['candidate'])
        with self.assertRaises(ValueError):g.validate()
        with study.research_scope(study.specification(120.)):g.validate()
        with self.assertRaises(ValueError):g.validate()
        text=(Path(__file__).with_name('pd_gain_options.hpp')).read_text()
        self.assertIn('100.F',text)


class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=capture();cls.g=study.specification();cls.s=study.ramp.SCENARIOS[0]
        cls.original,cls.arrays=study.ramp.core.simulate(cls.c,study.pj.Gains(**cls.g['candidate']),cls.s)
    def test_exact_original_baseline(self):
        with study.research_scope(self.g):r,a=study.ramp.core.simulate(self.c,study.pj.Gains(**self.g['candidate']),self.s)
        self.assertEqual(r,self.original)
        for k in a:np.testing.assert_array_equal(a[k],self.arrays[k])
    def test_actual_extended_pitch_and_changed_wrist_are_auditable(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'inputs').mkdir();study.ramp.write_capture(folder,0,self.c)
            g=study.specification(120.,1.4,30.,1.)
            j=study.recorded_plan('pitch',[g],[('send',self.s)])[0]
            r=study.run_case(j,folder);rr,a=study.checked_case(folder,j,self.c)
            self.assertEqual(r,rr);self.assertTrue(r['completed']);self.assertFalse(r['legacy_hardware_gain_compatible'])
            self.assertEqual(r['gains_kp'][22],120.);self.assertEqual(r['gains_kp'][27],30.)
            self.assertFalse(np.array_equal(a['q'],self.arrays['q']))
            self.assertEqual(r['quality_policy'],study.ramp.core.POLICY)
    def test_wrist_gain_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'inputs').mkdir();study.ramp.write_capture(folder,0,self.c)
            j=study.recorded_plan('pitch',[self.g],[('send',self.s)])[0];r=study.run_case(j,folder)
            r['gains_kp'][27]=30.;study.save(folder/'cases'/(j['case_id']+'.json'),r)
            with self.assertRaises(ValueError):study.checked_case(folder,j,self.c)
    def test_synthetic_single_axis_adapts_wrist_and_pitch(self):
        g=study.specification(120.,1.4,30.,1.)
        j=study.previous.regression_plan([g['candidate']])[6];j['wrist_pitch']=g['wrist_pitch']
        with tempfile.TemporaryDirectory() as d:
            r=study.run_case(j,d);rr,a=study.checked_case(d,j,self.c)
            self.assertEqual(r,rr);self.assertEqual(r['gains_kp'][27],30.)
            self.assertTrue(r['completed'])


class BundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.log=cls.root/'fixture.jsonl';cls.out=cls.root/'run'
        dump(cls.log,fixture_rows())
        study.main(['--recording',str(cls.log),'--output',str(cls.out),'--workers','1','--smoke'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_complete_smoke_has_no_formal_selection(self):
        r=study.read(self.out/'summary.json');self.assertEqual(r['actual_runs'],5)
        self.assertTrue(study.audit(self.out)['passed']);self.assertIsNone(r['selected_filtered_pipeline_spec'])
    def test_grid_or_policy_tamper_refused(self):
        path=self.out/'manifest.json';old=path.read_bytes();m=study.read(path);m['grid']['wrist_kp']=[40.]
        try:
            study.save(path,m)
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:path.write_bytes(old)
    def test_phase_selection_tamper_refused(self):
        path=self.out/'plans/wrist.json';old=path.read_bytes();jobs=study.read(path);jobs[0]['wrist_pitch']['kp']=20.
        try:
            study.save(path,jobs)
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:path.write_bytes(old)
    def test_summary_tamper_refused(self):
        path=self.out/'summary.json';old=path.read_bytes();r=study.read(path);r['eligible']+=1
        try:
            study.save(path,r)
            with self.assertRaises(ValueError):study.audit(self.out)
        finally:path.write_bytes(old)


if __name__=='__main__':unittest.main()
