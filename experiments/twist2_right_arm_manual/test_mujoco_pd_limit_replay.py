"""Offline guard evidence cannot turn a refused trial into an accepted one."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import mujoco_pd_limit_replay as replay
import mujoco_pd_sweep as engine

class LimitEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model,qa,va,motors,_=engine.load_model(engine.MODEL,.001)
        cls.result,_=engine.run_candidate(model,qa,va,motors,engine.load_contract(),56,3)
        cls.result['scenario']=['nominal',.001,1.,1.,0.]
    def test_full_historical_plan_is_unique(self):
        rows=replay.load_plan();self.assertEqual(len(rows),718)
        self.assertEqual(len({(r['dataset'],r['case_id']) for r in rows}),718)
    def test_missing_historical_case_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'plan.csv';p.write_text(replay.PLAN.read_text().rsplit('\n',2)[0]+'\n',encoding='utf-8')
            with self.assertRaises(ValueError):replay.load_plan(p)
    def test_untampered_all_joint_evidence(self):
        self.assertTrue(self.result['eligible']);self.assertTrue(replay.verify_guard_result(self.result))
    def test_limit_touch_cannot_be_eligible(self):
        r=copy.deepcopy(self.result);g=r['joint_limit_guard'];g['minimum_soft_margin_rad'][5]=0
        with self.assertRaises(ValueError):replay.verify_guard_result(r)
    def test_missing_joint_evidence_refused(self):
        r=copy.deepcopy(self.result);r['joint_limit_guard']['minimum_soft_witness'].pop()
        with self.assertRaises(ValueError):replay.verify_guard_result(r)
    def test_last_step_omission_refused(self):
        r=copy.deepcopy(self.result);r['joint_limit_guard']['observations']-=1
        with self.assertRaises(ValueError):replay.verify_guard_result(r)
    def test_intervention_never_passes(self):
        r=copy.deepcopy(self.result);r['joint_limit_guard']['event']={'reason':'joint_limit_command_intervention'}
        with self.assertRaises(ValueError):replay.verify_guard_result(r)
    def test_margin_witness_tampering_refused(self):
        r=copy.deepcopy(self.result);r['joint_limit_guard']['minimum_soft_witness'][28]['q']+=.2
        with self.assertRaises(ValueError):replay.verify_guard_result(r)
    def test_rejected_trial_can_retain_boundary_evidence(self):
        r=copy.deepcopy(self.result);r['completed']=False;r['eligible']=False
        g=r['joint_limit_guard'];g['event']={'reason':'injected'};g['no_intervention']=False
        self.assertTrue(replay.verify_guard_result(r))

if __name__=='__main__':unittest.main()
