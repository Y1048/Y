#!/usr/bin/env python3

import math
import unittest

from safety_gate import SafetyConfig, evaluate_target


class SafetyGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.measured = [
            math.radians(10.0),
            math.radians(-22.0),
            0.0,
            math.radians(55.0),
            0.0,
            0.0,
            0.0,
        ]

    def test_hold_target_is_allowed(self) -> None:
        decision = evaluate_target(
            self.measured,
            self.measured,
            None,
            lowstate_age_s=0.01,
            dt_s=0.01,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "ok")
        self.assertFalse(decision.rate_limited)
        self.assertEqual(tuple(self.measured), decision.command_q_rad)

    def test_stale_lowstate_is_denied(self) -> None:
        decision = evaluate_target(
            self.measured,
            self.measured,
            None,
            lowstate_age_s=0.30,
            dt_s=0.01,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "lowstate_stale")
        self.assertIsNone(decision.command_q_rad)

    def test_large_target_jump_is_denied(self) -> None:
        target = list(self.measured)
        target[0] += math.radians(20.0)
        decision = evaluate_target(
            self.measured,
            target,
            None,
            lowstate_age_s=0.01,
            dt_s=0.01,
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.reason.startswith("target_error:"))
        self.assertIsNone(decision.command_q_rad)

    def test_non_finite_target_is_denied(self) -> None:
        target = list(self.measured)
        target[3] = float("nan")
        decision = evaluate_target(
            self.measured,
            target,
            None,
            lowstate_age_s=0.01,
            dt_s=0.01,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("non-finite", decision.reason)

    def test_operational_elbow_limit_is_enforced(self) -> None:
        measured = list(self.measured)
        measured[3] = math.radians(3.0)
        decision = evaluate_target(
            measured,
            measured,
            None,
            lowstate_age_s=0.01,
            dt_s=0.01,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("right_elbow", decision.reason)

    def test_velocity_is_rate_limited(self) -> None:
        config = SafetyConfig(
            max_target_error_rad=math.radians(10.0),
            max_command_velocity_rad_s=math.radians(15.0),
        )
        target = list(self.measured)
        target[0] += math.radians(5.0)
        decision = evaluate_target(
            self.measured,
            target,
            self.measured,
            lowstate_age_s=0.01,
            dt_s=0.10,
            config=config,
        )
        self.assertTrue(decision.allowed)
        self.assertTrue(decision.rate_limited)
        self.assertAlmostEqual(
            decision.command_q_rad[0] - self.measured[0],
            math.radians(1.5),
            places=7,
        )

    def test_requested_joint_limit_is_denied(self) -> None:
        target = list(self.measured)
        target[5] = math.radians(92.0)
        decision = evaluate_target(
            self.measured,
            target,
            None,
            lowstate_age_s=0.01,
            dt_s=0.01,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("right_wrist_pitch", decision.reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
