"""Measured initialization tests. No network, motor publisher or live robot."""
from pathlib import Path
import copy
import json
import sys
import unittest
from unittest.mock import patch

import numpy as np
import mujoco
import mink

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_measured_start import (JOINT_NAMES, MAX_AGE_S, MAX_DRIFT_RAD,
    MeasuredStartGate, initialize_inactive_model, validate_snapshot, STATIONARY_SPEED_RAD_S)
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_unity_sim import UnityCycle, decode, MEASURED_START_SCHEMA
from g1_bimanual_target import BASIS


def model_pose(sim):
    joints = [mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_JOINT,
                              n + '_joint') for n in JOINT_NAMES]
    return sim.config.q[sim.model.jnt_qposadr[joints]].copy()


def snapshot(q, sequence=0, t=0., session='robot-A'):
    return dict(schema='g1.lowstate.view.v1', crc_valid=True,
        joint_names=list(JOINT_NAMES), session=session, sequence=sequence,
        source_monotonic_s=t, receipt_age_s=.01,
        q_rad=list(map(float, q)), dq_rad_s=[0.] * 29)


def packet(sim, sequence, *, engage=False, revision=-1, sample=None, aligned=True):
    hands = {}
    for side in ('left', 'right'):
        pose = sim.config.get_transform_frame_to_world(side + '_wrist_yaw_link', 'body')
        hands[side] = dict(tracked=True, position_m=(BASIS.T @ pose.translation()).tolist(),
            quaternion_wxyz=mink.SO3.from_matrix(BASIS.T @ pose.rotation().as_matrix() @ BASIS).wxyz.tolist())
    return dict(schema=MEASURED_START_SCHEMA, simulation_only=True,
        session='unity-A', sequence=sequence, sender_time_s=sequence * .02,
        input_frame='unity_display_world_v1', base_yaw_rad=sim.base_yaw_rad,
        engage=engage, return_home=False, start_aligned=aligned,
        start_state_available=sample is not None, start_state=sample,
        start_revision=revision, **hands)


class MeasuredStartTests(unittest.TestCase):
    def setUp(self):
        self.sim = BimanualSimulation()
        self.q = model_pose(self.sim)
        self.q[15] += .10
        self.q[22] += .10
        self.q[14] = -.04
        self.q[3] = self.q[9] = .5

    def settle(self, cycle, start=0, q=None):
        q = self.q if q is None else q
        for i in range(start, start + 22):
            p = packet(self.sim, i, sample=snapshot(q, i, i*.02))
            self.assertTrue(cycle.receive(decode(json.dumps(p)), i*.02))
            cycle.tick(i*.02)
            cycle.feedback()  # The seed must be announced before engage can acknowledge it.
        return start + 22

    def test_capture_is_stationary_deliberate_and_keeps_authored_home(self):
        home = self.sim.home[self.sim.qids].copy()
        base = self.sim.config.q[:7].copy()
        cycle = UnityCycle(self.sim)
        self.settle(cycle)
        self.assertTrue(cycle.start_gate.ready)
        self.assertEqual(cycle.start_gate.revision, 1)
        np.testing.assert_allclose(model_pose(self.sim), self.q, atol=0, rtol=0)
        np.testing.assert_array_equal(self.sim.home[self.sim.qids], home)
        np.testing.assert_array_equal(self.sim.config.q[:7], base)
        self.assertEqual(cycle.state, 'ready')
        self.assertEqual(self.sim.state, 'ready')
        self.assertFalse(np.any(self.sim.velocity))
        self.assertEqual(len(self.sim.brake_plan), 2)
        self.assertGreaterEqual(self.sim.clearance(self.sim.config.q), self.sim.clearance_m)

    def test_no_sample_no_alignment_no_inactive_packet_never_initializes(self):
        for kind in ('missing', 'unaligned', 'already_engaged'):
            with self.subTest(kind=kind):
                sim = BimanualSimulation(); cy = UnityCycle(sim); before = sim.config.q.copy()
                for i in range(30):
                    p = packet(sim, i, sample=None if kind == 'missing' else snapshot(self.q,i,i*.02),
                               aligned=kind != 'unaligned', engage=kind == 'already_engaged')
                    cy.receive(decode(json.dumps(p)), i*.02); cy.tick(i*.02)
                self.assertEqual(cy.state,'ready'); self.assertFalse(cy.start_gate.ready)
                np.testing.assert_array_equal(before,sim.config.q)

    def test_duplicate_samples_cannot_manufacture_stability_or_freshness(self):
        gate = MeasuredStartGate(); s = snapshot(self.q)
        for i in range(30):
            gate.observe(s, i*.02, self.sim, allow_initialize=True, aligned=True)
        self.assertFalse(gate.ready); self.assertFalse(gate.fresh(.6))
        self.assertEqual(gate.revision,0)

    def test_motion_age_gaps_and_drift_require_new_stable_window(self):
        for failure in ('speed','age','gap','drift'):
            with self.subTest(failure=failure):
                gate=MeasuredStartGate()
                for i in range(30):
                    s=snapshot(self.q,i,i*.02)
                    now=i*.02
                    if failure=='speed': s['dq_rad_s'][18]=STATIONARY_SPEED_RAD_S+.001
                    if failure=='age': s['receipt_age_s']=.101
                    if failure=='gap': s['source_monotonic_s']=i*.2;now=i*.2
                    if failure=='drift': s['q_rad'][15]+=i*.006
                    gate.observe(s,now,self.sim,allow_initialize=True,aligned=True)
                self.assertFalse(gate.ready);self.assertEqual(gate.revision,0)

    def test_old_revision_or_changed_pose_refuses_activation(self):
        for changed in (False,True):
            with self.subTest(changed=changed):
                sim=BimanualSimulation();cy=UnityCycle(sim);self.sim=sim
                i=self.settle(cy);revision=cy.start_gate.revision
                s=snapshot(self.q,i,i*.02)
                if changed:s['q_rad'][15]+=.006
                p=packet(sim,i,engage=True,revision=revision if changed else revision-1,sample=s)
                cy.receive(decode(json.dumps(p)),i*.02);cy.tick(i*.02)
                self.assertEqual(cy.state,'ready')

    def test_acknowledged_start_has_bounded_first_step_and_no_continuous_reseed(self):
        cy=UnityCycle(self.sim);i=self.settle(cy);before=self.sim.config.q[self.sim.qids].copy()
        p=packet(self.sim,i,engage=True,revision=cy.start_gate.revision,sample=snapshot(self.q,i,i*.02))
        cy.receive(decode(json.dumps(p)),i*.02);cy.tick(i*.02)
        self.assertEqual(cy.state,'tracking')
        self.assertLessEqual(np.max(np.abs(self.sim.config.q[self.sim.qids]-before)),
                             self.sim.profile.joint_acceleration_limit_rad_s2*self.sim.dt**2+1e-8)
        revision=cy.start_gate.revision
        for j in range(i+1,i+25):
            other=self.q.copy();other[18]+=.5
            p=packet(self.sim,j,engage=True,revision=revision,sample=snapshot(other,j,j*.02))
            cy.receive(decode(json.dumps(p)),j*.02);cy.tick(j*.02)
        self.assertEqual(cy.start_gate.revision,revision)
        self.assertLess(np.max(np.abs(self.sim.config.q[self.sim.qids]-before)),.03)
        np.testing.assert_array_equal(cy.start_gate.seed,self.q)

    def test_return_does_not_reseed_and_next_cycle_requires_new_acknowledgement(self):
        cy=UnityCycle(self.sim);i=self.settle(cy)
        p=packet(self.sim,i,engage=True,revision=cy.start_gate.revision,sample=snapshot(self.q,i,i*.02))
        cy.receive(p,i*.02);cy.tick(i*.02);revision=cy.start_gate.revision
        cy.start_return('test')
        for j in range(i+1,i+1000):
            q=self.q.copy();q[18]+=.2
            p=packet(self.sim,j,sample=snapshot(q,j,j*.02))
            cy.receive(p,j*.02);cy.tick(j*.02)
            self.assertEqual(cy.start_gate.revision,revision)
            if cy.state=='ready':break
        self.assertEqual(cy.state,'ready');self.assertFalse(cy.start_gate.ready)
        self.settle(cy,start=j+1)
        self.assertGreater(cy.start_gate.revision,revision)

    def test_bad_pose_or_nonready_model_fails_without_mutating_commands(self):
        cases=[]
        q=self.q.copy();q[20]=-1.59;cases.append(q)
        q=self.q.copy();q[18]=-.1;cases.append(q)
        cases += [np.ones(14),np.full(29,float('nan'))]
        for q in cases:
            before=self.sim.config.q.copy();home=self.sim.home.copy()
            with self.assertRaises(ValueError):initialize_inactive_model(self.sim,q)
            np.testing.assert_array_equal(before,self.sim.config.q)
            np.testing.assert_array_equal(home,self.sim.home)
        self.sim.state='tracking'
        with self.assertRaises(ValueError):initialize_inactive_model(self.sim,self.q)
        self.sim.state='ready';self.sim.velocity[self.sim.dofs[0]]=.001
        with self.assertRaises(ValueError):initialize_inactive_model(self.sim,self.q)

    def test_collision_failure_does_not_partially_apply_seed(self):
        before=self.sim.config.q.copy();home=self.sim.home.copy()
        with patch.object(self.sim,'clearance',return_value=.001):
            with self.assertRaises(ValueError):initialize_inactive_model(self.sim,self.q)
        np.testing.assert_array_equal(before,self.sim.config.q)
        np.testing.assert_array_equal(home,self.sim.home)

    def test_reconnect_and_retired_session_cannot_reuse_old_approval(self):
        gate=MeasuredStartGate()
        for i in range(23):gate.observe(snapshot(self.q,i,i*.02),i*.02,self.sim,allow_initialize=True,aligned=True)
        old=gate.revision;self.assertTrue(gate.ready)
        gate.observe(snapshot(self.q,0,5,session='B'),.5,self.sim,allow_initialize=True,aligned=True)
        self.assertFalse(gate.ready);self.assertFalse(gate.can_engage(.5,old))
        gate.observe(snapshot(self.q,100,10),.52,self.sim,allow_initialize=True,aligned=True)
        self.assertFalse(gate.ready);self.assertEqual(gate.reason,'retired_measurement_session')

    def test_schema_downgrade_within_live_session_is_rejected(self):
        cy=UnityCycle(self.sim);i=self.settle(cy)
        p=packet(self.sim,i,sample=snapshot(self.q,i,i*.02));p['schema']='g1.bimanual.unity.sim.v4'
        self.assertFalse(cy.receive(decode(json.dumps(p)),i*.02))
        self.assertEqual(cy.state,'ready')

    def test_malformed_state_is_not_treated_as_no_state(self):
        base=snapshot(self.q)
        for name,value in [('crc_valid',False),('session',''),('sequence',True),
                ('q_rad',[0.]*14),('dq_rad_s',[float('nan')]*29),
                ('receipt_age_s',-1),('joint_names',list(reversed(JOINT_NAMES)))]:
            with self.subTest(name=name):
                s=copy.deepcopy(base);s[name]=value
                with self.assertRaises(ValueError):validate_snapshot(s)
        p=packet(self.sim,0);p['start_state_available']=True
        with self.assertRaises(ValueError):decode(json.dumps(p))

    def test_source_arrays_and_seed_do_not_alias_and_no_absolute_age_claim(self):
        gate=MeasuredStartGate();s=snapshot(self.q)
        gate.observe(s,0.,self.sim,allow_initialize=True,aligned=True)
        s['q_rad'][15]=9
        self.assertNotEqual(gate.latest['q_rad'][15],9)
        self.assertLessEqual(gate.deadline,MAX_AGE_S)



    def test_stationary_position_with_recorded_scale_dq_noise_can_settle(self):
        gate=MeasuredStartGate()
        for i in range(24):
            sample=snapshot(self.q,i,i*.02)
            sample['dq_rad_s'][3]=.0753
            sample['q_rad'][3]+=.0001*(i%2)
            gate.observe(sample,i*.02,self.sim,allow_initialize=True,aligned=True)
        self.assertTrue(gate.ready)
        self.assertEqual(gate.revision,1)

    def test_revision_must_be_announced_before_it_can_activate(self):
        cy=UnityCycle(self.sim)
        for i in range(24):
            p=packet(self.sim,i,sample=snapshot(self.q,i,i*.02))
            cy.receive(p,i*.02);cy.tick(i*.02)
        self.assertTrue(cy.start_gate.ready)
        self.assertEqual(cy.start_gate.announced_revision,0)
        p=packet(self.sim,24,engage=True,revision=cy.start_gate.revision,
                 sample=snapshot(self.q,24,.48))
        cy.receive(p,.48);cy.tick(.48)
        self.assertEqual(cy.state,'ready')
        cy.feedback()
        self.assertEqual(cy.start_gate.announced_revision,cy.start_gate.revision)

    def test_v5_log_reports_inactive_reseed_not_fake_speed_and_rejects_forgery(self):
        import tempfile
        from g1_bimanual_runtime import runtime_metadata
        from g1_bimanual_session_report import analyze_session,replay_session
        cy=UnityCycle(self.sim)
        rows=[dict(kind='run',**runtime_metadata('test'))]
        for i in range(36):
            p=packet(self.sim,i,engage=i>=26,revision=cy.start_gate.revision,
                     sample=snapshot(self.q,i,i*.02))
            if i>=26:
                for side in ('left','right'):p[side]['position_m'][2]+=.04
            raw=json.dumps(p)
            accepted=cy.receive(decode(raw),i*.02)
            rows.append(dict(kind='input',accepted=accepted,receive_monotonic_s=i*.02,raw_json_text=raw))
            cy.tick(i*.02)
            rows.append(dict(kind='state',monotonic_s=i*.02,**cy.feedback(),**cy.diagnostics(i*.02)))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'v5.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in rows),encoding='utf-8')
            report=analyze_session(path)
            self.assertEqual(report['failures'],[])
            self.assertEqual(len(report['inactive_model_initializations']),1)
            self.assertGreater(report['inactive_model_initializations'][0]['maximum_inactive_reset_rad'],.05)
            replay=replay_session(path)
            self.assertTrue(replay['current_validation']['passed'])
            self.assertLess(replay['maximum_logged_q_difference_rad'],1e-9)
            forged=copy.deepcopy(rows)
            next(r for r in forged if r['kind']=='state' and r['state']=='tracking')['idle_measured_initialization']=True
            path.write_text('\n'.join(json.dumps(r) for r in forged),encoding='utf-8')
            report=analyze_session(path)
            self.assertIn('invalid_inactive_initialization_event',report['failures'])


if __name__=='__main__':unittest.main()
