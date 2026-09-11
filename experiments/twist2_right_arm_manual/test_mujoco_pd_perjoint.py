"""Per-joint simulation tests: no SDK, robot channels, sockets or physical output."""
import copy,json,math,subprocess,sys,tempfile,unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco_pd_perjoint as pj
import mujoco_pd_perjoint_study as study

class GainsAndPlanTest(unittest.TestCase):
    def test_only_roll_can_exceed_legacy_bound(self):
        pj.Gains((100,300,100,100)).validate()
        for i in (0,2,3):
            p=[100]*4;p[i]=101
            with self.assertRaises(ValueError):pj.Gains(tuple(p)).validate()
    def test_invalid_values(self):
        for p,d in (((100,301,100,100),(1.,)*4),((100,)*3,(1.,)*4),((100,)*4,(math.nan,)*4),((100,)*4,(21.,)*4)):
            with self.assertRaises(ValueError):pj.Gains(p,d).validate()
    def test_live_gain_validator_still_refuses_extended_gain(self):
        with self.assertRaises(ValueError):pj.engine.candidate_gains(pj.engine.load_contract(),300,4)
    def test_scope_restores_on_exception(self):
        old=pj.engine.candidate_gains
        with self.assertRaises(RuntimeError):
            with pj.scoped_gains(pj.Gains((100,300,100,100))):raise RuntimeError('injected')
        self.assertIs(pj.engine.candidate_gains,old)
    def test_only_proximal_arrays_modified(self):
        c=pj.engine.load_contract();before=c.kp.copy()
        with pj.scoped_gains(pj.Gains((72,240,88,100),(1.4,4,2,3))):
            p,d=pj.engine.candidate_gains(c,*pj.BASE)
        np.testing.assert_array_equal(p[:22],c.kp[:22]);np.testing.assert_array_equal(p[26:],c.kp[26:])
        np.testing.assert_array_equal(c.kp,before)
        np.testing.assert_array_equal(d[22:26],[1.4,4,2,3])
    def test_scope_rejects_unexpected_scalar(self):
        with pj.scoped_gains(pj.Gains()):
            with self.assertRaises(ValueError):pj.engine.candidate_gains(pj.engine.load_contract(),99,1)
    def test_roll_grid_40_unique(self):
        self.assertEqual(len(study.ROLL_PAIRS),40);self.assertEqual(len(set(study.ROLL_PAIRS)),40)
    def test_operating144_and_fresh48(self):
        self.assertEqual(len(study.operating_conditions()),144);self.assertEqual(len(study.fresh_conditions()),48)
        for p,s in study.operating_conditions()+study.fresh_conditions():p.validate();s.validate()
    def test_gains_and_conditions_not_mutated(self):
        g=pj.Gains();changed=study.change(g,23,240,4)
        self.assertEqual(g,pj.Gains());self.assertEqual(changed.kp,(100,240,100,100))
    def test_plan_deduplicates_identical_vectors_only(self):
        g=pj.Gains();plan=study.jobs([g,g],study.search_conditions(23),'roll')
        self.assertEqual(len(plan),6);self.assertEqual(len({j['case_id'] for j in plan}),6)
    def test_missing_cell_never_ranks(self):
        plan=study.jobs([pj.Gains()],study.search_conditions(23),'roll')
        with self.assertRaises(ValueError):pj.ranking([],plan)
    def test_candidate_changed_cannot_rank(self):
        j=study.jobs([pj.Gains()],study.search_conditions(23),'roll')[0]
        r=dict(j,eligible=True,metrics={'active_rmse_rad':.01},reason='',exclusions=[])
        r=copy.deepcopy(r);r['candidate']['kp'][1]=110
        with self.assertRaises(ValueError):pj.ranking([r],[j])
    def test_failed_lower_error_not_selected(self):
        jobs=study.jobs([pj.Gains(),pj.Gains((100,240,100,100))],study.search_conditions(23)[:1],'test')
        rs=[dict(j,eligible=i==1,metrics={'active_rmse_rad':.001 if i==0 else .01},reason='',exclusions=[]) for i,j in enumerate(jobs)]
        self.assertEqual(tuple(study.winner(rs,jobs).kp),(100,240,100,100))
    def test_summary_invariant_to_parallel_completion_order(self):
        plan=study.jobs([pj.Gains()],study.search_conditions(23)[:2],'diagnostic')
        records=[dict(j,completed=False,eligible=False,reason='synthetic',exclusions=['synthetic'],
          metrics=None,joint_limit_guard={'event':None,'minimum_soft_margin_rad':[.2]*29,
          'minimum_hard_margin_rad':[.25]*29}) for j in plan]
        normal=study.make_summary(records,plan,{},'manifest','selection')
        reversed_order=study.make_summary(list(reversed(records)),plan,{},'manifest','selection')
        self.assertEqual(normal,reversed_order)
        self.assertEqual([v['case_id'] for v in normal['ranking']['diagnostic'][0]['failures']],
                         sorted(j['case_id'] for j in plan))
    def test_bad_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'result'
            with self.assertRaises(SystemExit):study.main(['--output',str(p),'--workers','0'])
            self.assertFalse(p.exists())
    def test_socket_guard(self):
        code='import mujoco_pd_expand as e;e.init_worker();import socket\ntry:socket.socket()\nexcept RuntimeError:print("blocked")\nelse:raise SystemExit(3)'
        r=subprocess.run([sys.executable,'-B','-c',code],cwd=Path(__file__).parent,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('blocked',r.stdout)

class RealDynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.profile=pj.core.Profile('nominal23',joint=23);cls.scenario=pj.operating.SCENARIOS[0]
        cls.jobs=study.jobs([pj.Gains(),pj.Gains((100,240,100,100),(1.4,4,1.4,1.4))],[(cls.profile,cls.scenario)],'test')
        cls.records=[pj.write_case(j,cls.folder) for j in cls.jobs]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_uniform_vectors_exact_original_dynamics(self):
        r,a=pj.core.simulate(self.profile,*pj.BASE,self.scenario)
        saved=self.records[0]
        with np.load(self.folder/saved['trace']) as z:
            for k in a:np.testing.assert_array_equal(a[k],z[k])
        self.assertEqual(r['metrics'],saved['metrics'])
    def test_roll_static_error_improves_without_compensation(self):
        self.assertFalse(self.records[0]['eligible']);self.assertTrue(self.records[1]['eligible'])
        self.assertLess(self.records[1]['metrics']['max_active_tail_error_rad'],.02)
        self.assertFalse(self.records[1]['legacy_hardware_gain_compatible'])
    def test_readback_all29_and_torque_equation(self):
        for j in self.jobs:
            r,a=pj.audit_case(self.folder,j);self.assertEqual(a['q'].shape[1],29)
            self.assertEqual(r['joint_limit_guard']['event'],None)
    def test_core_never_modified(self):
        with self.assertRaises(ValueError):pj.engine.candidate_gains(pj.engine.load_contract(),240,4)
    def mutate(self,field,value):
        j=self.jobs[1];p=self.folder/'cases'/(j['case_id']+'.json');original=p.read_bytes()
        r=json.loads(original);r[field]=value;p.write_text(json.dumps(r))
        try:
            with self.assertRaises(ValueError):pj.audit_case(self.folder,j)
        finally:p.write_bytes(original)
    def test_wrong_applied_gain_refused(self):self.mutate('gains_kp',[100]*29)
    def test_relaxed_quality_refused(self):self.mutate('quality_policy',dict(pj.core.POLICY,active_tail_error_rad=1))
    def test_missing_final_step_refused(self):
        g=copy.deepcopy(self.records[1]['joint_limit_guard']);g['observations']-=2;self.mutate('joint_limit_guard',g)
    def test_hardware_recommendation_refused(self):self.mutate('recommended_hardware_gains',{'kp':240})
    def test_score_tampering_refused(self):
        m=dict(self.records[1]['metrics']);m['active_rmse_rad']=0;self.mutate('metrics',m)
    def test_trace_tampering_refused(self):
        j=self.jobs[1];dest=self.folder/self.records[1]['trace'];original=dest.read_bytes();dest.write_bytes(original+b'garbage')
        try:
            with self.assertRaises(ValueError):pj.audit_case(self.folder,j)
        finally:dest.write_bytes(original)
    def test_summary_survives_json_roundtrip(self):
        value=study.make_summary(self.records,self.jobs,{},"manifest","selection")
        self.assertEqual(value,json.loads(json.dumps(value)))
    def test_no_result_overwrite(self):
        with self.assertRaises(FileExistsError):study.main(['--output',str(self.folder)])

if __name__=='__main__':unittest.main()
