"""Deterministic near-hands threshold sweep around the recorded Quest posture."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller/scripts"))
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2, JOINT_VELOCITY_LIMIT_RAD_S
from g1_bimanual_sim import BimanualSimulation

FIXTURE = ROOT / "backend/tests/fixtures/bimanual_return_near_hands_20260918.json"
SEED = 20260920


class TriggerDecisionReached(Exception):
    pass


def fixture_q14():
    return np.asarray(json.loads(FIXTURE.read_text())["q14"], dtype=float)


def full_q(sim, q14):
    q = sim.home.copy()
    q[sim.qids] = q14
    return q


def find_threshold_fraction(sim, start14):
    policy = sim.return_motion
    home14 = sim.home[sim.qids]
    threshold = policy.near_hands_threshold_m

    def clearance(t):
        return policy._inter_arm_clearance(
            full_q(sim, start14 + t * (home14 - start14)))

    low_value, high_value = clearance(0.0), clearance(1.0)
    if not low_value < threshold < high_value:
        raise AssertionError(
            f"fixture/home do not bracket 12mm: {low_value}, {high_value}")
    low, high = 0.0, 1.0
    for _ in range(50):
        middle = (low + high) / 2
        if clearance(middle) < threshold:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def find_safe_lower_fraction(sim, start14, threshold_fraction):
    home14 = sim.home[sim.qids]
    # Walk backward from the 12 mm boundary until the hard 5 mm envelope is
    # crossed, then bisect that local crossing. The recorded fixture and the
    # boundary are both safe, but the direct interpolation between them is not
    # globally collision-free.
    high = threshold_fraction
    high_clearance = sim.clearance(
        full_q(sim, start14 + high * (home14 - start14)))
    if high_clearance < sim.clearance_m:
        raise AssertionError("12 mm boundary is below hard clearance")
    low = high
    while low > 0:
        candidate = max(0.0, low - 0.005)
        clearance = sim.clearance(
            full_q(sim, start14 + candidate * (home14 - start14)))
        if clearance < sim.clearance_m:
            low = candidate
            break
        low = candidate
    else:
        raise AssertionError("no lower hard-clearance crossing found")
    for _ in range(45):
        middle = (low + high) / 2
        clearance = sim.clearance(
            full_q(sim, start14 + middle * (home14 - start14)))
        if clearance < sim.clearance_m:
            low = middle
        else:
            high = middle
    return high


def set_pose(sim, q14):
    q = full_q(sim, q14)
    sim.config.update(q)
    sim.state = "ready"
    sim.reason = ""
    sim.velocity[:] = 0.0
    sim.acceleration[:] = 0.0
    sim.brake_plan = []
    sim._motion_returning = False
    sim.return_motion.reset()
    return q


def trigger_only(sim, q14):
    q = set_pose(sim, q14)
    start_clearance = sim.clearance(q)
    inter_arm = sim.return_motion._inter_arm_clearance(q)
    if start_clearance < sim.clearance_m:
        return None

    def stop_before_motion():
        raise TriggerDecisionReached

    with patch.object(sim.return_motion, "_begin_separation", return_value=True),             patch.object(sim.return_motion, "_make_limiter",
                         side_effect=stop_before_motion):
        try:
            sim.return_motion.step()
        except TriggerDecisionReached:
            pass
    return dict(
        global_clearance=start_clearance,
        inter_arm=inter_arm,
        triggered=sim.return_motion.near_hands_recovery,
        expected=inter_arm < sim.return_motion.near_hands_threshold_m)


def representative_return(sim, q14):
    set_pose(sim, q14)
    minimum = sim.clearance(sim.config.q)
    max_acceleration = 0.0
    stages = []
    for tick in range(900):
        previous_velocity = sim.velocity[sim.dofs].copy()
        applied = sim.step(returning=True)
        acceleration = np.max(
            np.abs(sim.velocity[sim.dofs] - previous_velocity)) / sim.dt
        max_acceleration = max(max_acceleration, float(acceleration))
        minimum = min(minimum, sim.clearance(sim.config.q))
        if not stages or stages[-1] != sim.return_motion.stage:
            stages.append(sim.return_motion.stage)
        if sim.state == "blocked":
            break
        if sim.state == "ready" and sim.return_motion.stage == "complete":
            break
        if not applied and sim.state != "blocked":
            raise AssertionError("return stopped without fail-closed state")

    if sim.state not in ("ready", "blocked"):
        raise AssertionError("representative return did not terminate")
    if minimum < sim.clearance_m - 1e-8:
        raise AssertionError(f"clearance violation: {minimum}")
    if max_acceleration > JOINT_ACCELERATION_LIMIT_RAD_S2 + 1e-5:
        raise AssertionError(
            f"acceleration violation: {np.rad2deg(max_acceleration)}")
    if np.any(sim.config.q[sim.qids] < sim.ranges[:, 0] - 1e-8):
        raise AssertionError("joint lower range violation")
    if np.any(sim.config.q[sim.qids] > sim.ranges[:, 1] + 1e-8):
        raise AssertionError("joint upper range violation")
    if sim.state == "blocked" and np.any(sim.velocity):
        raise AssertionError("BLOCKED return retained output velocity")
    return dict(
        final_state=sim.state,
        reason=sim.reason,
        stages=stages,
        minimum_clearance_mm=minimum * 1000.0,
        max_acceleration_deg_s2=float(np.rad2deg(max_acceleration)),
        ticks=tick + 1)


class NearHandsSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = BimanualSimulation()
        cls.start14 = fixture_q14()
        cls.boundary = find_threshold_fraction(cls.sim, cls.start14)
        cls.safe_lower = find_safe_lower_fraction(
            cls.sim, cls.start14, cls.boundary)

    def test_threshold_trigger_classification_320_safe_samples(self):
        sim = self.sim
        rng = np.random.default_rng(SEED)
        home14 = sim.home[sim.qids]
        checked = []

        # Deliberately balance the two sides of the 12 mm trigger. The near side
        # is sampled only inside the locally hard-clearance-safe interval.
        for expected_near in (True, False):
            accepted = 0
            attempts = 0
            while accepted < 160 and attempts < 4000:
                attempts += 1
                if expected_near:
                    lower = self.safe_lower + 2e-5
                    upper = self.boundary - 2e-6
                else:
                    lower = self.boundary + 2e-6
                    upper = min(1.0, self.boundary + 0.12)
                t = float(rng.uniform(lower, upper))
                q14 = self.start14 + t * (home14 - self.start14)
                q14 += rng.normal(0.0, np.deg2rad(0.02), 14)
                q14 = np.clip(q14, sim.ranges[:, 0], sim.ranges[:, 1])
                result = trigger_only(sim, q14)
                if result is None or result["expected"] != expected_near:
                    continue
                self.assertEqual(
                    result["triggered"], result["expected"],
                    msg=json.dumps(result))
                self.assertGreaterEqual(
                    result["global_clearance"], sim.clearance_m)
                checked.append(result)
                accepted += 1
            self.assertEqual(accepted, 160)

        self.assertEqual(len(checked), 320)
        near = sum(row["expected"] for row in checked)
        ordinary = len(checked) - near
        self.assertEqual((near, ordinary), (160, 160))
        nearest_margin = min(
            abs(row["inter_arm"] -
                sim.return_motion.near_hands_threshold_m)
            for row in checked)
        self.assertLess(nearest_margin, 0.0001)
        print("NEAR_HANDS_SWEEP", json.dumps(dict(
            seed=SEED,
            safe_samples=len(checked),
            near_samples=near,
            ordinary_samples=ordinary,
            threshold_fraction=self.boundary,
            safe_lower_fraction=self.safe_lower,
            closest_threshold_margin_mm=nearest_margin * 1000.0,
            minimum_global_clearance_mm=min(
                row["global_clearance"] for row in checked) * 1000.0,
        )), flush=True)

    def test_representative_boundary_returns_preserve_limits(self):
        sim = self.sim
        home14 = sim.home[sim.qids]
        near_span = self.boundary - self.safe_lower
        fractions = [
            self.safe_lower + near_span * 0.30,
            self.safe_lower + near_span * 0.75,
            self.boundary + 0.015,
            self.boundary + 0.050,
        ]
        results = []
        for t in fractions:
            q14 = self.start14 + t * (home14 - self.start14)
            q = full_q(sim, q14)
            self.assertGreaterEqual(sim.clearance(q), sim.clearance_m)
            before_inter = sim.return_motion._inter_arm_clearance(q)
            result = representative_return(sim, q14)
            result["start_inter_arm_mm"] = before_inter * 1000.0
            result["expected_near_hands"] = (
                before_inter < sim.return_motion.near_hands_threshold_m)
            results.append(result)

        self.assertEqual(len(results), 4)
        self.assertTrue(any(row["expected_near_hands"] for row in results))
        self.assertTrue(any(not row["expected_near_hands"] for row in results))
        self.assertTrue(all(
            row["minimum_clearance_mm"] >= sim.clearance_m * 1000.0 - 1e-5
            for row in results))
        self.assertTrue(all(
            row["max_acceleration_deg_s2"] <= np.rad2deg(JOINT_ACCELERATION_LIMIT_RAD_S2) + .001
            for row in results))
        print("NEAR_HANDS_BOUNDARY_RETURNS",
              json.dumps(results), flush=True)


if __name__ == "__main__":
    unittest.main()
