"""Bounded-drift fallback for blocked safe-progress reconfiguration.

The normal safe-progress supervisor first tries exact wrist-position null-space
reconfiguration. Some right-arm configurations have no clearance-improving
motion in that one-dimensional null space. This outer fallback is dormant unless
safe progress is blocked and the exact reconfigure failed. It then permits a
small temporary wrist-position drift while moving only the four proximal joints
along the MuJoCo clearance gradient. Subsequent tracking cycles recover the wrist
position after the arm has opened a safer redundancy branch.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


FINITE_DIFFERENCE_RAD = math.radians(0.5)
MAX_PROXIMAL_STEP_RAD = math.radians(0.35)
MAX_ELBOW_STEP_RAD = math.radians(0.25)
MAX_WRIST_DRIFT_M = 0.002
MIN_CLEARANCE_IMPROVEMENT_M = 1e-7
LINE_SEARCH_STEPS = 8
DIRECTION_SMOOTHING_ALPHA = 0.35


def _clearance(model: Any, data: Any, context: dict[str, Any], structural_neighbor_distance: int) -> float:
    value = dangerous_contact_clearance_m(
        model,
        data,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    return math.inf if value is None else float(value)


def _normalized(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(value))
    return value / norm if norm > 1e-10 else np.zeros_like(value)


def _gradient(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    structural_neighbor_distance: int,
) -> np.ndarray:
    saved_q = data.qpos[qpos_ids].copy()
    gradient = np.zeros(4, dtype=float)
    try:
        for index in range(4):
            samples: list[tuple[float, float]] = []
            for sign in (-1.0, 1.0):
                data.qpos[qpos_ids] = saved_q
                data.qpos[int(qpos_ids[index])] = saved_q[index] + sign * FINITE_DIFFERENCE_RAD
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                actual = float(data.qpos[int(qpos_ids[index])])
                mujoco.mj_forward(model, data)
                clearance = min(
                    _clearance(model, data, context, structural_neighbor_distance),
                    0.030,
                )
                samples.append((actual, clearance))
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                gradient[index] = (samples[1][1] - samples[0][1]) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def install_bounded_reconfigure_escape(base: ModuleType) -> None:
    if getattr(base, "_BOUNDED_RECONFIGURE_ESCAPE_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    previous_direction: np.ndarray | None = None

    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_ACTIVE = False
    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BEFORE_M = None
    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_AFTER_M = None
    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_STEP_DEG = 0.0
    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_WRIST_DRIFT_M = 0.0
    base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BLOCKED_REASON = None

    def solver(*args: Any, **kwargs: Any):
        nonlocal previous_direction

        result = original_solver(*args, **kwargs)
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if model is None or data is None or not isinstance(context, dict):
            return result

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or position_body is None:
            return result

        blocked = bool(getattr(base, "RUNTIME_SAFE_PROGRESS_BLOCKED", False))
        exact_active = bool(
            getattr(base, "RUNTIME_SAFE_PROGRESS_RECONFIGURE_ACTIVE", False)
        )

        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_ACTIVE = False
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BEFORE_M = None
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_AFTER_M = None
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_STEP_DEG = 0.0
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_WRIST_DRIFT_M = 0.0
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BLOCKED_REASON = None

        if not blocked or exact_active:
            if not blocked:
                previous_direction = None
            return result

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        mujoco.mj_forward(model, data)
        start_q = data.qpos[qpos_ids].copy()
        start_wrist = data.xpos[int(position_body)].copy()
        before = _clearance(model, data, context, structural_neighbor_distance)

        direction = _normalized(
            _gradient(
                base,
                model,
                data,
                context,
                qpos_ids,
                structural_neighbor_distance,
            )
        )
        if not np.any(direction):
            base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BLOCKED_REASON = "no_clearance_gradient"
            return result

        if previous_direction is not None:
            blended = (
                (1.0 - DIRECTION_SMOOTHING_ALPHA) * previous_direction
                + DIRECTION_SMOOTHING_ALPHA * direction
            )
            smooth_direction = _normalized(blended)
            if np.any(smooth_direction):
                direction = smooth_direction

        max_component = float(np.max(np.abs(direction)))
        step = direction / max(max_component, 1e-12) * MAX_PROXIMAL_STEP_RAD
        step[3] = float(np.clip(step[3], -MAX_ELBOW_STEP_RAD, MAX_ELBOW_STEP_RAD))

        accepted = False
        accepted_clearance = before
        accepted_drift = 0.0
        accepted_step = np.zeros(4, dtype=float)
        for line_index in range(LINE_SEARCH_STEPS):
            scale = 0.5 ** line_index
            data.qpos[qpos_ids[:4]] = start_q[:4] + scale * step
            data.qpos[qpos_ids[4:]] = start_q[4:]
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)

            if base.has_right_arm_core_contact(model, data, context):
                continue

            clearance = _clearance(model, data, context, structural_neighbor_distance)
            wrist_drift = float(
                np.linalg.norm(data.xpos[int(position_body)] - start_wrist)
            )
            if (
                clearance >= before + MIN_CLEARANCE_IMPROVEMENT_M
                and wrist_drift <= MAX_WRIST_DRIFT_M
            ):
                accepted = True
                accepted_clearance = clearance
                accepted_drift = wrist_drift
                accepted_step = data.qpos[qpos_ids[:4]] - start_q[:4]
                break

        if not accepted:
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BLOCKED_REASON = (
                "no_improving_bounded_reconfigure_step"
            )
            return result

        previous_direction = direction.copy()
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_ACTIVE = True
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BEFORE_M = before
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_AFTER_M = accepted_clearance
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_STEP_DEG = float(
            np.linalg.norm(np.degrees(accepted_step))
        )
        base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_WRIST_DRIFT_M = accepted_drift

        # The fallback has successfully replaced the blocked hold with a
        # clearance-opening configuration step.
        base.RUNTIME_SAFE_PROGRESS_BLOCKED = False
        base.RUNTIME_SAFE_PROGRESS_AFTER_M = accepted_clearance
        base.RUNTIME_SAFE_PROGRESS_JOINT_STEP_DEG = float(
            np.linalg.norm(np.degrees(data.qpos[qpos_ids] - start_q))
        )
        context["safe_progress_blocked"] = False
        context["safe_progress_after_m"] = accepted_clearance
        context["safe_progress_bounded_reconfigure_active"] = True
        return data.xpos[int(position_body)].copy()

    base.solve_right_arm_target = solver
    base._BOUNDED_RECONFIGURE_ESCAPE_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_BOUNDED_RECONFIGURE_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["safe_progress_bounded_reconfigure_active"] = bool(
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_ACTIVE
            )
            enriched["safe_progress_bounded_reconfigure_before_m"] = (
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BEFORE_M
            )
            enriched["safe_progress_bounded_reconfigure_after_m"] = (
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_AFTER_M
            )
            enriched["safe_progress_bounded_reconfigure_step_deg"] = float(
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_STEP_DEG
            )
            enriched["safe_progress_bounded_reconfigure_wrist_drift_m"] = float(
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_WRIST_DRIFT_M
            )
            enriched["safe_progress_bounded_reconfigure_max_wrist_drift_m"] = (
                MAX_WRIST_DRIFT_M
            )
            enriched["safe_progress_bounded_reconfigure_blocked_reason"] = (
                base.RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_BLOCKED_REASON
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._BOUNDED_RECONFIGURE_STATUS_INSTALLED = True
