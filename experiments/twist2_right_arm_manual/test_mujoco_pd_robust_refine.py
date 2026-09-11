"""Offline robust-refinement plan, ranking, dynamics and artifact tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import mujoco_pd_robust_refine as study
import mujoco_pd_motor_stress as motor
import mujoco_pd_sweep as engine


def synthetic(pair, scenario, error, eligible=True, phase='calibration'):
    return {'kp_proximal': pair[0], 'kd_proximal': pair[1], 'eligible': eligible,
      'study_phase': phase, 'study_scenario': scenario.identity,
      'metrics': {'reference_rmse_joint22_rad': error, 'peak_hold_overshoot_joint22_rad': .001,
                  'peak_torque_joint22_nm': 1.},
      'joint_limit_guard': {'minimum_soft_margin_rad': [.2]*29},
      'reason': '' if eligible else 'joint_stopping_envelope_exhausted',
      'exclusion_reasons': [] if eligible else ['joint_stopping_envelope_exhausted']}


class PlanTest(unittest.TestCase):
    def test_grid_is_unique_bounded_and_keeps_baselines(self):
        pairs=study.gain_pairs()
        self.assertEqual(len(pairs),44)
        self.assertTrue(set(study.CONTROLS)<=set(pairs))
        for p,d in pairs: engine.candidate_gains(engine.load_contract(),p,d)
        self.assertEqual(max(p for p,d in pairs),100)

    def test_prespecified_scenarios_and_partition(self):
        self.assertEqual(len(study.CALIBRATION),27)
        self.assertEqual(len(study.HOLDOUT),8)
        for s in study.CALIBRATION+study.HOLDOUT: s.validate()
        train={s.identity for s in study.CALIBRATION}
        self.assertFalse(train & {s.identity for s in study.HOLDOUT})

    def test_invalid_scenarios_refused(self):
        bad=(study.Scenario('other',('name',1,1,1,1)),
             study.Scenario('model',('name',.001,0,1,0)),
             study.Scenario('model',('name',.0007,1,1,0)),
             study.Scenario('motor',('name',1,.0005,0,.001)),
             study.Scenario('motor',('name',float('nan'),0,0,.001)))
        for s in bad:
            with self.subTest(s=s),self.assertRaises(ValueError): s.validate()

    def test_no_case_id_collision(self):
        a=study.make_jobs(study.gain_pairs(),study.CALIBRATION,'calibration',Path('unused'))
        b=study.make_jobs([(100.,1.)],study.HOLDOUT,'holdout',Path('unused'))
        self.assertEqual(len(a),1188)
        self.assertEqual(len({x[4] for x in a+b}),len(a+b))

    def test_missing_case_has_no_selectable_score(self):
        s=study.CALIBRATION[:2]
        r=study.rank_pairs([synthetic((100,1),s[0],.001)],[(100,1)],s,'calibration')[0]
        self.assertFalse(r['all_conditions_present']); self.assertIsNone(r['selectable_worst_rmse_rad'])

    def test_failed_condition_not_hidden_by_low_average(self):
        s=study.CALIBRATION[:2]
        rows=[synthetic((100,.6),s[0],.001),synthetic((100,.6),s[1],.001,False),
              synthetic((100,1),s[0],.01),synthetic((100,1),s[1],.02)]
        rank=study.rank_pairs(rows,[(100,.6),(100,1)],s,'calibration')
        self.assertEqual(rank[0]['pair'],[100,1]);self.assertIsNone(rank[1]['selectable_worst_rmse_rad'])

    def test_minimax_not_nominal_ranking(self):
        s=study.CALIBRATION[:2]
        rows=[synthetic((80,1),s[0],.01),synthetic((80,1),s[1],.02),
              synthetic((100,1),s[0],.001),synthetic((100,1),s[1],.03)]
        self.assertEqual(study.rank_pairs(rows,[(80,1),(100,1)],s,'calibration')[0]['pair'],[80,1])

    def test_duplicate_evidence_refused(self):
        r=synthetic((100,1),study.CALIBRATION[0],.01)
        with self.assertRaises(ValueError): study.rank_pairs([r,r],[(100,1)],study.CALIBRATION[:1],'calibration')

    def test_holdout_cannot_influence_finalist_selection(self):
        s=study.CALIBRATION[:1]
        rows=[synthetic((80,1),s[0],.01),synthetic((100,1),s[0],.02)]
        before=study.rank_pairs(rows,[(80,1),(100,1)],s,'calibration')
        rows.append(synthetic((80,1),study.HOLDOUT[0],999,False,'holdout'))
        after=study.rank_pairs(rows,[(80,1),(100,1)],s,'calibration')
        self.assertEqual(before,after)

    def test_bad_workers_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):study.main(['--output',str(Path(d)/'out'),'--workers','0'])
            self.assertFalse((Path(d)/'out').exists())


class DynamicsAndEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.out=cls.root/'smoke'
        cmd=[sys.executable,'-B',str(Path(study.__file__)),'--smoke','--workers','2','--output',str(cls.out)]
        cls.process=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        if cls.process.returncode:
            raise AssertionError(cls.process.stdout+cls.process.stderr)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_smoke_is_complete_audited_and_not_full_study(self):
        manifest=json.loads((self.out/'manifest.json').read_text())
        summary=json.loads((self.out/'summary.json').read_text())
        self.assertFalse(manifest['full_study']);self.assertEqual(summary['total_cases'],8)
        self.assertIsNone(summary['recommended_hardware_gains'])
        audit=study.verify_artifacts(self.out,engine.ROOT)
        self.assertTrue(audit['passed']);self.assertEqual(audit['all_joint_records'],232)

    def test_nominal_matches_existing_guarded_motor_engine(self):
        r=json.loads((self.out/'cases/calibration_00002.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            reference=motor.simulate((100.,1.,motor.SCENARIOS[0],d,'ref'))
            self.assertEqual(reference['metrics'],r['metrics'])
            self.assertEqual(reference['joint_limit_guard'],r['joint_limit_guard'])
            with np.load(self.out/r['trace_npz']) as a,np.load(Path(d)/reference['trace_npz']) as b:
                np.testing.assert_array_equal(a['values'],b['values'])

    def test_all_case_guards_present(self):
        for path in (self.out/'cases').glob('*.json'):
            r=json.loads(path.read_text());self.assertTrue(study.verify_guard_result(r))
            self.assertEqual(len(r['joint_limit_guard']['minimum_soft_margin_rad']),29)

    def test_existing_directory_not_overwritten(self):
        before=engine.sha256(self.out/'manifest.json')
        with self.assertRaises(FileExistsError):study.main(['--output',str(self.out),'--smoke'])
        self.assertEqual(before,engine.sha256(self.out/'manifest.json'))

    def test_missing_case_refused(self):
        path=self.out/'cases/holdout_00000.json';raw=path.read_bytes()
        try:
            path.unlink()
            with self.assertRaises(ValueError):study.verify_artifacts(self.out)
        finally:path.write_bytes(raw)

    def test_summary_score_tampering_refused(self):
        path=self.out/'summary.json';raw=path.read_bytes()
        try:
            value=json.loads(raw);value['calibration_ranking'][0]['partial_worst_rmse_rad']=999
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):study.verify_artifacts(self.out)
        finally:path.write_bytes(raw)

    def test_finalist_tampering_refused(self):
        path=self.out/'selection.json';raw=path.read_bytes()
        try:
            value=json.loads(raw);value['pairs'].append([100,2]);path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):study.verify_artifacts(self.out)
        finally:path.write_bytes(raw)

    def test_scenario_label_tampering_refused(self):
        path=self.out/'cases/calibration_00000.json';raw=path.read_bytes()
        try:
            value=json.loads(raw);value['study_scenario']='model/unknown';path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):study.verify_artifacts(self.out)
        finally:path.write_bytes(raw)

    def test_original_calibration_hash_freeze_checked(self):
        path=self.out/'cases/calibration_00000.json';raw=path.read_bytes()
        try:
            value=json.loads(raw);value['wall_seconds']+=1;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):study.verify_artifacts(self.out)
        finally:path.write_bytes(raw)


if __name__=='__main__':unittest.main()
