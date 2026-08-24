"""Emergency recovery when the right arm enters the hard torso-clearance zone.

Normal Cartesian IK and adaptive null-space redundancy remain authoritative above
5 mm. Below 5 mm this layer searches for a proximal-joint step that strictly
increases MuJoCo robot clearance, allowing a small temporary Cartesian drift if
the exact null space cannot provide an escape direction.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


HARD_CLEARANCE_FLOOR_M = 0.005
FINITE_DIFFERENCE_RAD = math.radians(0.5)
PROXIMAL_ESCAPE_MAX_STEP_RAD = math.radians(0.20)
ELBOW_ESCAPE_MAX_STEP_RAD = math.radians(0.12)
MAX_ESCAPE_PRIMARY_DRIFT_M = 0.002
MIN_CLEARANCE_IMPROVEMENT_M = 1e-9
LINE_SEARCH_STEPS = 8


def _clearance(model: Any, data: Any, context: dict[str, Any], structural_neighbor_distance: int) -> float:
    value = dangerous_contact_clearance_m(
        model,
        data,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    return math.inf if value is None else float(value)


def _exact_nullspace_projector(jacobian: np.ndarray) -> np.ndarray:
    j = np.asarray(jacobian, dtype=float)
    _, singular, vt = np.linalg.svd(j, full_matrices=True)
    if singular.size == 0:
        return np.eye(j.shape[1])
    threshold = max(j.shape) * np.finfo(float).eps * max(float(singular[0]), 1.0)
    rank = int(np.count_nonzero(singular > threshold))
    basis = vt[rank:, :].T
    return basis @ basis.T if basis.size else np.zeros((j.shape[1], j.shape[1]))


def _clearance_gradient(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    start_q: np.ndarray,
    structural_neighbor_distance: int,
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
                actual = float(data.qpos[qpos_ids[index]])
                mujoco.mj_forward(model, data)
                samples.append(
                    (actual, _clearance(model, data, context, structural_neighbor_distance))
                )
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                c0 = min(samples[0][1], HARD_CLEARANCE_FLOOR_M)
                c1 = min(samples[1][1], HARD_CLEARANCE_FLOOR_M)
                gradient[index] = (c1 - c0) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def install_emergency_clearance_escape(base: ModuleType) -> None:
    if getattr(base, "_EMERGENCY_CLEARANCE_ESCAPE_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_ACTIVE = False
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_MODE = None
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BEFORE_M = None
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_AFTER_M = None
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_STEP_DEG = 0.0
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_PRIMARY_DRIFT_M = 0.0
    base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON = None

    def escape_solver(*args: Any, **kwargs: Any):
        result = original_solver(*args, **kwargs)
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if model is None or data is None or target is None or not isinstance(context, dict):
            return result

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or dof_ids.size < 7 or position_body is None:
            return result

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        mujoco.mj_forward(model, data)
        clearance_before = _clearance(model, data, context, structural_neighbor_distance)

        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_ACTIVE = clearance_before < HARD_CLEARANCE_FLOOR_M
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_MODE = None
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BEFORE_M = None if math.isinf(clearance_before) else clearance_before
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_AFTER_M = None if math.isinf(clearance_before) else clearance_before
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_STEP_DEG = 0.0
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_PRIMARY_DRIFT_M = 0.0
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON = None

        if clearance_before >= HARD_CLEARANCE_FLOOR_M:
            return result

        start_q = data.qpos[qpos_ids].copy()
        target_position = np.asarray(target, dtype=float)
        start_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
        gradient = _clearance_gradient(
            base,
            model,
            data,
            context,
            qpos_ids,
            start_q,
            structural_neighbor_distance,
        )
        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm <= 1e-10:
            base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON = "no_clearance_gradient"
            return result

        direction = gradient / gradient_norm
        jacp = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp, jacr, int(position_body))
        null_projector = _exact_nullspace_projector(jacp[:, dof_ids[:4]])
        null_direction = null_projector @ direction
        null_norm = float(np.linalg.norm(null_direction))
        if null_norm > 1e-5:
            escape_direction = null_direction / null_norm
            escape_mode = "nullspace"
        else:
            # The one-dimensional proximal null space can become tangent to the
            # collision boundary. In that case allow a small task-space drift so
            # the arm can leave the torso instead of freezing against it.
            escape_direction = direction
            escape_mode = "bounded_primary_drift"

        max_component = float(np.max(np.abs(escape_direction)))
        if max_component <= 1e-10:
            base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON = "no_escape_direction"
            return result
        step = escape_direction / max_component * PROXIMAL_ESCAPE_MAX_STEP_RAD
        step[3] = float(np.clip(step[3], -ELBOW_ESCAPE_MAX_STEP_RAD, ELBOW_ESCAPE_MAX_STEP_RAD))

        accepted = False
        accepted_step = np.zeros(4, dtype=float)
        accepted_clearance = clearance_before
        accepted_drift = 0.0
        saw_collision = False
        saw_primary_drift = False
        for line_index in range(LINE_SEARCH_STEPS):
            scale = 0.5 ** line_index
            data.qpos[qpos_ids[:4]] = start_q[:4] + scale * step
            data.qpos[qpos_ids[4:]] = start_q[4:]
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)

            collision = bool(base.has_right_arm_core_contact(model, data, context))
            saw_collision = saw_collision or collision
            trial_clearance = _clearance(model, data, context, structural_neighbor_distance)
            final_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
            primary_drift = final_error - start_error
            saw_primary_drift = saw_primary_drift or primary_drift > MAX_ESCAPE_PRIMARY_DRIFT_M
            if (
                not collision
                and trial_clearance > clearance_before + MIN_CLEARANCE_IMPROVEMENT_M
                and primary_drift <= MAX_ESCAPE_PRIMARY_DRIFT_M
            ):
                accepted = True
                accepted_step = data.qpos[qpos_ids[:4]] - start_q[:4]
                accepted_clearance = trial_clearance
                accepted_drift = primary_drift
                break

        if not accepted:
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            if saw_collision:
                reason = "collision"
            elif saw_primary_drift:
                reason = "primary_drift"
            else:
                reason = "no_clearance_improvement"
            base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON = reason
            return result

        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_MODE = escape_mode
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_AFTER_M = accepted_clearance
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_STEP_DEG = float(
            np.linalg.norm(np.degrees(accepted_step))
        )
        base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_PRIMARY_DRIFT_M = float(accepted_drift)
        context["emergency_clearance_escape_active"] = True
        return data.xpos[int(position_body)].copy()

    base.solve_right_arm_target = escape_solver
    base._EMERGENCY_CLEARANCE_ESCAPE_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(base, "_EMERGENCY_CLEARANCE_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["emergency_clearance_escape_active"] = bool(
                base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_ACTIVE
            )
            enriched["emergency_clearance_escape_mode"] = base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_MODE
            enriched["emergency_clearance_escape_before_m"] = base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BEFORE_M
            enriched["emergency_clearance_escape_after_m"] = base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_AFTER_M
            enriched["emergency_clearance_escape_step_deg"] = float(
                base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_STEP_DEG
            )
            enriched["emergency_clearance_escape_primary_drift_m"] = float(
                base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_PRIMARY_DRIFT_M
            )
            enriched["emergency_clearance_escape_blocked_reason"] = (
                base.RUNTIME_EMERGENCY_CLEARANCE_ESCAPE_BLOCKED_REASON
            )
            enriched["emergency_clearance_escape_max_primary_drift_m"] = MAX_ESCAPE_PRIMARY_DRIFT_M
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._EMERGENCY_CLEARANCE_STATUS_INSTALLED = True


def install_recovery_aware_hard_clearance_floor(base: ModuleType) -> None:
    """Prevent entry into <5 mm, but allow any measurable escape once already inside."""
    if getattr(base, "_HARD_CLEARANCE_FLOOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_HARD_CLEARANCE_REVERTED = False
    base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE = False
    base.RUNTIME_HARD_CLEARANCE_BEFORE_M = None
    base.RUNTIME_HARD_CLEARANCE_AFTER_M = None

    def guarded_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if model is None or data is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)
        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        if qpos_ids.size < 7:
            return original_solver(*args, **kwargs)

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        start_q = data.qpos[qpos_ids].copy()
        before = _clearance(model, data, context, structural_neighbor_distance)
        result = original_solver(*args, **kwargs)
        after = _clearance(model, data, context, structural_neighbor_distance)

        recovery_active = before < HARD_CLEARANCE_FLOOR_M
        if recovery_active:
            reject = after <= before + MIN_CLEARANCE_IMPROVEMENT_M
        else:
            reject = after < HARD_CLEARANCE_FLOOR_M

        base.RUNTIME_HARD_CLEARANCE_REVERTED = bool(reject)
        base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE = bool(recovery_active)
        base.RUNTIME_HARD_CLEARANCE_BEFORE_M = None if math.isinf(before) else before
        base.RUNTIME_HARD_CLEARANCE_AFTER_M = None if math.isinf(after) else after
        context["hard_clearance_floor_m"] = HARD_CLEARANCE_FLOOR_M
        context["hard_clearance_reverted"] = bool(reject)
        context["hard_clearance_recovery_active"] = bool(recovery_active)

        if reject:
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            if context.get("position_body") is not None:
                return data.xpos[int(context["position_body"])].copy()
        return result

    base.solve_right_arm_target = guarded_solver
    base._HARD_CLEARANCE_FLOOR_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(base, "_HARD_CLEARANCE_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["hard_clearance_floor_m"] = HARD_CLEARANCE_FLOOR_M
            enriched["hard_clearance_reverted"] = bool(base.RUNTIME_HARD_CLEARANCE_REVERTED)
            enriched["hard_clearance_recovery_active"] = bool(
                base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE
            )
            enriched["hard_clearance_before_m"] = base.RUNTIME_HARD_CLEARANCE_BEFORE_M
            enriched["hard_clearance_after_m"] = base.RUNTIME_HARD_CLEARANCE_AFTER_M
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._HARD_CLEARANCE_STATUS_INSTALLED = True
