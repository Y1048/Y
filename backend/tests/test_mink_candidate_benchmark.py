"""Removing diagnostic work must not remove accepted-path safety checks."""

import sys
import multiprocessing as mp
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from benchmark_mink_candidate import (
    BoundedClearance, CachedClearance, CachedCollisionLimit, SummarizeTiming, BuildCandidate, comparison,
)
from benchmark_mink_rendered_replay import WaitForRelease, GetNextRelease, GetRunStatus
from offline_render_worker import LatestStateSlot


class BenchmarkTests(unittest.TestCase):
    def test_status_does_not_hide_stale_display_behind_fast_control(self):
        run = {"trajectory_parity": True, "render_check": {"nonblank_and_changing": True},
               "late_frames": [], "render_worker": {"timings": {"source_age_finish_ms": {"deadline_misses": 1}}}}
        self.assertEqual(GetRunStatus([run]), "DISPLAY_AGE_MISSES")
        run["late_frames"] = [0]
        self.assertEqual(GetRunStatus([run]), "DEADLINE_MISSES")
        run["trajectory_parity"] = False
        self.assertEqual(GetRunStatus([run]), "PARITY_OR_RENDER_FAILURE")
        self.assertEqual(GetRunStatus([]), "PARITY_OR_RENDER_FAILURE")

    def test_latest_slot_is_bounded_and_returns_only_latest_coherent_state(self):
        slot = LatestStateSlot(mp.get_context("spawn"), 2)
        self.assertIsNone(slot.ReadAfter(0))
        for sequence in range(1, 1001):
            self.assertTrue(slot.Publish(sequence, float(sequence), [sequence, -sequence], [1, 2, 3], [4, 5, 6]))
        state = slot.ReadAfter(0)
        np.testing.assert_array_equal(state, [1000, 1000, 1000, -1000, 1, 2, 3, 4, 5, 6])
        state[:] = 0
        self.assertEqual(slot.ReadAfter(0)[0], 1000)
        self.assertIsNone(slot.ReadAfter(1000))
        self.assertEqual(len(slot.values), 10)
        self.assertFalse(slot.Publish(999, 1., [0, 0], [0, 0, 0], [0, 0, 0]))

    def test_latest_slot_lock_contention_never_blocks_producer(self):
        slot = LatestStateSlot(mp.get_context("spawn"), 1)
        slot.lock.acquire()
        try:
            self.assertFalse(slot.Publish(1, 0., [0], [0, 0, 0], [0, 0, 0]))
            self.assertIsNone(slot.ReadAfter(0))
        finally:
            slot.lock.release()
        self.assertTrue(slot.Publish(2, 0., [1], [0, 0, 0], [0, 0, 0]))
        self.assertEqual(slot.ReadAfter(0)[0], 2)

    def test_latest_slot_invalid_payload_does_not_replace_state(self):
        slot = LatestStateSlot(mp.get_context("spawn"), 1)
        slot.Publish(1, 1., [1], [0, 0, 0], [0, 0, 0])
        for sequence, timestamp, q, goal, preview in (
            (0, 1., [0], [0, 0, 0], [0, 0, 0]),
            (1.5, 1., [0], [0, 0, 0], [0, 0, 0]),
            (2, np.nan, [0], [0, 0, 0], [0, 0, 0]),
            (2, 1., [np.nan], [0, 0, 0], [0, 0, 0]),
            (2, 1., [0], [0, 0], [0, 0, 0, 0]),
        ):
            with self.assertRaises(ValueError):
                slot.Publish(sequence, timestamp, q, goal, preview)
            self.assertEqual(slot.ReadAfter(0)[0], 1)

    def test_pacing_sleeps_only_for_positive_remaining_time(self):
        sleeps = []
        times = iter([0., .004, .0101])
        WaitForRelease(.01, clock=lambda: next(times), sleeper=sleeps.append)
        self.assertEqual(sleeps, [.005, .005])
        WaitForRelease(.01, clock=lambda: .02, sleeper=sleeps.append)
        self.assertEqual(len(sleeps), 2)

    def test_pacing_does_not_compress_interval_after_late_start(self):
        dt = 1 / 60
        start = 10.2
        self.assertEqual(GetNextRelease(start, dt), start + dt)
        for invalid in (0, -1, np.nan, np.inf):
            with self.assertRaises(ValueError):
                GetNextRelease(start, invalid)

    def BuildConstraintFixture(self):
        probe = comparison.probe
        model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        q = probe.base._initial_configuration(model)
        planner = BuildCandidate(model, q, False, constraint_cache=True)
        planner.configuration.update(q)
        limit = next(item for item in planner.limits if isinstance(item, CachedCollisionLimit))
        return planner, limit

    def test_constraint_cache_copies_and_invalidates_exact_inputs(self):
        planner, limit = self.BuildConstraintFixture()
        config = planner.configuration
        result = comparison.probe.mink.limits.Constraint(G=np.ones((1, planner.model.nv)), h=np.array([np.inf]))
        with patch.object(comparison.ResolvedCollisionLimit, "compute_qp_inequalities", return_value=result) as query:
            first = limit.compute_qp_inequalities(config, .01)
            first.G[:] = 2
            second = limit.compute_qp_inequalities(config, .01)
            np.testing.assert_array_equal(second.G, 1.)
            second.G[:] = 3
            np.testing.assert_array_equal(limit.compute_qp_inequalities(config, .01).G, 1.)
            self.assertEqual(query.call_count, 1)
            q = config.q
            q[planner.qpos_ids[0]] += 1e-14
            config.update(q)
            limit.compute_qp_inequalities(config, .01)
            limit.compute_qp_inequalities(config, .02)
            for name in ("gain", "minimum_distance_from_collisions", "collision_detection_distance", "bound_relaxation"):
                setattr(limit, name, getattr(limit, name) + .001)
                limit.compute_qp_inequalities(config, .02)
            limit.recover_reserve = not limit.recover_reserve
            limit.compute_qp_inequalities(config, .02)
            self.assertEqual(query.call_count, 8)

    def test_constraint_cache_invalid_result_exception_and_timestep(self):
        planner, limit = self.BuildConstraintFixture()
        config = planner.configuration
        constraint = comparison.probe.mink.limits.Constraint
        valid = constraint(G=np.ones((1, planner.model.nv)), h=np.array([1.]))
        results = [valid, RuntimeError("failed"), constraint(G=valid.G, h=np.array([np.nan])),
                   constraint(G=valid.G, h=np.array([-np.inf])), valid]
        with patch.object(comparison.ResolvedCollisionLimit, "compute_qp_inequalities", side_effect=results):
            limit.compute_qp_inequalities(config, .01)
            with self.assertRaises(RuntimeError):
                limit.compute_qp_inequalities(config, .02)
            self.assertIsNone(limit.cache_key)
            limit.compute_qp_inequalities(config, .01)
            self.assertIsNone(limit.cache_key)
            limit.compute_qp_inequalities(config, .01)
            self.assertIsNone(limit.cache_key)
            limit.compute_qp_inequalities(config, .01)
            self.assertIsNotNone(limit.cache_key)
        for dt in (0, -1, np.nan, np.inf):
            with self.assertRaises(ValueError):
                limit.compute_qp_inequalities(config, dt)
            self.assertIsNone(limit.cache_key)

    def test_constraint_cache_mocap_and_configuration_identity(self):
        planner, limit = self.BuildConstraintFixture()
        data = SimpleNamespace(mocap_pos=np.zeros((1, 3)), mocap_quat=np.array([[1., 0, 0, 0]]))
        config = SimpleNamespace(model=planner.model, q=planner.configuration.q, data=data)
        result = comparison.probe.mink.limits.Constraint(G=np.ones((1, planner.model.nv)), h=np.array([1.]))
        with patch.object(comparison.ResolvedCollisionLimit, "compute_qp_inequalities", return_value=result) as query:
            limit.compute_qp_inequalities(config, .01)
            limit.compute_qp_inequalities(config, .01)
            data.mocap_pos[0, 0] = .01
            limit.compute_qp_inequalities(config, .01)
            data.mocap_quat[0, 0] = .99
            limit.compute_qp_inequalities(config, .01)
            config = SimpleNamespace(model=planner.model, q=config.q.copy(), data=data)
            limit.compute_qp_inequalities(config, .01)
            self.assertEqual(query.call_count, 4)

    def test_constraint_cache_matches_uncached_g1_matrices(self):
        planner, limit = self.BuildConstraintFixture()
        model = planner.model
        rng = np.random.default_rng(843)
        active = 0
        for _ in range(32):
            q = planner.configuration.q
            q[planner.qpos_ids] = rng.uniform(model.jnt_range[planner.joint_ids, 0], model.jnt_range[planner.joint_ids, 1])
            planner.configuration.update(q)
            expected = comparison.ResolvedCollisionLimit.compute_qp_inequalities(limit, planner.configuration, .01)
            for _ in range(2):
                actual = limit.compute_qp_inequalities(planner.configuration, .01)
                np.testing.assert_array_equal(actual.G, expected.G)
                np.testing.assert_array_equal(actual.h, expected.h)
            active += np.count_nonzero(np.isfinite(expected.h))
        self.assertEqual(limit.hits, 32)
        self.assertEqual(limit.misses, 32)
        self.assertGreater(active, 0)

    def test_broadphase_preserves_contact_boundary_and_unbounded_pairs(self):
        mj = comparison.probe.mujoco
        model = mj.MjModel.from_xml_string('''<mujoco><worldbody>
          <geom type="sphere" size="0.1"/><body><freejoint/>
          <geom type="sphere" size="0.1"/></body>
          <geom type="plane" size="1 1 .1" pos="0 0 -1"/>
        </worldbody></mujoco>''')
        pairs = [(0, 1), (0, 2), (1, 2)]
        # Resolve types because compiled geom ordering is not XML ordering.
        plane = int(np.flatnonzero(model.geom_type == mj.mjtGeom.mjGEOM_PLANE)[0])
        spheres = np.flatnonzero(model.geom_type == mj.mjtGeom.mjGEOM_SPHERE).tolist()
        pairs = [tuple(spheres), (spheres[0], plane), (spheres[1], plane)]
        planner = SimpleNamespace(model=model, validation_data=mj.MjData(model), geom_pairs=pairs)
        query = BoundedClearance(planner)
        for offset in (.15, .2, .399999999, .4, .4000000001, .40000001, 1.):
            q = model.qpos0.copy()
            q[0] = offset
            actual = query(q)
            expected = comparison.probe.base._nearest_pair_distance(model, query.data, pairs)
            self.assertEqual(actual, float("inf") if expected is None else expected[0])
        self.assertFalse(query.bounded[1:].any())
        self.assertGreater(query.skipped_pairs, 0)
        # Unknown or invalid radii must fail back to narrow phase.
        model.geom_rbound[spheres[0]] = 0
        self.assertFalse(BoundedClearance(planner).bounded.any())

    def test_broadphase_matches_all_pairs_on_seeded_g1_poses(self):
        probe = comparison.probe
        model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        initial = probe.base._initial_configuration(model)
        planner = BuildCandidate(model, initial, False)
        query = BoundedClearance(planner)
        joints = [probe.base._joint_id(model, name) for name in probe.base.g1.G1_29_JOINTS]
        addresses = model.jnt_qposadr[joints]
        rng = np.random.default_rng(731)
        collisions = 0
        for _ in range(64):
            q = initial.copy()
            q[addresses] = rng.uniform(model.jnt_range[joints, 0], model.jnt_range[joints, 1])
            expected = planner.GetClearance(q)
            actual = query(q)
            self.assertEqual(actual, expected)
            collisions += actual < 0
        self.assertGreater(collisions, 0)
        self.assertGreater(query.skipped_pairs, query.pair_queries)

    def test_cache_is_exact_and_does_not_alias_input(self):
        calls = []
        cache = CachedClearance(lambda q: calls.append(q.copy()) or .03)
        q = np.zeros(2)
        self.assertEqual(cache(q), .03)
        self.assertEqual(cache(q.copy()), .03)
        q[0] = 1e-14
        cache(q)
        self.assertEqual(len(calls), 2)
        self.assertEqual(cache.hits, 1)

    def test_cache_invalidates_on_exception_and_nan(self):
        calls = iter((.03, RuntimeError("query"), np.nan, .04))
        def Query(q):
            value = next(calls)
            if isinstance(value, Exception):
                raise value
            return value
        cache = CachedClearance(Query)
        cache(np.zeros(2))
        with self.assertRaises(RuntimeError):
            cache(np.ones(2))
        self.assertIsNone(cache.q)
        self.assertTrue(np.isnan(cache(np.zeros(2))))
        self.assertIsNone(cache.q)
        self.assertEqual(cache(np.zeros(2)), .04)

    def test_timing_counts_deadline_misses_not_just_average(self):
        result = SummarizeTiming([1., 2., 17.], 1000 / 60)
        self.assertEqual(result["deadline_misses"], 1)
        for values, budget in (([], 10), ([np.nan], 10), ([-1], 10), ([1], 0)):
            with self.assertRaises(ValueError):
                SummarizeTiming(values, budget)

    def test_fast_path_matches_diagnostic_accepted_states(self):
        probe = comparison.probe
        model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        probe.base._apply_operational_joint_limits(model)
        initial = probe.base._initial_configuration(model)
        ids = [int(model.jnt_qposadr[probe.base._joint_id(model, n)]) for n in probe.base.g1.RIGHT_ARM_JOINTS]
        initial[ids] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
        goal_q = initial.copy()
        goal_q[ids[3]] += .1
        config = probe.mink.Configuration(model)
        config.update(goal_q)
        goal = config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        traces = []
        for diagnostic in (True, False):
            planner = BuildCandidate(model, initial, not diagnostic)
            q = initial.copy()
            samples = []
            for _ in range(8):
                q, result = comparison.EvaluateLookahead(planner, q, goal, consistent_position=True,
                    center_redundancy=True, limit_margin_rad=np.deg2rad(18), diagnostic_geometry=diagnostic)
                samples.append((q.copy(), result["lookahead_target_qpos"], result["lookahead_steps"]))
            traces.append(samples)
        for normal, fast in zip(*traces):
            np.testing.assert_allclose(normal[0], fast[0], atol=1e-10)
            np.testing.assert_allclose(normal[1], fast[1], atol=1e-10)
            self.assertEqual(normal[2], fast[2])

    def test_merit_rejection_skips_only_unusable_candidate_geometry(self):
        probe = comparison.probe
        model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
        q = probe.base._initial_configuration(model)
        planner = comparison.BuildPlanner(model, q)
        planner.configuration.update(q)
        goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        velocity = np.zeros(model.nv)
        velocity[planner.right_dofs[0]] = .01
        with patch.object(planner, "CheckConfiguration", return_value=True) as check, patch.object(
            planner, "GetMerit", return_value=1.
        ), patch.object(probe.mink, "solve_ik", return_value=velocity):
            actual, result = comparison.EvaluateStep(planner, q, goal, diagnostic_geometry=False)
            np.testing.assert_array_equal(actual, q)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(result["status"], "no_accepted_step")
        with patch.object(planner, "CheckConfiguration", side_effect=[True, False, False, False, False, False, False]) as check, patch.object(
            planner, "GetMerit", side_effect=[1., 0., 0., 0., 0., 0., 0.]
        ), patch.object(probe.mink, "solve_ik", return_value=velocity):
            actual, result = comparison.EvaluateStep(planner, q, goal, diagnostic_geometry=False)
            np.testing.assert_array_equal(actual, q)
            self.assertEqual(check.call_count, 7)
            self.assertNotEqual(result["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
