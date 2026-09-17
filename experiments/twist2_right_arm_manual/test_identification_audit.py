import csv
import json
import tempfile
import unittest
from pathlib import Path
from audit_identification_run import audit,sha


class AuditTest(unittest.TestCase):
    def test_provenance_and_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            run={'schema':'g1.pd.run.v1','mode':'pd_reach','kp':[40]*29,'kd':[5]*29}
            (d/'run.json').write_text(json.dumps(run))
            rows=[]
            for n in range(12):
                row=dict(writer_valid=1,writer_sequence=n*10+1,writer_write_returned_s=n*.02,
                         writer_trial_cycle=n//4,writer_trial_phase=n%4+2)
                for i in range(29):
                    for name in ('q','dq','target','target_dq','tau_est','tau_ff','kp','kd'):
                        row[f'writer_{name}_{i}']=40 if name=='kp' else 5 if name=='kd' else 0
                rows.append(row)
            with (d/'policy.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            result={'schema':'g1.pd.result.v1','csv_sha256':sha(d/'policy.csv'),
                    'run_sha256':sha(d/'run.json'),'completed_reach':True,
                    'reason':'pd trial completed','policy_samples':12}
            (d/'result.json').write_text(json.dumps(result))
            context={k:'fixture' for k in ('robot_id','session_group','support','payload','contact','operator_observations')}
            context['split']='train'
            report=audit(d,context)
            self.assertTrue(report['passes_basic_audit'])
            self.assertAlmostEqual(report['effective_sample_hz'],50)
            self.assertFalse(report['suitable_for_fast_dynamics'])
            self.assertEqual(report['skipped_writer_frames'],99)
            self.assertIn('missing_dataset_split',audit(d,{})['issues'])
            result['completed_reach']=False;(d/'result.json').write_text(json.dumps(result))
            self.assertIn('incomplete_trial',audit(d,context)['issues'])
            with (d/'policy.csv').open('a') as f:f.write('\n')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):audit(d,context)


if __name__=='__main__':unittest.main()
