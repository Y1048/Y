"""Private goal-preview math and nonblocking display lifecycle; no robot IO."""
from pathlib import Path
import copy
import io
import json
import sys
import time
import unittest
from concurrent.futures import Future
from unittest.mock import Mock, patch

import mink
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
import g1_bimanual_goal_preview as preview
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_target import BASIS
from g1_bimanual_measured_start import initialize_inactive_model


def encode(source):
    stream = io.BytesIO()
    preview._SnapshotWriter(stream, {id(v): k for k, v in
                            preview._snapshot_objects(source).items()}).dump(source)
    return stream.getvalue(), source.config.q.copy()


def manager():
    obj = object.__new__(preview.BimanualGoalPreview)
    obj.executor = Mock()
    obj.pending = None
    obj.result = None
    obj.context = ('backend', 'session', 1)
    obj.generation = 0
    obj.next_submit = 0.
    obj.error = None
    obj.closed = False
    obj.last_snapshot_ms = 0.
    obj.initializing = None
    obj.worker_ready = True
    obj.started = 0.
    return obj


def result(context=('backend', 'session', 1), generation=0, stamp=10.):
    return dict(valid=True, context=context, generation=generation,
                source_time=stamp, sequence=5, iterations=8, minimum_clearance_m=.02,
                position_error_m=[.001,.001], orientation_error_rad=[.01,.01],
                status='geometric_goal_converged', compute_ms=2.,
                poses={s: (np.array([.3, .2 if s == 'left' else -.2, .8]),
                           np.eye(3)) for s in ('left', 'right')})


class GoalPreviewTests(unittest.TestCase):
    def setUp(self):
        # Deterministic math comparisons do not depend on host scheduling.
        budget = patch.object(preview, 'SOLVE_BUDGET_S', None)
        budget.start()
        self.addCleanup(budget.stop)
        self.sim = BimanualSimulation()
        # Unit tests use private native buffers without changing process priority.
        self.native_owner = BimanualSimulation()
        preview._WORKER_NATIVE = preview._snapshot_objects(self.native_owner)
        preview._WORKER_GEOMETRIC_CACHE = None

    def goals(self, offset=.08):
        return {s: mink.SE3.from_rotation_and_translation(
                    p.rotation(), p.translation() + np.array([offset, 0., .02]))
                for s, p in self.sim.home_targets.items()}

    def roll(self, goals=None):
        payload, q = encode(self.sim)
        return preview._rollout(payload, q, self.goals() if goals is None else goals,
                                0, ('test', 1), 10., 1)

    def test_geometric_solution_and_live_state_is_unchanged(self):
        goals = self.goals()
        self.sim.step(goals)
        before, q = encode(self.sim)
        native = {name: (data.qpos.copy(), data.xpos.copy())
                  for name, data in preview._native_objects(self.sim).items()
                  if name != 'model'}
        digest = preview._model_digest(self.sim.model)
        expected = copy.deepcopy(self.sim, {id(self.sim.model): self.sim.model})
        from g1_bimanual_geometric_goal import solve_geometric_goal
        solution = solve_geometric_goal(expected, goals)
        self.assertTrue(solution['valid'])
        actual = self.roll(goals)
        self.assertTrue(actual['valid'])
        self.assertEqual(actual['iterations'], solution['iterations'])
        for side, (position, rotation) in actual['poses'].items():
            pose = expected.config.get_transform_frame_to_world(side+'_wrist_yaw_link', 'body')
            np.testing.assert_allclose(position, expected.base_rotation.T @ pose.translation(), atol=1e-12, rtol=0)
            np.testing.assert_allclose(rotation, expected.base_rotation.T @ pose.rotation().as_matrix(), atol=1e-12, rtol=0)
        self.assertEqual(encode(self.sim)[0], before)
        np.testing.assert_array_equal(self.sim.config.q, q)
        self.assertEqual(preview._model_digest(self.sim.model), digest)
        for name, (qpos, xpos) in native.items():
            data = preview._native_objects(self.sim)[name]
            np.testing.assert_array_equal(data.qpos, qpos)
            np.testing.assert_array_equal(data.xpos, xpos)

    def test_prediction_does_not_end_at_variable_stopping_tail(self):
        self.sim.step(self.goals())
        predicted = self.roll()
        stop = self.sim.checked_stop_target_poses()
        self.assertTrue(any(np.linalg.norm(predicted['poses'][s][0]-stop[s][0])>1e-6
                            for s in ('left','right')))

    def test_geometric_goal_does_not_run_the_rate_limited_live_step(self):
        self.sim.step(self.goals())
        with patch.object(BimanualSimulation, 'step', side_effect=AssertionError('live step')):
            prediction = self.roll()
        self.assertTrue(prediction['valid'])
        self.assertIn(prediction['status'], ('geometric_goal_converged','geometric_goal_partial'))

    def test_invalid_cached_witness_is_discarded_without_poisoning_live_state(self):
        self.assertTrue(self.roll()['valid'])
        preview._WORKER_GEOMETRIC_CACHE['arm_q'][:] = np.nan
        before = encode(self.sim)[0]
        self.assertTrue(self.roll()['valid'])
        self.assertTrue(np.isfinite(preview._WORKER_GEOMETRIC_CACHE['arm_q']).all())
        self.assertEqual(encode(self.sim)[0], before)

    def test_new_context_does_not_reuse_previous_geometric_witness(self):
        self.roll()
        preview._WORKER_GEOMETRIC_CACHE['key'] = (999, ('old-session', 1))
        from g1_bimanual_geometric_goal import solve_geometric_goal
        with patch('g1_bimanual_geometric_goal.solve_geometric_goal',
                   wraps=solve_geometric_goal) as solve:
            self.assertTrue(self.roll()['valid'])
            self.assertIsNone(solve.call_args.kwargs['initial_q'])

    def test_warm_start_never_replays_old_base_or_nonarm_coordinates(self):
        self.roll()
        from g1_bimanual_geometric_goal import solve_geometric_goal
        current = self.sim.config.q.copy()
        frozen = np.ones(self.sim.model.nq, dtype=bool)
        frozen[self.sim.qids] = False
        with patch('g1_bimanual_geometric_goal.solve_geometric_goal',
                   wraps=solve_geometric_goal) as solve:
            self.assertTrue(self.roll()['valid'])
            seed = solve.call_args.kwargs['initial_q']
            self.assertIsNotNone(seed)
            np.testing.assert_array_equal(seed[frozen], current[frozen])

    def test_independent_model_contracts_ignore_only_solver_scratch(self):
        self.assertEqual(preview._contract_digest(self.sim),
                         preview._contract_digest(self.native_owner))
        self.native_owner.limits[2]._fromto[:] = 7.
        self.assertEqual(preview._contract_digest(self.sim),
                         preview._contract_digest(self.native_owner))
        self.native_owner.limits[2].minimum_distance_from_collisions += .001
        self.assertNotEqual(preview._contract_digest(self.sim),
                            preview._contract_digest(self.native_owner))

    def test_startup_contract_detects_changed_caps_and_profile(self):
        from dataclasses import replace
        original = preview._contract_digest(self.sim)
        self.sim.caps[0] += .01
        self.assertNotEqual(preview._contract_digest(self.sim), original)
        self.sim.caps[0] -= .01
        self.sim.profile = replace(self.sim.profile, position_tracking_rate_s=9.)
        self.assertNotEqual(preview._contract_digest(self.sim), original)

    def test_cached_snapshot_remains_small_and_unknown_native_is_rejected(self):
        payload, _ = encode(self.sim)
        self.assertLess(len(payload), 40000)
        with self.assertRaises(ValueError):
            preview._SnapshotWriter(io.BytesIO(), {}).dump(self.sim.model)

    def test_model_signature_detects_changed_joint_contract(self):
        original = preview._model_digest(self.sim.model)
        joint = int(np.flatnonzero(self.sim.model.jnt_limited)[0])
        self.sim.model.jnt_range[joint,0] += .001
        self.assertNotEqual(preview._model_digest(self.sim.model), original)

    def test_invalid_snapshot_cannot_be_presented_as_a_goal(self):
        payload,q=encode(self.sim)
        for value in (np.full_like(q,np.nan),q[:14]):
            r=preview._rollout(payload,value,self.goals(),0,'test',0.,1)
            self.assertFalse(r['valid'])
        q[self.sim.qids[0]]=self.sim.ranges[0,1]+.01
        r=preview._rollout(payload,q,self.goals(),0,'test',0.,1)
        self.assertFalse(r['valid'])

    def test_measured_body_snapshot_and_omni_frame_survive_private_copy(self):
        fixture=json.loads((ROOT/'backend/tests/fixtures/g1_measured_start_20261007.json').read_text(encoding='utf-8-sig'))
        initialize_inactive_model(self.sim, np.array(fixture['q_rad']))
        self.sim.set_base_yaw(.4)
        goals={s:self.sim.config.get_transform_frame_to_world(s+'_wrist_yaw_link','body') for s in ('left','right')}
        r=self.roll(goals)
        self.assertTrue(r['valid'])
        for side in goals:
            np.testing.assert_allclose(self.sim.base_rotation@r['poses'][side][0],
                                       goals[side].translation(),atol=2e-4,rtol=0)

    def test_identical_input_repeats_identical_goal_prediction(self):
        a=self.roll();b=self.roll()
        for side in ('left','right'):
            np.testing.assert_array_equal(a['poses'][side][0],b['poses'][side][0])

    def test_pending_result_never_blocks_and_no_work_queue_accumulates(self):
        obj=manager();obj.pending=Future()
        obj.pending.result=Mock(side_effect=AssertionError('must not wait'))
        self.assertFalse(obj.feedback(obj.context,10.,np.eye(3))['valid'])
        self.assertFalse(obj.request(self.sim,self.goals(),10.,1))
        obj.pending.result.assert_not_called();obj.executor.submit.assert_not_called()

    def test_period_and_ready_worker_are_required_to_submit(self):
        obj=manager();obj.tokens={id(v):k for k,v in preview._snapshot_objects(self.sim).items()}
        obj.next_submit=11.
        self.assertFalse(obj.request(self.sim,self.goals(),10.,1))
        obj.next_submit=0.;obj.worker_ready=False
        self.assertFalse(obj.request(self.sim,self.goals(),10.,1))
        obj.executor.submit.assert_not_called()

    def test_display_refresh_uses_control_cadence_without_backlog(self):
        self.assertAlmostEqual(preview.UPDATE_PERIOD_S, 1. / 60.)
        obj=manager();obj.tokens={id(v):k for k,v in preview._snapshot_objects(self.sim).items()}
        future=Future();obj.executor.submit.return_value=future
        self.assertTrue(obj.request(self.sim,self.goals(),10.,1))
        self.assertAlmostEqual(obj.next_submit,10.+1./60.)
        # Even after its deadline, an unfinished job cannot queue more work.
        self.assertFalse(obj.request(self.sim,self.goals(),10.2,2))
        obj.executor.submit.assert_called_once()
        obj.pending=None
        self.assertFalse(obj.request(self.sim,self.goals(),10.001,3))
        self.assertTrue(obj.request(self.sim,self.goals(),10.+1./60.,4))

    def test_stale_and_reversed_clock_predictions_are_hidden(self):
        obj=manager();obj.result=result()
        self.assertTrue(obj.feedback(obj.context,10.05,np.eye(3))['valid'])
        self.assertTrue(obj.feedback(obj.context,10.199,np.eye(3))['valid'])
        self.assertFalse(obj.feedback(obj.context,10.201,np.eye(3))['valid'])
        self.assertFalse(obj.feedback(obj.context,9.9,np.eye(3))['valid'])

    def test_session_revision_and_inactive_transitions_discard_old_results(self):
        for changed in (None,('other','session',1),('backend','session',2)):
            obj=manager();obj.pending=Future();obj.pending.set_result(result())
            self.assertFalse(obj.feedback(changed,10.01,np.eye(3))['valid'])
            self.assertIsNone(obj.result)

    def test_worker_failure_disables_only_display(self):
        obj=manager();obj.pending=Future();obj.pending.set_exception(RuntimeError('test failure'))
        before=self.sim.config.q.copy()
        self.assertFalse(obj.feedback(obj.context,10.01,np.eye(3))['valid'])
        self.assertIsNotNone(obj.error)
        self.assertFalse(obj.request(self.sim,self.goals(),10.02,2))
        np.testing.assert_array_equal(before,self.sim.config.q)

    def test_malformed_worker_outputs_disable_only_display_before_serialization(self):
        for key, value in (('poses', {}), ('sequence', -1),
                           ('iterations', 65), ('compute_ms', float('nan'))):
            with self.subTest(key=key):
                obj=manager();obj.result=result();obj.result[key]=value
                before=encode(self.sim)[0]
                self.assertFalse(obj.feedback(obj.context,10.01,np.eye(3))['valid'])
                self.assertIsNotNone(obj.error)
                self.assertEqual(before,encode(self.sim)[0])
        for position, rotation in ((np.full(3,np.nan),np.eye(3)),
                                   (np.zeros(3),np.zeros((3,3)))):
            obj=manager();obj.result=result()
            obj.result['poses']['left']=(position,rotation)
            self.assertFalse(obj.feedback(obj.context,10.01,np.eye(3))['valid'])
            self.assertIsNotNone(obj.error)

    def test_repeated_transmission_does_not_renew_preview_source_age(self):
        obj=manager();obj.result=result()
        first=obj.feedback(obj.context,10.04,np.eye(3))
        repeated=obj.feedback(obj.context,10.12,np.eye(3))
        self.assertGreater(repeated['age_s'],first['age_s'])
        self.assertFalse(obj.feedback(obj.context,10.201,np.eye(3))['valid'])

    def test_actual_spawn_keeps_parent_command_and_cpu_settings_unchanged(self):
        import ctypes
        import os
        def cpu_settings():
            if os.name != 'nt': return None
            from ctypes import wintypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetCurrentProcess.restype=wintypes.HANDLE
            kernel.GetPriorityClass.argtypes=(wintypes.HANDLE,)
            kernel.GetPriorityClass.restype=wintypes.DWORD
            kernel.GetProcessAffinityMask.argtypes=(wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t))
            allowed=ctypes.c_size_t();system=ctypes.c_size_t()
            self.assertTrue(kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(),
                ctypes.byref(allowed),ctypes.byref(system)))
            return allowed.value,kernel.GetPriorityClass(kernel.GetCurrentProcess())
        before=encode(self.sim)[0]
        parent_cpu=cpu_settings()
        service=preview.BimanualGoalPreview(self.sim)
        try:
            until=time.perf_counter()+20.
            while not service.worker_ready and not service.error and time.perf_counter()<until:
                service.feedback('spawn-test',time.perf_counter(),self.sim.base_rotation)
                time.sleep(.005)
            self.assertTrue(service.worker_ready,service.error)
            self.assertTrue(service.request(self.sim,self.goals(),time.perf_counter(),1))
            frame=None
            while service.pending is not None and time.perf_counter()<until:
                frame=service.feedback('spawn-test',time.perf_counter(),self.sim.base_rotation)
                time.sleep(.002)
            self.assertIsNone(service.error)
            self.assertIsNone(service.pending)
            self.assertIsNotNone(service.result)
            self.assertTrue(service.result['valid'])
            self.assertEqual(before,encode(self.sim)[0])
            self.assertEqual(parent_cpu,cpu_settings())
        finally:
            service.close()

    def test_common_yaw_maps_preview_into_current_display_frame(self):
        obj=manager();obj.result=result()
        rotation=mink.SO3.exp(np.array([0.,0.,.7])).as_matrix()
        output=obj.feedback(obj.context,10.01,rotation)
        for side in ('left','right'):
            np.testing.assert_allclose(output[side+'_world_m'], BASIS.T@rotation@result()['poses'][side][0],atol=1e-12)
        self.assertLess(len(json.dumps(output)),2048)

    def test_child_math_environment_is_restored_even_on_failure(self):
        import os
        before = {name: os.environ.get(name) for name in
                  ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}
        with self.assertRaises(RuntimeError):
            with preview._child_math_environment():
                self.assertTrue(all(os.environ[name] == '1' for name in before))
                raise RuntimeError('spawn failure')
        self.assertEqual(before, {name: os.environ.get(name) for name in before})

    def test_closed_preview_cannot_show_or_submit_a_result(self):
        obj=manager();obj.result=result();obj.close()
        self.assertFalse(obj.feedback(obj.context,10.01,np.eye(3))['valid'])
        self.assertFalse(obj.request(self.sim,self.goals(),10.01,1))
        obj.executor.shutdown.assert_called_once_with(wait=True,cancel_futures=True)

    def test_held_out_of_range_goal_settles_and_retracts_without_hiding_limits(self):
        for phase, distance, ticks in (('near', .08, 500),
                                      ('far', .70, 900),
                                      ('retract', .06, 650)):
            goals = self.goals(distance)
            samples = []
            for tick in range(ticks):
                self.assertTrue(self.sim.step(goals))
                q = self.sim.config.q[self.sim.qids]
                self.assertTrue(np.all(q >= self.sim.ranges[:, 0] - 1e-9))
                self.assertTrue(np.all(q <= self.sim.ranges[:, 1] + 1e-9))
                if tick % 25 == 0 or tick == ticks - 1:
                    prediction = self.roll(goals)
                    self.assertTrue(prediction['valid'])
                    self.assertGreaterEqual(self.sim.clearance(self.sim.config.q), self.sim.clearance_m)
                    samples.append(np.stack([prediction['poses'][side][0]
                                             for side in ('left', 'right')]))
            values = np.stack(samples)
            target = np.stack([goals[side].translation() for side in ('left', 'right')])
            error = np.linalg.norm(values[-1] - target, axis=1)
            if phase == 'far':
                self.assertTrue(np.all(error > .2), 'Unreachable request must not be shown as achieved')
                self.assertLess(float(np.max(np.linalg.norm(np.ptp(values[-6:], axis=0), axis=1))), .002)
            else:
                self.assertLess(float(np.max(error)), .002)

    def test_live_display_uses_command_snapshot_without_independent_prediction(self):
        text=(ROOT/'MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py').read_text(encoding='utf-8-sig')
        main=text.split('def main():',1)[1]
        self.assertLess(main.index('feedback = cycle.feedback()'), main.index('observation.publish('))
        self.assertLess(main.index('observation.publish('), main.index('sock.sendto('))
        self.assertNotIn('BimanualGoalPreview', main)
        self.assertNotIn('goal_preview.request(', main)
        self.assertNotIn('g1_bimanual_geometric_goal', main)
        self.assertIn("result['command_target'] = command_target", text)
        cs=(ROOT/'Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs').read_text(encoding='utf-8-sig')
        self.assertIn('G1GoalPreviewState.Position(commandTarget, left)',cs)
        self.assertIn('HasFreshCommandTarget',cs)
        branch=cs.split('public bool TryGetIkTarget(',1)[1].split('public bool TryGetRightIkRotation(',1)[0]
        self.assertNotIn('leftWorldTarget',branch)
        self.assertNotIn('goalMarkerInterpolation',cs)
        self.assertNotIn('checkedWorldTargetValid',cs)
        self.assertNotIn('rightCheckedWorldTarget',cs)


if __name__=='__main__':
    unittest.main()
