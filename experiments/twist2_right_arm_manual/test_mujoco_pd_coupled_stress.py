"""SDK-free tests: coupled parameter composition, frozen selection and evidence."""
import copy,itertools,json,math,tempfile,unittest
from dataclasses import asdict,replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_coupled_stress as coupled
import mujoco_pd_accuracy_stability as quality
import mujoco_pd_robust_refine as previous
import mujoco_pd_sweep as engine

class PlanAndMutationTest(unittest.TestCase):
    def test_exact_factorial_coverage(self):
        expected=set(itertools.product(*coupled.AXES))
        actual={(s.mass_scale,s.damping_scale,s.friction_scale,s.delay_s,s.lag_s,s.dt) for s in coupled.CALIBRATION[1:]}
        self.assertEqual(actual,expected);self.assertEqual(len(actual),64)
        self.assertEqual(len(coupled.CALIBRATION),65);self.assertEqual(len(coupled.PAIRS),12)
        self.assertEqual(len(coupled.jobs(coupled.PAIRS,coupled.CALIBRATION,'calibration','none')),780)
    def test_frozen_parameters_are_unique_and_bounded(self):
        conditions=coupled.CALIBRATION+coupled.VALIDATION
        self.assertEqual(len(conditions),81)
        self.assertEqual(len({s.identity for s in conditions}),81)
        pars=[tuple(asdict(s).values())[1:] for s in conditions]
        self.assertEqual(len(set(pars)),81)
        for s in conditions:s.validate()
        for p in coupled.PAIRS:engine.candidate_gains(engine.load_contract(),*p)
        self.assertEqual(coupled.new_conditions(),coupled.VALIDATION)
    def test_bad_scenarios_rejected(self):
        for change in ({'name':'../escape'},{'mass_scale':2.},{'damping_scale':0.},
           {'friction_scale':-1.},{'lag_s':math.nan},{'delay_s':.0007},{'dt':.002}):
            with self.assertRaises(ValueError):replace(coupled.Coupled('test'),**change).validate()
    def test_only_named_arm_parameters_mutate_and_limits_unchanged(self):
        m,qa,va,motors,_=engine.load_model(engine.MODEL,.001)
        limits=m.jnt_range.copy();damping=m.dof_damping.copy()
        s=coupled.Coupled('test',1.25,.5,.25)
        e=coupled.apply_model(m,qa,va,s)
        coupled.check_model_evidence({'study_scenario_contract':asdict(s),'coupled_model_evidence':e,
            'torque_path':{'delay_s':0.,'lag_s':0.}})
        np.testing.assert_array_equal(m.jnt_range,limits)
        np.testing.assert_array_equal(m.dof_damping[va[:22]],damping[va[:22]])
        self.assertEqual(len(e['dof_ids']),7)
    def test_mass_update_recomputes_constants(self):
        m,qa,va,_,_=engine.load_model(engine.MODEL,.001)
        with patch.object(mujoco,'mj_setConst',wraps=mujoco.mj_setConst) as call:
            coupled.apply_model(m,qa,va,coupled.Coupled('test',1.25))
            call.assert_called_once()
    def test_zero_mass_change_does_not_recompute(self):
        m,qa,va,_,_=engine.load_model(engine.MODEL,.001)
        with patch.object(mujoco,'mj_setConst',wraps=mujoco.mj_setConst) as call:
            coupled.apply_model(m,qa,va,coupled.Coupled('test'))
            call.assert_not_called()
    def test_infrastructure_failure_restores_all_hooks(self):
        load,step=engine.load_model,mujoco.mj_step
        with tempfile.TemporaryDirectory() as d,patch.object(quality,'run_case',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                coupled.run_case((100.,2.,asdict(coupled.Coupled('failure')),d,'fail','calibration'))
        self.assertIs(engine.load_model,load);self.assertIs(mujoco.mj_step,step)
    def test_strict_rmse_ranking_not_plateau(self):
        rows=[{'pair':[100.,1.275],'all_quality_pass':True},{'pair':[100.,1.3],'all_quality_pass':True}]
        self.assertIn((100.,1.275),coupled.choose(rows,[(100.,1.275),(100.,1.3)]))
    def test_failed_low_error_never_selected(self):
        rows=[{'pair':[96.,1.5],'all_quality_pass':False}]
        self.assertNotIn((96.,1.5),coupled.choose(rows,[(96.,1.5)]))
    def test_bad_worker_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out'
            with self.assertRaises(SystemExit):coupled.main(['--output',str(p),'--workers','0'])
            self.assertFalse(p.exists())

class DynamicsAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.study=cls.root/'smoke'
        with patch.object(coupled,'ProcessPoolExecutor',SerialPool):
            coupled.main(['--output',str(cls.study),'--workers','1','--smoke'])
        cls.nominal=coupled.read(cls.study/'cases/calibration_00000.json')
    def test_complete_audited_smoke(self):
        s=coupled.read(self.study/'summary.json');a=coupled.read(self.study/'audit.json')
        self.assertEqual(s['total_cases'],4);self.assertTrue(a['passed'])
        self.assertFalse(coupled.read(self.study/'manifest.json')['full_study'])
        self.assertFalse(s['all_possible_cases_tested']);self.assertIsNone(s['recommended_hardware_gains'])
    def compare(self,scenario,old_scenario,prefix):
        directory=self.root/prefix;directory.mkdir()
        old=quality.run_case((100.,1.275,asdict(old_scenario),str(directory),'old','calibration'))
        new=coupled.run_case((100.,1.275,asdict(scenario),str(directory),'new','calibration'))
        self.assertEqual(old['metrics'],new['metrics']);self.assertEqual(old['stability'],new['stability'])
        with np.load(directory/old['full_state_npz']) as a,np.load(directory/new['full_state_npz']) as b:
            for key in a.files:np.testing.assert_array_equal(a[key],b[key])
    def test_nominal_exactly_matches_original(self):
        self.compare(coupled.Coupled('plain'),previous.Scenario('model',('plain',.001,1.,1.,0.)),'nominal')
    def test_motor_only_matches_original(self):
        self.compare(coupled.Coupled('motor',1.,1.,.5,.002,.006),
          previous.Scenario('motor',('motor',.5,.002,.006,.001)),'motor')
    def test_model_only_matches_original(self):
        self.compare(coupled.Coupled('model',1.25,.5,1.),
          previous.Scenario('model',('model',.001,1.25,.5,0.)),'model')
    def test_other_source_files_unchanged(self):
        manifest=coupled.read(self.study/'manifest.json')
        for name,digest in manifest['source_sha256'].items():
            self.assertEqual(engine.sha256(engine.ROOT/name),digest)
    def tamper(self,path,change):
        target=self.study/path;data=target.read_bytes()
        try:
            value=coupled.read(target);change(value);coupled.save(target,value)
            with self.assertRaises(ValueError):coupled.audit(self.study)
        finally:target.write_bytes(data)
    def test_changed_coupled_parameter_refused(self):
        self.tamper('cases/calibration_00000.json',lambda v:v['study_scenario_contract'].update(delay_s=.001))
    def test_changed_model_mutation_refused(self):
        self.tamper('cases/calibration_00000.json',lambda v:v['coupled_model_evidence']['after']['mass'].__setitem__(0,1.))
    def test_changed_endpoint_result_refused(self):
        self.tamper('cases/calibration_00000.json',lambda v:v.update(quality_eligible=not v['quality_eligible']))
    def test_changed_summary_refused(self):
        self.tamper('summary.json',lambda v:v.update(quality_eligible=999))
    def test_frozen_selection_refused(self):
        self.tamper('selection.json',lambda v:v['calibration_case_hashes'].update(calibration_00000='0'*64))
    def test_manifest_objective_refused(self):
        self.tamper('manifest.json',lambda v:v.update(selection_rule='relaxed'))
    def test_full_trace_tampering_refused(self):
        target=self.study/self.nominal['full_state_npz'];data=target.read_bytes()
        try:
            target.write_bytes(data+b'changed')
            with self.assertRaisesRegex(ValueError,'Full-state hash'):coupled.audit(self.study)
        finally:target.write_bytes(data)
    def test_missing_case_refused(self):
        target=self.study/'cases/calibration_00000.json';data=target.read_bytes()
        try:
            target.unlink()
            with self.assertRaises(ValueError):coupled.audit(self.study)
        finally:target.write_bytes(data)
    def test_existing_output_not_overwritten(self):
        before=(self.study/'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):coupled.main(['--output',str(self.study),'--smoke'])
        self.assertEqual(before,(self.study/'manifest.json').read_bytes())

class SerialPool:
    def __init__(self,*args,**kwargs):pass
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def submit(self,fn,arg):
        from concurrent.futures import Future
        f=Future()
        try:f.set_result(fn(arg))
        except BaseException as error:f.set_exception(error)
        return f

if __name__=='__main__':unittest.main()
