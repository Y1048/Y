"""Offline independent-clock reference, dynamics parity and evidence tests."""
from dataclasses import replace,asdict
import copy,json,math,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import mujoco_pd_independent_timing as core
import mujoco_pd_independent_study as study

class PlanTest(unittest.TestCase):
    def test_exact_96_cells(self):
        plan=study.jobs();self.assertEqual(len(plan),96);self.assertEqual(len({j['case_id'] for j in plan}),96)
    def test_candidates_see_identical_48(self):
        p=study.jobs();a=[(x['motion'],x['scenario']) for x in p[:48]];b=[(x['motion'],x['scenario']) for x in p[48:]]
        self.assertEqual(a,b);self.assertEqual(len({json.dumps(x,sort_keys=True) for x in a}),48)
    def test_frozen_gains(self):
        for g in study.VECTORS:
            self.assertEqual((g.kp[0],g.kp[1],g.kp[3]),(100.,300.,100.));self.assertIn(g.kp[2],(64.,72.));self.assertEqual(g.kd,(1.4,4.,1.,1.4))
    def test_only_simulated_roll_cap(self):
        self.assertIn('value>(p?100.F:20.F)', (Path(__file__).with_name('pd_gain_options.hpp')).read_text().replace(' ',''))
    def test_all_motions_valid_without_input_mutation(self):
        for m in study.motions():
            before=asdict(m);m.validate();core.Timeline(m);self.assertEqual(before,asdict(m))
    def test_invalid_motion(self):
        for kw in (dict(delays_s=(0.,)),dict(delays_s=(0.,0.,0.,math.nan)),dict(delays_s=(-.1,0,0,0)),dict(scales=(0,1,1,1)),dict(post_hold_s=1),dict(cycles=(3,3,3,2)),dict(amplitudes_deg=(13,8,8,8))):
            with self.assertRaises(ValueError):core.Motion(**kw).validate()
    def test_nonfinite_time_refused(self):
        for t in (-1,math.nan,math.inf):
            with self.assertRaises(ValueError):core.Timeline(core.Motion()).at(t)
    def test_own_clock_waits(self):
        t=core.Timeline(core.Motion());p=t.at(.1)
        self.assertEqual([q.segment for q in p],['initial_hold','waiting','waiting','waiting'])
        self.assertNotEqual(t.at(1.5)[0].offset,t.at(1.5)[3].offset)
    def test_all_finish_before_common_hold(self):
        for m in study.motions():
            t=core.Timeline(m);p=t.at(t.common_rest_start+.1)
            self.assertTrue(all(x.offset==0 and x.segment=='post_hold' for x in p))
            self.assertEqual(t.total,t.common_rest_start+m.post_hold_s)
    def test_analytical_path_caps(self):
        for m in study.motions():
            for p in core.Timeline(m).paths:
                points=[p.at(float(t)) for t in np.linspace(0,p.motion_total,901)]
                self.assertLessEqual(max(abs(x.offset) for x in points),p.offset+1e-12)
                self.assertLessEqual(max(abs(x.velocity) for x in points),p.speed+1e-12)
                self.assertLessEqual(max(abs(x.acceleration) for x in points),p.acceleration+1e-12)
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):study.main(['--output',d])
    def test_invalid_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'new'
            with self.assertRaises(SystemExit):study.main(['--output',str(target),'--workers','0'])
            self.assertFalse(target.exists())
    def test_socket_denied_worker(self):
        script="import sys;sys.path.insert(0,"+repr(str(Path(__file__).parent))+ ");import mujoco_pd_expand as e;e.init_worker();import mujoco,socket\ntry:\n socket.socket()\nexcept RuntimeError:\n print('blocked')\nelse:\n raise SystemExit(2)"
        p=subprocess.run([sys.executable,'-B','-c',script],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('blocked',p.stdout)

class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=study.motions()[1];cls.g=study.VECTORS[0];cls.s=study.SCENARIOS[0]
        cls.r,cls.a=core.simulate(cls.m,cls.g,cls.s)
    def evaluate(self,a):return core.evaluate(a,self.m,self.r['completed'],self.r['reason'],self.r['physics'])
    def test_real_independent_run(self):
        self.assertTrue(self.r['completed'],self.r['reason']);self.assertTrue(self.r['eligible'],self.r['exclusions'])
        self.assertEqual(self.r['metrics']['observed_axis_holds'],36)
        self.assertTrue(any(len(set(row))>1 for row in self.a['axis_segment']))
    def test_sync_exact_legacy_arrays(self):
        m=study.motions()[0];r,a=core.simulate(m,self.g,self.s)
        old,b=core.sync.simulate(core.sync.Motion(m.name,post_hold_s=m.post_hold_s),self.g,self.s)
        for k in ('q','dq','ref','cmd','requested','actual_tau','time_s'):np.testing.assert_array_equal(a[k],b[k],err_msg=k)
        self.assertEqual(r['completed'],old['completed']);self.assertEqual(r['joint_limit_guard'],old['joint_limit_guard'])
    def test_requested_torque_equation(self):
        np.testing.assert_allclose(np.array(self.r['gains_kp'])*(self.a['cmd']-self.a['q'])-np.array(self.r['gains_kd'])*self.a['dq'],self.a['requested'],rtol=1e-12,atol=1e-12)
    def test_own_rest_bias_rejected(self):
        a={k:v.copy() for k,v in self.a.items()};mask=a['axis_segment'][:,2]=='positive_hold';a['q'][mask,24]=a['ref'][mask,24]+.03
        self.assertIn('joint24:error_rad',self.evaluate(a)['exclusions'])
    def test_intentionally_moving_other_axis_not_residual(self):
        a={k:v.copy() for k,v in self.a.items()};mask=(a['axis_segment'][:,0]=='positive_hold')&(a['axis_segment'][:,1]=='out')
        self.assertTrue(mask.any());a['dq'][mask,23]=.3
        self.assertTrue(self.evaluate(a)['eligible'])
    def test_common_rest_wrist_motion_rejected(self):
        a={k:v.copy() for k,v in self.a.items()};a['dq'][-50:,28]=.08
        self.assertIn('common:right7_rms_speed_rad_s',self.evaluate(a)['exclusions'])
    def test_final_second_inactive_axis_bias_rejected(self):
        a={k:v.copy() for k,v in self.a.items()};a['q'][-400:-300,23]+= .03
        self.assertIn('common:error_rad',self.evaluate(a)['exclusions'])
    def test_missing_own_hold_rejected(self):
        a={k:v.copy() for k,v in self.a.items()};a['axis_segment'][a['axis_segment'][:,1]=='negative_hold',1]='cross'
        self.assertIn('joint23:incomplete_hold',self.evaluate(a)['exclusions'])
    def test_other_joint_nonfinite_refused(self):
        a={k:v.copy() for k,v in self.a.items()};a['q'][0,0]=math.nan
        with self.assertRaises(ValueError):self.evaluate(a)
    def test_clock_gap_refused(self):
        a={k:v.copy() for k,v in self.a.items()};a['time_s'][10]+=.01
        with self.assertRaises(ValueError):self.evaluate(a)
    def test_original_failure_cannot_be_erased(self):
        r=core.evaluate(self.a,self.m,False,'injected_failure',self.r['physics']);self.assertFalse(r['eligible']);self.assertIn('injected_failure',r['exclusions'])
    def test_guard_and_last_step(self):
        self.assertIsNone(self.r['joint_limit_guard']['event']);study.check_guard(self.r,self.a)
        r=copy.deepcopy(self.r);r['joint_limit_guard']['observations']-=1
        with self.assertRaises(ValueError):study.check_guard(r,self.a)
    def test_preflight_refusal_never_integrates(self):
        bad=replace(core.profile_contract(self.m.profile()),baseline=np.full(29,100.))
        with patch.object(core,'profile_contract',return_value=bad):r,a=core.simulate(self.m,self.g,self.s)
        self.assertFalse(r['completed']);self.assertEqual(r['physics']['steps'],0)

class ArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name)/'smoke'
        study.main(['--output',str(cls.folder),'--smoke','--workers','1'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def mutate(self,path,change,check=None):
        data=path.read_bytes()
        try:change(path);(check or (lambda:study.audit(self.folder)))()
        finally:path.write_bytes(data)
    def test_complete_bundle(self):
        a=study.audit(self.folder);self.assertTrue(a['passed']);self.assertEqual(a['cases'],2)
    def test_summary_reordering_deterministic(self):
        plan=study.base.read(self.folder/'plan.json');r=[study.base.read(self.folder/'cases'/(j['case_id']+'.json')) for j in plan];h=study.engine.sha256(self.folder/'manifest.json')
        self.assertEqual(study.summarize(r,plan,h,True),study.summarize(r[::-1],plan,h,True))
    def test_missing_case_fails(self):
        with self.assertRaises(ValueError):self.mutate(self.folder/'cases/case_0000.json',lambda p:p.unlink())
    def test_summary_score_tamper(self):
        def change(p):
            j=study.base.read(p);j['ranking'][0]['worst_rmse_rad']=0.;study.base.save(p,j)
        with self.assertRaises(ValueError):self.mutate(self.folder/'summary.json',change)
    def test_plan_tamper(self):
        def change(p):
            j=study.base.read(p);j[0]['motion']['delays_s'][0]=.4;study.base.save(p,j)
        with self.assertRaises(ValueError):self.mutate(self.folder/'plan.json',change)
    def test_hardware_claim_refused(self):
        def change(p):
            j=study.base.read(p);j['hardware_approved']=True;study.base.save(p,j)
        with self.assertRaises(ValueError):self.mutate(self.folder/'cases/case_0000.json',change)
    def test_archived_input_tamper(self):
        p=next((self.folder/'frozen_source').rglob('mujoco_pd_independent_timing.py'))
        with self.assertRaises(ValueError):self.mutate(p,lambda p:p.write_text('changed'))
    def test_trace_corruption_refused(self):
        p=self.folder/'full_state/case_0000.npz'
        with self.assertRaises(ValueError):self.mutate(p,lambda p:p.write_bytes(b'corrupted'))
    def test_no_candidate_from_partial_failure(self):
        plan=study.base.read(self.folder/'plan.json');r=[study.base.read(self.folder/'cases'/(j['case_id']+'.json')) for j in plan]
        for item in r:item.update(eligible=False,reason='failure',exclusions=['failure'])
        self.assertIsNone(study.summarize(r,plan,'hash')['selected_simulation_vector'])

if __name__=='__main__':unittest.main()
