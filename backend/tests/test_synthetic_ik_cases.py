import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_synthetic_ik import BuildCases


def test_path_observer_preserves_decision_and_records_joint_rejection():
    from compare_synthetic_ik import ObservePathChecks, comparison, probe
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    plain = comparison.BuildPlanner(model, q, collision_profile="mink-default")
    factory = comparison.BuildPlanner
    velocity = np.zeros(model.nv)
    velocity[plain.right_dofs[0]] = 10000
    expected = plain._PathClear(q, velocity, probe.base.DT)
    with ObservePathChecks(True) as rows:
        observed = comparison.BuildPlanner(model, q, collision_profile="mink-default")
        assert observed._PathClear(q, velocity, probe.base.DT) == expected == False
        assert rows[0]["joint_violations"]
        assert rows[0]["sample_fraction"] == .25
        np.testing.assert_array_equal(observed.configuration.q, plain.configuration.q)
    assert comparison.BuildPlanner is factory


def test_single_qp_cost_changes_only_proximal_damping_and_restores():
    from types import SimpleNamespace
    from unittest.mock import patch
    import pytest
    from compare_synthetic_ik import UseSingleQPCost, comparison
    task = SimpleNamespace(cost=np.arange(10, dtype=float))
    planner = SimpleNamespace(tasks=[object(), object(), object(), task], proximal_dofs=[2, 3, 4, 5])
    original = task.cost.copy()
    with patch.object(comparison, "BuildPlanner", return_value=planner) as factory:
        with pytest.raises(RuntimeError):
            with UseSingleQPCost(.3):
                result = comparison.BuildPlanner(None)
                np.testing.assert_array_equal(result.tasks[3].cost[[2, 3, 4, 5]], [.3] * 4)
                np.testing.assert_array_equal(result.tasks[3].cost[[0, 1, 6, 7, 8, 9]], original[[0, 1, 6, 7, 8, 9]])
                raise RuntimeError("test")
        assert comparison.BuildPlanner is factory


def test_single_qp_cost_rejects_nonfinite_or_negative():
    import pytest
    from compare_synthetic_ik import UseSingleQPCost
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            with UseSingleQPCost(value):
                pass


def test_out_of_range_start_is_rejected_before_output(tmp_path):
    import subprocess
    tool = Path(__file__).resolve().parents[1] / "tools" / "compare_synthetic_ik.py"
    output = tmp_path / "invalid.json"
    result = subprocess.run([sys.executable, str(tool), "--initial-arm-deg",
                             "999", "0", "0", "55", "0", "0", "0",
                             "--output", str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "initial angle outside limits" in result.stderr
    assert not output.exists()


def test_wrist_axes_are_distinct_and_positions_stay_fixed():
    for index, axis in enumerate(("x", "y", "z")):
        _, goals = BuildCases(axis)["wrist_only"]
        midpoint = goals[240].rotation().as_matrix()
        vector = np.eye(3)[:, index]
        np.testing.assert_allclose(midpoint @ vector, vector, atol=1e-12)
        assert not np.allclose(midpoint, np.eye(3))
        assert all(np.linalg.norm(goal.translation()) == 0 for goal in goals)


def test_progress_removal_keeps_other_constraints_and_limits():
    from unittest.mock import patch
    from compare_synthetic_ik import UseProgressBand, PositionProgressConstraint, probe
    progress = PositionProgressConstraint(np.eye(3), np.zeros(3))
    frozen = object()
    limit = object()
    with patch.object(probe.mink, "solve_ik", return_value=np.zeros(3)) as solve:
        with UseProgressBand(0., remove_progress=True):
            probe.mink.solve_ik(None, [], constraints=[frozen, progress], limits=[limit])
        assert probe.mink.solve_ik is solve
        assert solve.call_args.kwargs["constraints"] == [frozen]
        assert solve.call_args.kwargs["limits"] == [limit]


def test_invalid_proximal_cost_cli_does_not_write_result(tmp_path):
    import subprocess
    tool = Path(__file__).resolve().parents[1] / "tools" / "compare_synthetic_ik.py"
    output = tmp_path / "result.json"
    result = subprocess.run([sys.executable, str(tool), "--proximal-cost", "nan",
                             "--output", str(output)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "proximal-cost must be finite" in result.stderr
    assert not output.exists()


def test_merit_ablation_changes_only_flag_and_restores_factory():
    from types import SimpleNamespace
    from unittest.mock import patch
    import pytest
    from compare_synthetic_ik import UseMeritAblation, comparison
    limits = object()
    planner = SimpleNamespace(require_merit_decrease=True, limits=limits)
    with patch.object(comparison, "BuildPlanner", return_value=planner) as factory:
        with pytest.raises(RuntimeError):
            with UseMeritAblation(True):
                result = comparison.BuildPlanner(None, None)
                assert result.require_merit_decrease is False
                assert result.limits is limits
                raise RuntimeError("test")
        assert comparison.BuildPlanner is factory


def test_merit_tolerance_dead_zone_and_factory_restore():
    from types import SimpleNamespace
    from unittest.mock import patch
    from compare_synthetic_ik import UseMeritAblation, comparison, probe
    planner = SimpleNamespace(require_merit_decrease=True,
                              GetPositionMerit=lambda error, target=None: probe.base.POSITION_COST ** 2 * error ** 2)
    with patch.object(comparison, "BuildPlanner", return_value=planner) as factory:
        with UseMeritAblation(False, 1.):
            result = comparison.BuildPlanner(None, None)
            assert result.require_merit_decrease
            assert result.GetPositionMerit(.0009) == 0
            assert result.GetPositionMerit(.001) == 0
            np.testing.assert_allclose(result.GetPositionMerit(.002), probe.base.POSITION_COST ** 2 * .001 ** 2)
        assert comparison.BuildPlanner is factory


def test_merit_tolerance_rejects_invalid_and_conflicting_values():
    import pytest
    from compare_synthetic_ik import UseMeritAblation
    for enabled, tolerance in ((False, -1), (False, float("nan")), (False, float("inf")), (True, 1)):
        with pytest.raises(ValueError):
            with UseMeritAblation(enabled, tolerance):
                pass


def test_progress_band_bounds_and_restore():
    import pytest
    from compare_synthetic_ik import ProgressBand, PositionProgressConstraint, UseProgressBand, probe
    progress = PositionProgressConstraint(np.eye(3), np.array([.001, 0, -.001]))
    band = ProgressBand(progress, .0001).compute_qp_inequalities(None, 1 / 60)
    assert np.all(band.G @ np.array([.001, 0, -.001]) <= band.h)
    assert not np.all(band.G @ np.array([.002, 0, -.001]) <= band.h)
    original = probe.mink.solve_ik
    with pytest.raises(RuntimeError):
        with UseProgressBand(.1):
            raise RuntimeError("test")
    assert probe.mink.solve_ik is original
    for value in (-1., float("nan"), float("inf")):
        with pytest.raises(ValueError):
            with UseProgressBand(value):
                pass


def test_target_error_band_limits_residual_and_preserves_primary_recovery():
    from compare_synthetic_ik import TargetErrorBand, PositionProgressConstraint
    error = np.array([.010, .0005, 0.])
    primary = np.array([-.002, -.0001, 0.])
    progress = PositionProgressConstraint(np.eye(3), primary)
    band = TargetErrorBand(progress, error, .001)
    np.testing.assert_allclose(band.bound, [.008, .001, .001])
    constraints = band.compute_qp_inequalities(None, 1 / 60)
    assert np.all(constraints.G @ primary <= constraints.h + 1e-12)
    assert not np.all(constraints.G @ np.zeros(3) <= constraints.h)
    assert not np.all(constraints.G @ np.array([-.002, .002, 0]) <= constraints.h)


def test_cases_are_identical_on_repeat_and_return_to_origin():
    cases = BuildCases()
    repeat = BuildCases()
    assert len(cases) == 4
    for name, (times, goals) in cases.items():
        assert len(times) == len(goals) == 481
        assert np.all(np.diff(times) > 0)
        np.testing.assert_allclose(goals[0].as_matrix(), np.eye(4), atol=1e-12)
        np.testing.assert_allclose(goals[-1].as_matrix(), np.eye(4), atol=1e-12)
        for first, second in zip(goals, repeat[name][1]):
            np.testing.assert_array_equal(first.as_matrix(), second.as_matrix())


def test_wrist_only_has_zero_translation_and_reversal_changes_sign():
    cases = BuildCases()
    assert all(np.linalg.norm(goal.translation()) == 0 for goal in cases["wrist_only"][1])
    goals = cases["reversal_step"][1]
    assert goals[120].translation()[0] > 0
    assert goals[240].translation()[0] < 0
