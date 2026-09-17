from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from g1_mink_trajectory import StatefulMinkTrajectory  # noqa: E402


class MinkStatefulTrajectoryTest(unittest.TestCase):
    def Build(self, check=True):
        planner = Mock()
        planner.CheckConfiguration.return_value = check
        trajectory = StatefulMinkTrajectory(
            planner,
            range(7),
            [0.08] * 7,
            [0.16] * 7,
            [0.64] * 7,
            0.01,
        )
        return planner, trajectory

    def test_step_respects_velocity_acceleration_and_jerk_limits(self):
        _, trajectory = self.Build()
        q = np.zeros(7)
        target = np.ones(7)
        velocities = []
        accelerations = []
        for _ in range(300):
            step = trajectory.Step(q, target)
            self.assertTrue(step.applied)
            q = step.q
            velocities.append(np.asarray(step.velocity_rad_s))
            accelerations.append(np.asarray(step.acceleration_rad_s2))
        self.assertLessEqual(max(np.max(np.abs(v)) for v in velocities), 0.08 + 1e-9)
        self.assertLessEqual(
            max(np.max(np.abs(a)) for a in accelerations), 0.16 + 1e-9
        )
        jerks = [
            np.max(np.abs(accelerations[i] - accelerations[i - 1])) / 0.01
            for i in range(1, len(accelerations))
        ]
        self.assertLessEqual(max(jerks), 0.64 + 1e-7)

    def test_collision_rejection_holds_and_resets_motion_state(self):
        planner, trajectory = self.Build()
        q = np.zeros(7)
        target = np.ones(7)
        first = trajectory.Step(q, target)
        self.assertTrue(first.applied)
        planner.CheckConfiguration.return_value = False
        blocked = trajectory.Step(first.q, target)
        self.assertFalse(blocked.applied)
        self.assertEqual("trajectory_collision_hold", blocked.status)
        np.testing.assert_array_equal(blocked.q, first.q)
        self.assertEqual((0.0,) * 7, blocked.velocity_rad_s)

    def test_external_pose_change_rebases_without_a_jump(self):
        _, trajectory = self.Build()
        q = np.zeros(7)
        trajectory.Step(q, np.ones(7))
        external = np.full(7, 0.25)
        step = trajectory.Step(external, external)
        self.assertTrue(step.applied)
        np.testing.assert_allclose(step.q, external, atol=1e-12)
        self.assertLessEqual(max(abs(value) for value in step.velocity_rad_s), 1e-12)


if __name__ == "__main__":
    unittest.main()
