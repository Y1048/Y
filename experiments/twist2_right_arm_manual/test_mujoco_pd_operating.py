"""SDK-free reference, actual dynamics, endpoint/limit and artifact regressions."""
from dataclasses import asdict,replace
import copy,json,math
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_operating_core as core
import mujoco_pd_operating_study as study
import mujoco_pd_sweep as engine
import mujoco_pd_coupled_stress as coupled

class PlanTest(unittest.TestCase):
    def test_full_plan_counts_and_unique(self):
        plan=study.make_plan();self.assertEqual(len(plan),1728)
        ids={j['case_id'] for j in plan};self.assertEqual(len(ids),1728)
        self.assertEqual(sum(j['phase']=='main' for j in plan),1440)
        self.assertEqual(sum(j['phase']=='long' for j in plan),288)
    def test_every_pair_has_every_declared_cell(self):
        plan=study.make_plan();conditions=None
        for p,d in study.PAIRS:
            observed={(j['profile']['name'],j['scenario']['name'],j['phase']) for j in plan if j['kp']==p and j['kd']==d}
            if conditions is None:conditions=observed
            self.assertEqual(observed,conditions);self.assertEqual(len(observed),144)
    def test_all_proximal_axes_and_long_profiles_present(self):
        normal,long=study.profiles();self.assertEqual({p.joint for p in normal},set(range(22,26)))
        self.assertEqual(len(normal),20);self.assertEqual(len(long),12)
        self.assertTrue(any(p.cycles==12 for p in long));self.assertTrue(any(p.post_hold_s==30 for p in long))
        self.assertTrue(any(p.elbow_offset_deg<0 for p in long))
    def test_default_reference_exact_inherited_parity(self):
        a,b=core.Path(core.Profile()),core.RoundTrip()
        self.assertEqual(a.total,b.total)
        for t in np.linspace(0,b.total+1,10000):self.assertEqual(a.at(float(t)),b.at(float(t)))
    def test_generalized_derivatives_and_caps(self):
        normal,long=study.profiles()
        for p in normal+long:
            path=core.Path(p);t=1+.4*path.outbound;h=1e-5
            point=path.at(t)
            self.assertAlmostEqual((path.at(t+h).offset-path.at(t-h).offset)/(2*h),point.velocity,places=7)
            self.assertLessEqual(1.875*path.offset/path.outbound,path.speed+1e-12)
            self.assertLessEqual((10/math.sqrt(3))*path.offset/path.outbound**2,path.acceleration+1e-12)
    def test_profile_bounds_fail_closed(self):
        for p in (core.Profile(joint=26),core.Profile(amplitude_deg=13),core.Profile(speed_deg_s=31),
                  core.Profile(cycles=2),core.Profile(cycles=3.0),core.Profile(elbow_offset_deg=11),
                  core.Profile(post_hold_s=31),core.Profile(amplitude_deg=math.nan)):
            with self.assertRaises(ValueError):p.validate()
    def test_invalid_time(self):
        for t in (math.nan,math.inf,-1):
            with self.assertRaises(ValueError):core.Path(core.Profile()).at(t)
    def test_post_hold_and_cycles_explicit(self):
        p=core.Path(core.Profile(cycles=12,post_hold_s=30))
        self.assertEqual(p.at(p.motion_total+1).segment,'post_hold')
        self.assertEqual(p.at(p.motion_total+1).cycle,12)
        self.assertEqual(p.at(p.total).segment,'done')
    def test_original_contract_and_live_defaults_not_mutated(self):
        before=engine.load_contract();other=core.profile_contract(core.Profile(elbow_offset_deg=10))
        self.assertNotEqual(before.baseline[25],other.baseline[25])
        np.testing.assert_array_equal(engine.load_contract().baseline,before.baseline)
        for key in ('lower','upper','kp','kd','torque'):np.testing.assert_array_equal(getattr(before,key),getattr(other,key))
    def test_bad_workers_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'new'
            with self.assertRaises(SystemExit):study.main(['--output',str(path),'--workers','9'])
            self.assertFalse(path.exists())
    def test_missing_or_duplicate_cell_never_complete(self):
        with self.assertRaises(ValueError):study.summarize([],study.make_plan(True),'x')
    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            marker=Path(td)/'keep';marker.write_text('untouched')
            with self.assertRaises(FileExistsError):study.main(['--output',td,'--smoke'])
            self.assertEqual(marker.read_text(),'untouched')

class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result,cls.arrays=core.simulate(core.Profile(),100.,1.4,core.Coupled('nominal'))
    def test_all29_nominal_exact_inherited_dynamics(self):
        m,qa,va,motors,_=engine.load_model(engine.MODEL,.001)
        old,rows=engine.run_candidate(m,qa,va,motors,engine.load_contract(),100.,1.4)
        for k in ('q','dq','ref','cmd'):
            expected=np.array([[r[f'{k}_{j}'] for j in range(29)] for r in rows])
            np.testing.assert_array_equal(self.arrays[k],expected)
        self.assertEqual(self.result['metrics']['active_rmse_rad'],old['metrics']['reference_rmse_joint22_rad'])
    def test_perturbed_exact_coupled_parity(self):
        s=core.Coupled('test_heavy',1.1,.8,.5,.002,.004)
        new,a=core.simulate(core.Profile(),100.,2.,s)
        with tempfile.TemporaryDirectory() as td:
            old=coupled.run_case((100.,2.,asdict(s),td,'old','parity'))
            with np.load(Path(td)/old['full_state_npz'],allow_pickle=False) as z:
                for k in ('q','dq','ref','cmd'):np.testing.assert_array_equal(a[k],z[k])
    def test_non_pitch_axis_is_actually_excited(self):
        r,a=core.simulate(core.Profile(joint=24),100.,1.4,core.Coupled('nominal'))
        self.assertGreater(float(np.ptp(a['ref'][:,24])),.27)
        self.assertEqual(float(np.ptp(a['ref'][:,22])),0.)
        self.assertTrue(r['completed'])
    def test_roll_failure_not_hidden_by_pitch_error(self):
        r,a=core.simulate(core.Profile(joint=23),100.,1.4,core.Coupled('nominal'))
        self.assertTrue(r['completed']);self.assertFalse(r['eligible'])
        self.assertIn('active_tail_error_rad',r['exclusions'])
    def test_unsafe_initial_reference_never_integrates(self):
        contract=engine.load_contract();q=contract.baseline.copy();q[22]=contract.upper[22]-.01
        with patch.object(core,'profile_contract',return_value=replace(contract,baseline=q)),patch.object(mujoco,'mj_step',side_effect=AssertionError('Must not integrate')):
            r,a=core.simulate(core.Profile(),100.,1.4,core.Coupled('nominal'))
        self.assertFalse(r['completed']);self.assertEqual(r['physics']['steps'],0)
    def test_final_step_limit_violation_refused(self):
        original=mujoco.mj_step;path=core.Path(core.Profile());dt=.001
        final=(round(engine.WARMUP/dt)+math.ceil(path.total/dt))*dt
        def corrupt(m,d):
            original(m,d)
            if d.time>=final-1e-7:d.qpos[0]=m.jnt_range[0,1]+.001
        with patch.object(mujoco,'mj_step',side_effect=corrupt):r,a=core.simulate(core.Profile(),100.,1.4,core.Coupled('nominal'))
        self.assertFalse(r['completed']);self.assertFalse(r['eligible']);self.assertIsNotNone(r['joint_limit_guard']['event'])
    def test_all_state_rows_and_final_guard_coverage(self):
        self.assertEqual(self.arrays['q'].shape,(9133,29))
        study.check_guard(self.result,self.arrays)
        self.assertEqual(self.result['joint_limit_guard']['observations'],2*self.result['physics']['steps'])
    def test_saved_reference_matches_analytic_path(self):study.check_reference(self.result,self.arrays)
    def test_reference_tampering_detected(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['ref'][0,1]+=.01
        with self.assertRaises(ValueError):study.check_reference(self.result,a)
    def test_clock_gap_refused(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['time_s'][2]+=.001
        with self.assertRaises(ValueError):core.evaluate(a,core.Profile(),True,'',self.result['physics'])
    def test_nonfinite_nonactive_axis_refused(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['q'][0,0]=math.nan
        with self.assertRaises(ValueError):core.evaluate(a,core.Profile(),True,'',self.result['physics'])
    def test_bias_without_motion_is_not_accurate(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['q'][:,22]=a['ref'][:,22]+.03;a['dq'][:,22]=0
        r=core.evaluate(a,core.Profile(),True,'',self.result['physics'])
        self.assertFalse(r['eligible']);self.assertIn('active_tail_error_rad',r['exclusions'])
    def test_wrist_tail_motion_is_checked(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['dq'][:,28]=.1
        r=core.evaluate(a,core.Profile(),True,'',self.result['physics'])
        self.assertIn('right7_tail_rms_speed_rad_s',r['exclusions'])
    def test_contact_any_physics_step_refused(self):
        physics=dict(self.result['physics']);physics['contact_steps']=1
        r=core.evaluate(self.arrays,core.Profile(),True,'',physics)
        self.assertIn('contact_influenced_including_warmup',r['exclusions'])
    def test_missing_holds_fail_closed(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['segment'][a['segment']=='negative_hold']='other'
        r=core.evaluate(a,core.Profile(),True,'',self.result['physics'])
        self.assertIn('incomplete_hold_tails',r['exclusions'])
    def test_post_hold_last_second_has_strict_check(self):
        p=core.Profile(post_hold_s=1.)
        r,a=core.simulate(p,100.,1.4,core.Coupled('nominal'))
        self.assertIn('post_hold_last_second_error_rad',r['metrics'])
        ids=np.flatnonzero(a['segment']=='post_hold');a['dq'][ids[-400],22]=.11
        check=core.evaluate(a,p,True,'',r['physics'])
        self.assertIn('post_hold_last_second_not_settled',check['exclusions'])

class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name)/'run'
        study.main(['--output',str(cls.folder),'--smoke','--workers','2'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def copy_run(self):
        import shutil
        td=tempfile.TemporaryDirectory();dest=Path(td.name)/'copy';shutil.copytree(self.folder,dest);return td,dest
    def test_real_smoke_audit_includes_failure(self):
        audit=study.audit(self.folder);summary=study.read(self.folder/'summary.json')
        self.assertTrue(audit['passed']);self.assertEqual(audit['cases'],2)
        self.assertEqual(summary['rejected'],1);self.assertIsNone(summary['minimum_fully_passing_pair'])
    def test_full_trace_tampering_refused(self):
        td,p=self.copy_run()
        with td:
            f=next((p/'full_state').glob('*.npz'));f.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):study.audit(p)
    def test_score_tampering_refused(self):
        td,p=self.copy_run()
        with td:
            f=next((p/'cases').glob('*.json'));r=study.read(f);r['metrics']['active_rmse_rad']=0.;study.save(f,r)
            with self.assertRaises(ValueError):study.audit(p)
    def test_policy_tampering_refused(self):
        td,p=self.copy_run()
        with td:
            f=p/'manifest.json';r=study.read(f);r['quality_policy']['active_tail_error_rad']=1.;study.save(f,r)
            with self.assertRaises(ValueError):study.audit(p)
    def test_summary_tampering_refused(self):
        td,p=self.copy_run()
        with td:
            f=p/'summary.json';r=study.read(f);r['eligible']=2;study.save(f,r)
            with self.assertRaises(ValueError):study.audit(p)
    def test_missing_matrix_cell_refused(self):
        td,p=self.copy_run()
        with td:
            next((p/'cases').glob('*.json')).unlink()
            with self.assertRaises(ValueError):study.audit(p)
    def test_missing_final_guard_state_refused(self):
        td,p=self.copy_run()
        with td:
            f=next((p/'cases').glob('*.json'));r=study.read(f);r['joint_limit_guard']['observations']-=1;study.save(f,r)
            with self.assertRaises(ValueError):study.audit(p)
    def test_model_evidence_tampering_refused(self):
        td,p=self.copy_run()
        with td:
            f=next((p/'cases').glob('*.json'));r=study.read(f);r['model_evidence']['after']['mass'][1]+=1.;study.save(f,r)
            with self.assertRaises(ValueError):study.audit(p)

if __name__=='__main__':unittest.main()
