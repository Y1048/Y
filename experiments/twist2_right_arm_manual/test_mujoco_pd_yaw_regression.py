"""Regression protocol tests; no robot imports, sockets or hardware commands."""
import copy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import mujoco_pd_yaw_regression as reg


def source_summary():
    rows=[]
    for p in (72.,64.):
        candidate={'kp':[100.,300.,p,100.], 'kd':[1.4,4.,1.,1.4]}
        rows.append(dict(candidate=candidate,all_pass=True,cases=144,passed=144,selectable_worst_rmse_rad=.012))
    return dict(complete=True,simulation_only=True,hardware_approved=False,hardware_config_modified=False,
        recommended_hardware_gains=None,ranking={'operating':rows,
            'validation':[dict(r,cases=24,passed=24) for r in rows]})


def mock_record(job,eligible=True):
    return dict(job,completed=eligible,eligible=eligible,reason='' if eligible else 'injected',
        exclusions=[] if eligible else ['injected'],metrics={'max_proximal_rmse_rad':.01},
        simulation_only=True,hardware_approved=False,hardware_config_modified=False,recommended_hardware_gains=None,
        joint_limit_guard={'event':None,'minimum_soft_margin_rad':[.2]*29,
                           'minimum_hard_margin_rad':[.25]*29,'minimum_stopping_slack_rad':[.1]*29})


class PlanTest(unittest.TestCase):
    def test_full_432_plan_and_same_216_each(self):
        vs=reg.accepted(source_summary());jobs=reg.plan(vs)
        self.assertEqual(len(jobs),432);self.assertEqual(len({j['case_id'] for j in jobs}),432)
        self.assertEqual([j['motion'] for j in jobs[:216]],[j['motion'] for j in jobs[216:]])
        self.assertEqual([j['scenario'] for j in jobs[:216]],[j['scenario'] for j in jobs[216:]])
    def test_each_axis_and_condition_group(self):
        cs=reg.conditions()
        self.assertEqual(reg.Counter(c[0] for c in cs),{'prior_operating':144,'prior_fresh':48,'prior_final':24})
        self.assertEqual(reg.Counter(m.scales.index(1.)+22 for _,m,_ in cs),dict.fromkeys(range(22,26),54))
    def test_original_profile_mapping_exact(self):
        profiles=reg.prior.operating_conditions()+reg.prior.fresh_conditions()+reg.final.conditions()
        for (_,m,s),(p,expected_s) in zip(reg.conditions(),profiles):
            self.assertEqual(m.profile(p.joint),p);self.assertEqual(s,expected_s)
            self.assertEqual(sum(m.scales),1.);self.assertEqual(sum(v!=0 for v in m.scales),1)
    def test_frozen_order_not_new_rank(self):
        s=source_summary();vs=reg.accepted(s)
        self.assertEqual([g.kp[2] for g in vs],[72.,64.])
    def test_no_failed_source_is_accepted(self):
        s=source_summary();s['ranking']['validation'][0]['all_pass']=False
        self.assertEqual([g.kp[2] for g in reg.accepted(s)],[64.])
    def test_missing_full_source_coverage_is_not_inherited(self):
        s=source_summary();s['ranking']['operating'][0]['cases']=143
        self.assertEqual(len(reg.accepted(s)),1)
    def test_duplicate_source_refused(self):
        s=source_summary();s['ranking']['operating'].append(copy.deepcopy(s['ranking']['operating'][0]))
        with self.assertRaises(ValueError):reg.accepted(s)
    def test_source_hardware_claim_refused(self):
        for key,value in (('simulation_only',False),('hardware_approved',True),('hardware_config_modified',True),('recommended_hardware_gains',{})):
            s=source_summary();s[key]=value
            with self.assertRaises(ValueError):reg.accepted(s)
    def test_non_yaw_change_refused(self):
        s=source_summary()
        for r in s['ranking']['operating']+s['ranking']['validation']:r['candidate']['kd'][0]=3.
        with self.assertRaises(ValueError):reg.accepted(s)
    def test_bad_workers_before_data_access(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'new'
            with self.assertRaises(SystemExit):reg.main(['--source-yaw',t,'--output',str(out),'--workers','0'])
            self.assertFalse(out.exists())
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
            with patch.object(reg,'receipt',side_effect=AssertionError('unexpected source access')):
                with self.assertRaisesRegex(ValueError,'Output exists'):reg.main(['--source-yaw',a,'--output',b])
    def test_nested_output_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'overlap'):reg.main(['--source-yaw',t,'--output',str(Path(t)/'nested')])
    def test_incomplete_result_cannot_rank(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs)
        with self.assertRaises(ValueError):reg.summarize([mock_record(j) for j in p[:-1]],p,vs,source_summary(),'hash')
    def test_one_failed_cell_excludes_candidate(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs);rs=[mock_record(j) for j in p]
        rs[0]=mock_record(p[0],False)
        result=reg.summarize(rs,p,vs,source_summary(),'hash')
        self.assertEqual(result['selected_simulation_vector']['kp'][2],64.)
        self.assertIsNone(next(r for r in result['ranking'] if not r['all_pass'])['combined_384_worst_rmse_rad'])
    def test_no_survivor_does_not_invent_gain(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs)
        r=reg.summarize([mock_record(j,False) for j in p],p,vs,source_summary(),'hash')
        self.assertIsNone(r['selected_simulation_vector'])
    def test_result_order_is_deterministic(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs);rs=[mock_record(j) for j in p]
        self.assertEqual(reg.summarize(rs,p,vs,source_summary(),'h'),reg.summarize(rs[::-1],p,vs,source_summary(),'h'))
    def test_wrong_gain_record_refused(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs);rs=[mock_record(j) for j in p]
        rs[0]=copy.deepcopy(rs[0]);rs[0]['candidate']['kp'][2]=32.
        with self.assertRaises(ValueError):reg.summarize(rs,p,vs,source_summary(),'h')
    def test_hardware_result_refused(self):
        vs=reg.accepted(source_summary());p=reg.plan(vs);rs=[mock_record(j) for j in p];rs[0]['hardware_approved']=True
        with self.assertRaises(ValueError):reg.summarize(rs,p,vs,source_summary(),'h')


class ActualTraceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.folder=Path(cls.temp.name)
        cls.g=reg.accepted(source_summary())[0]
        cls.job=reg.plan([cls.g])[0]
        cls.record=reg.base.run_case(cls.job,str(cls.folder))
        cls.audited,cls.arrays=reg.base.audit_case(cls.folder,cls.job)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_real_record_and_fullstate_audit(self):
        self.assertTrue(self.audited['completed']);self.assertTrue(self.audited['eligible'])
        self.assertEqual(self.arrays['q'].shape[1],29)
        self.assertEqual(len(self.audited['axis_evaluations']),4)
    def test_pure_pd_and_limits_unchanged(self):
        a=self.arrays;r=self.audited
        np.testing.assert_allclose(np.asarray(r['gains_kp'])*(a['cmd']-a['q'])-np.asarray(r['gains_kd'])*a['dq'],a['requested'],atol=1e-12)
        self.assertIsNone(r['joint_limit_guard']['event']);self.assertFalse(r['hardware_approved'])
    def test_exact_prior_engine_state_parity(self):
        p,s=reg.prior.operating_conditions()[0]
        old,a=reg.pj.simulate(p,self.g,s)
        for field in a:np.testing.assert_array_equal(self.arrays[field],a[field],err_msg=field)
    def test_inactive_axis_error_still_rejected(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['q'][:,23]+=0.04
        m=reg.multi.Motion(**self.job['motion'])
        checked=reg.multi.evaluate(a,m,True,'',self.audited['physics'])
        self.assertFalse(checked['eligible'])
        self.assertIn('joint23:active_tail_error_rad',checked['exclusions'])



class BundleAuditTest(unittest.TestCase):
    """Real two-case dynamics and bundle audit, with a deliberately mocked source receipt.
    This fixture is NOT an extra full regression study or original source audit.
    """
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.source=cls.root/'source';cls.source.mkdir();cls.output=cls.root/'output'
        cls.cs=reg.conditions()[:1]
        _,_,_,_,assets=reg.engine.load_model(reg.engine.MODEL,.001)
        archive={}
        for name,digest in assets.items():
            p=reg.base.safe_path(reg.engine.MODEL.parent if name.replace(chr(92),'/').startswith('meshes/') else reg.engine.ROOT,name)
            archive[p.relative_to(reg.engine.ROOT).as_posix()]=digest
        reg.base.save(cls.source/'manifest.json',{'asset_archive_sha256':archive})
        cls.receipt_value={'source_cases':462,'source_rows':0,'metadata_sha256':{},'case_json_sha256':{}}
        with patch.object(reg,'conditions',return_value=cls.cs),patch.object(reg,'receipt',return_value=(source_summary(),cls.receipt_value)):
            reg.main(['--source-yaw',str(cls.source),'--output',str(cls.output),'--workers','1'])
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def check(self):
        with patch.object(reg,'conditions',return_value=self.cs),patch.object(reg,'receipt',return_value=(source_summary(),self.receipt_value)):
            return reg.audit(self.source,self.output)
    def corrupt(self,name,mutate):
        p=self.output/name;old=p.read_bytes()
        try:
            r=reg.base.read(p);mutate(r);reg.base.save(p,r)
            with self.assertRaises(ValueError):self.check()
        finally:p.write_bytes(old)
    def test_complete_bundle_audit(self):
        a=self.check();self.assertTrue(a['passed']);self.assertEqual(a['cases'],2)
        self.assertGreater(a['all29_500hz_rows'],0)
    def test_changed_summary_refused(self):
        self.corrupt('summary.json',lambda r:r.update(eligible=0))
    def test_changed_source_receipt_refused(self):
        self.corrupt('source_receipt.json',lambda r:r.update(source_cases=1))
    def test_missing_case_refused(self):
        p=self.output/'cases/regression_00000.json';other=p.with_suffix('.bak')
        p.rename(other)
        try:
            with self.assertRaises(ValueError):self.check()
        finally:other.rename(p)
    def test_frozen_input_tampering_refused(self):
        p=reg.base.safe_path(self.output/'frozen_source',next(iter(reg.base.read(self.output/'manifest.json')['source_sha256'])))
        old=p.read_bytes()
        try:
            p.write_bytes(old+b'\n# altered\n')
            with self.assertRaises(ValueError):self.check()
        finally:p.write_bytes(old)

if __name__=='__main__':unittest.main()
