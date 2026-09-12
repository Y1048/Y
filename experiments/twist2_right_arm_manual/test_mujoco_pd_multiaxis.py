"""Simultaneous-reference parity, safety and fail-closed result tests. No DDS."""
from contextlib import contextmanager
from dataclasses import asdict,replace
import itertools,json,math
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_multiaxis as multi
import mujoco_pd_multiaxis_study as study
pj=multi.pj

class PlanTest(unittest.TestCase):
    def test_288_unique_cells(self):
        jobs=study.plan();self.assertEqual(len(jobs),288)
        self.assertEqual(len({j['case_id'] for j in jobs}),288)
        self.assertEqual(sum(j['phase']=='main' for j in jobs),256)
        self.assertEqual(sum(j['phase']=='long' for j in jobs),32)
    def test_all_16_signs_and_same_conditions_for_candidates(self):
        jobs=study.plan();self.assertEqual({tuple(j['motion']['scales']) for j in jobs},set(itertools.product((-1.,1.),repeat=4)))
        groups=[[dict(motion=j['motion'],scenario=j['scenario'],phase=j['phase']) for j in jobs if j['candidate']==study.norm(asdict(g))] for g in study.VECTORS]
        self.assertEqual(groups[0],groups[1])
    def test_all_motion_bounds_before_dynamics(self):
        for job in study.plan():
            p=multi.Motion(**job['motion']);p.validate();pj.Gains(**job['candidate']).validate()
            self.assertLessEqual(p.amplitude_deg,12);self.assertLessEqual(p.speed_deg_s,30)
    def test_invalid_scales(self):
        for value in ((),(1.,)*5,(0.,)*4,(2.,1.,1.,1.),(math.nan,1.,1.,1.)):
            with self.assertRaises(ValueError):multi.Motion(scales=value).validate()
    def test_no_expanded_physical_gain_cap(self):
        with self.assertRaises(ValueError):multi.engine.candidate_gains(multi.engine.load_contract(),300.,4.)
        with self.assertRaises(ValueError):pj.Gains((100.,301.,100.,100.)).validate()
    def test_signed_reference_and_extrema(self):
        m=multi.Motion(scales=(1.,-.5,0.,-1.));q=multi.profile_contract(m.profile()).baseline
        path=multi.Path(m.profile());p=path.at(1+path.outbound)
        actual=m.reference(q,p);expected=q.copy();expected[22:26]+=np.array(m.scales)*math.radians(8)
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-14)
        lo,hi=m.extrema(q);self.assertTrue(np.all(actual>=lo-1e-14) and np.all(actual<=hi+1e-14))
        np.testing.assert_array_equal(q,multi.profile_contract(m.profile()).baseline)
    def test_invalid_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'result'
            with self.assertRaises(SystemExit):study.main(['--output',str(dest),'--workers','0'])
            self.assertFalse(dest.exists())
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):study.main(['--output',d])
    def test_profile_and_gain_input_immutable(self):
        a=multi.Motion();b=pj.Gains();self.assertEqual(a.scales,(1.,1.,1.,1.));self.assertEqual(b.kp,(100.,100.,100.,100.))
    def test_network_forbidden_worker(self):
        code="import sys;sys.path.insert(0,"+repr(str(Path(__file__).parent))+");import mujoco_pd_expand as e;e.init_worker();import mujoco;import socket\ntry:\n socket.socket()\nexcept RuntimeError:\n print('blocked')\nelse:\n raise SystemExit(3)\n"
        r=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('blocked',r.stdout)

class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motion=multi.Motion(post_hold_s=2.);cls.gains=study.VECTORS[0];cls.scenario=study.SCENARIOS[0]
        cls.r,cls.a=multi.simulate(cls.motion,cls.gains,cls.scenario)
    def test_actual_simultaneous_motion(self):
        for j in range(22,26):
            self.assertGreater(np.ptp(self.a['ref'][:,j]),.2)
            self.assertGreater(np.ptp(self.a['q'][:,j]),.1)
        for j in tuple(range(22))+tuple(range(26,29)):
            self.assertEqual(np.ptp(self.a['ref'][:,j]),0.)
    def test_full29_and_vector_torques(self):
        for name in ('q','dq','ref','cmd','requested','actual_tau'):self.assertEqual(self.a[name].shape[1],29)
        np.testing.assert_allclose(np.asarray(self.r['gains_kp'])*(self.a['cmd']-self.a['q'])-np.asarray(self.r['gains_kd'])*self.a['dq'],self.a['requested'],rtol=1e-12,atol=1e-12)
    def test_all_four_endpoint_gates_present(self):
        self.assertEqual(len(self.r['axis_evaluations']),4)
        self.assertEqual(self.r['eligible'],all(v['eligible'] for v in self.r['axis_evaluations']))
    def test_individual_axis_exact_legacy_parity(self):
        for joint in range(22,26):
            with self.subTest(joint=joint):
                scales=[0.]*4;scales[joint-22]=1.
                motion=multi.Motion(f'parity{joint}',tuple(scales));g=self.gains;s=self.scenario
                old,oa=pj.simulate(motion.profile(joint),g,s);new,na=multi.simulate(motion,g,s)
                for name in oa:np.testing.assert_array_equal(oa[name],na[name])
                self.assertEqual(old['joint_limit_guard'],new['joint_limit_guard'])
                self.assertEqual(old['physics'],new['physics'])
                self.assertEqual(old['final_q'],new['final_q'])
    def test_stationary_joint_bias_not_hidden(self):
        altered={k:v.copy() for k,v in self.a.items()};altered['q'][:,24]+=.05
        r=multi.evaluate(altered,self.motion,True,'',self.r['physics'])
        self.assertFalse(r['eligible']);self.assertIn('joint24:active_tail_error_rad',r['exclusions'])
    def test_hold_velocity_not_hidden(self):
        altered={k:v.copy() for k,v in self.a.items()};altered['dq'][:,25]=.2
        r=multi.evaluate(altered,self.motion,True,'',self.r['physics']);self.assertFalse(r['eligible'])
    def test_contact_rejects(self):
        r=multi.evaluate(self.a,self.motion,True,'',dict(self.r['physics'],contact_steps=1))
        self.assertFalse(r['eligible'])
    def test_last_state_guard_present(self):
        from mujoco_pd_operating_study import check_guard
        check_guard(self.r,self.a)
        self.assertEqual(self.r['joint_limit_guard']['observations'],2*self.r['physics']['steps'])
    def test_command_on_limit_refused_before_success(self):
        def wrong(ref,old,q,dq,kp,kd,contract):
            v=old.copy();v[23]=contract.upper[23];return v,np.zeros(29,dtype=bool),np.zeros(29,dtype=bool)
        with patch.object(multi.engine,'writer_target',wrong):
            r,a=multi.simulate(self.motion,self.gains,self.scenario)
        self.assertFalse(r['completed']);self.assertFalse(r['eligible']);self.assertIsNotNone(r['joint_limit_guard']['event'])
    def test_nonfinite_nonactive_joint_refused(self):
        altered={k:v.copy() for k,v in self.a.items()};altered['q'][0,0]=np.nan
        with self.assertRaises(ValueError):multi.evaluate(altered,self.motion,True,'',self.r['physics'])
    def test_not_hardware_approved(self):
        self.assertFalse(self.r['hardware_approved']);self.assertIsNone(self.r['recommended_hardware_gains'])

@contextmanager
def changed(path,value):
    original=path.read_bytes()
    try:
        path.write_text(json.dumps(value),encoding='utf-8');yield
    finally:path.write_bytes(original)

class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)/'smoke'
        r=subprocess.run([sys.executable,'-B',str(Path(study.__file__)),'--output',str(cls.folder),'--workers','2','--smoke'],capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        cls.jobs=study.read(cls.folder/'plan.json');cls.job=cls.jobs[0];cls.path=cls.folder/'cases'/(cls.job['case_id']+'.json')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_smoke_is_audited_not_full(self):
        r=study.audit(self.folder);self.assertEqual(r['cases'],2)
        s=study.read(self.folder/'summary.json');self.assertFalse(s['full_study']);self.assertIsNone(s['selected_simulation_vector'])
    def test_recorded_gain_tampering(self):
        r=study.read(self.path);r['gains_kp'][23]-=1
        with changed(self.path,r),self.assertRaises(ValueError):study.audit_case(self.folder,self.job)
    def test_metrics_tampering(self):
        r=study.read(self.path);r['metrics']['max_proximal_rmse_rad']=0.
        with changed(self.path,r),self.assertRaises(ValueError):study.audit_case(self.folder,self.job)
    def test_hardware_claim_tampering(self):
        r=study.read(self.path);r['hardware_approved']=True
        with changed(self.path,r),self.assertRaises(ValueError):study.audit_case(self.folder,self.job)
    def test_trace_tampering(self):
        r=study.read(self.path);p=study.safe_path(self.folder,r['trace']);old=p.read_bytes()
        try:
            p.write_bytes(old+b'x')
            with self.assertRaises(ValueError):study.audit_case(self.folder,self.job)
        finally:p.write_bytes(old)
    def test_missing_cell(self):
        jobs=study.plan(True);records=[study.read(self.folder/'cases'/(j['case_id']+'.json')) for j in jobs]
        with self.assertRaises(ValueError):study.summary(records[:-1],jobs,'hash',True)
    def test_ordering_is_deterministic(self):
        jobs=study.plan(True);records=[study.read(self.folder/'cases'/(j['case_id']+'.json')) for j in jobs]
        self.assertEqual(study.summary(records,jobs,'hash',True),study.summary(records[::-1],jobs,'hash',True))
    def test_archive_tampering(self):
        m=study.read(self.folder/'manifest.json');p=study.safe_path(self.folder/'frozen_source',next(iter(m['source_sha256'])))
        old=p.read_bytes()
        try:
            p.write_bytes(old+b'\n')
            with self.assertRaises(ValueError):study.audit(self.folder)
        finally:p.write_bytes(old)
    def test_plan_tampering(self):
        p=self.folder/'plan.json';x=study.read(p);x[0]['motion']['scales'][0]*=-1
        with changed(p,x),self.assertRaises(ValueError):study.audit(self.folder)
    def test_policy_tampering(self):
        p=self.folder/'manifest.json';x=study.read(p);x['quality_policy']['active_tail_error_rad']=1.
        with changed(p,x),self.assertRaises(ValueError):study.audit(self.folder)
    def test_failed_low_error_has_no_score(self):
        jobs=study.plan(True);records=[study.read(self.folder/'cases'/(j['case_id']+'.json')) for j in jobs]
        records[0]['eligible']=False;records[0]['exclusions']=['injected'];records[0]['metrics']['max_proximal_rmse_rad']=0.
        r=study.summary(records,jobs,'hash',True)
        self.assertFalse(r['ranking'][-1]['all_pass']);self.assertIsNone(r['ranking'][-1]['worst_proximal_rmse_rad'])

if __name__=='__main__':unittest.main()
