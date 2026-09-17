"""Offline comparison contract; no viewer, network or robot output."""

from pathlib import Path
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from view_ik_comparison import Comparison, CASES, probe, HandleComparisonKey, glfw
from unittest.mock import Mock, patch
from view_ik_comparison import RecordedPlayback, NextPlaybackSpeed
from view_ik_comparison import GetCompositeGoal


def test_composite_goals_are_closed_multiaxis_pose_paths():
    for case in range(6, 10):
        samples = [GetCompositeGoal(case, t) for t in np.linspace(0, 20, 81)]
        positions = np.array([p for p, _ in samples])
        for index in (0, -1):
            np.testing.assert_allclose(samples[index][0], 0, atol=1e-12)
            np.testing.assert_allclose(samples[index][1], np.eye(3), atol=1e-12)
        if case < 9:
            assert (np.ptp(positions, axis=0) > .04).all()
        else:
            np.testing.assert_array_equal(positions, np.zeros_like(positions))
        assert max(np.linalg.norm(r - np.eye(3)) for _, r in samples) > .2
        for _, rotation in samples:
            np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
            assert np.linalg.det(rotation) > .999999


def test_invalid_standard_velocity_holds_pose_without_hiding_failure():
    from types import SimpleNamespace
    model = probe.base.LoadMinkModel()
    probe.base._apply_operational_joint_limits(model)
    run = Comparison(model, "mink-default")
    initial = run.q[1].copy()
    for magnitude in (float("nan"), 100.):
        velocity = np.zeros(model.nv)
        velocity[run.planner.right_dofs[0]] = magnitude
        with patch.object(run.planner, "Plan", return_value=SimpleNamespace(next_q=initial, status="fixture")), \
             patch.object(probe.mink, "solve_ik", return_value=velocity):
            run.Step(8)
        np.testing.assert_array_equal(run.q[1], initial)
        assert run.rows[1]["status"].startswith("REJECTED")
    assert run.rows[1]["rejected_steps"] == 2


def test_playback_speed_preserves_fixed_steps_and_pause():
    from types import SimpleNamespace
    simulation = SimpleNamespace(model=None, q=np.zeros((2, 1)), goal=None,
                                 Step=Mock(), Reset=Mock())
    playback = RecordedPlayback(simulation, 1)
    playback.frames = [(np.array([[i], [i]]), None, [], i * probe.base.DT) for i in range(20)]
    playback.Reset()
    playback.Advance(probe.base.DT, 4, False)
    assert playback.seconds == 4 * probe.base.DT
    playback.Advance(1, 8, True)
    assert playback.seconds == 4 * probe.base.DT
    playback.Advance(100, 8, False)
    assert playback.seconds == 19 * probe.base.DT
    simulation.Step.assert_not_called()
    assert NextPlaybackSpeed(4) == 8
    assert NextPlaybackSpeed(8) == .25


def test_comparison_keys_do_not_use_mujoco_shortcuts():
    simulation = Mock()
    state = (0, 0, False)
    for key in (49, 50, 78, 82, 32, glfw.KEY_ESCAPE):
        assert HandleComparisonKey(key, simulation, *state) == state
    simulation.Reset.assert_not_called()
    state = HandleComparisonKey(glfw.KEY_F12, simulation, *state)
    assert state == (0, 0, True)
    state = HandleComparisonKey(glfw.KEY_F8, simulation, *state)
    assert state == (0, 1, True)
    simulation.Reset.assert_not_called()
    assert HandleComparisonKey(glfw.KEY_F9, simulation, len(CASES)-1, 1, True) == (0, 1, True)
    assert HandleComparisonKey(glfw.KEY_F10, simulation, 2, 1, True) == (2, 1, True)
    assert simulation.Reset.call_count == 2


def test_comparison_reset_and_independent_joint_states():
    original = probe.base.g1.DEMO_XML.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        path = probe.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
        model = probe.mujoco.MjModel.from_xml_path(str(path))
    probe.base._apply_operational_joint_limits(model)
    run = Comparison(model, "mink-default")
    assert not np.shares_memory(run.q[0], run.q[1])
    np.testing.assert_allclose(run.planner.velocity_caps,
        [probe.live.virtual_center_velocity_limits()[n] for n in probe.base.g1.RIGHT_ARM_JOINTS])
    for case in range(len(CASES)):
        run.Reset()
        assert run.seconds == 0
        for _ in range(4):
            run.Step(case)
        assert len(run.rows) == 2
        assert np.isfinite(np.array(run.q)).all()
        assert run.rows[1]["status"] == "direct QP"
    assert probe.base.g1.DEMO_XML.read_bytes() == original
    replay = RecordedPlayback(run, 4 * probe.base.DT)
    replay.Prepare(0, lambda *_: None)
    expected = [q.copy() for q, _, _, _ in replay.frames]
    run.Reset()
    for q in expected:
        run.Step(0)
        np.testing.assert_allclose(run.q, q, atol=1e-10)
    with patch.object(run, "Step", side_effect=AssertionError("cached")):
        replay.Prepare(0, lambda *_: None)
        replay.Advance(.5, 8, False)
