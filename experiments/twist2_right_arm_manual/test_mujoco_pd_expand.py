"""Allowlisted offline regressions for the additive expanded search."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import mujoco
import mujoco_pd_expand as expanded
import mujoco_pd_sweep as engine

class ExpandedTest(unittest.TestCase):
    def test_coarse_unique_and_within_existing_bounds(self):
        pairs=list(expanded.itertools.product(expanded.KP,expanded.KD))
        self.assertEqual(len(pairs),192)
        self.assertEqual(len(set(pairs)),192)
        for p,d in pairs: engine.candidate_gains(engine.load_contract(),p,d)
    def test_refinement_bounds_and_no_duplicates(self):
        r={'kp_proximal':100.,'kd_proximal':.1,'scenario':['nominal'],'eligible':True,
           'metrics':{'reference_rmse_joint22_rad':.01}}
        pairs=expanded.fine_pairs([r])
        self.assertTrue(pairs)
        self.assertNotIn((100.,.1),pairs)
        self.assertEqual(len(pairs),len(set(pairs)))
        self.assertTrue(all(1<=p<=100 and .1<=d<=20 for p,d in pairs))
    def test_scenario_step_divisibility_and_unique_names(self):
        self.assertEqual(len({s[0] for s in expanded.SCENARIOS}),len(expanded.SCENARIOS))
        for _,dt,mass,damping,friction in expanded.SCENARIOS:
            self.assertAlmostEqual(.002/dt,round(.002/dt))
            self.assertGreater(mass,0); self.assertGreaterEqual(damping,0)
            self.assertGreaterEqual(friction,0)
    def test_missing_stress_cannot_pass(self):
        r={'kp_proximal':40.,'kd_proximal':5.,'scenario':['nominal'],'eligible':True,
           'metrics':{'reference_rmse_joint22_rad':.02}}
        self.assertFalse(expanded.robust_rank([r],[(40.,5.)])[0]['all_scenarios_eligible'])
    def test_failed_stress_cannot_pass(self):
        rows=[{'kp_proximal':40.,'kd_proximal':5.,'scenario':s,'eligible':s[0]!='mass_125',
               'metrics':{'reference_rmse_joint22_rad':.02},'reason':'','exclusion_reasons':[]}
              for s in expanded.SCENARIOS]
        self.assertFalse(expanded.robust_rank(rows,[(40.,5.)])[0]['all_scenarios_eligible'])
    def test_nominal_observer_parity_and_saved_trace(self):
        model,qa,va,motors,_=engine.load_model(engine.MODEL,.001)
        baseline,original=engine.run_candidate(model,qa,va,motors,engine.load_contract(),40,5)
        with tempfile.TemporaryDirectory() as folder:
            a=expanded.simulate((40.,5.,expanded.SCENARIOS[0],folder,'a','test'))
            self.assertEqual(a['metrics'],baseline['metrics'])
            self.assertEqual(a['completed'],baseline['completed'])
            self.assertEqual(a['physics_observation']['trial_contact_steps'],0)
            self.assertGreater(a['physics_observation']['trial_physics_steps'],a['samples'])
            with np.load(Path(folder)/a['trace_npz']) as trace:
                np.testing.assert_array_equal(trace['values'][:,7],[r['q_22'] for r in original])
    def test_mass_perturbation_changes_response(self):
        with tempfile.TemporaryDirectory() as folder:
            a=expanded.simulate((56.,3.,expanded.SCENARIOS[0],folder,'a','test'))
            b=expanded.simulate((56.,3.,expanded.SCENARIOS[3],folder,'b','test'))
            self.assertNotEqual(a['metrics']['reference_rmse_joint22_rad'],b['metrics']['reference_rmse_joint22_rad'])
    def test_failed_gain_is_retained_but_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            r=expanded.simulate((1.,.1,expanded.SCENARIOS[0],folder,'bad','test'))
            self.assertFalse(r['eligible'])
            self.assertTrue((Path(folder)/'cases/bad.json').exists())
            self.assertTrue((Path(folder)/r['trace_npz']).exists())
    def test_observer_restored_on_exception(self):
        original=mujoco.mj_step
        with tempfile.TemporaryDirectory() as folder, patch.object(engine,'run_candidate',side_effect=RuntimeError('injected')):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                expanded.simulate((40.,5.,expanded.SCENARIOS[0],folder,'a','test'))
        self.assertIs(mujoco.mj_step,original)
    def test_output_folder_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'keep'; marker.write_text('unchanged')
            with self.assertRaises(FileExistsError): expanded.main(['--output',folder])
            self.assertEqual(marker.read_text(),'unchanged')

if __name__=='__main__': unittest.main()
