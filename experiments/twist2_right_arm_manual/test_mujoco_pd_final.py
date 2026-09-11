"""Final-review regressions. All simulated cases are SDK/DDS-free."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import mujoco_pd_final as final


def source_fixture():
    a = {'kp':[100.,300.,100.,100.], 'kd':[1.4,4.,1.4,1.4]}
    b = {'kp':[100.,300.,100.,100.], 'kd':[3.,5.,3.,3.]}
    def rank(g,n): return {'candidate':g,'cases':n,'passed':n,'all_pass':True}
    summary = {'complete':True,'simulation_only':True,'hardware_config_modified':False,
      'recommended_hardware_gains':None,
      'ranking':{'operating':[rank(a,144),rank(b,144)],'fresh':[rank(a,48),rank(b,48)]}}
    return {'summary':summary, 'receipt':{'test_fixture':True,'cases':0,'all29_500hz_rows':0,
                                       'all29_margin_records':0}}


class FinalPolicyTest(unittest.TestCase):
    def test_all_fixed_cases_and_bounds(self):
        cases=final.conditions()
        self.assertEqual(len(cases),24)
        self.assertEqual(len({(p.name,s.name) for p,s in cases}),24)
        self.assertEqual({p.joint for p,s in cases},{22,23,24,25})
        self.assertEqual(sum(p.cycles==12 for p,s in cases),4)
        self.assertEqual(sum(p.post_hold_s==30 for p,s in cases),4)
        for p,s in cases: p.validate();s.validate()

    def test_finalists_preserve_source_order(self):
        s=source_fixture()['summary']
        s['ranking']['fresh'].reverse()
        self.assertEqual(tuple(final.accepted_vectors(s)[0].kd),(1.4,4.,1.4,1.4))

    def test_failed_source_candidate_excluded(self):
        s=source_fixture()['summary'];s['ranking']['fresh'][0]['all_pass']=False
        self.assertEqual(len(final.accepted_vectors(s)),1)

    def test_missing_full_coverage_excluded(self):
        for phase,field in (('operating','cases'),('fresh','passed')):
            s=source_fixture()['summary'];s['ranking'][phase][0][field]-=1
            self.assertEqual(len(final.accepted_vectors(s)),1)

    def test_duplicate_source_candidate_refused(self):
        s=source_fixture()['summary'];s['ranking']['operating'].append(s['ranking']['operating'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):final.accepted_vectors(s)

    def test_hardware_claim_or_incomplete_refused(self):
        for key,value in (('complete',False),('simulation_only',False),('hardware_config_modified',True),('recommended_hardware_gains',{})):
            s=source_fixture()['summary'];s[key]=value
            with self.assertRaises(ValueError):final.accepted_vectors(s)

    def test_no_feasible_candidate_not_fabricated(self):
        result=final.decision([],[],[])
        self.assertEqual(result['status'],'no_final_candidate')
        self.assertIsNone(result['candidate'])
        self.assertFalse(result['hardware_approved'])

    def test_invalid_workers_before_writing(self):
        with tempfile.TemporaryDirectory() as root:
            for workers in (0,9,True):
                with self.assertRaises(ValueError):final.finalize(Path(root)/'absent',Path(root)/'out',workers)
            self.assertFalse((Path(root)/'out').exists())

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):final.finalize(root,root)

    def test_nested_output_refused_before_audit(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'outside'):final.finalize(root,Path(root)/'out')


class FinalDynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name);cls.source=cls.root/'source';cls.source.mkdir()
        cls.bundle=cls.root/'final';cls.fixture=source_fixture()
        # Two physical MuJoCo cases with a mocked, explicitly labeled source receipt.
        # Formal1020+48-case audit is performed outside this test fixture.
        cls.cases=[(final.pj.core.Profile('test_final',joint=23,post_hold_s=2.), final.pj.core.Coupled('test_nominal'))]
        cls.source_patch=patch.object(final,'source_receipt',return_value=cls.fixture)
        cls.cond_patch=patch.object(final,'conditions',return_value=cls.cases)
        cls.source_patch.start();cls.cond_patch.start()
        try:cls.result=final.finalize(cls.source,cls.bundle,workers=2)
        except BaseException:
            cls.source_patch.stop();cls.cond_patch.stop();cls.tmp.cleanup();raise
        cls.plan=final.read(cls.bundle/'plan.json')
        cls.r,cls.arrays=final.pj.audit_case(cls.bundle,cls.plan[0])

    @classmethod
    def tearDownClass(cls):
        cls.source_patch.stop();cls.cond_patch.stop();cls.tmp.cleanup()

    def assert_tamper(self,name,change,pattern=None):
        path=self.bundle/name;original=path.read_bytes()
        value=final.read(path);change(value)
        try:
            path.write_text(final.json.dumps(value),encoding='utf-8')
            with self.assertRaises(ValueError):final.verify(self.source,self.bundle)
        finally:path.write_bytes(original)

    def test_real_completion_and_readback(self):
        self.assertEqual(self.result['actual_new_simulations'],2)
        self.assertIsNotNone(self.result['candidate'])
        self.assertTrue(final.verify(self.source,self.bundle)['passed'])

    def test_research_not_hardware_approved(self):
        self.assertFalse(self.result['hardware_approved'])
        self.assertFalse(self.result['legacy_hardware_gain_compatible'])
        self.assertIsNone(self.result['recommended_hardware_gains'])
        self.assertEqual(self.result['kp_at_research_cap_joints'],[22,23,24,25])

    def test_inactive_joint_bias_fails(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['q'][:,24]=a['ref'][:,24]+.021
        self.assertIn('all_proximal_tail_error',final.final_quality(self.r,a)['rejections'])

    def test_inactive_joint_velocity_fails(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['dq'][:,25]=.101
        self.assertIn('all_proximal_tail_speed',final.final_quality(self.r,a)['rejections'])

    def test_whole_last_second_checked(self):
        a={k:v.copy() for k,v in self.arrays.items()}
        i=np.flatnonzero(a['segment']=='post_hold')[-450];a['q'][i,24]=a['ref'][i,24]+.03
        self.assertFalse(final.final_quality(self.r,a)['passes'])

    def test_original_failure_cannot_be_erased(self):
        r=dict(self.r,eligible=False)
        self.assertIn('original_case_rejected',final.final_quality(r,self.arrays)['rejections'])

    def test_missing_window_fails(self):
        a={k:v.copy() for k,v in self.arrays.items()};a['segment'][a['segment']=='post_hold']='missing'
        self.assertIn('missing_final_window',final.final_quality(self.r,a)['rejections'])

    def test_final_policy_tampering(self):
        self.assert_tamper('manifest.json',lambda m:m['final_quality_policy'].update(all_proximal_tail_error_rad=.1))

    def test_source_receipt_tampering(self):
        self.assert_tamper('source_receipt.json',lambda m:m.update(cases=1000))

    def test_candidate_hardware_tampering(self):
        self.assert_tamper('simulation_candidate.json',lambda m:m.update(hardware_approved=True))

    def test_score_tampering(self):
        self.assert_tamper('simulation_candidate.json',lambda m:m['final_ranking_in_frozen_source_order'][0].update(worst_active_rmse_rad=0.))

    def test_verification_record_tampering(self):
        self.assert_tamper('verification.json',lambda m:m.update(passed=False))

    def test_missing_final_case_fails(self):
        path=self.bundle/'cases'/(self.plan[0]['case_id']+'.json');saved=path.read_bytes();path.unlink()
        try:
            with self.assertRaises(ValueError):final.verify(self.source,self.bundle)
        finally:path.write_bytes(saved)

    def test_trace_tampering_fails(self):
        path=self.bundle/self.r['trace'];original=path.read_bytes();path.write_bytes(original+b'altered')
        try:
            with self.assertRaises(ValueError):final.verify(self.source,self.bundle)
        finally:path.write_bytes(original)

    def test_archived_source_tampering_fails(self):
        manifest=final.read(self.bundle/'manifest.json')
        path=final.pj.safe_path(self.bundle/'frozen_source',next(iter(manifest['source_sha256'])))
        original=path.read_bytes();path.write_bytes(original+b'\n')
        try:
            with self.assertRaises(ValueError):final.verify(self.source,self.bundle)
        finally:path.write_bytes(original)


if __name__=='__main__':unittest.main()
