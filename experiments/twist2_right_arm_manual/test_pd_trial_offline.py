import csv
import math
from pathlib import Path
import tempfile
import unittest
from pd_trial_offline import duration, generate, segment, review


class TrialTests(unittest.TestCase):
    def test_writer_pair_deduplicates_and_excludes_damping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'writer.csv'
            rows=[]
            for n, seq, kp in ((0,1,40),(1,1,40),(2,2,0),(3,3,40)):
                row=dict(elapsed_s=n*.02, phase='test', writer_valid=1,
                    writer_trial_phase=2 if seq==1 else 4,
                    writer_sequence=seq, writer_state_received_s=seq*.02-.001,
                    writer_cycle_started_s=seq*.02, writer_write_returned_s=seq*.02+.001)
                for i in range(22,29):
                    row.update({f'writer_q_{i}':.2,f'writer_target_{i}':.3,
                                f'writer_kp_{i}':kp,f'q_{i}':100,f'desired_target_{i}':0})
                rows.append(row)
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,rows[0].keys());w.writeheader();w.writerows(rows)
            result=review(path,'test','writer')
            self.assertEqual(result['samples'],2)
            self.assertAlmostEqual(result['joints']['22']['rms_rad'],.1)
            result=review(path,'unrelated_policy_phase','writer',2)
            self.assertEqual(result['samples'],1)
            with self.assertRaises(ValueError):review(path,'test','desired',2)

    def test_exact_bounds_and_endpoints(self):
        for angle in (1, 10, 90):
            d = math.radians(angle)
            v = math.radians(45)
            t = duration(d, v, .32)
            self.assertAlmostEqual(segment(0, d, t)[0], 0)
            self.assertAlmostEqual(segment(t, d, t)[0], d)
            for s in (0, 1, .5, (3-math.sqrt(3))/6, (3+math.sqrt(3))/6):
                q, dq, ddq = segment(t*s, d, t)
                self.assertGreaterEqual(q, -1e-12)
                self.assertLessEqual(q, d+1e-12)
                self.assertLessEqual(abs(dq), v+1e-12)
                self.assertLessEqual(abs(ddq), .32+1e-12)
            for s in (0, 1):
                self.assertEqual(segment(t*s, d, t)[1:], (0, 0))

    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'trial.csv'
            result = generate(path)
            self.assertLess(result['peak_speed_deg_s'], 45)
            with path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(float(rows[-1]['offset_rad']), 0)
            self.assertEqual({r['phase'] for r in rows},
                             {'outbound', 'return', 'hold_far', 'hold_start'})
            with self.assertRaises(FileExistsError):
                generate(path)

    def test_invalid_parameters(self):
        for value in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                duration(.1, .5, value)

    def test_review_known_error_and_bad_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'log.csv'
            fields = ['elapsed_s', 'phase']
            for i in range(22, 29):
                fields += [f'q_{i}', f'desired_target_{i}']
            def write(times):
                with path.open('w', newline='') as f:
                    w = csv.DictWriter(f, fields); w.writeheader()
                    for t in times:
                        row = {'elapsed_s':t, 'phase':'test'}
                        for i in range(22, 29):
                            row.update({f'q_{i}':.2, f'desired_target_{i}':.1})
                        w.writerow(row)
            write([0, .02])
            result = review(path, 'test')
            self.assertAlmostEqual(result['joints']['22']['rms_rad'], .1)
            with self.assertRaises(ValueError): review(path, 'missing')
            write([0, 0])
            with self.assertRaises(ValueError): review(path, 'test')


if __name__ == '__main__': unittest.main()
