#!/usr/bin/env python3
"""Offline path and derivative tests for the Ruckig joint limiter."""

from __future__ import annotations

import math
import unittest

from ruckig_joint_motion_limiter import RuckigJointMotionLimiter


class RuckigJointMotionLimiterTests(unittest.TestCase):
    def _run(self, targets):
        dt_s = 0.004
        velocity_limit = math.radians(40.0)
        acceleration_limit = math.radians(80.0)
        jerk_limit = math.radians(320.0)
        limiter = RuckigJointMotionLimiter(
            [0.0],
            [velocity_limit],
            [acceleration_limit],
            [jerk_limit],
            dt_s,
        )
        positions = [0.0]
        for target in targets:
            positions.append(limiter.Step([target], dt_s)[0])
        velocities = [
            (current - previous) / dt_s
            for previous, current in zip(positions, positions[1:])
        ]
        accelerations = [
            (current - previous) / dt_s
            for previous, current in zip(velocities, velocities[1:])
        ]
        jerks = [
            (current - previous) / dt_s
            for previous, current in zip(accelerations, accelerations[1:])
        ]
        self.assertLessEqual(max(map(abs, velocities)), velocity_limit + 1.0e-7)
        self.assertLessEqual(max(map(abs, accelerations)), acceleration_limit + 1.0e-6)
        self.assertLessEqual(max(map(abs, jerks)), jerk_limit + 1.0e-4)
        return limiter, positions

    def test_step_target_converges_without_overshoot(self):
        target = math.radians(30.0)
        limiter, positions = self._run([target] * 1000)
        self.assertAlmostEqual(target, limiter.q_rad[0], delta=math.radians(0.01))
        self.assertLessEqual(max(positions), target + math.radians(0.01))

    def test_direction_reversal_stays_between_targets(self):
        positive = math.radians(25.0)
        negative = math.radians(-20.0)
        limiter, positions = self._run([positive] * 1000 + [negative] * 1500)
        self.assertAlmostEqual(negative, limiter.q_rad[0], delta=math.radians(0.01))
        self.assertLessEqual(max(positions), positive + math.radians(0.01))
        self.assertGreaterEqual(min(positions), negative - math.radians(0.01))

    def test_variable_control_period_preserves_finite_state(self):
        limiter = RuckigJointMotionLimiter(
            [0.0],
            [math.radians(40.0)],
            [math.radians(80.0)],
            [math.radians(320.0)],
            0.004,
        )
        target = math.radians(15.0)
        for dt_s in (0.004, 0.0042, 0.0038, 0.0041) * 100:
            limiter.Step([target], dt_s)
        self.assertTrue(all(math.isfinite(value) for value in limiter.q_rad))
        self.assertLessEqual(limiter.q_rad[0], target + math.radians(0.01))


if __name__ == "__main__":
    unittest.main()
