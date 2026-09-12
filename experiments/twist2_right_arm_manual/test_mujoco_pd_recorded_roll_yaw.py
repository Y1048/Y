"""Memory-only planning, scoped research and real offline replay regressions."""
import copy, json, tempfile, unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco_pd_recorded_roll_yaw as study
import test_mujoco_pd_recorded as fixture

class PlanTest(unittest.TestCase):
    def fake(self,job,score=.02,good=True):
        return dict(job,completed=good,eligible=good,reason='' if good else 'injected failure',exclusions=[] if good else ['failure'],
          metrics={'max_right7_recorded_rmse_rad':score},simulation_only=True,hardware_approved=False,
          recommended_hardware_gains=None,hardware_config_modified=False)
    def test_yaw_grid_unique_equal_conditions(self):
        jobs=study.phase_plan('yaw',[],{})
        self.assertEqual(len(jobs),108)
        groups={study.identity(j['candidate']) for j in jobs};self.assertEqual(len(groups),36)
        for g in groups:
            self.assertEqual({(j['clock'],j['scenario']['name']) for j in jobs if study.identity(j['candidate'])==g},
              {('send','nominal'),('send','delay_boundary'),('sample','delay_boundary')})
    def test_roll_grid_and_boundaries(self):
        jobs=study.phase_plan('yaw',[],{},True);rs=[self.fake(j) for j in jobs]
        plan=study.phase_plan('roll',rs,{'yaw':jobs})
        self.assertEqual(len(plan),60)
        self.assertEqual({j['candidate']['kp'][1] for j in plan},{250.,275.,300.,325.,350.})
    def test_only_roll_research_bound_extended(self):
        study.validate_vector(study.vector(rollp=350.))
        for index in (0,2,3):
            g=study.vector();g['kp'][index]=101
            with self.assertRaises(ValueError):study.validate_vector(g)
        with self.assertRaises(ValueError):study.validate_vector(study.vector(rollp=351.))
    def test_boolean_and_nonfinite_rejected(self):
        for value in (True,float('nan'),float('inf'),0):
            g=study.vector();g['kp'][1]=value
            with self.assertRaises(ValueError):study.validate_vector(g)
    def test_scope_restoration_exception(self):
        before=study.pj.KP_CAP
        with self.assertRaisesRegex(RuntimeError,'injected'):
            with study.research_scope():
                study.pj.Gains(**study.vector(rollp=350.)).validate();raise RuntimeError('injected')
        self.assertEqual(study.pj.KP_CAP,before)
    def test_original_bound_still_refuses325(self):
        with self.assertRaises(ValueError):study.pj.Gains(**study.vector(rollp=325.)).validate()
    def test_nested_scope_rejected(self):
        with study.research_scope():
            with self.assertRaises(ValueError):
                with study.research_scope():pass
        self.assertEqual(study.pj.KP_CAP,(100.,300.,100.,100.))
    def test_missing_case_refused(self):
        jobs=study.phase_plan('yaw',[],{},True)
        with self.assertRaises(ValueError):study.rank([self.fake(jobs[0])],jobs)
    def test_failure_not_hidden_by_low_error(self):
        jobs=study.phase_plan('yaw',[],{},True)
        rs=[self.fake(jobs[0],.001,False),self.fake(jobs[1],.02,True)]
        self.assertEqual(study.top(rs,jobs),[jobs[1]['candidate']])
    def test_all_fail_no_fabricated_roll_plan(self):
        jobs=study.phase_plan('yaw',[],{},True);rs=[self.fake(j,good=False) for j in jobs]
        self.assertEqual(study.phase_plan('roll',rs,{'yaw':jobs}),[])
    def test_ranking_order_invariant(self):
        jobs=study.phase_plan('yaw',[],{},True);rs=[self.fake(j) for j in jobs]
        self.assertEqual(study.rank(rs,jobs),study.rank(rs[::-1],jobs))
    def test_wrong_gain_refused(self):
        jobs=study.phase_plan('yaw',[],{},True);rs=[self.fake(j) for j in jobs]
        rs[0]=copy.deepcopy(rs[0]);rs[0]['candidate']['kp'][2]+=1
        with self.assertRaises(ValueError):study.rank(rs,jobs)
    def test_14regression_cases(self):
        p=study.regression_plan([study.vector()]);self.assertEqual(len(p),14)
        self.assertEqual(sum(j['kind']=='single' for j in p),8)
        self.assertEqual(sum(j['kind']=='independent' for j in p),6)
        for j in p:
            if j['kind']=='single':study.multi.Motion(**j['motion']).validate()
            else:study.independent.core.Motion(**j['motion']).validate()
    def test_invalid_phase(self):
        with self.assertRaises(ValueError):study.phase_plan('typo',[],{})
    def test_no_changed_filter_or_guard(self):
        self.assertEqual(study.POLICY['command_filter'],study.ramp.core.COMMAND_FILTER)
        self.assertEqual(study.POLICY['command_filter']['interval_s'],.02)
        self.assertEqual(study.POLICY['live_kp_cap_unchanged'],100.)
    def test_invalid_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'no'
            with self.assertRaises(SystemExit):study.main(['--output',str(out),'--workers','0'])
            self.assertFalse(out.exists())

class DynamicsTest(unittest.TestCase):
    def test_exact_baseline_and_real_extended_roll(self):
        c=fixture.capture();sc=study.ramp.SCENARIOS[0]
        baseline,ba=study.ramp.core.simulate(c,study.pj.Gains(**study.vector(64.,1.)),sc)
        with tempfile.TemporaryDirectory() as d:
            f=Path(d);(f/'inputs').mkdir();study.ramp.write_capture(f,0,c)
            job=study.recorded_plan('test',[study.vector(64.,1.)],[('send',sc)])[0]
            r=study.run_case(job,f);_,a=study.checked_case(f,job,c)
            self.assertEqual(r['metrics'],baseline['metrics'])
            for k in a:np.testing.assert_array_equal(a[k],ba[k])
            job=study.recorded_plan('extended',[study.vector(64.,1.,350.,4.)],[('send',sc)])[0]
            r=study.run_case(job,f);study.checked_case(f,job,c)
            self.assertEqual(r['gains_kp'][23],350.)
            self.assertFalse(r['legacy_hardware_gain_compatible']);self.assertFalse(r['hardware_approved'])
            self.assertEqual(study.pj.KP_CAP,(100.,300.,100.,100.))
    def test_single_axis_extended_record_and_audit(self):
        job=next(j for j in study.regression_plan([study.vector(rollp=325.)]) if j['kind']=='single')
        with tempfile.TemporaryDirectory() as d:
            r=study.run_case(job,d);checked,a=study.checked_case(d,job,fixture.capture())
            self.assertEqual(r,checked);self.assertEqual(a['q'].shape[1],29)
            self.assertEqual(r['gains_kp'][23],325.)

class BundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.folder=cls.root/'results'
        raw=cls.root/'fixture.jsonl';fixture.dump(raw,fixture.fixture_rows())
        study.main(['--recording',str(raw),'--output',str(cls.folder),'--workers','2','--smoke'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_smoke_not_hardware_or_final_selection(self):
        s=study.read(self.folder/'summary.json');self.assertTrue(s['complete'])
        self.assertEqual(s['actual_runs'],5);self.assertIsNone(s['selected_filtered_pipeline_vector'])
        self.assertFalse(s['hardware_approved']);self.assertTrue(study.audit(self.folder)['passed'])
    def test_manifest_grid_tamper(self):
        path=self.folder/'manifest.json';raw=path.read_bytes();m=study.read(path);m['roll_kp']=[900]
        try:
            study.save(path,m)
            with self.assertRaises(ValueError):study.audit(self.folder)
        finally:path.write_bytes(raw)
    def test_summary_tamper(self):
        path=self.folder/'summary.json';raw=path.read_bytes();s=study.read(path);s['eligible']+=1
        try:
            study.save(path,s)
            with self.assertRaises(ValueError):study.audit(self.folder)
        finally:path.write_bytes(raw)
    def test_stage_selection_tamper(self):
        path=self.folder/'plans/roll.json';raw=path.read_bytes();p=study.read(path);p[0]['candidate']['kp'][1]=300
        try:
            study.save(path,p)
            with self.assertRaises(ValueError):study.audit(self.folder)
        finally:path.write_bytes(raw)
    def test_trace_tamper(self):
        path=next((self.folder/'full_state').glob('*.npz'));raw=path.read_bytes()
        try:
            path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            with self.assertRaises(ValueError):study.audit(self.folder)
        finally:path.write_bytes(raw)
    def test_existing_output_preserved(self):
        with self.assertRaises(ValueError):study.main(['--output',str(self.folder)])
        self.assertTrue((self.folder/'summary.json').exists())

if __name__=='__main__':unittest.main()
