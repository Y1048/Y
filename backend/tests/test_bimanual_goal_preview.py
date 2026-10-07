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
                source_time=stamp, sequence=5, accepted_steps=3,
                braking_steps=0, status='checked_goal_prefix', compute_ms=2.,
                poses={s: (np.array([.3, .2 if s == 'left' else -.2, .8]),
                           np.eye(3)) for s in ('left', 'right')})


class GoalPreviewTests(unittest.TestCase):
    def setUp(self):
        self.sim = BimanualSimulation()
        # Unit tests use private native buffers without changing process priority.
        self.native_owner = BimanualSimulation()
        preview._WORKER_NATIVE = preview._snapshot_objects(self.native_owner)

    def goals(self, offset=.08):
        return {s: mink.SE3.from_rotation_and_translation(
                    p.rotation(), p.translation() + np.array([offset, 0., .02]))
                for s, p in self.sim.home_targets.items()}

    def roll(self, goals=None):
        payload, q = encode(self.sim)
        return preview._rollout(payload, q, self.goals() if goals is None else goals,
                                0, ('test', 1), 10., 1)

    def test_same_three_checked_steps_and_live_state_is_unchanged(self):
        goals = self.goals()
        self.sim.step(goals)
        before, q = encode(self.sim)
        native = {name: (data.qpos.copy(), data.xpos.copy())
                  for name, data in preview._native_objects(self.sim).items()
                  if name != 'model'}
        digest = preview._model_digest(self.sim.model)
        expected = copy.deepcopy(self.sim, {id(self.sim.model): self.sim.model})
        for _ in range(3): self.assertTrue(expected.step(goals))
        actual = self.roll(goals)
        self.assertTrue(actual['valid'])
        self.assertEqual(actual['accepted_steps'], 3)
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

    def test_checked_braking_does_not_truncate_a_safe_horizon(self):
        self.sim.step(self.goals())
        with patch('g1_bimanual_sim.qpsolvers.solve_problem', return_value=None):
            prediction = self.roll()
        self.assertTrue(prediction['valid'])
        self.assertEqual(prediction['accepted_steps'],3)
        self.assertEqual(prediction['braking_steps'],3)
        self.assertEqual(prediction['status'],'checked_braking_prefix')

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
                           ('accepted_steps', 2), ('compute_ms', float('nan'))):
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

    def test_live_publication_precedes_optional_prediction_and_ui_has_no_stop_fallback(self):
        text=(ROOT/'MuJoCo_G1_Controller/scripts/g1_bimanual_unity_sim.py').read_text(encoding='utf-8-sig')
        main=text.split('def main():',1)[1]
        self.assertLess(main.index('observation.publish('),main.index("feedback['goal_preview']"))
        self.assertLess(main.index('sock.sendto('),main.index('goal_preview.request('))
        self.assertNotIn('goal_preview',text.split('class UnityCycle:',1)[1].split('def main():',1)[0])
        cs=(ROOT/'Unity_G1_VR/Assets/G1Teleop/G1BimanualSimulationSender.cs').read_text(encoding='utf-8-sig')
        self.assertIn('G1GoalPreviewState.Position(goalPreview, left)',cs)
        self.assertNotIn('checkedWorldTargetValid',cs)
        self.assertNotIn('rightCheckedWorldTarget',cs)


if __name__=='__main__':
    unittest.main()
