"""Continuous collision-safe progress with null-space reconfiguration.

A full tracking candidate is accepted when safe. If it crosses the soft robot
clearance floor, only the largest safe joint-space fraction is applied. When no
meaningful Cartesian progress is possible at that boundary, the supervisor does
not freeze: it changes shoulder/elbow configuration in the wrist-position null
space to increase clearance while holding wrist XYZ nearly fixed. Subsequent
cycles can then continue toward the operator target using the newly opened
configuration. The existing 5 mm hard floor remains the final emergency guard.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


SAFE_PROGRESS_CLEARANCE_M = 0.012
SAFE_PROGRESS_MARGIN_M = 0.00025
BISECTION_STEPS = 14
MIN_PROGRESS_SCALE = 1e-5
MAX_SAFE_PROGRESS_JOINT_STEP_RAD = math.radians(0.45)

RECONFIGURE_FINITE_DIFFERENCE_RAD = math.radians(0.5)
RECONFIGURE_MAX_STEP_RAD = math.radians(0.30)
RECONFIGURE_ELBOW_MAX_STEP_RAD = math.radians(0.20)
RECONFIGURE_MAX_PRIMARY_DRIFT_M = 0.0005
RECONFIGURE_LINE_SEARCH_STEPS = 8
RECONFIGURE_MIN_CLEARANCE_IMPROVEMENT_M = 1e-7
RECONFIGURE_DIRECTION_SMOOTHING_ALPHA = 0.35


def _clearance(
    model: Any,
    data: Any,
    context: dict[str, Any],
    structural_neighbor_distance: int,
) -> float:
    value = dangerous_contact_clearance_m(
        model,
        data,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    return math.inf if value is None else float(value)


def _bounded_delta(delta_q: np.ndarray) -> np.ndarray:
    delta = np.asarray(delta_q, dtype=float).copy()
    max_abs = float(np.max(np.abs(delta))) if delta.size else 0.0
    if max_abs > MAX_SAFE_PROGRESS_JOINT_STEP_RAD:
        delta *= MAX_SAFE_PROGRESS_JOINT_STEP_RAD / max_abs
    return delta


def _normalized(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(value))
    if norm <= 1e-10:
        return np.zeros_like(value)
    return value / norm


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


def _proximal_clearance_gradient(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    structural_neighbor_distance: int,
) -> np.ndarray:
    gradient = np.zeros(4, dtype=float)
    saved_q = data.qpos[qpos_ids].copy()
    try:
        for index in range(4):
            samples: list[tuple[float, float]] = []
            for sign in (-1.0, 1.0):
                data.qpos[qpos_ids] = saved_q
                data.qpos[int(qpos_ids[index])] = (
                    saved_q[index] + sign * RECONFIGURE_FINITE_DIFFERENCE_RAD
                )
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                actual = float(data.qpos[int(qpos_ids[index])])
                mujoco.mj_forward(model, data)
                clearance = _clearance(
                    model,
                    data,
                    context,
                    structural_neighbor_distance,
                )
                # Only the near-boundary geometry should dominate the local
                # derivative. Saturation also keeps absent contacts finite.
                clearance = min(clearance, 0.030)
                samples.append((actual, clearance))
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                gradient[index] = (samples[1][1] - samples[0][1]) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def _try_nullspace_reconfigure(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    dof_ids: np.ndarray,
    position_body: int,
    structural_neighbor_distance: int,
    previous_direction: np.ndarray | None,
) -> tuple[bool, float, float, float, np.ndarray | None, str | None]:
    """Increase clearance by changing proximal redundancy at nearly fixed wrist XYZ."""
    start_q = data.qpos[qpos_ids].copy()
    start_wrist = data.xpos[int(position_body)].copy()
    start_clearance = _clearance(
        model, data, context, structural_neighbor_distance
    )

    gradient = _proximal_clearance_gradient(
        base,
        model,
        data,
        context,
        qpos_ids,
        structural_neighbor_distance,
    )
    raw_gradient_direction = _normalized(gradient)
    if not np.any(raw_gradient_direction):
        return False, start_clearance, 0.0, 0.0, previous_direction, "no_clearance_gradient"

    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    mujoco.mj_jacBody(model, data, jacp, jacr, int(position_body))
    position_jacobian = jacp[:, dof_ids[:4]]
    projector = _exact_nullspace_projector(position_jacobian)
    raw_direction = _normalized(projector @ raw_gradient_direction)
    if not np.any(raw_direction):
        return False, start_clearance, 0.0, 0.0, previous_direction, "no_nullspace_clearance_direction"

    if previous_direction is None:
        direction = raw_direction
    else:
        blended = (
            (1.0 - RECONFIGURE_DIRECTION_SMOOTHING_ALPHA) * previous_direction
            + RECONFIGURE_DIRECTION_SMOOTHING_ALPHA * raw_direction
        )
        direction = _normalized(blended)
        if not np.any(direction):
            direction = raw_direction

    max_component = float(np.max(np.abs(direction)))
    if max_component <= 1e-10:
        return False, start_clearance, 0.0, 0.0, previous_direction, "no_reconfigure_direction"

    step = direction / max_component * RECONFIGURE_MAX_STEP_RAD
    step[3] = float(
        np.clip(
            step[3],
            -RECONFIGURE_ELBOW_MAX_STEP_RAD,
            RECONFIGURE_ELBOW_MAX_STEP_RAD,
        )
    )

    for line_index in range(RECONFIGURE_LINE_SEARCH_STEPS):
        scale = 0.5 ** line_index
        data.qpos[qpos_ids[:4]] = start_q[:4] + scale * step
        data.qpos[qpos_ids[4:]] = start_q[4:]
        base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
        mujoco.mj_forward(model, data)

        if base.has_right_arm_core_contact(model, data, context):
            continue

        trial_clearance = _clearance(
            model, data, context, structural_neighbor_distance
        )
        primary_drift = float(
            np.linalg.norm(data.xpos[int(position_body)] - start_wrist)
        )
        if (
            trial_clearance
            >= start_clearance + RECONFIGURE_MIN_CLEARANCE_IMPROVEMENT_M
            and primary_drift <= RECONFIGURE_MAX_PRIMARY_DRIFT_M
        ):
            step_deg = float(
                np.linalg.norm(np.degrees(data.qpos[qpos_ids[:4]] - start_q[:4]))
            )
            return (
                True,
                trial_clearance,
                step_deg,
                primary_drift,
                direction.copy(),
                None,
            )

    data.qpos[qpos_ids] = start_q
    mujoco.mj_forward(model, data)
    return False, start_clearance, 0.0, 0.0, previous_direction, "no_improving_reconfigure_step"


def install_clearance_recovery_supervisor(base: ModuleType) -> None:
    """Install continuous safe progress plus blocked-boundary reconfiguration."""
    if getattr(base, "_CLEARANCE_RECOVERY_SUPERVISOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    previous_reconfigure_direction: np.ndarray | None = None

    base.RUNTIME_SAFE_PROGRESS_ACTIVE = False
    base.RUNTIME_SAFE_PROGRESS_BEFORE_M = None
    base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M = None
    base.RUNTIME_SAFE_PROGRESS_AFTER_M = None
    base.RUNTIME_SAFE_PROGRESS_SCALE = 1.0
    base.RUNTIME_SAFE_PROGRESS_JOINT_STEP_DEG = 0.0
    base.RUNTIME_SAFE_PROGRESS_BLOCKED = False
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_ACTIVE = False
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BEFORE_M = None
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_AFTER_M = None
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_STEP_DEG = 0.0
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_WRIST_DRIFT_M = 0.0
    base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BLOCKED_REASON = None

    # Legacy dashboard fields remain permanently false; there is no latch/hold.
    base.RUNTIME_SAFETY_RECOVERY_LATCHED = False
    base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = False

    def supervised_solver(*args: Any, **kwargs: Any):
        nonlocal previous_reconfigure_direction

        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if model is None or data is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or dof_ids.size < 7 or position_body is None:
            return original_solver(*args, **kwargs)

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        mujoco.mj_forward(model, data)
        start_q = data.qpos[qpos_ids].copy()
        before = _clearance(model, data, context, structural_neighbor_distance)

        result = original_solver(*args, **kwargs)
        mujoco.mj_forward(model, data)
        candidate_q = data.qpos[qpos_ids].copy()
        candidate_clearance = _clearance(
            model, data, context, structural_neighbor_distance
        )

        active = False
        blocked = False
        scale = 1.0
        accepted_q = candidate_q.copy()
        accepted_clearance = candidate_clearance
        reconfigure_active = False
        reconfigure_before = None
        reconfigure_after = None
        reconfigure_step_deg = 0.0
        reconfigure_wrist_drift = 0.0
        reconfigure_blocked_reason = None

        if (
            before >= SAFE_PROGRESS_CLEARANCE_M
            and candidate_clearance < SAFE_PROGRESS_CLEARANCE_M
        ):
            active = True
            delta_q = _bounded_delta(candidate_q - start_q)
            target_clearance = min(
                before,
                SAFE_PROGRESS_CLEARANCE_M + SAFE_PROGRESS_MARGIN_M,
            )
            low = 0.0
            high = 1.0
            for _ in range(BISECTION_STEPS):
                mid = 0.5 * (low + high)
                data.qpos[qpos_ids] = start_q + mid * delta_q
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)
                clearance_mid = _clearance(
                    model, data, context, structural_neighbor_distance
                )
                if (
                    clearance_mid >= target_clearance
                    and not base.has_right_arm_core_contact(model, data, context)
                ):
                    low = mid
                else:
                    high = mid

            if low >= MIN_PROGRESS_SCALE:
                scale = float(low)
                accepted_q = start_q + scale * delta_q
                data.qpos[qpos_ids] = accepted_q
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)
                accepted_clearance = _clearance(
                    model, data, context, structural_neighbor_distance
                )
                result = data.xpos[int(position_body)].copy()
            else:
                # Cartesian advance is blocked at the soft boundary. Restore the
                # safe pose, then use redundancy to open clearance without moving
                # the wrist target appreciably.
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                reconfigure_before = before
                (
                    reconfigure_active,
                    reconfigure_after_value,
                    reconfigure_step_deg,
                    reconfigure_wrist_drift,
                    previous_reconfigure_direction,
                    reconfigure_blocked_reason,
                ) = _try_nullspace_reconfigure(
                    base,
                    model,
                    data,
                    context,
                    qpos_ids,
                    dof_ids,
                    int(position_body),
                    structural_neighbor_distance,
                    previous_reconfigure_direction,
                )
                if reconfigure_active:
                    accepted_q = data.qpos[qpos_ids].copy()
                    accepted_clearance = reconfigure_after_value
                    reconfigure_after = reconfigure_after_value
                    blocked = False
                    scale = 0.0
                    result = data.xpos[int(position_body)].copy()
                else:
                    accepted_q = start_q.copy()
                    accepted_clearance = before
                    reconfigure_after = before
                    scale = 0.0
                    blocked = True
                    result = data.xpos[int(position_body)].copy()

        elif before < SAFE_PROGRESS_CLEARANCE_M:
            if candidate_clearance > before:
                # If ordinary tracking itself moves outward, accept it.
                accepted_q = candidate_q.copy()
                accepted_clearance = candidate_clearance
                previous_reconfigure_direction = None
            else:
                active = True
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                reconfigure_before = before
                (
                    reconfigure_active,
                    reconfigure_after_value,
                    reconfigure_step_deg,
                    reconfigure_wrist_drift,
                    previous_reconfigure_direction,
                    reconfigure_blocked_reason,
                ) = _try_nullspace_reconfigure(
                    base,
                    model,
                    data,
                    context,
                    qpos_ids,
                    dof_ids,
                    int(position_body),
                    structural_neighbor_distance,
                    previous_reconfigure_direction,
                )
                if reconfigure_active:
                    accepted_q = data.qpos[qpos_ids].copy()
                    accepted_clearance = reconfigure_after_value
                    reconfigure_after = reconfigure_after_value
                    scale = 0.0
                    result = data.xpos[int(position_body)].copy()
                else:
                    accepted_q = start_q.copy()
                    accepted_clearance = before
                    reconfigure_after = before
                    scale = 0.0
                    blocked = True
                    result = data.xpos[int(position_body)].copy()
        else:
            previous_reconfigure_direction = None

        joint_step_deg = float(
            np.linalg.norm(np.degrees(accepted_q - start_q))
        )

        base.RUNTIME_SAFE_PROGRESS_ACTIVE = bool(active)
        base.RUNTIME_SAFE_PROGRESS_BEFORE_M = None if math.isinf(before) else float(before)
        base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M = (
            None if math.isinf(candidate_clearance) else float(candidate_clearance)
        )
        base.RUNTIME_SAFE_PROGRESS_AFTER_M = (
            None if math.isinf(accepted_clearance) else float(accepted_clearance)
        )
        base.RUNTIME_SAFE_PROGRESS_SCALE = float(scale)
        base.RUNTIME_SAFE_PROGRESS_JOINT_STEP_DEG = joint_step_deg
        base.RUNTIME_SAFE_PROGRESS_BLOCKED = bool(blocked)
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_ACTIVE = bool(reconfigure_active)
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BEFORE_M = reconfigure_before
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_AFTER_M = reconfigure_after
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_STEP_DEG = float(reconfigure_step_deg)
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_WRIST_DRIFT_M = float(
            reconfigure_wrist_drift
        )
        base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BLOCKED_REASON = (
            reconfigure_blocked_reason
        )
        base.RUNTIME_SAFETY_RECOVERY_LATCHED = False
        base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = False

        context["safe_progress_active"] = bool(active)
        context["safe_progress_before_m"] = base.RUNTIME_SAFE_PROGRESS_BEFORE_M
        context["safe_progress_candidate_m"] = base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M
        context["safe_progress_after_m"] = base.RUNTIME_SAFE_PROGRESS_AFTER_M
        context["safe_progress_scale"] = float(scale)
        context["safe_progress_blocked"] = bool(blocked)
        context["safe_progress_reconfigure_active"] = bool(reconfigure_active)
        context["safe_progress_reconfigure_before_m"] = reconfigure_before
        context["safe_progress_reconfigure_after_m"] = reconfigure_after
        context["safe_progress_reconfigure_step_deg"] = float(reconfigure_step_deg)
        context["safe_progress_reconfigure_wrist_drift_m"] = float(
            reconfigure_wrist_drift
        )
        context["safe_progress_reconfigure_blocked_reason"] = (
            reconfigure_blocked_reason
        )
        context["safety_recovery_latched"] = False
        context["safety_recovery_wrist_hold"] = False
        return result

    base.solve_right_arm_target = supervised_solver
    base._CLEARANCE_RECOVERY_SUPERVISOR_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_CLEARANCE_RECOVERY_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["safe_progress_active"] = bool(base.RUNTIME_SAFE_PROGRESS_ACTIVE)
            enriched["safe_progress_clearance_m"] = SAFE_PROGRESS_CLEARANCE_M
            enriched["safe_progress_margin_m"] = SAFE_PROGRESS_MARGIN_M
            enriched["safe_progress_before_m"] = base.RUNTIME_SAFE_PROGRESS_BEFORE_M
            enriched["safe_progress_candidate_m"] = base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M
            enriched["safe_progress_after_m"] = base.RUNTIME_SAFE_PROGRESS_AFTER_M
            enriched["safe_progress_scale"] = float(base.RUNTIME_SAFE_PROGRESS_SCALE)
            enriched["safe_progress_joint_step_deg"] = float(
                base.RUNTIME_SAFE_PROGRESS_JOINT_STEP_DEG
            )
            enriched["safe_progress_blocked"] = bool(base.RUNTIME_SAFE_PROGRESS_BLOCKED)
            enriched["safe_progress_reconfigure_active"] = bool(
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_ACTIVE
            )
            enriched["safe_progress_reconfigure_before_m"] = (
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BEFORE_M
            )
            enriched["safe_progress_reconfigure_after_m"] = (
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_AFTER_M
            )
            enriched["safe_progress_reconfigure_step_deg"] = float(
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_STEP_DEG
            )
            enriched["safe_progress_reconfigure_wrist_drift_m"] = float(
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_WRIST_DRIFT_M
            )
            enriched["safe_progress_reconfigure_max_wrist_drift_m"] = (
                RECONFIGURE_MAX_PRIMARY_DRIFT_M
            )
            enriched["safe_progress_reconfigure_blocked_reason"] = (
                base.RUNTIME_SAFE_PROGRESS_RECONFIGURE_BLOCKED_REASON
            )
            enriched["safety_recovery_latched"] = False
            enriched["safety_recovery_wrist_hold"] = False
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._CLEARANCE_RECOVERY_STATUS_INSTALLED = True
