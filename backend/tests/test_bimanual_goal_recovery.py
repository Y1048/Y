"""Display-solver recovery lifecycle checks using controlled solver outcomes.

These fixtures reproduce a valid but stalled cached branch. They are generated
mechanism tests, not recorded Quest replay or measured G1 validation.
"""
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_geometric_goal as geometric
import g1_bimanual_goal_preview as preview
from g1_bimanual_sim import BimanualSimulation


class GoalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.sim = BimanualSimulation()
        self.pose_model = BimanualSimulation()
        self.q = self.sim.home.copy()
        self.q[self.sim.qids[0]] += .02
        self.bad = self.q.copy()
        self.bad[self.sim.qids[0]] += .02
        self.better = self.q.copy()
        self.better[self.sim.qids[0]] += .03
        self.goals = dict(self.sim.home_targets)
        self.sim.config.update(self.q)

    def solution(self, q, errors=(.20, .12), angles=(1., 1.), *, iterations=0,
                 termination='local_stationary'):
        self.pose_model.config.update(q)
        return dict(valid=True, status='geometric_goal_partial',
                    q=q.copy(), poses=geometric._poses(self.pose_model),
                    iterations=iterations, termination=termination,
                    position_error_m=dict(zip(('left', 'right'), errors)),
                    orientation_error_rad=dict(zip(('left', 'right'), angles)),
                    minimum_clearance_m=.02)

    def cache(self):
        return dict(arm_q=self.bad[self.sim.qids].copy())

    def test_repeated_stalled_cache_recovers_from_progressing_alternate(self):
        # Primary branch stays valid, so invalid-seed fallback alone cannot fix
        # this case. The alternate first makes progress, then becomes better.
        cache = self.cache()
        calls = []
        recovery_seeds = []
        for frame in range(3):
            def solve(sim, goals, **kwargs):
                seed = kwargs.get('initial_q')
                calls.append(None if seed is None else seed.copy())
                if len(calls) % 2 == 1:
                    return self.solution(self.bad)
                recovery_seeds.append(seed.copy() if seed is not None else sim.config.q.copy())
                q = self.better.copy()
                q[self.sim.qids[1]] += frame * .01
                return self.solution(q, errors=(.24, .13) if frame < 2 else (.05, .04),
                                     iterations=3, termination='time_budget')
            with patch.object(geometric, 'solve_geometric_goal', side_effect=solve):
                result, cache = preview._solve_with_recovery(
                    self.sim, self.goals, self.q, cache)
            self.assertTrue(result['valid'])
            self.assertTrue(result['recovery_attempted'])
            self.assertEqual(result['recovery_selected'], frame == 2)
            if frame < 2:
                np.testing.assert_array_equal(result['q'], self.bad)
            else:
                self.assertLessEqual(max(result['position_error_m'].values()), .05)
            np.testing.assert_array_equal(self.sim.config.q, result['q'])
        self.assertEqual(len(calls), 6, 'Recovery must stay bounded to two solves per frame')
        np.testing.assert_array_equal(recovery_seeds[1][self.sim.qids], self.better[self.sim.qids])
        self.assertFalse(np.array_equal(recovery_seeds[2][self.sim.qids],
                                        recovery_seeds[0][self.sim.qids]))

    def test_one_arm_improvement_cannot_hide_other_arm_regression(self):
        # A lower summed error alone would choose the second result, worsening
        # the opposite arm by 10 mm, beyond the solver's 1 mm precision.
        outcomes = [self.solution(self.bad, errors=(.20, .02)),
                    self.solution(self.better, errors=(.01, .03), iterations=4)]
        with patch.object(geometric, 'solve_geometric_goal', side_effect=outcomes):
            result, _ = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertFalse(result['recovery_selected'])
        np.testing.assert_array_equal(result['q'], self.bad)

    def test_meaningful_pareto_position_improvement_is_selected(self):
        outcomes = [self.solution(self.bad, errors=(.20, .02)),
                    self.solution(self.better, errors=(.18, .02), iterations=2)]
        with patch.object(geometric, 'solve_geometric_goal', side_effect=outcomes):
            result, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertTrue(result['recovery_selected'])
        np.testing.assert_array_equal(result['q'], self.better)
        np.testing.assert_array_equal(cache['arm_q'], self.better[self.sim.qids])

    def test_sub_two_millimetre_position_gain_does_not_switch_branch(self):
        outcomes = [self.solution(self.bad, errors=(.20, .02)),
                    self.solution(self.better, errors=(.1985, .02), iterations=2)]
        with patch.object(geometric, 'solve_geometric_goal', side_effect=outcomes):
            result, _ = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertFalse(result['recovery_selected'])
        np.testing.assert_array_equal(result['q'], self.bad)

    def test_solver_spatial_precision_allows_tiny_trade_but_not_arm_regression(self):
        cases = (
            # Regression taken from replay residuals, tested as a ranking
            # fixture: a 20 micrometre right-arm change must not veto 85 mm.
            ((.12712, .04123), (.04157, .04125), True),
            ((.180, .00020), (.040, .00021), True),
            ((.030, .0100), (.020, .0101), True),
            ((.030, .0100), (.020, .0120), False),
            ((.180, .00020), (.040, .00121), False),
        )
        for old, new, expected in cases:
            with self.subTest(old=old, new=new):
                primary = self.solution(self.bad, errors=old)
                candidate = self.solution(self.better, errors=new)
                self.assertEqual(preview._prefer_recovery(candidate, primary), expected)

    def test_invalid_alternate_does_not_replace_valid_primary(self):
        outcomes = [self.solution(self.bad), dict(valid=False, status='invalid_warm_start', iterations=0)]
        with patch.object(geometric, 'solve_geometric_goal', side_effect=outcomes):
            result, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertTrue(result['valid'])
        self.assertFalse(result['recovery_selected'])
        np.testing.assert_array_equal(result['q'], self.bad)
        self.assertIsNone(cache.get('recovery_arm_q'))

    def test_stationary_alternate_restarts_on_other_seed(self):
        cache = self.cache()
        seen = []
        def solve(sim, goals, **kwargs):
            seed = kwargs.get('initial_q')
            seen.append(None if seed is None else seed.copy())
            return self.solution(self.bad)
        with patch.object(geometric, 'solve_geometric_goal', side_effect=solve):
            for _ in range(2):
                result, cache = preview._solve_with_recovery(
                    self.sim, self.goals, self.q, cache)
        self.assertTrue(result['valid'])
        np.testing.assert_array_equal(seen[1][self.sim.qids], self.sim.home[self.sim.qids])
        np.testing.assert_array_equal(seen[3][self.sim.qids], self.q[self.sim.qids])

    def test_reachable_primary_does_not_pay_for_recovery_search(self):
        with patch.object(geometric, 'solve_geometric_goal',
                          return_value=self.solution(self.better, errors=(.001, .001))) as solve:
            result, _ = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertEqual(solve.call_count, 1)
        self.assertFalse(result['recovery_attempted'])

    def test_live_seed_selection_uses_fresh_bilateral_fk_not_cached_errors(self):
        # The same cached q can become better or worse after the hand target
        # changes. Old residual diagnostics must never decide the next seed.
        cases = (
            ('live_improves_both', (.010, .010), (.100, .100), (0., 0.), True),
            ('warm_still_better', (.100, .100), (.010, .010), (9., 9.), False),
            ('live_worsens_right', (.010, .030), (.100, .020), (9., 9.), False),
        )
        for name, live_errors, warm_errors, obsolete_errors, choose_live in cases:
            with self.subTest(name=name):
                cache = self.cache()
                cache.update(seed_kind='reference',
                             position_error_m=dict(zip(('left', 'right'), obsolete_errors)))
                evaluations = []
                def evaluate(poses, goals):
                    self.assertIs(goals, self.goals)
                    evaluations.append(self.sim.config.q.copy())
                    values = live_errors if len(evaluations) == 1 else warm_errors
                    return (dict(zip(('left', 'right'), values)),
                            dict(left=.1, right=.1))
                solved = self.solution(self.q if choose_live else self.bad,
                                       errors=(.001, .001))
                def solve(sim, goals, **kwargs):
                    np.testing.assert_array_equal(sim.config.q, self.q)
                    self.assertIs(goals, self.goals)
                    initial = kwargs.get('initial_q')
                    if choose_live:
                        self.assertIsNone(initial)
                    else:
                        np.testing.assert_array_equal(initial, self.bad)
                    return solved
                with patch.object(geometric, '_errors', side_effect=evaluate), \
                     patch.object(geometric, 'solve_geometric_goal', side_effect=solve) as solver:
                    result, next_cache = preview._solve_with_recovery(
                        self.sim, self.goals, self.q, cache)
                self.assertEqual(solver.call_count, 1)
                self.assertEqual(len(evaluations), 2)
                np.testing.assert_array_equal(evaluations[0], self.q)
                np.testing.assert_array_equal(evaluations[1], self.bad)
                self.assertEqual(result['seed_kind'], 'live' if choose_live else 'reference')
                self.assertEqual(next_cache['seed_kind'], result['seed_kind'])
                self.assertFalse(result['recovery_attempted'])

    def test_fresh_fk_comparison_consumes_shared_deadline_and_restores_current_q(self):
        now = [100.]
        previous = self.cache()
        previous.update(recovery_arm_q=self.better[self.sim.qids].copy(),
                        recovery_seed='reference')
        before = copy.deepcopy(previous)
        def evaluate(poses, goals):
            now[0] += .006
            return dict(left=.1, right=.1), dict(left=.1, right=.1)
        with patch.object(preview.time, 'perf_counter', side_effect=lambda: now[0]), \
             patch.object(geometric, '_errors', side_effect=evaluate), \
             patch.object(geometric, 'solve_geometric_goal') as solver:
            result, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, previous, deadline=100.010)
        self.assertEqual(result, dict(valid=False, status='time_budget'))
        self.assertIs(cache, previous)
        self.assertEqual(set(cache), set(before))
        for name in ('arm_q', 'recovery_arm_q'):
            np.testing.assert_array_equal(cache[name], before[name])
        self.assertEqual(cache['recovery_seed'], before['recovery_seed'])
        solver.assert_not_called()
        np.testing.assert_array_equal(self.sim.config.q, self.q)

    def test_preserved_expired_cache_is_revalidated_on_next_fresh_request(self):
        previous = self.cache()
        previous['seed_kind'] = 'reference'
        with patch.object(preview.time, 'perf_counter', return_value=101.):
            expired, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, previous, deadline=100.)
        self.assertFalse(expired['valid'])
        self.assertIs(cache, previous)
        fresh_goals = dict(self.goals)
        evaluations = []
        def evaluate(poses, goals):
            self.assertIs(goals, fresh_goals)
            evaluations.append(self.sim.config.q.copy())
            error = .010 if len(evaluations) == 1 else .100
            return dict(left=error, right=error), dict(left=.1, right=.1)
        solved = self.solution(self.q, errors=(.001, .001))
        with patch.object(geometric, '_errors', side_effect=evaluate), \
             patch.object(geometric, 'solve_geometric_goal', return_value=solved) as solver:
            result, cache = preview._solve_with_recovery(
                self.sim, fresh_goals, self.q, cache)
        self.assertEqual(len(evaluations), 2)
        np.testing.assert_array_equal(evaluations[0], self.q)
        np.testing.assert_array_equal(evaluations[1], self.bad)
        self.assertIs(solver.call_args.args[1], fresh_goals)
        self.assertIsNone(solver.call_args.kwargs['initial_q'])
        self.assertTrue(result['valid'])
        self.assertEqual(result['seed_kind'], 'live')

    def test_invalid_geometry_still_discards_cache(self):
        invalid = dict(valid=False, status='invalid_warm_start', iterations=0)
        with patch.object(geometric, 'solve_geometric_goal', side_effect=[invalid.copy(), invalid.copy()]):
            result, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertFalse(result['valid'])
        self.assertIsNone(cache)
        np.testing.assert_array_equal(self.sim.config.q, self.q)

    def test_invalid_primary_can_recover_without_reusing_invalid_result(self):
        outcomes = [dict(valid=False, status='invalid_warm_start', iterations=0),
                    self.solution(self.better, errors=(.05, .04), iterations=2)]
        with patch.object(geometric, 'solve_geometric_goal', side_effect=outcomes):
            result, cache = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache())
        self.assertTrue(result['valid'])
        self.assertTrue(result['recovery_selected'])
        np.testing.assert_array_equal(cache['arm_q'], self.better[self.sim.qids])

    def test_orientation_tie_break_cannot_override_position_failure(self):
        primary = self.solution(self.bad, errors=(.0005, .0006), angles=(.5, .5))
        candidate = self.solution(self.better, errors=(.0005, .0006), angles=(.48, .5))
        self.assertTrue(preview._prefer_recovery(candidate, primary))
        candidate['orientation_error_rad']['right'] = .51
        self.assertFalse(preview._prefer_recovery(candidate, primary))
        candidate['orientation_error_rad']['right'] = .5
        candidate['position_error_m']['left'] = .003
        self.assertFalse(preview._prefer_recovery(candidate, primary))

    def test_context_change_discards_primary_and_recovery_cache(self):
        payload = io.BytesIO()
        preview._SnapshotWriter(payload, {id(v): k for k, v in
            preview._snapshot_objects(self.sim).items()}).dump(self.sim)
        old_cache = self.cache()
        old_cache.update(key=(0, ('old', 1)), recovery_arm_q=self.better[self.sim.qids].copy(),
                         recovery_seed='live')
        solution = self.solution(self.q, errors=(.001, .001))
        solution.update(seed_kind='live', recovery_attempted=False, recovery_selected=False)
        with patch.object(preview, '_WORKER_NATIVE', preview._snapshot_objects(self.pose_model)), \
             patch.object(preview, '_WORKER_GEOMETRIC_CACHE', old_cache), \
             patch.object(preview, '_solve_with_recovery', return_value=(solution, None)) as helper:
            result = preview._rollout(payload.getvalue(), self.q, self.goals,
                                      1, ('new', 2), 10., 17)
            self.assertIsNone(helper.call_args.args[3])
            self.assertIsNone(preview._WORKER_GEOMETRIC_CACHE)
        self.assertTrue(result['valid'])

    def test_attempts_share_absolute_deadline(self):
        now = [100.]
        allowances = []
        def solve(sim, goals, **kwargs):
            allowance = kwargs.get('max_duration_s')
            self.assertIsNotNone(allowance)
            self.assertGreater(allowance, 0.)
            self.assertLessEqual(allowance, 100.025 - now[0] + 1e-9)
            allowances.append(allowance)
            now[0] += .018 if len(allowances) == 1 else .005
            return self.solution(self.bad, termination='time_budget')
        with patch.object(preview.time, 'perf_counter', side_effect=lambda: now[0]), \
             patch.object(geometric, 'solve_geometric_goal', side_effect=solve):
            result, _ = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache(), deadline=100.025)
        self.assertTrue(result['valid'])
        self.assertEqual(len(allowances), 2)
        self.assertLessEqual(allowances[1], .007 + 1e-9,
                             'Recovery must not receive a new independent full budget')

    def test_native_overrun_does_not_start_extra_solve(self):
        now = [100.]
        def solve(sim, goals, **kwargs):
            now[0] = 100.05
            return self.solution(self.bad, termination='time_budget')
        with patch.object(preview.time, 'perf_counter', side_effect=lambda: now[0]), \
             patch.object(geometric, 'solve_geometric_goal', side_effect=solve) as solver:
            result, _ = preview._solve_with_recovery(
                self.sim, self.goals, self.q, self.cache(), deadline=100.04)
        self.assertEqual(solver.call_count, 1)
        self.assertTrue(result['valid'])
        np.testing.assert_array_equal(result['q'], self.bad)

    def test_recovery_uses_current_frozen_body_and_preserves_external_inputs(self):
        self.sim.set_base_yaw(.4)
        q = self.sim.config.q.copy()
        cache = self.cache()
        cache['recovery_arm_q'] = self.better[self.sim.qids].copy()
        cache['recovery_seed'] = 'reference'
        before_cache = copy.deepcopy(cache)
        before_q = q.copy()
        before_goals = {s: g.as_matrix().copy() for s, g in self.goals.items()}
        frozen = np.ones(self.sim.model.nq, dtype=bool)
        frozen[self.sim.qids] = False
        seen = []
        def solve(sim, goals, **kwargs):
            np.testing.assert_array_equal(sim.config.q, q)
            seed = kwargs.get('initial_q')
            if seed is not None:
                np.testing.assert_array_equal(seed[frozen], q[frozen])
                seen.append(seed.copy())
            candidate = q.copy()
            candidate[self.sim.qids] = self.bad[self.sim.qids]
            return self.solution(candidate)
        with patch.object(geometric, 'solve_geometric_goal', side_effect=solve):
            preview._solve_with_recovery(self.sim, self.goals, q, cache)
        self.assertGreaterEqual(len(seen), 1)
        np.testing.assert_array_equal(q, before_q)
        for name in ('arm_q', 'recovery_arm_q'):
            np.testing.assert_array_equal(cache[name], before_cache[name])
        for side in before_goals:
            np.testing.assert_array_equal(self.goals[side].as_matrix(), before_goals[side])


if __name__ == '__main__':
    unittest.main()
