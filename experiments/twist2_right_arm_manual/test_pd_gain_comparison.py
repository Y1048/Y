import copy
import csv
import tempfile
import unittest
from pathlib import Path
from pd_gain_comparison import candidates,evaluate,sha


class GainTests(unittest.TestCase):
    def fixture(self,folder,error=.02):
        plan=candidates();plan['limits']=dict(max_error_rad=.1,max_tau_est_nm=10,max_hold_rms_speed_rad_s=.1)
        candidate=next(c for c in plan['candidates'] if c['baseline'])
        rows=[];t=0.;sequence=0
        for cycle in range(3):
            for phase in (2,3,4,5):
                duration=plan['move_seconds'] if phase in (2,4) else 1
                for n in range(round(duration*50)):
                    sequence+=1;t+=.02
                    row=dict(writer_valid=1,writer_sequence=sequence,writer_write_returned_s=t,
                             writer_trial_phase=phase,writer_trial_cycle=cycle)
                    for i in range(29):
                        row.update({f'writer_kp_{i}':candidate['kp'][i],f'writer_kd_{i}':candidate['kd'][i]})
                    row.update(writer_q_22=error,writer_target_22=0,writer_dq_22=.01,writer_tau_est_22=1)
                    rows.append(row)
        path=Path(folder)/'run.csv'
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
        run=dict(candidate_id=candidate['id'],reference_sha256=plan['reference_sha256'],
                 termination_reason='pd trial completed',csv=str(path),csv_sha256=sha(path),move_seconds=plan['move_seconds'])
        return plan,run

    def test_grid_only_changes_selected_joint(self):
        plan=candidates(22);base=next(c for c in plan['candidates'] if c['baseline'])
        self.assertEqual(len(plan['candidates']),9)
        for c in plan['candidates']:
            for name in ('kp','kd'):
                self.assertEqual(c[name][:22]+c[name][23:],base[name][:22]+base[name][23:])

    def test_known_error_and_limit_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            plan,run=self.fixture(d)
            result=evaluate(plan,run);self.assertTrue(result['eligible'])
            self.assertAlmostEqual(result['mean_cycle_rms_error_rad'],.02)
            plan['limits']['max_error_rad']=.01
            self.assertFalse(evaluate(plan,run)['eligible'])

    def test_incomplete_hash_duration_and_gain_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            plan,run=self.fixture(d)
            for field,value in [('termination_reason','input_disengaged'),('reference_sha256','x'),
                                ('csv_sha256','x'),('move_seconds',2),('candidate_id','p0.8_d0.8')]:
                modified=copy.deepcopy(run);modified[field]=value
                with self.assertRaises(ValueError):evaluate(plan,modified)

    def test_missing_thresholds_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            plan,run=self.fixture(d);plan['limits']['max_error_rad']=None
            with self.assertRaises(ValueError):evaluate(plan,run)


if __name__=='__main__':unittest.main()
