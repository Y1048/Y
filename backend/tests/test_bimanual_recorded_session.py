"""Replay the first logged staged-return session without sockets or Unity.

The fixture is a selected simulation recording, not measured G1 telemetry.
All derivatives use the recorded fixed simulation dt, never wall-clock jitter.
"""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest
from collections import Counter

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'MuJoCo_G1_Controller/scripts'))
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_unity_sim import UnityCycle, decode

FIXTURE = ROOT / 'backend/tests/fixtures/bimanual_staged_session_20260918.json.gz'
FIXTURE_SHA256 = 'a7410f6433fa5f18c73fbcc23880ca14213f78e4accc1e70e46e2e6ffc855341'


def load_fixture():
    raw = FIXTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
        raise ValueError('Recorded fixture bytes changed; review provenance before updating.')
    return json.loads(gzip.decompress(raw))


class RecordedStagedSessionTests(unittest.TestCase):
    def test_fixture_provenance_and_observed_scope(self):
        fixture = load_fixture()
        self.assertTrue(fixture['simulation_only'])
        self.assertFalse(fixture['hardware_measured'])
        run = fixture['source_run']
        self.assertEqual(run['mujoco_version'], '3.12.0')
        self.assertEqual(run['motion_policy'], 'bimanual_motion_v1')
        self.assertEqual(run['boundary_policy'], 'bimanual_boundary_v1')
        self.assertEqual(run['return_policy'], 'bimanual_staged_return_v1')
        self.assertIn('g1_bimanual_return.py', run['source_sha256'])
        states = [r for r in fixture['records'] if r['kind'] == 'state']
        self.assertEqual(len(states), 3433)
        transitions = []
        for row in states:
            if not transitions or transitions[-1] != row['state']:
                transitions.append(row['state'])
        self.assertEqual(transitions, ['ready', 'tracking', 'returning', 'ready'])
        self.assertEqual(states[-1]['reason'], 'tracking_lost')
        self.assertEqual(states[-1]['return_motion']['stage'], 'complete')
        self.assertEqual(states[-1]['return_motion']['settle_elapsed_s'], .5)

    def test_recorded_tracking_braking_and_staged_return(self):
        fixture = load_fixture()
        sim = BimanualSimulation()
        cycle = UnityCycle(sim)
        self.assertEqual(sim.dt, fixture['source_run']['simulation_dt_s'])
        previous_velocity = np.zeros(14)
        peak_velocity = np.zeros(14)
        max_acceleration = max_q_delta = 0.
        minimum_clearance = float('inf')
        actions, stages, reasons = Counter(), [], Counter()
        timing = []
        return_started = ready_at = None
        frozen = np.ones(sim.model.nq, dtype=bool)
        frozen[sim.qids] = False
        for row in fixture['records']:
            if row['kind'] == 'input':
                packet = decode(json.dumps(row['packet'], allow_nan=False).encode('utf-8'))
                self.assertEqual(cycle.receive(packet, row['now']), row['accepted'])
                continue
            before = sim.config.q.copy()
            start = time.perf_counter()
            cycle.tick(row['now'])
            timing.append((time.perf_counter() - start) * 1000)
            self.assertEqual(cycle.state, row['state'], (row['now'], cycle.reason))
            self.assertEqual(cycle.last_tick_action, row['tick_action'])
            velocity = (sim.config.q[sim.qids] - before[sim.qids]) / sim.dt
            np.testing.assert_allclose(velocity, sim.velocity[sim.dofs], atol=1e-10, rtol=0)
            acceleration = float(np.max(np.abs(velocity - previous_velocity)) / sim.dt)
            self.assertLessEqual(acceleration, np.deg2rad(60.) + 1e-5)
            self.assertTrue(np.all(np.abs(velocity) <= sim.caps + 1e-6))
            self.assertTrue(np.all(sim.config.q[sim.qids] >= sim.ranges[:, 0] - 1e-8))
            self.assertTrue(np.all(sim.config.q[sim.qids] <= sim.ranges[:, 1] + 1e-8))
            np.testing.assert_array_equal(sim.config.q[frozen], sim.home[frozen])
            clearance = sim.clearance(sim.config.q)
            self.assertTrue(np.isfinite(clearance))
            self.assertGreaterEqual(clearance, sim.clearance_m)
            minimum_clearance = min(minimum_clearance, clearance)
            q_delta = float(np.max(np.abs(sim.config.q[sim.qids] - np.asarray(row['q_rad']))))
            # A small tolerance permits solver rounding, not changed motion.
            self.assertLessEqual(q_delta, 5e-6, row['now'])
            max_q_delta = max(max_q_delta, q_delta)
            max_acceleration = max(max_acceleration, acceleration)
            peak_velocity = np.maximum(peak_velocity, np.abs(velocity))
            previous_velocity = velocity
            actions[cycle.last_tick_action] += 1
            if cycle.last_tick_action == 'tracking' and cycle.checked_braking_applied:
                reasons[sim.reason] += 1
            stage = sim.return_motion.stage
            if stage != 'inactive' and (not stages or stages[-1] != stage):
                stages.append(stage)
            if cycle.last_tick_action == 'returning' and return_started is None:
                return_started = row['now']
            if cycle.state == 'ready' and return_started is not None:
                ready_at = row['now']
        self.assertEqual(stages, ['safe_waypoint', 'home', 'complete'])
        self.assertEqual(actions['tracking_braking'], 20)
        self.assertGreater(sum(reasons.values()), 0)
        self.assertEqual(sim.return_motion.replans, 0)
        self.assertEqual(cycle.state, 'ready')
        self.assertEqual(np.max(np.abs(sim.velocity)), 0.)
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids], atol=1e-6, rtol=0)
        self.assertEqual(sim.return_motion.settled_ticks * sim.dt, .5)
        report = dict(simulation_only=True, state_ticks=len(timing), actions=dict(actions),
            tracking_braking_reasons=dict(reasons), stages=stages,
            recorded_return_wall_s=ready_at - return_started,
            return_simulation_s=sim.return_motion.elapsed_ticks * sim.dt,
            minimum_clearance_mm=minimum_clearance * 1000,
            max_output_acceleration_deg_s2=float(np.rad2deg(max_acceleration)),
            peak_speed_deg_s=float(np.rad2deg(np.max(peak_velocity))),
            maximum_logged_q_difference_rad=max_q_delta,
            replay_tick_p95_ms=float(np.percentile(timing, 95)),
            replay_tick_max_ms=max(timing))
        print('RECORDED_STAGED_SESSION ' + json.dumps(report, allow_nan=False), flush=True)


if __name__ == '__main__':
    unittest.main()
