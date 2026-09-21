"""Replay the user-confirmed Quest pinch/return/re-engage session."""
import gzip
import json
from collections import Counter
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))
from g1_bimanual_limits import JOINT_VELOCITY_LIMITS_RAD_S, JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation
from g1_bimanual_unity_sim import UnityCycle, decode
from backend.tests.bimanual_replay_profiles import (
    RECORDED_ACCELERATION_RAD_S2, historical_recording_profile)

FIXTURE = ROOT / "backend/tests/fixtures/bimanual_quest_reengage_20260918.json.gz"


def rows():
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


class QuestReengageReplayTests(unittest.TestCase):
    def test_fixture_scope_and_provenance(self):
        data = rows()
        self.assertEqual(data[0]["kind"], "run")
        self.assertEqual(data[0]["motion_policy"], "bimanual_motion_v1")
        self.assertEqual(data[0]["boundary_policy"], "bimanual_boundary_v1")
        self.assertEqual(data[0]["return_policy"], "bimanual_staged_return_v1")
        self.assertEqual(data[0]["mujoco_version"], "3.12.0")
        kinds = Counter(row["kind"] for row in data)
        self.assertEqual(kinds, {"run": 1, "input": 2016, "state": 2927})
        states = [row for row in data if row["kind"] == "state"]
        transitions = []
        previous = None
        for row in states:
            key = (row["state"], row["reason"])
            if key != previous:
                transitions.append(key)
                previous = key
        self.assertEqual(transitions, [
            ("ready", ""),
            ("tracking", ""),
            ("returning", "pinch"),
            ("ready", "pinch"),
            ("tracking", ""),
            ("returning", "pinch"),
            ("ready", "pinch"),
        ])

        accepted = []
        for row in data:
            if row["kind"] == "input" and row.get("accepted"):
                accepted.append(json.loads(row["raw_json_text"]))
        engage_edges = [(p["sequence"], p["engage"], p["return_home"])
                        for p in accepted]
        self.assertIn((457, True, False), engage_edges)
        self.assertIn((1786, False, True), engage_edges)
        self.assertIn((2119, True, False), engage_edges)
        self.assertIn((2215, False, True), engage_edges)

    def test_replay_matches_logged_joint_path_and_two_returns(self):
        with historical_recording_profile() as sim:
            self._replay(sim, exact_recording=True)

    def test_current_profile_preserves_two_cycles_and_bounds(self):
        sim = BimanualSimulation()
        np.testing.assert_array_equal(sim.caps, np.asarray(JOINT_VELOCITY_LIMITS_RAD_S))
        self._replay(sim, exact_recording=False)

    def _replay(self, sim, *, exact_recording):
        data = rows()
        cycle = UnityCycle(sim)
        acceleration_limit = (RECORDED_ACCELERATION_RAD_S2 if exact_recording
                              else JOINT_ACCELERATION_LIMIT_RAD_S2)
        frozen = np.ones(sim.model.nq, dtype=bool)
        frozen[sim.qids] = False
        state_changes = []
        previous_state = None
        minimum_clearance = .2
        maximum_q_error = 0.0
        maximum_acceleration = 0.0
        for row in data[1:]:
            if row["kind"] == "input":
                packet = decode(row["raw_json_text"].encode("utf-8"))
                accepted = cycle.receive(packet, row["receive_monotonic_s"])
                self.assertEqual(accepted, row["accepted"])
                continue
            if row["kind"] != "state":
                continue

            previous_velocity = sim.velocity[sim.dofs].copy()
            previous_q = sim.config.q[sim.qids].copy()
            cycle.tick(row["monotonic_s"])
            if exact_recording:
                self.assertEqual(cycle.state, row["state"])
                self.assertEqual(cycle.reason, row["reason"])
            logged_q = np.asarray(row["q_rad"], dtype=float)
            actual_q = sim.config.q[sim.qids]
            maximum_q_error = max(maximum_q_error,
                                  float(np.max(np.abs(actual_q - logged_q))))
            if exact_recording:
                np.testing.assert_allclose(actual_q, logged_q, atol=5e-6, rtol=0)
            np.testing.assert_allclose((actual_q - previous_q) / sim.dt,
                                       sim.velocity[sim.dofs], atol=1e-10, rtol=0)
            self.assertTrue(np.all(np.abs(sim.velocity[sim.dofs]) <= sim.caps + 1e-6))
            self.assertTrue(np.all(actual_q >= sim.ranges[:, 0] - 1e-8))
            self.assertTrue(np.all(actual_q <= sim.ranges[:, 1] + 1e-8))
            np.testing.assert_array_equal(sim.config.q[frozen], sim.home[frozen])
            acceleration = np.max(np.abs(sim.velocity[sim.dofs] - previous_velocity)) / sim.dt
            maximum_acceleration = max(maximum_acceleration, float(acceleration))
            self.assertLessEqual(acceleration, acceleration_limit + 1e-4)
            clearance = sim.clearance(sim.config.q)
            self.assertTrue(np.isfinite(clearance))
            minimum_clearance = min(minimum_clearance, clearance)
            self.assertGreaterEqual(minimum_clearance, sim.clearance_m)

            key = (cycle.state, cycle.reason)
            if key != previous_state:
                state_changes.append(key)
                previous_state = key

        self.assertEqual(state_changes.count(("tracking", "")), 2)
        self.assertEqual(state_changes.count(("returning", "pinch")), 2)
        self.assertEqual(state_changes.count(("ready", "pinch")), 2)
        self.assertEqual(cycle.state, "ready")
        self.assertEqual(sim.return_motion.stage, "complete")
        self.assertEqual(sim.return_motion.replans, 0)
        self.assertEqual(np.max(np.abs(sim.velocity)), 0.0)
        np.testing.assert_allclose(sim.config.q[sim.qids], sim.home[sim.qids],
                                   atol=1e-6, rtol=0)
        result = {
            "exact_recording": exact_recording,
            "state_ticks": sum(row["kind"] == "state" for row in data),
            "input_rows": sum(row["kind"] == "input" for row in data),
            "transitions": state_changes,
            "minimum_clearance_mm": minimum_clearance * 1000.0,
            "max_output_acceleration_deg_s2": float(np.rad2deg(maximum_acceleration)),
            "maximum_logged_q_difference_rad": maximum_q_error,
        }
        print("QUEST_REENGAGE_REPLAY", json.dumps(result), flush=True)


if __name__ == "__main__":
    unittest.main()
