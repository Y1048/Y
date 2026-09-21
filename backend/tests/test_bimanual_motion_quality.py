"""Motion quality gates in addition to the collision/range/protocol tests.

Synthetic fixed targets are not Quest or hardware verification.
"""
import sys
import time
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_unity_sim import PairedHandFilter
from test_bimanual_unity_sim import packet

import numpy as np
import json
from collections import Counter
from g1_bimanual_limits import JOINT_VELOCITY_LIMITS_RAD_S, JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation, mink


def quality_case(side='right', axis=0, distance=None, ticks=600):
    sim = BimanualSimulation()
    home = sim.home_targets[side]
    rotation = home.rotation() if distance is not None else home.rotation() @ mink.SO3.exp(np.eye(3)[axis]*np.deg2rad(45.))
    position = home.translation() + (np.array([distance, 0, 0]) if distance is not None else np.zeros(3))
    goals = dict(sim.home_targets)
    goals[side] = mink.SE3.from_rotation_and_translation(rotation, position)
    policy = sim.motion[side]
    peak = np.zeros(7)
    maximum_error = overshoot = 0.
    reasons = Counter()
    frozen = np.ones(sim.model.nq, dtype=bool)
    frozen[sim.qids] = False
    for _ in range(ticks):
        previous = sim.velocity.copy()
        assert sim.step(goals), sim.reason
        assert np.max(np.abs(sim.velocity-previous)) <= JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt+1e-6
        assert np.all(np.abs(sim.velocity[sim.dofs]) <= sim.caps+1e-6)
        assert np.all(sim.config.q[sim.qids] >= sim.ranges[:,0]-1e-8)
        assert np.all(sim.config.q[sim.qids] <= sim.ranges[:,1]+1e-8)
        assert np.array_equal(sim.config.q[frozen],sim.home[frozen])
        assert sim.clearance(sim.config.q) >= .005
        pose = sim.config.get_transform_frame_to_world(side+'_wrist_yaw_link','body')
        error = np.linalg.norm(pose.translation()-position)
        maximum_error = max(maximum_error,error)
        overshoot = max(overshoot,pose.translation()[0]-position[0])
        peak = np.maximum(peak,np.abs(sim.config.q[policy.qpos_ids]-sim.home[policy.qpos_ids]))
        reasons[sim.reason or 'tracking'] += 1
    result=dict(side=side,axis=axis,distance=distance,ticks=ticks,
        peak_joint_excursion_deg=np.rad2deg(peak).tolist(),peak_position_error_mm=float(maximum_error*1000),
        overshoot_mm=float(overshoot*1000),final_position_error_mm=float(error*1000),
        final_rotation_error_deg=float(np.rad2deg(np.linalg.norm((pose.rotation().inverse()@rotation).log()))),
        reasons=dict(reasons))
    print('QUALITY',json.dumps(result),flush=True)
    return result


def replay_recorded_motion():
    from g1_bimanual_unity_sim import UnityCycle
    sim=BimanualSimulation()
    cycle=UnityCycle(sim)
    timings=[]
    states=set()
    counts=Counter()
    minimum=.2
    frozen=np.ones(sim.model.nq,dtype=bool)
    frozen[sim.qids]=False
    for line in (ROOT/'backend/tests/fixtures/bimanual_motion_regression_20260918.jsonl').read_text().splitlines():
        row=json.loads(line)
        if row['kind']=='input':
            cycle.receive(json.loads(row['raw_json_text']),row['receive_monotonic_s'])
            continue
        previous=sim.velocity.copy()
        start=time.perf_counter()
        cycle.tick(row['monotonic_s'])
        timings.append((time.perf_counter()-start)*1000)
        states.add(cycle.state)
        assert cycle.state!='blocked',cycle.reason
        assert np.max(np.abs(sim.velocity-previous))<=JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt+1e-6
        assert np.all(np.abs(sim.velocity[sim.dofs])<=sim.caps+1e-6)
        assert np.all(sim.config.q[sim.qids]>=sim.ranges[:,0]-1e-8)
        assert np.all(sim.config.q[sim.qids]<=sim.ranges[:,1]+1e-8)
        assert np.array_equal(sim.config.q[frozen],sim.home[frozen])
        minimum=min(minimum,sim.clearance(sim.config.q))
        assert minimum>=.005
        if cycle.last_tick_action=='tracking':
            counts[sim.reason or 'tracking']+=1
    # Keep stepping return if the new input filtering changed the return duration.
    extra=0
    while cycle.state=='returning' and extra<1800:
        previous=sim.velocity.copy()
        cycle.tick(row['monotonic_s']+(extra+1)*sim.dt)
        assert np.max(np.abs(sim.velocity-previous))<=JOINT_ACCELERATION_LIMIT_RAD_S2*sim.dt+1e-6
        assert sim.clearance(sim.config.q)>=.005
        extra+=1
    assert cycle.state=='ready',cycle.reason
    result=dict(ticks=len(timings),tracking_reasons=dict(counts),states=sorted(states),
        braking_total=sim.braking_steps,minimum_clearance_mm=minimum*1000,
        p95_ms=float(np.percentile(timings,95)),max_ms=max(timings),extra_return_ticks=extra)
    print('NEW_RECORDED_REPLAY',json.dumps(result),flush=True)
    return result


class MotionQualityTests(unittest.TestCase):
    def test_reported_quest_regression_preserves_limits_and_returns(self):
        replay_recorded_motion()

    def test_local_x_rotation_stays_wrist_dominant_on_both_arms(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                result = quality_case(side,0)
                self.assertLess(result['peak_position_error_mm'],3.)
                self.assertLess(max(result['peak_joint_excursion_deg'][:4]),10.)
                self.assertLess(result['peak_joint_excursion_deg'][3],1.5)
                self.assertLess(result['final_position_error_mm'],1.)
                self.assertLess(result['final_rotation_error_deg'],.1)

    def test_local_z_rotation_stays_wrist_dominant_on_both_arms(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                result = quality_case(side,2)
                self.assertLess(result['peak_position_error_mm'],9.)
                self.assertLess(max(result['peak_joint_excursion_deg'][:4]),10.)
                self.assertLess(result['peak_joint_excursion_deg'][3],1.5)
                self.assertLess(result['final_position_error_mm'],1.)
                self.assertLess(result['final_rotation_error_deg'],.1)

    def test_fixed_position_approach_has_no_overshoot(self):
        for side in ('left', 'right'):
            for distance in (.02,.05):
                with self.subTest(side=side,distance=distance):
                    result = quality_case(side,distance=distance)
                    self.assertLessEqual(result['overshoot_mm'],.1)
                    self.assertLess(result['final_position_error_mm'],3.)

    def test_right_arm_matches_unchanged_reference_in_free_space(self):
        sys.path.insert(0,str(ROOT/'experiments/twist2_right_arm_manual'))
        from replay_upstream_mink import build, base
        from bimanual_replay_profiles import historical_recording_profile
        # Compare algorithms under the reference's original limits. The new
        # 3/3 profile intentionally differs in timing and has separate gates.
        sim = self.enterContext(historical_recording_profile())
        model, planner, tracking = build()
        q = base._initial_configuration(model)
        planner.configuration.update(q)
        tracking.Reset(q)
        home = sim.home_targets['right']
        goal = mink.SE3.from_rotation_and_translation(
            home.rotation() @ mink.SO3.exp(np.array([np.pi/4,0,0])),home.translation())
        targets = dict(sim.home_targets,right=goal)
        for _ in range(600):
            self.assertTrue(sim.step(targets),sim.reason)
            result = tracking.Track(q,goal)
            self.assertTrue(result.applied,result.status)
            q = result.q
            np.testing.assert_allclose(sim.config.q[sim.motion['right'].qpos_ids],q[planner.qpos_ids],atol=1e-7,rtol=0)

    def test_orientation_priority_hysteresis_is_reversible_for_each_arm(self):
        sim=BimanualSimulation()
        for side,policy in sim.motion.items():
            home=sim.home_targets[side]
            outside=mink.SE3.from_rotation_and_translation(home.rotation(),home.translation()+[.09,0,0])
            for _ in range(10):
                policy._update_orientation_priority(sim.config.q,outside,.006)
            self.assertFalse(policy.position_priority_active)
            policy._update_orientation_priority(sim.config.q,home,.006)
            for _ in range(60):
                policy._update_orientation_priority(sim.config.q,outside,.006)
            self.assertTrue(policy.position_priority_active)
            self.assertAlmostEqual(policy.orientation_priority_scale,.5)
            for _ in range(60):
                policy._update_orientation_priority(sim.config.q,home,.04)
            self.assertFalse(policy.position_priority_active)
            self.assertAlmostEqual(policy.orientation_priority_scale,1.)

    def test_preference_state_is_per_arm_and_return_resets_it(self):
        sim = BimanualSimulation()
        left,right = sim.motion['left'],sim.motion['right']
        left.position_priority_active=True
        left.orientation_priority_scale=.5
        left.elbow_assist_active=True
        self.assertFalse(right.position_priority_active)
        self.assertFalse(right.elbow_assist_active)
        self.assertEqual(right.orientation_priority_scale,1.)
        self.assertIsNot(left.wrist_priority_task.cost,right.wrist_priority_task.cost)
        self.assertTrue(sim.step(returning=True))
        self.assertTrue(sim.step(sim.home_targets))
        self.assertFalse(left.position_priority_active)
        self.assertFalse(left.elbow_assist_active)
        self.assertEqual(left.orientation_priority_scale,1.)

    def test_torso_projection_preserves_rotation_and_side_reference(self):
        sim = BimanualSimulation()
        for side,policy in sim.motion.items():
            geom = policy.torso_geom_ids[0]
            inside = sim.config.data.geom_xpos[geom].copy()
            current = sim.home_targets[side]
            goal = mink.SE3.from_rotation_and_translation(current.rotation(),inside)
            projected,changed = policy._project_target_outside_torso(goal,current.translation())
            self.assertTrue(changed)
            np.testing.assert_allclose(projected.rotation().as_matrix(),goal.rotation().as_matrix(),atol=1e-12)
            for gid in policy.torso_geom_ids:
                center=sim.config.data.geom_xpos[gid]
                rotation=sim.config.data.geom_xmat[gid].reshape(3,3)
                half=sim.model.geom_size[gid]+policy.wrist_target_radius_m+sim.clearance_m
                local=rotation.T@(projected.translation()-center)
                self.assertTrue(np.any(np.abs(local)>=half-1e-8))

    def test_policies_do_not_remove_bilateral_collision_constraints(self):
        sim = BimanualSimulation()
        self.assertEqual(len(sim.dofs),14)
        self.assertEqual(set(sim.motion),{'left','right'})
        self.assertEqual(sim.clearance_m,.005)
        self.assertEqual(sim.limits[2].minimum_distance_from_collisions,.006)
        np.testing.assert_allclose(sim.caps,np.asarray(JOINT_VELOCITY_LIMITS_RAD_S))
        for side,policy in sim.motion.items():
            np.testing.assert_allclose(policy.acceleration_limits,np.full(7, JOINT_ACCELERATION_LIMIT_RAD_S2))
            rows,bounds=policy.yaw_velocity_bounds()
            self.assertEqual(rows.shape,(2,sim.model.nv))
            self.assertTrue(np.isfinite(bounds).all())


class PoseFilterTests(unittest.TestCase):
    def setUp(self):
        self.packet = packet
        self.filter = PairedHandFilter()
        self.filter.reset(packet())

    def test_first_packet_and_reengage_reset_without_jump(self):
        for side in ('left','right'):
            np.testing.assert_array_equal(self.filter.hands[side]['position_m'],packet()[side]['position_m'])
        moved=packet(1,True)
        moved['left']['position_m'][0]+=1
        self.filter.update(moved)
        self.filter.reset(moved)
        np.testing.assert_array_equal(self.filter.hands['left']['position_m'],moved['left']['position_m'])

    def test_smoothing_is_independent_per_hand(self):
        moved=packet(1,True)
        moved['left']['position_m'][0]+=.06
        self.filter.update(moved)
        expected=.06*(-np.expm1(-(1/60)/.060))
        self.assertAlmostEqual(self.filter.hands['left']['position_m'][0]-packet()['left']['position_m'][0],expected)
        np.testing.assert_array_equal(self.filter.hands['right']['position_m'],packet()['right']['position_m'])

    def test_invalid_hand_does_not_advance_either_filtered_target(self):
        invalid=packet(1,True)
        invalid['left']['tracked']=False
        invalid['right']['position_m'][0]+=1
        self.filter.update(invalid)
        for side in ('left','right'):
            np.testing.assert_array_equal(self.filter.hands[side]['position_m'],packet()[side]['position_m'])

    def test_duplicate_packet_does_not_advance_filter(self):
        moved=packet(1,True)
        moved['left']['position_m'][0]+=.06
        self.filter.update(moved)
        saved=self.filter.hands['left']['position_m'].copy()
        self.filter.update(moved)
        np.testing.assert_array_equal(self.filter.hands['left']['position_m'],saved)

    def test_tolerated_wire_rounding_is_normalized_before_filtering(self):
        initial=packet()
        initial['right']['quaternion_wxyz']=[1.00001,0,0,0]
        self.filter.reset(initial)
        self.assertAlmostEqual(np.linalg.norm(self.filter.hands['right']['quaternion_wxyz']),1.)
        moved=packet(1,True)
        moved['right']['quaternion_wxyz']=(1.00001*mink.SO3.exp(np.array([0,0,.6])).wxyz).tolist()
        self.filter.update(moved)
        self.assertAlmostEqual(np.linalg.norm(self.filter.hands['right']['quaternion_wxyz']),1.)

    def test_quaternion_hemisphere_does_not_invent_a_rotation(self):
        moved=packet(1,True)
        moved['right']['quaternion_wxyz']=[-1,0,0,0]
        self.filter.update(moved)
        rotation=mink.SO3(self.filter.hands['right']['quaternion_wxyz'])
        np.testing.assert_allclose(rotation.as_matrix(),np.eye(3),atol=1e-12)

    def test_rotation_smoothing_and_unit_norm(self):
        moved=packet(1,True)
        moved['right']['quaternion_wxyz']=mink.SO3.exp(np.array([0,0,.6])).wxyz.tolist()
        self.filter.update(moved)
        q=self.filter.hands['right']['quaternion_wxyz']
        self.assertAlmostEqual(np.linalg.norm(q),1.)
        np.testing.assert_allclose(mink.SO3(q).log(),[0,0,.6*(-np.expm1(-(1/60)/.050))],atol=1e-12)


if __name__ == "__main__":
    unittest.main()
