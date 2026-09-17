"""Offline standard solver substitution; no network, viewer or SDK."""
from pathlib import Path
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_feasible_target import BuildPlanner, probe
from g1_standard_mink_planner import StandardMinkPlanner
from g1_virtual_center_tasks import virtual_center_velocity_limits

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("profile", ["mink-default", "hardware-guarded"])
def test_standard_qp_shared_limits_and_goal(profile):
    with tempfile.TemporaryDirectory() as directory:
        path = probe.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
        model = probe.mujoco.MjModel.from_xml_path(str(path))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                 for name in probe.base.g1.RIGHT_ARM_JOINTS]
    q[addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
    shared = BuildPlanner(model, q, collision_profile=profile)
    planner = StandardMinkPlanner(
        model, *shared.tasks, shared.limits, shared.constraints, shared.solver,
        shared.clearance_m, virtual_center_velocity_limits(), horizon_steps=1)
    planner.configuration.update(q)
    pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    goal = probe.base._matrix_to_se3(pose.rotation().as_matrix(), pose.translation() + [0.002, 0, 0.002])
    assert planner.limits is shared.limits
    plan = planner.Plan(q, goal, goal.translation())
    assert plan.valid and plan.accepted_steps == 1
    assert planner.CheckConfiguration(plan.next_q)
    # Feed real solver output through the production packet and relay parser.
    import json
    sys.path.insert(0, str(ROOT / "hardware/g1_arm_bridge"))
    from gate7_mink_wsl_relay import MinkOrderGuard, ValidateAndForward
    from arm_sdk_teleop_contract import parse_mink_arm_sample
    from gate7_relay_provenance_guard import require_relay_token
    planner.configuration.update(plan.next_q)
    all_addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                     for name in probe.base.g1.G1_29_JOINTS]
    from g1_mink_command_provenance import wrap_state_packet_factory
    packet = wrap_state_packet_factory(probe.base._state_packet)(planner.configuration, addresses, all_addresses,
        True, goal.translation(), pose.translation(), False,
        minimum_clearance_m=planner.GetClearance(plan.next_q), control_state="active",
        input_command_mode="active", state_sequence=1, session_id="offline-standard",
        input_packet_age_s=0.0)
    class Sink:
        def sendto(self, payload, target):
            self.payload = payload
    sink = Sink()
    token = "1234567890abcdef1234567890abcdef"
    ValidateAndForward(json.dumps(packet).encode(), MinkOrderGuard(), sink,
                       ("127.0.0.1", 1), relay_token=token)
    require_relay_token(sink.payload, token)
    sample = parse_mink_arm_sample(sink.payload)
    np.testing.assert_allclose(sample.all_joint_q_rad,
        plan.next_q[all_addresses], atol=5.1e-8, rtol=0)
    # First step is the ordinary weighted Mink QP, without hierarchical stages.
    planner.configuration.update(q)
    velocity = probe.mink.solve_ik(planner.configuration, planner.standard_tasks,
        probe.base.DT, solver=planner.solver, damping=probe.base.QP_DAMPING,
        limits=planner.limits, constraints=planner.constraints)
    planner.configuration.integrate_inplace(velocity, probe.base.DT)
    np.testing.assert_allclose(plan.next_q, planner.configuration.q, atol=1e-10)
    # A rejected path holds instead of bypassing the common collision gate.
    planner._PathClear = lambda *args: False
    held = planner.Plan(q, goal, goal.translation())
    assert held.accepted_steps == 0 and held.status == "collision_hold"
    np.testing.assert_array_equal(held.next_q, q)
    planner.ResetDetour()
    assert planner.posture_reference is None
    bad = probe.base._matrix_to_se3(pose.rotation().as_matrix(), [np.nan, 0, 0])
    assert planner.Plan(q, bad).status == "invalid_goal"


def test_launcher_selection_and_locked_profile():
    import json
    wrapper = (ROOT / "tools/START_G1_GATE7_STANDARD_MINK.bat").read_text()
    assert "--first-live --standard-mink" in wrapper
    live = (ROOT / "tools/START_G1_GATE7_LIVE_HARDWARE.bat").read_text()
    assert '--hardware-display %IK_ARGUMENT%' in live
    config = json.loads((ROOT / "config/g1_gate7_first_live_hardware_output.json").read_text())
    assert config["hardware_output_authorized"] is False
    entry = (ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
    assert '--ik-solver %IK_SOLVER%' in entry
    assert 'set "COLLISION_PROFILE=hardware-guarded"' in entry


def test_live_parser_preserves_default_and_selects_vanilla(monkeypatch):
    import run_mink_g1_right_arm_virtual_center_live as live
    monkeypatch.setattr(sys, "argv", ["controller"])
    assert live.parse_args().ik_solver == "hierarchical"
    monkeypatch.setattr(sys, "argv", ["controller", "--ik-solver", "vanilla",
                                      "--collision-profile", "hardware-guarded"])
    args = live.parse_args()
    assert args.ik_solver == "vanilla"
    assert args.collision_profile == "hardware-guarded"


@pytest.mark.parametrize("arguments, expected", [
    ([], "vanilla"),
    (["--hierarchical"], "hierarchical"),
    (["--hardware-display"], "hierarchical"),
    (["--hardware-display", "--standard-mink"], "vanilla"),
    (["--standard-mink", "--hardware-display"], "vanilla"),
    (["--check", "--hierarchical"], "hierarchical"),
])
def test_local_launcher_default_without_starting_runtime(tmp_path, arguments, expected):
    import os
    import subprocess
    if os.name != "nt":
        pytest.skip("Windows CMD selection test")
    # Execute only variable assignments, never the launcher runtime section.
    source = (ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text()
    prefix = source.split("rem Local Unity/MuJoCo", 1)[0]
    script = tmp_path / "selection.bat"
    script.write_text(prefix + '\necho SOLVER=%IK_SOLVER%\n')
    result = subprocess.run(["cmd.exe", "/d", "/c", str(script), *arguments],
                            capture_output=True, text=True, check=True)
    assert f"SOLVER={expected}" in result.stdout


@pytest.mark.parametrize("profile", ["mink-default", "hardware-guarded"])
@pytest.mark.parametrize("axis", range(7))
def test_continuous_standard_motion(profile, axis):
    with tempfile.TemporaryDirectory() as directory:
        path = probe.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
        model = probe.mujoco.MjModel.from_xml_path(str(path))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                 for name in probe.base.g1.RIGHT_ARM_JOINTS]
    q[addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
    shared = BuildPlanner(model, q, collision_profile=profile)
    planner = StandardMinkPlanner(model, *shared.tasks, shared.limits,
        shared.constraints, shared.solver, shared.clearance_m,
        virtual_center_velocity_limits(), horizon_steps=1)
    planner.configuration.update(q)
    pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    initial = q.copy()
    moving_steps = 0
    for step in range(120):
        wave = np.sin(step * np.pi / 119)
        delta = np.zeros(3)
        rotation = pose.rotation().as_matrix()
        if axis < 3:
            delta[axis] = 0.01 * wave
        else:
            factory = (probe.mink.SO3.from_x_radians, probe.mink.SO3.from_y_radians,
                       probe.mink.SO3.from_z_radians)[(axis - 3) % 3]
            rotation = rotation @ factory(0.08 * wave).as_matrix()
        if axis == 6:
            delta[:] = [0.005 * wave, -0.005 * wave, 0.005 * wave]
        goal = probe.base._matrix_to_se3(rotation, pose.translation() + delta)
        plan = planner.Plan(q, goal, goal.translation())
        assert plan.valid
        assert planner.CheckConfiguration(plan.next_q)
        actual_velocity = np.abs((plan.next_q[addresses] - q[addresses]) / probe.base.DT)
        assert np.all(actual_velocity <= planner.velocity_caps + 1e-6)
        other = np.ones(model.nq, dtype=bool)
        other[addresses] = False
        np.testing.assert_allclose(plan.next_q[other], initial[other], atol=1e-10)
        moving_steps += int(np.linalg.norm(plan.next_q - q) > 1e-8)
        q = plan.next_q
    assert moving_steps > 60
