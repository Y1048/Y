"""Offline right-arm diagnostics that isolate IK/reference/workspace from Unity and UDP."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import mujoco
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import apply_to_base_module, apply_to_projected_runtime, load_teleop_config
from g1_teleop.ik_emergency import load_severe_ik_fallback_settings
from g1_teleop.ik_fallback import install_coupled_ik_fallback, load_ik_fallback_settings
from g1_teleop.ik_primary_guard import install_primary_task_guard
from g1_teleop.inspection_contact import install_inspection_contact_monitor
from g1_teleop.runtime_collision import install_runtime_collision_policy

import g1_right_arm_udp_ik_demo as base
import g1_right_arm_udp_ik_runtime as runtime
import run_configured_g1_teleop as configured

CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"
DT = 1.0 / 60.0
ROTATION_TEST_DEG = 35.0
POSITION_PROBE_M = 0.08


def rotation_about_axis(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= max(float(np.linalg.norm(axis)), 1e-12)
    x, y, z = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    C = 1.0 - c
    return np.array([
        [c + x*x*C, x*y*C - z*s, x*z*C + y*s],
        [y*x*C + z*s, c + y*y*C, y*z*C - x*s],
        [z*x*C - y*s, z*y*C + x*s, c + z*z*C],
    ])


def install_configured_stack():
    config = load_teleop_config(CONFIG_PATH)
    fallback = load_ik_fallback_settings(CONFIG_PATH)
    severe = load_severe_ik_fallback_settings(CONFIG_PATH)
    apply_to_base_module(base, config)
    install_runtime_collision_policy(base, config)
    install_inspection_contact_monitor(base, config)
    supervisor = install_coupled_ik_fallback(base, fallback)
    configured.install_position_only_fallback_policy(supervisor)
    configured.install_position_only_severe_trigger(base, supervisor, severe)
    install_primary_task_guard(base)
    configured.install_absolute_vr_wrist_orientation(base)
    apply_to_projected_runtime(runtime, config, PROJECT_ROOT)
    return config


def test_reference_speed(config) -> tuple[bool, str]:
    current = np.array([0.0, 0.0, 0.0])
    desired = np.array([1.0, 0.0, 0.0])
    steps = []
    for _ in range(120):
        nxt = base.update_safe_position_reference(current, desired, DT)
        steps.append(float(np.linalg.norm(nxt - current)))
        current = nxt
    measured = max(steps) / DT
    expected = float(config.motion.position_max_speed_mps)
    passed = measured <= expected + 1e-6 and measured >= expected - 1e-4
    return passed, f"measured={measured:.6f} m/s expected={expected:.6f} m/s"


def test_workspace_speed(config, anchor: np.ndarray) -> tuple[bool, str]:
    projector = runtime.load_workspace_projector(anchor)
    if projector is None:
        return False, "workspace map unavailable"

    directions = [
        np.array([1.0, 0.0, 0.0]), np.array([-1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, -1.0]),
    ]
    best = None
    for direction in directions:
        operator = anchor + POSITION_PROBE_M * direction
        projection = projector.workspace.project_from(anchor, operator, max_boundary_steps=0)
        available = float(np.linalg.norm(projection.feasible_target - anchor))
        if best is None or available > best[0]:
            best = (available, direction)

    available, direction = best
    current = anchor.copy()
    desired = anchor + POSITION_PROBE_M * direction
    max_speed = 0.0
    total = 0.0
    for _ in range(120):
        candidate = base.update_safe_position_reference(current, desired, DT)
        projection = projector.workspace.project_from(current, candidate, max_boundary_steps=0)
        nxt = projection.feasible_target
        step = float(np.linalg.norm(nxt - current))
        max_speed = max(max_speed, step / DT)
        total += step
        current = nxt
    expected = float(config.motion.position_max_speed_mps)
    passed = max_speed <= expected + 1e-6
    constrained = available < 0.01
    suffix = " (locally workspace-constrained)" if constrained else ""
    return passed, (
        f"direction={direction.tolist()} available={available*100:.1f} cm "
        f"total={total*100:.1f} cm max={max_speed:.6f} m/s "
        f"expected<={expected:.6f} m/s{suffix}"
    )


def test_rotation_ik() -> tuple[bool, str]:
    model, data, initial_qpos, preferred = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    mujoco.mj_forward(model, data)
    qids = np.asarray(context["right_qpos_ids"], dtype=int)
    position_body = int(context["position_body"])
    orientation_body = int(context["orientation_body"])
    target_position = data.xpos[position_body].copy()
    initial_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
    target_rotation = initial_rotation @ rotation_about_axis(
        np.array([0.0, 0.0, 1.0]), math.radians(ROTATION_TEST_DEG)
    )
    initial_q = data.qpos[qids].copy()
    initial_error = float(np.linalg.norm(base.calculate_rotation_error(target_rotation, initial_rotation)))

    for _ in range(180):
        base.solve_right_arm_target(
            model, data, initial_qpos, preferred, target_position,
            target_rotation=target_rotation,
            context=context,
            elbow_pole_reference=None,
        )

    final_q = data.qpos[qids].copy()
    final_rotation = data.xmat[orientation_body].reshape(3, 3)
    final_error = float(np.linalg.norm(base.calculate_rotation_error(target_rotation, final_rotation)))
    delta_deg = np.degrees(final_q - initial_q)
    proximal = float(np.linalg.norm(delta_deg[:4]))
    wrist = float(np.linalg.norm(delta_deg[4:]))
    drift = float(np.linalg.norm(data.xpos[position_body] - target_position))
    fallback_active = bool(getattr(base.IK_FALLBACK_SUPERVISOR, "active", False))
    severe_triggered = bool(getattr(base, "RUNTIME_IK_SEVERE_TRIGGERED", False))
    passed = (
        wrist >= 3.0
        and final_error < initial_error * 0.7
        and drift <= 0.01
        and proximal <= 3.0
        and not fallback_active
        and not severe_triggered
    )
    return passed, (
        f"wrist={wrist:.1f} deg proximal={proximal:.1f} deg "
        f"position_drift={drift*100:.2f} cm rot_error={initial_error:.3f}->{final_error:.3f} "
        f"fallback_active={fallback_active} severe={severe_triggered}"
    )


def main() -> int:
    print("G1 OFFLINE BACKEND DIAGNOSTIC")
    print("=============================")
    config = install_configured_stack()

    ref_pass, ref_detail = test_reference_speed(config)
    print(f"REFERENCE 0.08 m/s: {'PASS' if ref_pass else 'FAIL'} - {ref_detail}")

    model, data, _, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    mujoco.mj_forward(model, data)
    anchor = data.xpos[int(context['position_body'])].copy()
    workspace_pass, workspace_detail = test_workspace_speed(config, anchor)
    print(f"WORKSPACE FINAL STEP: {'PASS' if workspace_pass else 'FAIL'} - {workspace_detail}")

    rotation_pass, rotation_detail = test_rotation_ik()
    print(f"PURE WRIST IK: {'PASS' if rotation_pass else 'FAIL'} - {rotation_detail}")

    print("\nINTERPRETATION")
    if not rotation_pass:
        print("- PURE WRIST IK still fails with rotation-only fallback escalation disabled; inspect the decoupled wrist solver/collision guard next.")
    else:
        print("- PURE WRIST IK passes without coupled fallback: wrist orientation is isolated correctly inside the backend.")
    if not ref_pass:
        print("- Reference limiter itself is wrong.")
    elif not workspace_pass:
        print("- Workspace post-processing violates the configured speed ceiling.")
    else:
        print("- Position limiter + workspace post-processing preserve the 0.08 m/s ceiling offline.")

    return 0 if ref_pass and workspace_pass and rotation_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
