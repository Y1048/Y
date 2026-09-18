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
from g1_bimanual_sim import BimanualSimulation, base, mink
from g1_bimanual_return import BimanualReturnMotion, RuckigJointMotionLimiter
from g1_mink_return_cycle import SAFE_RIGHT_ARM_RAD


def assert_output(sim, before, previous_velocity):
    velocity = (sim.config.q[sim.qids]-before[sim.qids])/sim.dt
    np.testing.assert_allclose(velocity, sim.velocity[sim.dofs], atol=1e-10, rtol=0)
    acceleration = np.max(np.abs(velocity-previous_velocity))/sim.dt
    assert acceleration <= np.deg2rad(60.)+1e-5, acceleration
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
    next_velocity = np.sign(sim.velocity)*np.maximum(0., np.abs(sim.velocity)-np.deg2rad(60.)*sim.dt)
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
    def test_profile_and_waypoint_match_original_right_arm(self):
        sim = BimanualSimulation()
        policy = sim.return_motion
        np.testing.assert_array_equal(policy.waypoint[7:], SAFE_RIGHT_ARM_RAD)
        np.testing.assert_allclose(np.rad2deg(policy.waypoint[:7]), [10,35,0,70,0,0,0])
        np.testing.assert_allclose(policy.jerk_limits, base.RIGHT_ARM_MAX_JERK_RAD_S3)
        np.testing.assert_allclose(policy.acceleration_limits, np.deg2rad(60.))
        np.testing.assert_allclose(sim.caps, np.tile(np.deg2rad([90]*4+[180]*3),2))
        self.assertEqual(policy.settle_s, .5)
        self.assertEqual(len(sim.dofs), 14)
        self.assertEqual(sim.clearance_m, .005)

    def test_actual_return_start_fixtures_visit_waypoint_and_finish(self):
        fixture = json.loads((ROOT/'backend/tests/fixtures/bimanual_return_starts_20260918.json').read_text())
        for entry in fixture['starts']:
            with self.subTest(reason=entry['reason']):
                sim, result = recorded_return(entry)
                self.assertLess(result['simulation_s'], 7.)
                self.assertLess(result['simulation_s'], result['old_simulation_s'])
                self.assertGreaterEqual(sim.return_motion.settled_ticks*sim.dt, .5)
                self.assertEqual(result['replans'], 0)

    def test_right_waypoint_trajectory_matches_original_limiter(self):
        sim = BimanualSimulation()
        q = sim.home.copy()
        q[sim.motion['right'].qpos_ids[4]] = .3
        q[sim.motion['left'].qpos_ids[4]] = -.3
        sim.config.update(q)
        single = RuckigJointMotionLimiter(q[sim.qids[7:]], sim.caps[7:],
            np.full(7,np.deg2rad(60.)), np.full(7,base.RIGHT_ARM_MAX_JERK_RAD_S3),sim.dt)
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
            np.full(7,np.deg2rad(60.)),np.full(7,base.RIGHT_ARM_MAX_JERK_RAD_S3),sim.dt)
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
