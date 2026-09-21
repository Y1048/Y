"""Output-continuity and input-failure regressions; no physical robot I/O."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
import g1_bimanual_sim as core
from g1_bimanual_unity_sim import UnityCycle, decode, mink
from test_bimanual_unity_sim import packet


class OutputContinuityTests(unittest.TestCase):
    def setup_motion(self):
        self.sim = core.BimanualSimulation()
        self.cycle = UnityCycle(self.sim)
        self.sequence = 0
        self.previous_output_velocity = np.zeros(14)
        self.max_output_acceleration = 0.
        self.cycle.receive(packet(0), 0.)
        self.advance(packet(1, True))
        for _ in range(30):
            p = packet(self.sequence+1, True)
            p['right']['position_m'][2] += .10
            self.advance(p)
        self.assertGreater(np.max(np.abs(self.sim.velocity)), .01)

    def advance(self, p):
        self.sequence = p['sequence']
        now = self.sequence*self.sim.dt
        self.cycle.receive(p, now)
        before = self.sim.config.q.copy()
        self.cycle.tick(now)
        output_velocity = (self.sim.config.q[self.sim.qids]-before[self.sim.qids])/self.sim.dt
        np.testing.assert_allclose(output_velocity, self.sim.velocity[self.sim.dofs], atol=1e-10, rtol=0)
        acceleration = np.max(np.abs(output_velocity-self.previous_output_velocity))/self.sim.dt
        self.max_output_acceleration = max(self.max_output_acceleration, acceleration)
        self.assertLessEqual(acceleration, JOINT_ACCELERATION_LIMIT_RAD_S2+1e-4)
        self.previous_output_velocity = output_velocity
        self.assertTrue(np.all(np.abs(output_velocity) <= self.sim.caps+1e-6))
        self.assertGreaterEqual(self.sim.clearance(self.sim.config.q), .005)
        self.assertNotEqual(self.cycle.state, 'blocked', self.cycle.reason)

    def test_transient_loss_and_recovery_are_output_continuous(self):
        for side in ('left', 'right'):
            for ticks in (1, 6, 20):
                with self.subTest(side=side, ticks=ticks):
                    self.setup_motion()
                    for _ in range(ticks):
                        p = packet(self.sequence+1, True)
                        p[side]['tracked'] = False
                        self.advance(p)
                        self.assertEqual(self.cycle.last_tick_action, 'tracking_braking')
                    self.assertEqual(self.cycle.state, 'tracking')
                    for _ in range(20):
                        p = packet(self.sequence+1, True)
                        p['right']['position_m'][2] += .10
                        self.advance(p)
                    print('CONTINUITY', side, ticks, 'max_output_accel_deg_s2=',
                          np.rad2deg(self.max_output_acceleration), flush=True)

    def test_long_loss_returns_at_zero_speed_then_reengages(self):
        self.setup_motion()
        for _ in range(30):
            self.advance(packet(self.sequence+1, True, tracked=False))
        self.assertEqual(self.cycle.state, 'returning')
        for _ in range(1800):
            self.advance(packet(self.sequence+1, False))
            if self.cycle.state == 'ready':
                break
        self.assertEqual(self.cycle.state, 'ready')
        self.assertEqual(np.max(np.abs(self.sim.velocity)), 0.)
        self.advance(packet(self.sequence+1, False))
        self.advance(packet(self.sequence+1, True))
        self.assertEqual(self.cycle.state, 'tracking')

    def test_loss_immediately_after_engage_checks_stationary_hold(self):
        self.sim = core.BimanualSimulation()
        self.cycle = UnityCycle(self.sim)
        self.previous_output_velocity = np.zeros(14)
        self.max_output_acceleration = 0.
        self.cycle.receive(packet(0), 0.)
        self.cycle.receive(packet(1, True), self.sim.dt)
        self.advance(packet(2, True, tracked=False))
        self.assertEqual(np.max(np.abs(self.sim.velocity)), 0.)
        self.assertTrue(self.sim.brake_plan)

    def test_missing_moving_tail_is_fault_not_velocity_reset(self):
        self.setup_motion()
        self.sim.brake_plan.clear()
        before_q, before_v = self.sim.config.q.copy(), self.sim.velocity.copy()
        self.assertFalse(self.sim.brake())
        self.assertEqual(self.sim.state, 'blocked')
        self.assertTrue(self.sim.reason.startswith('missing_checked_tail:'))
        np.testing.assert_array_equal(before_q, self.sim.config.q)
        np.testing.assert_array_equal(before_v, self.sim.velocity)

    def test_known_solver_exception_uses_tail_and_can_resume(self):
        self.setup_motion()
        with patch.object(core.qpsolvers, 'solve_problem', side_effect=core.SolverError('test numerical failure')):
            for _ in range(40):
                p = packet(self.sequence+1, True)
                p['right']['position_m'][2] += .10
                self.advance(p)
                self.assertEqual(self.sim.last_solver_error['type'], 'SolverError')
        self.assertEqual(np.max(np.abs(self.sim.velocity)), 0.)
        p = packet(self.sequence+1, True)
        p['right']['position_m'][2] += .10
        self.advance(p)
        self.assertIsNone(self.sim.last_solver_error)

    def test_solver_exception_without_tail_fails_closed(self):
        sim = core.BimanualSimulation()
        before = sim.config.q.copy()
        with patch.object(core.qpsolvers, 'solve_problem', side_effect=core.SolverError('test')):
            self.assertFalse(sim.step(sim.home_targets))
        self.assertEqual(sim.state, 'blocked')
        self.assertEqual(sim.reason, 'solver_error:SolverError')
        np.testing.assert_array_equal(before, sim.config.q)

    def test_programming_error_is_not_hidden_as_solver_failure(self):
        sim = core.BimanualSimulation()
        with patch.object(core.qpsolvers, 'solve_problem', side_effect=TypeError('bad code')):
            with self.assertRaises(TypeError):
                sim.step(sim.home_targets)

    def test_nonfinite_solver_result_uses_checked_tail(self):
        self.setup_motion()
        with patch.object(core.qpsolvers, 'solve_problem', return_value=SimpleNamespace(found=True,x=np.full(14,np.nan))):
            for _ in range(40):
                self.advance(packet(self.sequence+1, True))
        self.assertEqual(np.max(np.abs(self.sim.velocity)), 0.)


class ProtocolBoundaryTests(unittest.TestCase):
    def test_large_numbers_and_deep_json_are_value_errors(self):
        for field in ('sender_time_s', 'position'):
            p = packet()
            if field == 'sender_time_s':
                p[field] = 10**400
            else:
                p['left']['position_m'][0] = 10**400
            with self.assertRaises(ValueError):
                decode(json.dumps(p).encode())
        raw = json.dumps(packet())[:-1] + ',"extra":' + '['*1100 + '0' + ']'*1100 + '}'
        self.assertLess(len(raw), 8192)
        with self.assertRaisesRegex(ValueError, 'json_depth'):
            decode(raw.encode())

    def test_brackets_in_strings_do_not_count_as_depth(self):
        p = packet()
        p['extra'] = '[{'*20 + '\\"' + '}]'*20
        self.assertEqual(decode(json.dumps(p).encode()), p)

    def test_parse_rejections_do_not_modify_cycle(self):
        sim = core.BimanualSimulation()
        cycle = UnityCycle(sim)
        cycle.receive(packet(0), 0.)
        before = (cycle.session, cycle.sequence, cycle.received, cycle.sender_time)
        for raw in (b'{"schema":1,"schema":2}', b'NaN', b'{', b'\xff'):
            try:
                cycle.receive(decode(raw), 1.)
            except (ValueError, UnicodeError):
                pass
            self.assertEqual(before, (cycle.session, cycle.sequence, cycle.received, cycle.sender_time))
        self.assertTrue(cycle.receive(decode(json.dumps(packet(1,True)).encode()), .1))
        self.assertEqual(cycle.state, 'tracking')

    def test_engage_origin_and_filter_share_normalized_rotation(self):
        sim = core.BimanualSimulation()
        cycle = UnityCycle(sim)
        cycle.receive(packet(0), 0.)
        p = packet(1, True)
        for side in ('left','right'):
            p[side]['quaternion_wxyz'] = (1.00009*mink.SO3.exp(np.array([.4,.2,-.3])).wxyz).tolist()
        cycle.receive(decode(json.dumps(p).encode()), .02)
        for side in ('left','right'):
            rotation = cycle.origins[side][1]
            np.testing.assert_allclose(rotation.T@rotation,np.eye(3),atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(rotation),1.)
        before=sim.config.q.copy()
        cycle.tick(.02)
        np.testing.assert_allclose(sim.config.q,before,atol=1e-9)

    def test_backend_generation_and_feedback_order_are_explicit(self):
        sim = core.BimanualSimulation()
        a,b = UnityCycle(sim),UnityCycle(sim)
        self.assertNotEqual(a.backend_id,b.backend_id)
        self.assertLess(a.backend_started_ns,b.backend_started_ns)
        a.receive(packet(0),0.)
        f1,f2=a.feedback(),a.feedback()
        self.assertEqual(f1['sequence'],f2['sequence'])
        self.assertLess(f1['feedback_sequence'],f2['feedback_sequence'])
        self.assertEqual(f1['backend_id'],a.backend_id)
        for n in range(10):
            b.receive(packet(n,True),n/60)
        self.assertEqual(b.state,'ready')
        b.receive(packet(10),.2)
        b.receive(packet(11,True),.3)
        self.assertEqual(b.state,'tracking')


if __name__ == '__main__':
    unittest.main()
