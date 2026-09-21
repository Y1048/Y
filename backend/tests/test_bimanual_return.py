"""Staged-return parity and output-continuity gates; simulation-only evidence."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
sys.path.insert(0, str(ROOT/'backend/tests'))
from g1_bimanual_limits import JOINT_VELOCITY_LIMITS_RAD_S, JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation, base, mink
from g1_bimanual_return import BimanualReturnMotion, RuckigJointMotionLimiter
from g1_mink_return_cycle import SAFE_RIGHT_ARM_RAD


def assert_output(sim, before, previous_velocity):
    velocity = (sim.config.q[sim.qids]-before[sim.qids])/sim.dt
    np.testing.assert_allclose(velocity, sim.velocity[sim.dofs], atol=1e-10, rtol=0)
    acceleration = np.max(np.abs(velocity-previous_velocity))/sim.dt
    assert acceleration <= JOINT_ACCELERATION_LIMIT_RAD_S2+1e-5, acceleration
    assert np.all(np.abs(velocity) <= sim.caps+1e-6)
    assert np.all(sim.config.q[sim.qids] >= sim.ranges[:, 0]-1e-8)
    assert np.all(sim.config.q[sim.qids] <= sim.ranges[:, 1]+1e-8)
    frozen = np.ones(sim.model.nq, dtype=bool)
    frozen[sim.qids] = False
    np.testing.assert_array_equal(sim.config.q[frozen], sim.home[frozen])
    clearance = sim.clearance(sim.config.q)
    assert clearance >= sim.clearance_m, clearance
    return velocity, float(acceleration), clearance


def recorded_return(entry):
    sim = BimanualSimulation()
    q = sim.home.copy()
    q[sim.qids] = entry['start_q']
    sim.config.update(q)
    sim.velocity[sim.dofs] = entry['initial_velocity']
    sim.acceleration[sim.dofs] = entry['initial_acceleration']
    next_velocity = np.sign(sim.velocity)*np.maximum(0., np.abs(sim.velocity)-JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt)
    sim.brake_plan, reason = sim.checked_stop_plan(next_velocity)
    assert sim.brake_plan is not None, reason
    stages, poses = [], {}
    previous_stage = 'inactive'
    max_acceleration = maximum_speed = 0.
    minimum = .2
    for tick in range(1800):
        before, velocity = sim.config.q.copy(), sim.velocity[sim.dofs].copy()
        assert sim.step(returning=True), sim.reason
        velocity, acceleration, clearance = assert_output(sim, before, velocity)
        maximum_speed = max(maximum_speed, float(np.max(np.abs(velocity))))
        max_acceleration = max(max_acceleration, acceleration)
        minimum = min(minimum, clearance)
        if previous_stage != sim.return_motion.stage:
            stages.append([tick+1, sim.return_motion.stage])
            poses[sim.return_motion.stage] = sim.config.q[sim.qids].tolist()
            previous_stage = sim.return_motion.stage
        if sim.state == 'ready':
            break
    assert sim.state == 'ready', sim.reason
    assert not np.any(sim.velocity)
    np.testing.assert_allclose(poses['home'], sim.return_motion.waypoint, atol=1e-6, rtol=0)
    np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-6, rtol=0)
    result = dict(reason=entry['reason'],ticks=tick+1,simulation_s=(tick+1)*sim.dt,
        old_simulation_s=entry['ticks']*sim.dt,old_observed_wall_s=entry['wall_s'],
        stages=stages,minimum_clearance_mm=minimum*1000,
        peak_speed_deg_s=float(np.rad2deg(maximum_speed)),
        max_output_acceleration_deg_s2=float(np.rad2deg(max_acceleration)),
        replans=sim.return_motion.replans)
    print('STAGED_RETURN', json.dumps(result), flush=True)
    return sim, result


class StagedReturnTests(unittest.TestCase):
    def test_recovery_waits_for_checked_stationary_acceleration_before_replan(self):
        sim = BimanualSimulation()
        motion = sim.return_motion
        sim.velocity[sim.motion['right'].dofs[4]] = .01
        sim.brake_plan = [(sim.config.q.copy(), np.zeros(sim.model.nv))]*2
        motion.recovering = True
        motion.rejected_reason = 'return_joint_range'
        before = sim.config.q.copy()
        self.assertTrue(motion._stop())
        self.assertTrue(motion.recovering)
        self.assertGreater(np.max(np.abs(sim.acceleration)), 0.)
        self.assertTrue(motion._stop())
        self.assertFalse(motion.recovering)
        np.testing.assert_array_equal(sim.acceleration, np.zeros(sim.model.nv))
        np.testing.assert_array_equal(sim.config.q, before)

    def test_profile_and_waypoint_match_original_right_arm(self):
        sim = BimanualSimulation()
        policy = sim.return_motion
        np.testing.assert_array_equal(policy.waypoint[7:], SAFE_RIGHT_ARM_RAD)
        np.testing.assert_allclose(np.rad2deg(policy.waypoint[:7]), [10,35,0,70,0,0,0])
        np.testing.assert_allclose(policy.jerk_limits, base.RIGHT_ARM_MAX_JERK_RAD_S3)
        np.testing.assert_allclose(policy.acceleration_limits, JOINT_ACCELERATION_LIMIT_RAD_S2)
        np.testing.assert_allclose(sim.caps, np.asarray(JOINT_VELOCITY_LIMITS_RAD_S))
        self.assertEqual(policy.settle_s, .5)
        self.assertEqual(policy.policy, 'bimanual_staged_return_v2')
        self.assertEqual(policy.near_hands_threshold_m, .012)
        self.assertEqual(len(sim.dofs), 14)
        self.assertEqual(sim.clearance_m, .005)

    def test_near_hands_return_stops_separates_and_finishes(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_near_hands_20260918.json').read_text())
        self.assertTrue(fixture['simulation_only'])
        self.assertEqual(fixture['source_sequence'], 697)
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = fixture['q14']
        sim.config.update(q)
        sim.velocity[:] = 0.
        sim.velocity[sim.dofs] = fixture['velocity14']
        sim.acceleration[:] = 0.
        sim.acceleration[sim.dofs] = fixture['acceleration14']
        sim.brake_plan = []
        for item in fixture['brake_plan']:
            candidate = sim.home.copy()
            candidate[sim.qids] = item['q14']
            velocity = np.zeros(sim.model.nv)
            velocity[sim.dofs] = item['velocity14']
            sim.brake_plan.append((candidate, velocity))
        start_clearance = sim.clearance(sim.config.q)
        self.assertGreaterEqual(start_clearance, sim.clearance_m)
        self.assertLess(start_clearance, sim.return_motion.near_hands_threshold_m)
        stages = []
        minimum = start_clearance
        max_acceleration = 0.
        for tick in range(900):
            before = sim.config.q.copy()
            previous = sim.velocity[sim.dofs].copy()
            self.assertTrue(sim.step(returning=True), sim.reason)
            _, acceleration, clearance = assert_output(sim, before, previous)
            max_acceleration = max(max_acceleration, acceleration)
            minimum = min(minimum, clearance)
            if not stages or stages[-1] != sim.return_motion.stage:
                stages.append(sim.return_motion.stage)
            if sim.state == 'ready':
                break
        self.assertEqual(sim.state, 'ready')
        self.assertEqual(sim.return_motion.stage, 'complete')
        self.assertEqual(sim.return_motion.policy, 'bimanual_staged_return_v2')
        self.assertTrue(sim.return_motion.near_hands_recovery)
        self.assertAlmostEqual(sim.return_motion.return_start_clearance_m, start_clearance, places=12)
        self.assertLess(sim.return_motion.near_hands_start_clearance_m,
                        sim.return_motion.near_hands_threshold_m)
        self.assertGreater(sim.return_motion.near_hands_start_clearance_m, start_clearance)
        self.assertEqual(sim.return_motion.separation_side, 'left')
        self.assertGreaterEqual(sim.return_motion.separation_probe_clearance_m['left'], sim.clearance_m)
        self.assertEqual(stages, ['near_hands_stop','separate_left','safe_waypoint','home','complete'])
        self.assertGreaterEqual(minimum, sim.clearance_m)
        self.assertLessEqual(max_acceleration, JOINT_ACCELERATION_LIMIT_RAD_S2+1e-5)
        self.assertLess((tick+1)*sim.dt, 10.)
        self.assertEqual(sim.return_motion.replans, 0)
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-6, rtol=0)

    def test_near_hands_mirror_chooses_right_side(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_near_hands_20260918.json').read_text())
        sign = np.array([1.,-1.,-1.,1.,-1.,1.,-1.])
        mirror = lambda values: np.r_[np.asarray(values)[7:]*sign, np.asarray(values)[:7]*sign]
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = mirror(fixture['q14'])
        sim.config.update(q)
        sim.velocity[:] = 0.
        sim.velocity[sim.dofs] = mirror(fixture['velocity14'])
        sim.acceleration[:] = 0.
        sim.acceleration[sim.dofs] = mirror(fixture['acceleration14'])
        sim.brake_plan = []
        for item in fixture['brake_plan']:
            candidate = sim.home.copy()
            candidate[sim.qids] = mirror(item['q14'])
            velocity = np.zeros(sim.model.nv)
            velocity[sim.dofs] = mirror(item['velocity14'])
            sim.brake_plan.append((candidate, velocity))
        minimum = sim.clearance(sim.config.q)
        for tick in range(900):
            before = sim.config.q.copy()
            previous = sim.velocity[sim.dofs].copy()
            self.assertTrue(sim.step(returning=True), sim.reason)
            _, _, clearance = assert_output(sim, before, previous)
            minimum = min(minimum, clearance)
            if sim.state == 'ready':
                break
        self.assertEqual(sim.state, 'ready')
        self.assertEqual(sim.return_motion.separation_side, 'right')
        self.assertGreaterEqual(minimum, sim.clearance_m)
        self.assertLess((tick+1)*sim.dt, 10.)
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-6, rtol=0)

    def _near_hands_fixture_sim(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_near_hands_20260918.json').read_text())
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = fixture['q14']
        sim.config.update(q)
        sim.velocity[:] = 0.
        sim.velocity[sim.dofs] = fixture['velocity14']
        sim.acceleration[:] = 0.
        sim.acceleration[sim.dofs] = fixture['acceleration14']
        sim.brake_plan = []
        for item in fixture['brake_plan']:
            candidate = sim.home.copy()
            candidate[sim.qids] = item['q14']
            velocity = np.zeros(sim.model.nv)
            velocity[sim.dofs] = item['velocity14']
            sim.brake_plan.append((candidate, velocity))
        return sim

    def test_near_hands_checked_sweep_rejection_can_switch_to_opposite_candidate(self):
        sim = self._near_hands_fixture_sim()
        original_checked_stop_plan = sim.checked_stop_plan
        original_probe = sim.return_motion._probe_separation_side
        rejected = []
        minimum = sim.clearance(sim.config.q)

        def probe_with_safe_retry(side):
            if side == 'right' and sim.return_motion.tried_separation_sides == ['left']:
                return sim.clearance_m + .001
            return original_probe(side)

        def reject_first_left_separation(velocity):
            if sim.return_motion.stage == 'separate_left' and not rejected:
                rejected.append('left')
                return None, 'swept_clearance'
            return original_checked_stop_plan(velocity)

        with patch.object(sim.return_motion, '_probe_separation_side',
                          side_effect=probe_with_safe_retry), \
                patch.object(sim, 'checked_stop_plan',
                             side_effect=reject_first_left_separation):
            for _ in range(120):
                before = sim.config.q.copy()
                previous = sim.velocity[sim.dofs].copy()
                applied = sim.step(returning=True)
                _, _, clearance = assert_output(sim, before, previous)
                minimum = min(minimum, clearance)
                self.assertTrue(applied, sim.reason)
                if sim.return_motion.stage == 'separate_right':
                    break

        self.assertEqual(rejected, ['left'])
        self.assertEqual(sim.return_motion.stage, 'separate_right')
        self.assertEqual(sim.return_motion.tried_separation_sides, ['left', 'right'])
        self.assertEqual(sim.return_motion.separation_side, 'right')
        self.assertGreaterEqual(sim.return_motion.separation_probe_clearance_m['right'],
                                sim.clearance_m)
        self.assertGreaterEqual(minimum, sim.clearance_m)

    def test_near_hands_rejected_left_fails_closed_when_right_probe_is_unsafe(self):
        sim = self._near_hands_fixture_sim()
        original_checked_stop_plan = sim.checked_stop_plan
        rejected = []
        minimum = sim.clearance(sim.config.q)

        def reject_first_left_separation(velocity):
            if sim.return_motion.stage == 'separate_left' and not rejected:
                rejected.append('left')
                return None, 'swept_clearance'
            return original_checked_stop_plan(velocity)

        with patch.object(sim, 'checked_stop_plan', side_effect=reject_first_left_separation):
            for _ in range(120):
                before = sim.config.q.copy()
                previous = sim.velocity[sim.dofs].copy()
                applied = sim.step(returning=True)
                _, _, clearance = assert_output(sim, before, previous)
                minimum = min(minimum, clearance)
                if not applied:
                    break

        self.assertFalse(applied)
        self.assertEqual(rejected, ['left'])
        self.assertEqual(sim.return_motion.tried_separation_sides, ['left'])
        self.assertIn('right', sim.return_motion.separation_probe_clearance_m)
        self.assertLess(sim.return_motion.separation_probe_clearance_m['right'],
                        sim.clearance_m)
        self.assertEqual(sim.state, 'blocked')
        self.assertEqual(sim.return_motion.stage, 'fault')
        self.assertEqual(sim.reason, 'return_path_blocked:near_hands_no_separation_route')
        self.assertEqual(np.max(np.abs(sim.velocity)), 0.)
        self.assertGreaterEqual(minimum, sim.clearance_m)

    def test_near_hands_trigger_uses_inter_arm_clearance_only(self):
        q14 = np.array([
            0.37877105997466565, 0.5018709993910249, 1.3869880803444947,
            1.7752305760909797, -1.0995418598260935, -1.5892583669620304,
            0.17414428402689253, -2.2018477350905616, 0.2429193076737186,
            1.371685727018746, 0.5828341110909996, -0.5412371620371859,
            0.970856138973355, 1.2987824485641153,
        ])
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = q14
        sim.config.update(q)
        global_clearance = sim.clearance(sim.config.q)
        inter_arm_clearance = sim.return_motion._inter_arm_clearance(sim.config.q)
        self.assertGreaterEqual(global_clearance, sim.clearance_m)
        self.assertLess(global_clearance, sim.return_motion.near_hands_threshold_m)
        self.assertGreaterEqual(inter_arm_clearance, sim.return_motion.near_hands_threshold_m)

        sim.step(returning=True)
        self.assertFalse(sim.return_motion.near_hands_recovery)
        self.assertAlmostEqual(sim.return_motion.return_start_clearance_m, global_clearance, places=12)
        self.assertAlmostEqual(sim.return_motion.near_hands_start_clearance_m,
                               inter_arm_clearance, places=12)
        self.assertNotEqual(sim.return_motion.stage, 'near_hands_stop')

    def test_actual_return_start_fixtures_visit_waypoint_and_finish(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_starts_20260918.json').read_text())
        for entry in fixture['starts']:
            with self.subTest(reason=entry['reason']):
                sim, result = recorded_return(entry)
                self.assertLess(result['simulation_s'], 7.)
                self.assertLess(result['simulation_s'], result['old_simulation_s'])
                self.assertGreaterEqual(sim.return_motion.settled_ticks*sim.dt, .5)
                self.assertFalse(sim.return_motion.near_hands_recovery)
                self.assertGreaterEqual(sim.return_motion.near_hands_start_clearance_m,
                                        sim.return_motion.near_hands_threshold_m)
                self.assertEqual(result['replans'], 0)

    def test_right_waypoint_trajectory_matches_original_limiter(self):
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.motion['right'].qpos_ids[4]] = .3
        q[sim.motion['left'].qpos_ids[4]] = -.3
        sim.config.update(q)
        single = RuckigJointMotionLimiter(q[sim.qids[7:]], sim.caps[7:],
            np.full(7,JOINT_ACCELERATION_LIMIT_RAD_S2), np.full(7,base.RIGHT_ARM_MAX_JERK_RAD_S3),sim.dt)
        for _ in range(600):
            expected = single.Step(SAFE_RIGHT_ARM_RAD,sim.dt)
            self.assertTrue(sim.step(returning=True),sim.reason)
            np.testing.assert_allclose(sim.config.q[sim.qids[7:]], expected, atol=1e-8, rtol=0)
            if sim.return_motion.stage == 'home':
                break
        self.assertEqual(sim.return_motion.stage,'home')

    def test_right_home_trajectory_matches_original_limiter(self):
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.qids] = sim.return_motion.waypoint
        sim.config.update(q)
        sim._motion_returning = True
        sim.return_motion.stage = 'home'
        single = RuckigJointMotionLimiter(q[sim.qids[7:]],sim.caps[7:],
            np.full(7,JOINT_ACCELERATION_LIMIT_RAD_S2),np.full(7,base.RIGHT_ARM_MAX_JERK_RAD_S3),sim.dt)
        for _ in range(600):
            expected = single.Step(sim.home[sim.qids[7:]],sim.dt)
            self.assertTrue(sim.step(returning=True),sim.reason)
            np.testing.assert_allclose(sim.config.q[sim.qids[7:]],expected,atol=1e-8,rtol=0)
            if sim.state == 'ready':
                break
        self.assertEqual(sim.state,'ready')

    def test_complete_return_does_not_restart_and_reengage_is_possible(self):
        sim = BimanualSimulation()
        for _ in range(600):
            self.assertTrue(sim.step(returning=True))
            if sim.state == 'ready':
                break
        self.assertEqual(sim.state,'ready')
        q = sim.config.q.copy()
        for _ in range(60):
            self.assertTrue(sim.step(returning=True))
            np.testing.assert_array_equal(q,sim.config.q)
            self.assertEqual(sim.state,'ready')
        self.assertTrue(sim.step(sim.home_targets))
        self.assertEqual(sim.state,'tracking')
        self.assertEqual(sim.return_motion.stage,'inactive')

    def test_full_cycle_pinch_return_inactive_rearm_and_reengage(self):
        from g1_bimanual_unity_sim import UnityCycle
        from test_bimanual_unity_sim import packet
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        sequence = 0
        previous_velocity = np.zeros(14)
        stages = []

        def advance(message):
            nonlocal sequence, previous_velocity
            sequence = message['sequence']
            now = sequence * sim.dt
            cycle.receive(message, now)
            before = sim.config.q.copy()
            cycle.tick(now)
            velocity, _, _ = assert_output(sim, before, previous_velocity)
            previous_velocity = velocity

        cycle.receive(packet(0), 0.)
        advance(packet(1, True))
        self.assertEqual(cycle.state, 'tracking')
        for _ in range(35):
            message = packet(sequence + 1, True)
            message['right']['position_m'][2] += .08
            advance(message)
        self.assertGreater(np.max(np.abs(sim.velocity)), .01)

        advance(packet(sequence + 1, True, returning=True))
        self.assertEqual(cycle.state, 'returning')
        for _ in range(600):
            advance(packet(sequence + 1, False, returning=True))
            if not stages or stages[-1] != sim.return_motion.stage:
                stages.append(sim.return_motion.stage)
            if cycle.state == 'ready':
                break
        self.assertEqual(cycle.state, 'ready')
        self.assertEqual(sim.return_motion.stage, 'complete')
        self.assertIn('safe_waypoint', stages)
        self.assertIn('home', stages)
        self.assertEqual(np.max(np.abs(sim.velocity)), 0.)

        # The backend must not accept an active-only edge after return.
        advance(packet(sequence + 1, True))
        self.assertEqual(cycle.state, 'ready')
        self.assertFalse(cycle.armed)
        advance(packet(sequence + 1, False))
        self.assertEqual(cycle.state, 'ready')
        self.assertTrue(cycle.armed)
        advance(packet(sequence + 1, True))
        self.assertEqual(cycle.state, 'tracking')
        self.assertEqual(sim.state, 'tracking')
        self.assertEqual(sim.return_motion.stage, 'inactive')
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-5)

    def moving_sim(self):
        sim = BimanualSimulation()
        goals = {side:mink.SE3.from_rotation_and_translation(home.rotation(),home.translation()+[.05,0,.02])
                 for side,home in sim.home_targets.items()}
        for _ in range(35):
            self.assertTrue(sim.step(goals))
        self.assertGreater(np.max(np.abs(sim.velocity)),.01)
        return sim

    def assert_stops_on_return_fault(self, sim):
        for _ in range(200):
            before, previous = sim.config.q.copy(),sim.velocity[sim.dofs].copy()
            applied=sim.step(returning=True)
            assert_output(sim,before,previous)
            if not applied:
                break
        self.assertEqual(sim.state,'blocked')
        self.assertEqual(np.max(np.abs(sim.velocity)),0.)
        self.assertTrue(sim.brake_plan)

    def test_nonfinite_return_proposal_uses_checked_tail_and_faults_at_rest(self):
        sim=self.moving_sim()
        with patch.object(RuckigJointMotionLimiter,'Step',return_value=np.full(14,np.nan)):
            self.assert_stops_on_return_fault(sim)
        self.assertTrue(sim.reason.startswith('return_path_blocked:'))

    def test_collision_rejection_uses_checked_stop_instead_of_publishing_proposal(self):
        sim=self.moving_sim()
        with patch.object(sim,'checked_stop_plan',return_value=(None,'swept_clearance')):
            self.assert_stops_on_return_fault(sim)
        self.assertIn('swept_clearance',sim.reason)

    def test_return_generator_exception_brakes_before_fault(self):
        sim=self.moving_sim()
        with patch.object(RuckigJointMotionLimiter,'Step',side_effect=RuntimeError('injected trajectory failure')):
            self.assert_stops_on_return_fault(sim)
        self.assertIn('return_trajectory_error',sim.reason)

    def test_invalid_waypoint_never_bypasses_joint_guards(self):
        sim=self.moving_sim()
        sim.return_motion.waypoint[3] = 100.
        self.assert_stops_on_return_fault(sim)
        self.assertEqual(sim.reason,'invalid_return_waypoint')

    def test_timeout_brakes_before_fault(self):
        sim=self.moving_sim()
        sim.return_motion.maximum_duration_s = sim.dt/2
        self.assert_stops_on_return_fault(sim)
        self.assertEqual(sim.reason,'return_timeout')


if __name__ == '__main__':
    unittest.main()
