"""Offline candidate checks; no robot or socket."""
import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_mink_trajectory import ThroughTrajectory
from g1_mink_trajectory import StatefulMinkTrajectory
from g1_virtual_center_tasks import (
    JOINT_MAX_ACCELERATION_RAD_S2,
    JOINT_TRACKING_MAX_JERK_RAD_S3,
)
import run_mink_g1_right_arm_prototype as base


def test_live_tracking_reaches_acceleration_limit_within_one_control_tick():
    assert JOINT_TRACKING_MAX_JERK_RAD_S3 * base.DT >= JOINT_MAX_ACCELERATION_RAD_S2


def test_forward_then_wrist_keeps_requested_position_fixed():
    from compare_mink_trajectory import ForwardWristGoal
    np.testing.assert_array_equal(ForwardWristGoal(0)[0], [0, 0, 0])
    for t in (5, 19, 20, 25, 30, 40):
        np.testing.assert_allclose(ForwardWristGoal(t)[0], [.04, 0, 0], atol=1e-15)
    assert ForwardWristGoal(20)[1] == 0
    assert ForwardWristGoal(25)[1] > 0
    assert abs(ForwardWristGoal(40)[1] - np.deg2rad(35)) < 1e-15


def test_candidate_bounds_and_stop_without_changing_baseline():
    speeds = []
    for cls in (StatefulMinkTrajectory, ThroughTrajectory):
        planner = Mock()
        planner.CheckConfiguration.return_value = True
        trajectory = cls(planner, range(7), [.16]*7, [.32]*7, [1.28]*7, 1/60)
        q = np.zeros(7)
        velocity, acceleration = [], []
        for i in range(600):
            if i < 300:
                target = q + .008
            step = trajectory.Step(q, target)
            q = step.q
            velocity.append(step.velocity_rad_s)
            acceleration.append(step.acceleration_rad_s2)
        assert np.max(np.abs(velocity)) <= .16 + 1e-9
        assert np.max(np.abs(acceleration)) <= .32 + 1e-9
        assert np.max(np.abs(np.diff(acceleration, axis=0))) * 60 <= 1.28 + 1e-7
        assert np.max(np.abs(q-target)) < 1e-4
        assert np.max(np.abs(velocity[-1])) < 1e-4
        speeds.append(float(np.median(np.asarray(velocity)[120:290,0])))
        planner.CheckConfiguration.return_value = False
        stopped = trajectory.Step(q, q+.01)
        np.testing.assert_array_equal(stopped.q, q)
        assert not stopped.applied
    # Comparison is allowed to reject the candidate; speedup is not guaranteed.
    assert abs(speeds[0] - .041520372059) < 1e-8
    assert np.isfinite(speeds[1]) and speeds[1] > 0


def test_candidate_rejects_nonfinite():
    import pytest
    trajectory = ThroughTrajectory(Mock(), range(7), [.16]*7, [.32]*7, [1.28]*7, 1/60)
    with pytest.raises(ValueError):
        trajectory.Step(np.zeros(7), np.full(7, np.nan))
