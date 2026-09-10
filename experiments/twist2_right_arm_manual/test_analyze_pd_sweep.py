import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from analyze_pd_sweep import analyze


class SweepAnalysisTest(unittest.TestCase):
    def make_csv(self,path,omit=None):
        fields=['writer_valid','writer_sequence','writer_trial_phase','writer_trial_cycle']
        for j in range(22,29):fields += [f'writer_q_{j}',f'writer_dq_{j}',f'writer_tau_est_{j}',f'writer_target_{j}',f'writer_kp_{j}',f'writer_kd_{j}']
        with path.open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();seq=0
            for kp,error in ((40.,.06),(48.,.04),(56.,.05)):
                for cycle in range(3):
                    for phase in (2,3,4,5):
                        if omit==(kp,cycle,phase):continue
                        seq+=1;row={'writer_valid':'1','writer_sequence':seq,'writer_trial_phase':phase,'writer_trial_cycle':cycle}
                        for j in range(22,29):row.update({f'writer_q_{j}':1-error,f'writer_dq_{j}':.2,f'writer_tau_est_{j}':3,f'writer_target_{j}':1,f'writer_kp_{j}':kp if j<26 else 20,f'writer_kd_{j}':5 if j<26 else 1})
                        w.writerow(row)

    def test_ranks_complete_candidates(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.csv';self.make_csv(path)
            result=analyze(path)
            self.assertEqual([x['proximal_kp'] for x in result['ranking']],[48.,56.,40.])

    def test_rejects_incomplete_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.csv';self.make_csv(path,(48.,2,5))
            with self.assertRaisesRegex(ValueError,'incomplete Kp 48'):
                analyze(path)


if __name__=='__main__':unittest.main()
