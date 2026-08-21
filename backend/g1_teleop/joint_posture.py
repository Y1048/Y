"""Joint-space posture scheduling for redundant right-arm Cartesian IK."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .workspace_map import WorkspaceProjection, WorkspaceTargetProjector


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "joint_postures.json"
SECONDARY_MAX_STEP_RAD = math.radians(0.35)
SECONDARY_MAX_PRIMARY_DRIFT_M = 0.0002
SECONDARY_GAIN = 0.18


def _smoothstep(value: float) -> float:
    t = float(np.clip(value, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def load_right_arm_posture_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    arm = payload["right_arm"]
    ready = np.asarray(arm["ready_deg"], dtype=float)
    torso_raw = arm.get("torso_front_deg")
    torso = None if torso_raw is None else np.asarray(torso_raw, dtype=float)
    if ready.shape != (7,):
        raise ValueError("right_arm.ready_deg must contain 7 joint angles")
    if torso is not None and torso.shape != (7,):
        raise ValueError("right_arm.torso_front_deg must contain 7 joint angles or null")
    return {
        "ready_rad": np.radians(ready),
        "torso_rad": None if torso is None else np.radians(torso),
        "blend": dict(arm["blend"]),
    }


def posture_blend(target_position: np.ndarray, blend_cfg: dict[str, Any]) -> float:
    """Blend from side/ready posture to torso-front posture using robot-space geometry."""
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
    linear = (release - ay) / (release - enter)
    return _smoothstep(linear)


def _exact_nullspace_projector(jacobian: np.ndarray) -> np.ndarray:
    """Return the orthogonal projector onto the exact numerical null space of J."""
    j = np.asarray(jacobian, dtype=float)
    if j.ndim != 2:
        raise ValueError("jacobian must be a matrix")
    _, singular, vt = np.linalg.svd(j, full_matrices=True)
    if singular.size == 0:
        return np.eye(j.shape[1])
    threshold = max(j.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > threshold))
    if rank >= j.shape[1]:
        return np.zeros((j.shape[1], j.shape[1]), dtype=float)
    basis = vt[rank:, :].T
    return basis @ basis.T


def _install_configuration_aware_workspace(base: ModuleType, torso: np.ndarray | None, blend_cfg: dict[str, Any]) -> None:
    """Let live collision checks own torso-center feasibility when a posture exists."""
    projector_type = WorkspaceTargetProjector
    if torso is None or getattr(projector_type, "_JOINT_POSTURE_WORKSPACE_INSTALLED", False):
        return

    original_update = projector_type.update
    base.RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS = False

    def update_with_joint_posture(self: Any, operator_target_m: np.ndarray):
        target = np.asarray(operator_target_m, dtype=float)
        alpha = posture_blend(target, blend_cfg)
        bypass = alpha > 1e-6
        base.RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS = bypass
        if not bypass:
            return original_update(self, target)
        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=target.copy(),
            projected=False,
            distance_m=0.0,
        )

    projector_type.update = update_with_joint_posture
    projector_type._JOINT_POSTURE_WORKSPACE_INSTALLED = True


def install_joint_space_posture_scheduler(
    base: ModuleType,
    *,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> None:
    """Apply the captured seven-joint posture as the secondary task.

    Cartesian wrist position remains the primary task. The full 7-DOF posture is
    projected into the exact numerical null space of the translational Jacobian,
    so shoulder/elbow and wrist configuration are kept together. Quest wrist
    orientation is handled later as a lower-priority task by the launcher.
    """
    if getattr(base, "_JOINT_SPACE_POSTURE_SCHEDULER_INSTALLED", False):
        return

    profile = load_right_arm_posture_profile(profile_path)
    ready = profile["ready_rad"]
    torso = profile["torso_rad"]
    blend_cfg = profile["blend"]
    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before posture scheduler install")

    operational_limits = getattr(base, "RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES", None)
    if torso is not None and isinstance(operational_limits, dict):
        operational_limits.pop("right_elbow_joint", None)

    _install_configuration_aware_workspace(base, torso, blend_cfg)

    base.RUNTIME_JOINT_POSTURE_ENABLED = torso is not None
    base.RUNTIME_JOINT_POSTURE_BLEND = 0.0
    base.RUNTIME_JOINT_POSTURE_TARGET_DEG = None
    base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG = None
    base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG = 0.0
    base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED = False
    base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON = None
    base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = 0.0

    def scheduled_solver(*args: Any, **kwargs: Any):
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
        alpha = 0.0 if torso is None else posture_blend(target_position, blend_cfg)
        scheduled = np.asarray(preferred, dtype=float).copy()
        if torso is not None:
            scheduled = (1.0 - alpha) * ready + alpha * torso

        # Remove the legacy damped-nullspace posture contribution from the base
        # solver. The wrapper below owns the complete 7-DOF secondary task.
        current_before = data.qpos[qpos_ids].copy()
        primary_preferred = np.asarray(preferred, dtype=float).copy()
        primary_preferred[:4] = current_before[:4]

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = None
        if len(args) > 3:
            adjusted_args = list(args)
            adjusted_args[3] = primary_preferred
            result = original_solver(*adjusted_args, **adjusted_kwargs)
        else:
            adjusted_kwargs["preferred"] = primary_preferred
            result = original_solver(*args, **adjusted_kwargs)

        base.RUNTIME_JOINT_POSTURE_ENABLED = torso is not None
        base.RUNTIME_JOINT_POSTURE_BLEND = float(alpha)
        base.RUNTIME_JOINT_POSTURE_TARGET_DEG = np.degrees(scheduled).tolist()
        base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG = 0.0
        base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED = False
        base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON = None
        base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = 0.0

        if torso is not None and alpha > 1e-6:
            mujoco.mj_forward(model, data)
            start_q = data.qpos[qpos_ids].copy()
            start_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))

            jacp = np.zeros((3, model.nv))
            jacr_dummy = np.zeros((3, model.nv))
            mujoco.mj_jacBody(model, data, jacp, jacr_dummy, int(position_body))
            task_jacobian = jacp[:, dof_ids]
            null_projector = _exact_nullspace_projector(task_jacobian)
            posture_error = scheduled - start_q
            secondary_delta = null_projector @ (SECONDARY_GAIN * posture_error)
            secondary_delta = np.clip(
                secondary_delta,
                -SECONDARY_MAX_STEP_RAD,
                SECONDARY_MAX_STEP_RAD,
            )

            accepted = False
            accepted_step = np.zeros(7, dtype=float)
            saw_collision = False
            best_primary_drift = math.inf
            for line_search_index in range(6):
                scale = 0.5 ** line_search_index
                trial_step = scale * secondary_delta
                data.qpos[qpos_ids] = start_q + trial_step
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)
                final_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
                primary_drift = final_error - start_error
                best_primary_drift = min(best_primary_drift, primary_drift)
                collision = bool(base.has_right_arm_core_contact(model, data, context))
                saw_collision = saw_collision or collision
                if (
                    not collision
                    and primary_drift <= SECONDARY_MAX_PRIMARY_DRIFT_M
                ):
                    accepted = True
                    accepted_step = data.qpos[qpos_ids] - start_q
                    base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = float(primary_drift)
                    break

            if not accepted:
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED = True
                if saw_collision:
                    reason = "collision"
                elif math.isfinite(best_primary_drift):
                    reason = "primary_drift"
                else:
                    reason = "unknown"
                base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON = reason
                if math.isfinite(best_primary_drift):
                    base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M = float(best_primary_drift)
            else:
                base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG = float(
                    np.linalg.norm(np.degrees(accepted_step))
                )
                result = data.xpos[int(position_body)].copy()

        actual_deg = np.degrees(data.qpos[qpos_ids]).tolist()
        base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG = actual_deg
        context["joint_posture_enabled"] = bool(torso is not None)
        context["joint_posture_blend"] = float(alpha)
        context["joint_posture_target_deg"] = list(base.RUNTIME_JOINT_POSTURE_TARGET_DEG)
        context["joint_posture_actual_deg"] = list(actual_deg)
        context["joint_posture_secondary_step_deg"] = float(base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG)
        context["joint_posture_secondary_blocked"] = bool(base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED)
        context["joint_posture_secondary_blocked_reason"] = base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON
        context["joint_posture_secondary_primary_drift_m"] = float(
            base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M
        )
        return result

    base.solve_right_arm_target = scheduled_solver
    base._JOINT_SPACE_POSTURE_SCHEDULER_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_JOINT_POSTURE_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["joint_posture_enabled"] = bool(base.RUNTIME_JOINT_POSTURE_ENABLED)
            enriched["joint_posture_blend"] = float(base.RUNTIME_JOINT_POSTURE_BLEND)
            enriched["joint_posture_target_deg"] = base.RUNTIME_JOINT_POSTURE_TARGET_DEG
            enriched["joint_posture_actual_deg"] = base.RUNTIME_JOINT_POSTURE_ACTUAL_DEG
            enriched["joint_posture_secondary_step_deg"] = float(
                base.RUNTIME_JOINT_POSTURE_SECONDARY_STEP_DEG
            )
            enriched["joint_posture_secondary_blocked"] = bool(
                base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED
            )
            enriched["joint_posture_secondary_blocked_reason"] = (
                base.RUNTIME_JOINT_POSTURE_SECONDARY_BLOCKED_REASON
            )
            enriched["joint_posture_secondary_primary_drift_m"] = float(
                base.RUNTIME_JOINT_POSTURE_SECONDARY_PRIMARY_DRIFT_M
            )
            enriched["joint_posture_workspace_bypass"] = bool(
                getattr(base, "RUNTIME_JOINT_POSTURE_WORKSPACE_BYPASS", False)
            )
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._JOINT_POSTURE_STATUS_INSTALLED = True
