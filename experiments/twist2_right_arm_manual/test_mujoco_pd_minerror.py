"""Offline finite-grid pruning proofs and full-state artifact regressions."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest
from unittest.mock import patch
import mujoco_pd_minerror as search

SS=(search.CALIBRATION[0],search.CALIBRATION[1])
PAIRS=[(100.,1.25),(100.,1.3)]

def record(index,k,rmse=.1,good=True):
    return {'case_id':f'calibration_{index:04d}_{k:02d}',
      'kp_proximal':PAIRS[index][0],'kd_proximal':PAIRS[index][1],
      'study_phase':'calibration','study_scenario_contract':asdict(SS[k]),
      'quality_eligible':good,'metrics':{'reference_rmse_joint22_rad':rmse}}

def proof_fixture():
    rs=[record(1,0),record(1,1),record(0,0,.2)]
    decisions=[{'pair':list(PAIRS[1]),'index':1,'status':'fully_evaluated',
       'case_ids':[rs[0]['case_id'],rs[1]['case_id']],'incumbent':None,
       'force_full':True,'observed_lower_bound_rad':.1},
      {'pair':list(PAIRS[0]),'index':0,'status':'bound_pruned',
       'case_ids':[rs[2]['case_id']],'incumbent':{'pair':list(PAIRS[1]),'score':.1},
       'force_full':False,'observed_lower_bound_rad':.2}]
    return decisions,rs

class ProofTest(unittest.TestCase):
    def test_grid_bounds_unique_and_dense(self):
        ps=search.grid();self.assertEqual(len(ps),len(set(ps)))
        self.assertGreater(len(ps),450)
        for p,d in ps:search.engine.candidate_gains(search.engine.load_contract(),p,d)
        self.assertIn((100.,1.255),ps);self.assertIn((99.5,1.315),ps)
        self.assertIn((16,20),ps);self.assertIn((100,2),ps)
    def test_scenarios_prespecified_and_disjoint(self):
        all_s=search.CALIBRATION+search.VALIDATION
        self.assertEqual((len(search.CALIBRATION),len(search.VALIDATION)),(45,16))
        self.assertEqual(len({(s.family,s.parameters[1:]) for s in all_s}),len(all_s))
        self.assertEqual(search.validation_plan(),search.VALIDATION)
        for s in all_s:s.validate()
    def test_strict_error_order_not_plateau(self):
        rows=[{'pair':[100,1.3],'all_quality_pass':True,'worst_rmse_rad':.01,
               'worst_tail_rms_speed_rad_s':.01,'worst_tail_p2p_rad':.001},
              {'pair':[100,2],'all_quality_pass':True,'worst_rmse_rad':.0101,
               'worst_tail_rms_speed_rad_s':.001,'worst_tail_p2p_rad':.0001}]
        self.assertEqual(search.strict_rank(rows)[0]['pair'],[100,1.3])
        rows[0]['all_quality_pass']=False
        self.assertEqual(search.strict_rank(rows)[0]['pair'],[100,2])
    def test_valid_lower_bound_proof(self):
        ds,rs=proof_fixture();self.assertEqual(search.check_decisions(ds,rs,PAIRS,SS),{(100.,1.3):.1})
    def test_json_and_native_tuple_normalize(self):
        ds,rs=proof_fixture()
        self.assertEqual(search.check_decisions(ds,rs,PAIRS,SS),search.check_decisions(ds,json.loads(json.dumps(rs)),PAIRS,SS))
    def test_bound_tampering_refused(self):
        ds,rs=proof_fixture();ds[1]['observed_lower_bound_rad']=.3
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_unverified_incumbent_refused(self):
        ds,rs=proof_fixture();ds[1]['incumbent']['pair']=[80,1]
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_understated_incumbent_score_refused(self):
        ds,rs=proof_fixture();ds[1]['incumbent']['score']=.05
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_missing_grid_cell_refused(self):
        ds,rs=proof_fixture()
        with self.assertRaises(ValueError):search.check_decisions(ds[:1],rs,PAIRS,SS)
    def test_missing_condition_cannot_be_full(self):
        ds,rs=proof_fixture();ds[1]['status']='fully_evaluated'
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_constraint_failure_requires_witness(self):
        ds,rs=proof_fixture();ds[1]['status']='constraint_rejected';ds[1]['observed_lower_bound_rad']=None
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
        rs[-1]['quality_eligible']=False
        search.check_decisions(ds,rs,PAIRS,SS)
    def test_pruning_requires_strictly_worse_error(self):
        ds,rs=proof_fixture();ds[1]['observed_lower_bound_rad']=.1;rs[-1]['metrics']['reference_rmse_joint22_rad']=.1
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_duplicate_case_assignment_refused(self):
        ds,rs=proof_fixture();ds[1]['case_ids']=ds[0]['case_ids']
        with self.assertRaises(ValueError):search.check_decisions(ds,rs,PAIRS,SS)
    def test_early_prune_runs_only_necessary_case(self):
        with tempfile.TemporaryDirectory() as f,patch.object(search.quality,'run_case',side_effect=[record(0,0,.2)]) as run:
            d,rs=search.evaluate_pair((PAIRS[0],0,[asdict(s) for s in SS],f,{'pair':list(PAIRS[1]),'score':.1},False))
            self.assertEqual(run.call_count,1);self.assertEqual(d['status'],'bound_pruned')
    def test_force_full_never_bound_prunes(self):
        with tempfile.TemporaryDirectory() as f,patch.object(search.quality,'run_case',side_effect=[record(0,0,.2),record(0,1,.3)]) as run:
            d,rs=search.evaluate_pair((PAIRS[0],0,[asdict(s) for s in SS],f,{'pair':list(PAIRS[1]),'score':.1},True))
            self.assertEqual(run.call_count,2);self.assertEqual(d['status'],'fully_evaluated')
    def test_infrastructure_exception_is_not_success(self):
        with tempfile.TemporaryDirectory() as f,patch.object(search.quality,'run_case',side_effect=RuntimeError('infrastructure')):
            with self.assertRaises(RuntimeError):search.evaluate_pair((PAIRS[0],0,[asdict(s) for s in SS],f,None,False))
            self.assertFalse((Path(f)/'decisions/0000.json').exists())
    def test_bad_workers_do_not_write(self):
        with tempfile.TemporaryDirectory() as f:
            p=Path(f)/'results'
            with self.assertRaises(SystemExit):search.main(['--workers','9','--output',str(p)])
            self.assertFalse(p.exists())

class RealSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)/'run'
        cmd=[sys.executable,'-B',str(Path(search.__file__)),'--smoke','--workers','3','--output',str(cls.root)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=150)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def copy(self,name):
        folder=Path(self.temp.name)/name;shutil.copytree(self.root,folder);return folder
    def test_complete_smoke_and_full_state_audit(self):
        a=search.verify_records(self.root,search.engine.ROOT)
        self.assertTrue(a['passed']);self.assertEqual(a['cases'],6)
        self.assertFalse(search.read(self.root/'manifest.json')['full_study'])
        self.assertTrue(search.read(self.root/'summary.json')['calibration_finite_grid_minimum_verified'])
    def test_summary_tampering_refused(self):
        f=self.copy('summary');s=search.read(f/'summary.json');s['calibration_best_pair']=[1,1];search.save(f/'summary.json',s)
        with self.assertRaises(ValueError):search.verify_records(f)
    def test_missing_decision_refused(self):
        f=self.copy('missing');next((f/'decisions').glob('*.json')).unlink()
        with self.assertRaises(ValueError):search.verify_records(f)
    def test_stability_policy_cannot_be_relaxed(self):
        f=self.copy('policy');m=search.read(f/'manifest.json');m['quality_policy']['q22_tail_error_rad']=1;search.save(f/'manifest.json',m)
        with self.assertRaises(ValueError):search.verify_records(f)
    def test_full_trace_tampering_refused(self):
        f=self.copy('full');p=next((f/'full_state').glob('*.npz'));p.write_bytes(p.read_bytes()+b'tamper')
        with self.assertRaises(ValueError):search.verify_records(f)
    def test_frozen_selection_tampering_refused(self):
        f=self.copy('selected');s=search.read(f/'selection.json');s['pairs']=s['pairs'][:-1];search.save(f/'selection.json',s)
        with self.assertRaises(ValueError):search.verify_records(f)
    def test_existing_output_not_overwritten(self):
        m=search.engine.sha256(self.root/'manifest.json')
        with self.assertRaises(FileExistsError):search.main(['--smoke','--output',str(self.root)])
        self.assertEqual(m,search.engine.sha256(self.root/'manifest.json'))

if __name__=='__main__':unittest.main()
