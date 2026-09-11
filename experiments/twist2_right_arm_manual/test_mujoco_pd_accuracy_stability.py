"""Offline metric, selection, unchanged-engine and artifact regressions."""
from contextlib import contextmanager
import copy,json,math,os
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import mujoco_pd_accuracy_stability as study


def fixture():
    n=9*250
    q=np.zeros((n,29))
    return {'time_s':3.+np.arange(n)*.002,'trial_time_s':np.arange(n)*.002,
      'cycle':np.repeat(np.arange(3),750),
      'segment':np.tile(np.repeat(np.array(study.HOLDS),250),3),
      'q':q,'dq':q.copy(),'ref':q.copy(),'cmd':q.copy()}


class MetricAndPlanTest(unittest.TestCase):
    def test_zero_error_constant_hold(self):
        result=study.stability(fixture())
        self.assertTrue(result['passes']);self.assertEqual(len(result['holds']),9)
        self.assertTrue(all(r['tail_samples']==50 for r in result['holds']))
    def test_bias_not_mistaken_for_stability(self):
        a=fixture();a['q'][:,22]=.021
        result=study.stability(a)
        self.assertFalse(result['passes']);self.assertIn('max_q22_tail_error_rad',result['rejections'])
        self.assertEqual(result['max_right7_tail_p2p_rad'],0.)
    def test_wrist_motion_is_checked_not_only_shoulder(self):
        a=fixture();a['q'][:,28]=np.where(np.arange(len(a['q']))%2,.004,-.004)
        result=study.stability(a)
        self.assertFalse(result['passes']);self.assertIn('max_right7_tail_p2p_rad',result['rejections'])
        self.assertEqual(result['max_q22_tail_error_rad'],0.)
    def test_measured_speed_not_inferred_from_position(self):
        a=fixture();a['dq'][:,25]=.051
        result=study.stability(a)
        self.assertIn('max_right7_tail_rms_speed_rad_s',result['rejections'])
    def test_incomplete_hold_never_passes(self):
        a={k:v[:-251] for k,v in fixture().items()}
        self.assertFalse(study.stability(a)['passes'])
    def test_short_tail_never_passes(self):
        a=fixture();a['segment'][-240:]='interrupted'
        self.assertFalse(study.stability(a)['passes'])
    def test_nonfinite_any_joint_refused(self):
        for key in ('q','dq','ref','cmd'):
            a=fixture();a[key][0,1]=math.nan
            with self.assertRaises(ValueError):study.stability(a)
    def test_clock_gap_refused(self):
        a=fixture();a['time_s'][100]+=.003
        with self.assertRaises(ValueError):study.stability(a)
    def test_last100ms_not_entire_hold(self):
        a=fixture()
        a['q'][0,22]=1.
        self.assertTrue(study.stability(a)['passes'])
    def test_grid_bounds_and_original_conditions(self):
        self.assertEqual(len(study.PAIRS),12);self.assertEqual(len(study.CALIBRATION),35)
        self.assertEqual(len(study.VALIDATION),10)
        for p in study.PAIRS:study.engine.candidate_gains(study.engine.load_contract(),*p)
        for s in study.CALIBRATION+study.VALIDATION:s.validate()
        known={(s.family,s.parameters[1:]) for s in study.CALIBRATION}
        self.assertTrue(all((s.family,s.parameters[1:]) not in known for s in study.VALIDATION))
    def test_no_duplicate_scenario_names(self):
        all_s=study.CALIBRATION+study.VALIDATION
        self.assertEqual(len({s.identity for s in all_s}),len(all_s))
    def test_plateau_prefers_less_tail_motion(self):
        def r(p,error,speed):
            return {'pair':list(p),'all_quality_pass':True,'worst_rmse_rad':error,
              'worst_tail_rms_speed_rad_s':speed,'worst_tail_p2p_rad':speed*.1,'worst_q22_torque_nm':1.}
        ranking=[r((100,1.3),.01,.006),r((100,1.4),.01015,.003),r((100,2),.0103,.001)]
        self.assertEqual(study.preference(ranking)[0],[100,1.4])
        self.assertNotEqual(study.preference(ranking)[0],[100,2])
    def test_ineligible_low_error_is_not_preferred(self):
        r={'pair':[100,.1],'all_quality_pass':False,'worst_rmse_rad':None}
        self.assertEqual(study.preference([r]),[])
    def test_pareto_keeps_real_tradeoff(self):
        rows=[]
        for p,e,s in ((1,1,1),(2,2,2),(3,.5,2)):
            rows.append({'pair':[p,1],'all_quality_pass':True,'worst_rmse_rad':e,
              'worst_tail_rms_speed_rad_s':s,'worst_q22_torque_nm':1.})
        self.assertEqual(study.pareto(rows),[[1,1],[3,1]])
    def test_missing_condition_has_no_score(self):
        r=study.rank([],[(100,2)],study.CALIBRATION,'calibration')[0]
        self.assertFalse(r['all_quality_pass']);self.assertIsNone(r['worst_rmse_rad'])
    def test_capture_hook_restored_on_exception(self):
        original=study.engine.run_candidate
        with patch.object(study.previous,'run_case',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):study.run_case(None)
        self.assertIs(study.engine.run_candidate,original)
    def test_bad_worker_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'must_not_exist'
            with self.assertRaises(SystemExit):study.main(['--output',str(dest),'--workers','0'])
            self.assertFalse(dest.exists())


class RealSmokeAndAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'results'
        cls.engine_hash=study.engine.sha256(Path(study.engine.__file__))
        p=subprocess.run([sys.executable,'-B',str(Path(study.__file__)),'--smoke','--workers','2','--output',str(cls.root)],
                         capture_output=True,text=True,timeout=150)
        if p.returncode:raise AssertionError(p.stdout+p.stderr)
        cls.case=sorted((cls.root/'cases').glob('*.json'))[0]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    @contextmanager
    def changed(self,path,value):
        old=path.read_bytes()
        path.write_text(json.dumps(value),encoding='utf-8')
        try:yield
        finally:path.write_bytes(old)
    def test_real_smoke_audited_and_no_engine_change(self):
        summary=study.read(self.root/'summary.json');audit=study.audit(self.root)
        self.assertEqual(summary['total_cases'],4);self.assertTrue(audit['passed'])
        self.assertFalse(study.read(self.root/'manifest.json')['full_study'])
        self.assertEqual(self.engine_hash,study.engine.sha256(Path(study.engine.__file__)))
    def test_full_29_state_traces_retained(self):
        for p in (self.root/'cases').glob('*.json'):
            r=study.read(p)
            with np.load(self.root/r['full_state_npz']) as a:
                self.assertEqual(a['q'].shape[1],29);self.assertEqual(a['dq'].shape,a['q'].shape)
            self.assertTrue(r['joint_limit_guard']['no_intervention'])
            self.assertEqual(r['joint_limit_guard']['event'],None)
    def test_summary_tampering_refused(self):
        p=self.root/'summary.json';v=study.read(p);v['quality_eligible']=0
        with self.changed(p,v),self.assertRaises(ValueError):study.audit(self.root)
    def test_policy_tampering_refused(self):
        p=self.root/'manifest.json';v=study.read(p);v['quality_policy']['right7_tail_p2p_rad']=1.
        with self.changed(p,v),self.assertRaises(ValueError):study.audit(self.root)
    def test_case_stability_tampering_refused(self):
        v=study.read(self.case);v['stability']['max_right7_tail_p2p_rad']+=.1
        with self.changed(self.case,v),self.assertRaises(ValueError):study.audit(self.root)
    def test_full_trace_tampering_refused(self):
        r=study.read(self.case);p=self.root/r['full_state_npz'];old=p.read_bytes();p.write_bytes(old+b'bad')
        try:
            with self.assertRaises(ValueError):study.audit(self.root)
        finally:p.write_bytes(old)
    def test_missing_case_refused(self):
        old=self.case.read_bytes();self.case.unlink()
        try:
            with self.assertRaises(ValueError):study.audit(self.root)
        finally:self.case.write_bytes(old)
    def test_selection_changed_after_calibration_refused(self):
        p=self.root/'selection.json';v=study.read(p);v['pairs']=[]
        with self.changed(p,v),self.assertRaises(ValueError):study.audit(self.root)
    def test_existing_output_preserved(self):
        digest=study.engine.sha256(self.root/'summary.json')
        with self.assertRaises(FileExistsError):study.main(['--smoke','--output',str(self.root)])
        self.assertEqual(digest,study.engine.sha256(self.root/'summary.json'))


if __name__=='__main__':unittest.main()
