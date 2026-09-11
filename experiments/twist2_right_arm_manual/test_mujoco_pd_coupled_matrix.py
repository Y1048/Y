"""Completion-matrix evidence regressions; no hardware or DDS."""
from dataclasses import asdict
import copy,itertools,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import mujoco_pd_coupled_matrix as matrix
import mujoco_pd_coupled_stress as study
from test_mujoco_pd_coupled_stress import SerialPool

class MatrixPlanTest(unittest.TestCase):
    def test_every_unselected_pair_is_scheduled_even_if_failed(self):
        m={'pairs':study.PAIRS,'validation':[asdict(s) for s in study.VALIDATION]}
        jobs=matrix.missing_jobs([],m,'unused')
        self.assertEqual(len(jobs),192)
        self.assertEqual(len({(j[0],j[1],j[2]['name']) for j in jobs}),192)
    def test_completed_cells_are_not_counted_twice(self):
        s=study.VALIDATION[0];p,d=study.PAIRS[0]
        r={'kp_proximal':p,'kd_proximal':d,'study_scenario':s.identity}
        jobs=matrix.missing_jobs([r],{'pairs':study.PAIRS,'validation':[asdict(x) for x in study.VALIDATION]},'unused')
        self.assertEqual(len(jobs),191)
        self.assertNotIn((p,d,s.name),[(j[0],j[1],j[2]['name']) for j in jobs])
    def test_duplicate_observations_refused(self):
        r={'kp_proximal':100.,'kd_proximal':2.,'study_scenario':'coupled/nominal'}
        with self.assertRaises(ValueError):matrix.missing_jobs([r,r],{'pairs':[],'validation':[]},'unused')
    def test_invalid_worker_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'out'
            with self.assertRaises(SystemExit):matrix.main(['--base-run',d,'--output',str(output),'--workers','0'])
            self.assertFalse(output.exists())

class MatrixAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.base=cls.root/'base';cls.output=cls.root/'matrix'
        with patch.object(study,'ProcessPoolExecutor',SerialPool):
            study.main(['--output',str(cls.base),'--smoke','--workers','1'])
        with patch.object(matrix,'ProcessPoolExecutor',SerialPool):
            matrix.main(['--base-run',str(cls.base),'--output',str(cls.output),'--workers','1'])
    def test_zero_missing_completion_preserves_base_count(self):
        result=matrix.read(self.output/'summary.json');audit=matrix.read(self.output/'audit.json')
        self.assertEqual(result['total_cases'],4);self.assertEqual(audit['extra_cases'],0)
        self.assertTrue(audit['passed']);self.assertFalse(result['all_possible_cases_tested'])
    def test_missing_cell_never_counts_as_complete(self):
        records=matrix.source_records(self.base);m=matrix.read(self.base/'manifest.json')
        with self.assertRaises(ValueError):matrix.summarize(records[:-1],m)
    def test_real_supplemental_case_and_all_state_evidence(self):
        folder=self.root/'single';folder.mkdir()
        job=(100.,2.,asdict(study.VALIDATION[0]),str(folder),'extra_00000','validation')
        observed=study.run_case(job)
        checked,n=matrix.verify_extra(folder,folder/'cases/extra_00000.json',job)
        self.assertEqual(observed,checked);self.assertGreater(n,0)
        modified=list(job);modified[1]=1.275
        with self.assertRaises(ValueError):matrix.verify_extra(folder,folder/'cases/extra_00000.json',modified)
    def test_matrix_summary_tampering_refused(self):
        target=self.output/'summary.json';before=target.read_bytes()
        try:
            data=matrix.read(target);data['quality_eligible']=999;matrix.save(target,data)
            with self.assertRaises(ValueError):matrix.audit(self.base,self.output)
        finally:target.write_bytes(before)
    def test_base_freeze_tampering_refused(self):
        target=self.output/'manifest.json';before=target.read_bytes()
        try:
            data=matrix.read(target);data['base_artifact_sha256']['summary.json']='0'*64;matrix.save(target,data)
            with self.assertRaises(ValueError):matrix.audit(self.base,self.output)
        finally:target.write_bytes(before)
    def test_existing_results_preserved(self):
        before=(self.output/'summary.json').read_bytes()
        with self.assertRaises(FileExistsError):matrix.main(['--base-run',str(self.base),'--output',str(self.output)])
        self.assertEqual((self.output/'summary.json').read_bytes(),before)

if __name__=='__main__':unittest.main()
