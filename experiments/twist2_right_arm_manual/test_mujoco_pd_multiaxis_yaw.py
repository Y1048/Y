"""The focused search cannot hide failures or tune on its final validation."""
from dataclasses import asdict,replace
from concurrent.futures import Future
import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import mujoco_pd_multiaxis_yaw as yaw
base=yaw.base

def fake(job,good=True,error=.01):
    return dict(copy.deepcopy(job),completed=good,eligible=good,reason='' if good else 'rejected',exclusions=[] if good else ['rejected'],
      metrics={'max_proximal_rmse_rad':error},joint_limit_guard={'event':None,'minimum_soft_margin_rad':[.2]*29,'minimum_hard_margin_rad':[.25]*29})

class PlanAndSelectionTest(unittest.TestCase):
    def test_42_unique_pairs(self):
        self.assertEqual(len(yaw.YAW_PAIRS),42);self.assertEqual(len(set(yaw.YAW_PAIRS)),42)
    def test_only_joint24_changes(self):
        for g in yaw.vectors():
            g.validate()
            for i in (0,1,3):self.assertEqual((g.kp[i],g.kd[i]),(base.VECTORS[0].kp[i],base.VECTORS[0].kd[i]))
            self.assertLessEqual(g.kp[2],100.)
    def test_126_screen_jobs(self):
        ps=yaw.jobs(yaw.vectors(),yaw.screen_conditions(),'screen');self.assertEqual(len(ps),126)
        self.assertEqual(len({p['case_id'] for p in ps}),126)
    def test_each_candidate_sees_same_conditions(self):
        ps=yaw.jobs(yaw.vectors(),yaw.screen_conditions(),'screen')
        for i in range(0,len(ps),3):self.assertEqual([(x['motion'],x['scenario']) for x in ps[i:i+3]],[(x['motion'],x['scenario']) for x in ps[:3]])
    def test_new24_conditions_unique_and_valid(self):
        c=yaw.validation_conditions();self.assertEqual(len(c),24)
        self.assertEqual(len({(p.name,s.name) for _,p,s in c}),24)
        for _,p,s in c:p.validate();s.validate()
    def test_two_finalists_288_operating(self):
        self.assertEqual(len(yaw.jobs(yaw.vectors()[:2],base.conditions(),'operating')),288)
    def test_no_duplicates(self):
        with self.assertRaises(ValueError):yaw.jobs([yaw.vectors()[0]]*2,yaw.screen_conditions(),'x')
    def test_failed_low_error_cannot_win(self):
        ps=yaw.jobs(yaw.vectors()[:2],yaw.screen_conditions(),'screen');rs=[fake(p) for p in ps]
        rs[0]['eligible']=False;rs[0]['metrics']['max_proximal_rmse_rad']=0
        ranks=yaw.ranking(rs,ps);self.assertTrue(ranks[0]['all_pass']);self.assertIsNone(ranks[1]['selectable_worst_rmse_rad'])
    def test_missing_case_refused(self):
        ps=yaw.jobs(yaw.vectors()[:1],yaw.screen_conditions(),'screen')
        with self.assertRaises(ValueError):yaw.ranking([fake(p) for p in ps[:-1]],ps)
    def test_changed_motion_refused(self):
        ps=yaw.jobs(yaw.vectors()[:1],yaw.screen_conditions(),'screen');rs=[fake(p) for p in ps];rs[0]['motion']['scales'][0]*=-1
        with self.assertRaises(ValueError):yaw.ranking(rs,ps)
    def test_summary_order_invariant(self):
        plans={phase:yaw.jobs(yaw.vectors()[:2],yaw.screen_conditions(),phase) for phase in ('screen','operating','validation')}
        rs=[fake(p) for pp in plans.values() for p in pp]
        self.assertEqual(yaw.make_summary(rs,plans,'hash'),yaw.make_summary(rs[::-1],plans,'hash'))
    def test_validation_failure_has_no_candidate(self):
        plans={phase:yaw.jobs(yaw.vectors()[:1],yaw.screen_conditions(),phase) for phase in ('screen','operating','validation')}
        rs=[fake(p,p['phase']!='validation') for pp in plans.values() for p in pp]
        self.assertIsNone(yaw.make_summary(rs,plans,'hash')['selected_simulation_vector'])
    def test_empty_validation_no_candidate(self):
        ps=yaw.jobs(yaw.vectors()[:1],yaw.screen_conditions(),'screen');plans={'screen':ps,'operating':[],'validation':[]}
        self.assertIsNone(yaw.make_summary([fake(p) for p in ps],plans,'hash')['selected_simulation_vector'])
    def test_infrastructure_exception_not_a_simulation_pass(self):
        class BrokenPool:
            def submit(self,*args):
                f=Future();f.set_exception(RuntimeError('injected'));return f
        with tempfile.TemporaryDirectory() as d,self.assertRaisesRegex(RuntimeError,'injected'):
            yaw.block(BrokenPool(),Path(d),yaw.jobs(yaw.vectors()[:1],yaw.screen_conditions(),'screen'))
    def test_invalid_worker(self):
        with tempfile.TemporaryDirectory() as d,self.assertRaises(SystemExit):yaw.main(['--output',str(Path(d)/'new'),'--workers','0'])
    def test_existing_output(self):
        with tempfile.TemporaryDirectory() as d,self.assertRaises(ValueError):yaw.main(['--output',d])

class ActualRecordTest(unittest.TestCase):
    def test_changed_yaw_torque_and_fullstate_audit(self):
        g=base.pj.Gains((100.,300.,64.,100.),(1.4,4.,1.4,1.4))
        job=yaw.jobs([g],[yaw.screen_conditions()[0]],'test')[0]
        with tempfile.TemporaryDirectory() as d:
            r=base.run_case(job,d);rr,a=base.audit_case(d,job)
            self.assertEqual(rr['gains_kp'][24],64.);self.assertEqual(rr['gains_kd'][24],1.4)
            np.testing.assert_allclose(np.asarray(rr['gains_kp'])*(a['cmd']-a['q'])-np.asarray(rr['gains_kd'])*a['dq'],a['requested'],rtol=1e-12,atol=1e-12)
            self.assertFalse(r['hardware_approved']);self.assertIsNone(r['recommended_hardware_gains'])

if __name__=='__main__':unittest.main()
