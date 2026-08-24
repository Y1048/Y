"""Geometry-aware redundancy resolution for G1 right-arm teleoperation.

The operator commands the wrist Cartesian task. Shoulder/elbow configuration is
chosen automatically from the one-dimensional proximal null space using the
actual MuJoCo robot geometry, collision clearance, joint limits, and continuity.
The captured torso posture remains only a baseline/reference artifact and is not
used as a live joint target.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m
from .workspace_map import WorkspaceProjection, WorkspaceTargetProjector


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "joint_postures.json"
FINITE_DIFFERENCE_RAD = math.radians(0.5)
PROXIMAL_MAX_STEP_RAD = math.radians(0.20)
ELBOW_MAX_STEP_RAD = math.radians(0.12)
MAX_PRIMARY_DRIFT_M = 0.0002
CLEARANCE_REGRESSION_TOLERANCE_M = 0.0001
JOINT_CENTER_WEIGHT = 0.10
LINE_SEARCH_STEPS = 7


def _smoothstep(value: float) -> float:
    t = float(np.clip(value, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def _load_blend_config(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return dict(payload["right_arm"]["blend"])


def posture_region_blend(target_position: np.ndarray, blend_cfg: dict[str, Any]) -> float:
    """Return torso-center blend used only for workspace/orientation priorities."""
    x, y, z = (float(v) for v in np.asarray(target_position, dtype=float))
    x_min = float(blend_cfg["front_x_min_m"])
    x_max = float(blend_cfg["front_x_max_m"])
    z_min = float(blend_cfg["z_min_m"])
    z_max = float(blend_cfg["z_max_m"])
    if not (x_min <= x <= x_max and z_min <= z <= z_max):
        return 0.0

    enter = float(blend_cfg["centerline_enter_abs_y_m"])
    release = float(blend_cfg["centerline_release_abs_y_m"])
    if release <= enter:
        raise ValueError("centerline_release_abs_y_m must be greater than enter")
    ay = abs(y)
    if ay <= enter:
        return 1.0
    if ay >= release:
        return 0.0
    return _smoothstep((release - ay) / (release - enter))


def _exact_nullspace_projector(jacobian: np.ndarray) -> np.ndarray:
    j = np.asarray(jacobian, dtype=float)
    _, singular, vt = np.linalg.svd(j, full_matrices=True)
    if singular.size == 0:
        return np.eye(j.shape[1])
    threshold = max(j.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > threshold))
    if rank >= j.shape[1]:
        return np.zeros((j.shape[1], j.shape[1]), dtype=float)
    basis = vt[rank:, :].T
    return basis @ basis.T


def _install_configuration_aware_workspace(base: ModuleType, blend_cfg: dict[str, Any]) -> None:
    projector_type = WorkspaceTargetProjector
    if getattr(projector_type, "_GEOMETRY_REDUNDANCY_WORKSPACE_INSTALLED", False):
        return

    original_update = projector_type.update
    base.RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS = False

    def update_with_geometry(self: Any, operator_target_m: np.ndarray):
        target = np.asarray(operator_target_m, dtype=float)
        blend = posture_region_blend(target, blend_cfg)
        bypass = blend > 1e-6
        base.RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS = bypass
        if not bypass:
            return original_update(self, target)
        # A wrist-only voxel map cannot distinguish redundant elbow/shoulder
        # configurations. In the torso-center region, actual joint-space collision
        # geometry is authoritative instead.
        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=target.copy(),
            projected=False,
            distance_m=0.0,
        )

    projector_type.update = update_with_geometry
    projector_type._GEOMETRY_REDUNDANCY_WORKSPACE_INSTALLED = True


def _joint_center_direction(model: Any, qpos_ids: np.ndarray, q: np.ndarray) -> np.ndarray:
    direction = np.zeros(4, dtype=float)
    for index, qpos_id in enumerate(qpos_ids[:4]):
        joint_id = -1
        for candidate in range(int(model.njnt)):
            if int(model.jnt_qposadr[candidate]) == int(qpos_id):
                joint_id = candidate
                break
        if joint_id < 0 or not bool(model.jnt_limited[joint_id]):
            continue
        low, high = (float(v) for v in model.jnt_range[joint_id])
        half = 0.5 * (high - low)
        if half <= 1e-9:
            continue
        middle = 0.5 * (low + high)
        direction[index] = -(float(q[index]) - middle) / half
    norm = float(np.linalg.norm(direction))
    return direction / norm if norm > 1e-9 else direction


def _clearance_value(
    model: Any,
    data: Any,
    context: dict[str, Any],
    *,
    structural_neighbor_distance: int,
    safe_distance_m: float,
) -> tuple[float, float | None]:
    raw = dangerous_contact_clearance_m(
        model,
        data,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    if raw is None:
        return safe_distance_m, None
    return float(np.clip(raw, 0.0, safe_distance_m)), float(raw)


def _clearance_gradient(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    start_q: np.ndarray,
    *,
    structural_neighbor_distance: int,
    safe_distance_m: float,
) -> np.ndarray:
    gradient = np.zeros(4, dtype=float)
    saved_q = data.qpos[qpos_ids].copy()
    try:
        for index in range(4):
            samples: list[tuple[float, float]] = []
            for sign in (-1.0, 1.0):
                trial = start_q.copy()
                trial[index] += sign * FINITE_DIFFERENCE_RAD
                data.qpos[qpos_ids] = trial
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                actual_value = float(data.qpos[qpos_ids[index]])
                mujoco.mj_forward(model, data)
                clearance, _ = _clearance_value(
                    model,
                    data,
                    context,
                    structural_neighbor_distance=structural_neighbor_distance,
                    safe_distance_m=safe_distance_m,
                )
                samples.append((actual_value, clearance))
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                gradient[index] = (samples[1][1] - samples[0][1]) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def install_geometry_aware_redundancy_resolver(
    base: ModuleType,
    *,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> None:
    """Install automatic geometry-based proximal redundancy resolution."""
    if getattr(base, "_GEOMETRY_REDUNDANCY_RESOLVER_INSTALLED", False):
        return

    blend_cfg = _load_blend_config(profile_path)
    _install_configuration_aware_workspace(base, blend_cfg)

    # A manually captured negative elbow is valid in the G1 MuJoCo model. The
    # geometry resolver uses the model's true joint limits rather than the legacy
    # hand-authored +5 degree elbow lower bound.
    operational_limits = getattr(base, "RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES", None)
    if isinstance(operational_limits, dict):
        operational_limits.pop("right_elbow_joint", None)

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before installing redundancy resolver")

    base.RUNTIME_JOINT_POSTURE_ENABLED = True
    base.RUNTIME_JOINT_POSTURE_BLEND = 0.0
    base.RUNTIME_JOINT_POSTURE_TARGET_DEG = None
    base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG = None
    base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG = 0.0
    base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED = False
    base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON = None
    base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = 0.0
    base.RUNTIME_JOINT_POSTURE_LEGACY_ELBOW_AVOIDANCE_DISABLED = True
    base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_BEFORE_M = None
    base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_AFTER_M = None
    base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_PRESSURE = 0.0
    base.RUNTIME_GEOMETRY_REDUNDANCY_GRADIENT = [0.0, 0.0, 0.0, 0.0]

    def geometry_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        preferred = args[3] if len(args) > 3 else kwargs.get("preferred")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]
        if model is None or data is None or preferred is None or target is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or dof_ids.size < 7 or position_body is None:
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        blend = posture_region_blend(target_position, blend_cfg)
        start_before_primary = data.qpos[qpos_ids].copy()

        # Keep the base solver purely Cartesian: suppress its old posture and
        # elbow-pole/lateral heuristics. Runtime collision geometry remains active.
        primary_preferred = np.asarray(preferred, dtype=float).copy()
        primary_preferred[:4] = start_before_primary[:4]
        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = None
        previous_enforce = bool(context.get("enforce_torso_safety", False))
        context["enforce_torso_safety"] = False
        try:
            if len(args) > 3:
                adjusted_args = list(args)
                adjusted_args[3] = primary_preferred
                result = original_solver(*adjusted_args, **adjusted_kwargs)
            else:
                adjusted_kwargs["preferred"] = primary_preferred
                result = original_solver(*args, **adjusted_kwargs)
        finally:
            context["enforce_torso_safety"] = previous_enforce

        mujoco.mj_forward(model, data)
        start_q = data.qpos[qpos_ids].copy()
        start_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        safe_distance_m = max(
            float(getattr(base, "RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M", 0.015)),
            1e-4,
        )
        _, raw_clearance_before = _clearance_value(
            model,
            data,
            context,
            structural_neighbor_distance=structural_neighbor_distance,
            safe_distance_m=safe_distance_m,
        )

        jacp = np.zeros((3, model.nv))
        jacr_dummy = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp, jacr_dummy, int(position_body))
        task_jacobian = jacp[:, dof_ids[:4]]
        null_projector = _exact_nullspace_projector(task_jacobian)

        clearance_gradient = _clearance_gradient(
            base,
            model,
            data,
            context,
            qpos_ids,
            start_q,
            structural_neighbor_distance=structural_neighbor_distance,
            safe_distance_m=safe_distance_m,
        )
        gradient_norm = float(np.linalg.norm(clearance_gradient))
        clearance_direction = (
            clearance_gradient / gradient_norm if gradient_norm > 1e-9 else clearance_gradient
        )
        if raw_clearance_before is None:
            clearance_pressure = 0.0
        else:
            clearance_pressure = _smoothstep(
                (safe_distance_m - float(raw_clearance_before)) / safe_distance_m
            )

        center_direction = _joint_center_direction(model, qpos_ids, start_q)
        raw_secondary = (
            clearance_pressure * clearance_direction
            + JOINT_CENTER_WEIGHT * center_direction
        )
        projected = null_projector @ raw_secondary
        projected_norm = float(np.linalg.norm(projected))
        accepted = False
        accepted_step = np.zeros(4, dtype=float)
        blocked_reason = None
        best_primary_drift = math.inf
        raw_clearance_after = raw_clearance_before

        if projected_norm > 1e-10:
            max_component = float(np.max(np.abs(projected)))
            intensity = min(1.0, float(np.linalg.norm(raw_secondary)))
            step = projected / max(max_component, 1e-12) * PROXIMAL_MAX_STEP_RAD * intensity
            step[3] = float(np.clip(step[3], -ELBOW_MAX_STEP_RAD, ELBOW_MAX_STEP_RAD))

            saw_collision = False
            saw_clearance_regression = False
            for line_index in range(LINE_SEARCH_STEPS):
                scale = 0.5 ** line_index
                trial_step = scale * step
                data.qpos[qpos_ids[:4]] = start_q[:4] + trial_step
                data.qpos[qpos_ids[4:]] = start_q[4:]
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)

                final_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
                primary_drift = final_error - start_error
                best_primary_drift = min(best_primary_drift, primary_drift)
                collision = bool(base.has_right_arm_core_contact(model, data, context))
                saw_collision = saw_collision or collision
                _, trial_raw_clearance = _clearance_value(
                    model,
                    data,
                    context,
                    structural_neighbor_distance=structural_neighbor_distance,
                    safe_distance_m=safe_distance_m,
                )
                clearance_ok = True
                if raw_clearance_before is not None:
                    trial_value = safe_distance_m if trial_raw_clearance is None else float(trial_raw_clearance)
                    clearance_ok = trial_value >= float(raw_clearance_before) - CLEARANCE_REGRESSION_TOLERANCE_M
                    saw_clearance_regression = saw_clearance_regression or not clearance_ok

                if (
                    not collision
                    and clearance_ok
                    and primary_drift <= MAX_PRIMARY_DRIFT_M
                ):
                    accepted = True
                    accepted_step = data.qpos[qpos_ids[:4]] - start_q[:4]
                    raw_clearance_after = trial_raw_clearance
                    break

            if not accepted:
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                if saw_collision:
                    blocked_reason = "collision"
                elif saw_clearance_regression:
                    blocked_reason = "clearance_regression"
                else:
                    blocked_reason = "primary_drift"
        else:
            blocked_reason = "no_nullspace_descent"

        if accepted:
            result = data.xpos[int(position_body)].copy()

        actual_deg = np.degrees(data.qpos[qpos_ids]).tolist()
        step_deg = float(np.linalg.norm(np.degrees(accepted_step))) if accepted else 0.0
        primary_drift_value = (
            float(np.linalg.norm(target_position - data.xpos[int(position_body)])) - start_error
            if accepted
            else (0.0 if not math.isfinite(best_primary_drift) else float(best_primary_drift))
        )

        base.RUNTIME_JOINT_POSTURE_BLEND = float(blend)
        base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG = actual_deg
        base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG = step_deg
        base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED = bool(not accepted and projected_norm > 1e-10)
        base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON = blocked_reason
        base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = primary_drift_value
        base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_BEFORE_M = raw_clearance_before
        base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_AFTER_M = raw_clearance_after
        base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_PRESSURE = float(clearance_pressure)
        base.RUNTIME_GEOMETRY_REDUNDANCY_GRADIENT = clearance_gradient.tolist()

        context["joint_posture_enabled"] = True
        context["joint_posture_blend"] = float(blend)
        context["joint_posture_target_deg"] = None
        context["joint_posture_actual_deg"] = actual_deg
        context["joint_posture_secondary_step_deg"] = step_deg
        context["joint_posture_secondary_blocked"] = base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED
        context["joint_posture_secondary_blocked_reason"] = blocked_reason
        context["joint_posture_secondary_primary_drift_m"] = primary_drift_value
        context["joint_posture_legacy_elbow_avoidance_disabled"] = True
        context["geometry_redundancy_mode"] = "clearance_gradient"
        context["geometry_clearance_before_m"] = raw_clearance_before
        context["geometry_clearance_after_m"] = raw_clearance_after
        context["geometry_clearance_pressure"] = float(clearance_pressure)
        context["geometry_clearance_gradient"] = clearance_gradient.tolist()
        return result

    base.solve_right_arm_target = geometry_solver
    base._GEOMETRY_REDUNDANCY_RESOLVER_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_GEOMETRY_REDUNDANCY_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["joint_posture_enabled"] = True
            enriched["joint_posture_blend"] = float(base.RUNTIME_JOINT_POSTURE_BLEND)
            enriched["joint_posture_target_deg"] = None
            enriched["joint_posture_actual_deg"] = base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG
            enriched["joint_posture_secondary_step_deg"] = float(base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG)
            enriched["joint_posture_secondary_blocked"] = bool(base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED)
            enriched["joint_posture_secondary_blocked_reason"] = base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON
            enriched["joint_posture_secondary_primary_drift_m"] = float(base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M)
            enriched["joint_posture_workspace_bypass"] = bool(
                getattr(base, "RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS", False)
            )
            enriched["joint_posture_legacy_elbow_avoidance_disabled"] = True
            enriched["joint_posture_elbow_step_cap_deg"] = math.degrees(ELBOW_MAX_STEP_RAD)
            enriched["geometry_redundancy_mode"] = "clearance_gradient"
            enriched["geometry_clearance_before_m"] = base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_BEFORE_M
            enriched["geometry_clearance_after_m"] = base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_AFTER_M
            enriched["geometry_clearance_pressure"] = float(base.RUNTIME_GEOMETRY_REDUNDANCY_CLEARANCE_PRESSURE)
            enriched["geometry_clearance_gradient"] = list(base.RUNTIME_GEOMETRY_REDUNDANCY_GRADIENT)
            enriched["geometry_safe_distance_m"] = float(
                getattr(base, "RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M", 0.015)
            )
            enriched["manual_posture_reference_active"] = False
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._GEOMETRY_REDUNDANCY_STATUS_INSTALLED = True
