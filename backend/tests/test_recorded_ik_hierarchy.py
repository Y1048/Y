"""Normalization and short offline comparison checks."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_recorded_ik_hierarchy import GetNormalizedGoal, RunComparison, probe, UseOfflineProximalCost, task_policy, SummarizeTargetEvents


def test_goal_rebase_preserves_delta_and_neutral():
    reference = probe.base._matrix_to_se3(np.eye(3), np.array([1., 2., 3.]))
    center = np.array([.1, -.2, .8])
    neutral = GetNormalizedGoal(reference, reference, center, np.eye(3))
    np.testing.assert_allclose(neutral.translation(), center)
    rotation = probe.mink.SO3.from_z_radians(.2).as_matrix()
    target = probe.base._matrix_to_se3(rotation, np.array([1.1, 2.2, 3.3]))
    normalized = GetNormalizedGoal(reference, target, center, np.eye(3))
    np.testing.assert_allclose(normalized.translation(), center + [.1, .2, .3])
    np.testing.assert_allclose(normalized.rotation().as_matrix(), rotation)


@pytest.mark.parametrize("step", [.01, .5, 2.8])
def test_fixed_basis_and_clutch_preserve_rotation_step(step):
    from scipy.spatial.transform import Rotation

    source = Rotation.from_euler("xyz", [[.3, -.2, .7], [-.1, .4, -.6]])
    first = source[0]
    second = Rotation.from_rotvec(np.array([1., 2., -1.]) / np.sqrt(6) * step) * first
    convert = probe.base.g1.operator_rotation_to_robot_matrix
    reference = convert(source[1].as_quat())
    neutral = Rotation.from_euler("xyz", [.6, -.4, .2]).as_matrix()
    targets = [convert(value.as_quat()) @ reference.T @ neutral
               for value in (first, second)]
    actual = Rotation.from_matrix(targets[1] @ targets[0].T).magnitude()
    assert actual == pytest.approx(step, abs=1e-12)


def test_operator_quaternion_sign_does_not_change_target():
    quaternion = np.array([.2, -.3, .4, .7])
    convert = probe.base.g1.operator_rotation_to_robot_matrix
    np.testing.assert_allclose(convert(quaternion), convert(-quaternion), atol=1e-12)


def test_qp_summary_includes_small_rotation_errors():
    from compare_recorded_ik_hierarchy import SummarizeQP

    row = dict(primary_saturated=[False] * 7, final_saturated=[False] * 7,
               rotation_error_deg=10., constrained_predicted_error_deg=9.,
               shadow_predicted_error_deg=8.)
    summary = SummarizeQP([row])
    assert summary["rotation_over_30_deg_frames"] == 0
    assert summary["all_shadow_frames"] == 1
    assert summary["all_shadow_improves_fraction"] == 1
    assert summary["all_shadow_advantage_deg_p50_p95"] == [1., 1.]


def test_short_stationary_comparison():
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    target = probe.base._matrix_to_se3(np.eye(3), np.zeros(3))
    for mode in ("single_weighted_qp", "hierarchy"):
        result = RunComparison(model, q, [target], np.array([0.]), mode, .05, "mink-default")
        assert result["position_final_mm"] < 1e-6
        assert result["rotation_final_deg"] < 1e-4
        assert result["clearance_violating_frames"] == 0


def test_replay_speed_changes_duration_not_goal():
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    target = probe.base._matrix_to_se3(np.eye(3), np.zeros(3))
    for speed in (1., .5, .25):
        result = RunComparison(model, q, [target, target], np.array([0., .1]),
                               "hierarchy", .05, "mink-default", speed)
        assert result["motion_duration_s"] == pytest.approx(.1 / speed)
        assert result["frames"] == np.ceil((.1 / speed + .05) / probe.base.DT)
        assert result["position_final_mm"] < 1e-6
        assert result["motion_saturated_frame_fraction"] == 0


@pytest.mark.parametrize("speed", [0., -1., float("nan"), float("inf")])
def test_invalid_replay_speed(speed):
    with pytest.raises(ValueError, match="playback_speed"):
        RunComparison(None, None, None, None, "hierarchy", 5., "mink-default", speed)


def test_offline_cost_override_is_restored_after_failure():
    original = task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX
    with pytest.raises(RuntimeError):
        with UseOfflineProximalCost(1.0):
            assert task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX == 1.0
            raise RuntimeError("trial failed")
    assert task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX == original


def test_qp_observer_does_not_change_applied_result():
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    targets = [probe.base._matrix_to_se3(np.eye(3), np.zeros(3)),
               probe.base._matrix_to_se3(probe.mink.SO3.from_z_radians(.2).as_matrix(), np.array([.01, .005, 0.]))]
    solve = probe.mink.solve_ik
    targets.append(targets[-1])
    times = np.array([0., .05, .1])
    plain = RunComparison(model, q, targets, times, "hierarchy", .1, "mink-default")
    traced = RunComparison(model, q, targets, times, "hierarchy", .1, "mink-default", diagnose_qp=True)
    assert probe.mink.solve_ik is solve
    assert traced["qp_diagnostic"]["first_pair_frames"] > 0
    assert sum(plain["joint_total_travel_deg"]) > 0
    for key in plain:
        if key not in ("qp_diagnostic", "compute_p95_ms"):
            assert plain[key] == traced[key]


@pytest.mark.parametrize("cost", [0., -1., float("nan"), float("inf")])
def test_invalid_offline_cost(cost):
    with pytest.raises(ValueError, match="proximal cost"):
        with UseOfflineProximalCost(cost):
            pytest.fail("invalid cost was accepted")


def test_event_summary_respects_threshold_and_window():
    trace = [{"time_s": t, "moving": True, "target_step_deg": step, "error_deg": error}
             for t, step, error in [(0, 0, 2), (1, 5, 7), (2, 0, 9), (3.1, 0, 12)]]
    summary = SummarizeTargetEvents(trace)
    assert len(summary["events"]) == 1
    assert summary["events"][0]["error_before_deg"] == 2
    assert summary["events"][0]["next_2s_max_error_deg"] == 9
    assert summary["outside_event_window_frames"] == 2
    assert summary["peak_error_frame"]["time_s"] == 3.1


def test_single_qp_backtrack_preserves_guards_and_uses_checked_duration():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from compare_recorded_ik_hierarchy import ApplySingleQPStep
    q = np.zeros(2)
    configuration = SimpleNamespace(q=q.copy(), update=Mock(), integrate_inplace=Mock())
    planner = SimpleNamespace(right_dofs=[0, 1], _VelocityValid=Mock(return_value=True),
                              _PathClear=Mock(side_effect=[False, True]))
    _, status = ApplySingleQPStep(planner, configuration, q, np.ones(2), True)
    assert status == "single_qp_reduced_step"
    assert planner._PathClear.call_args.args[2] == probe.base.DT * .5
    configuration.integrate_inplace.assert_called_once()
    assert configuration.integrate_inplace.call_args.args[1] == probe.base.DT * .5
    planner._VelocityValid.return_value = False
    configuration.integrate_inplace.reset_mock()
    planner._PathClear.reset_mock()
    candidate, status = ApplySingleQPStep(planner, configuration, q, np.ones(2), True)
    assert status == "guard_rejected"
    np.testing.assert_array_equal(candidate, q)
    planner._PathClear.assert_not_called()
    configuration.integrate_inplace.assert_not_called()


def test_single_qp_all_rejected_does_not_integrate():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from compare_recorded_ik_hierarchy import ApplySingleQPStep
    q = np.zeros(2)
    configuration = SimpleNamespace(integrate_inplace=Mock())
    planner = SimpleNamespace(right_dofs=[0, 1], _VelocityValid=Mock(return_value=True),
                              _PathClear=Mock(return_value=False))
    for enabled, count in ((False, 1), (True, 6)):
        planner._PathClear.reset_mock()
        candidate, status = ApplySingleQPStep(planner, configuration, q, q, enabled)
        assert status == "guard_rejected"
        assert planner._PathClear.call_count == count
        np.testing.assert_array_equal(candidate, q)
    configuration.integrate_inplace.assert_not_called()
