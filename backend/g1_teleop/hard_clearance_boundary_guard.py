"""Hard right-arm clearance guard with safe-side configuration escape.

When a solver update would cross from the safe side of the 5 mm robot-clearance
floor, first try to change shoulder/elbow configuration from the last safe pose
along a clearance-improving Cartesian null-space direction. Only if that escape
is unavailable do we clip the original solver update at the clearance boundary.
If already inside the floor, only strictly improving recovery steps are accepted.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


HARD_CLEARANCE_FLOOR_M = 0.005
RECOVERY_IMPROVEMENT_EPS_M = 1e-9
BOUNDARY_MARGIN_M = 2e-5
BOUNDARY_BISECTION_STEPS = 14
FINITE_DIFFERENCE_RAD = math.radians(0.5)
BOUNDARY_ESCAPE_MAX_STEP_RAD = math.radians(0.18)
BOUNDARY_ESCAPE_ELBOW_MAX_STEP_RAD = math.radians(0.12)
BOUNDARY_ESCAPE_MAX_PRIMARY_DRIFT_M = 0.001
BOUNDARY_ESCAPE_LINE_SEARCH_STEPS = 8


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
                actual = float(data.qpos[int(qpos_ids[index])])
                mujoco.mj_forward(model, data)
                samples.append(
                    (actual, _clearance(model, data, context, structural_neighbor_distance))
                )
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                gradient[index] = (samples[1][1] - samples[0][1]) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def install_boundary_hard_clearance_floor(base: ModuleType) -> None:
    """Install a 5 mm floor with safe-side configuration escape."""
    if getattr(base, "_HARD_CLEARANCE_FLOOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_HARD_CLEARANCE_REVERTED = False
    base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE = False
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_CLIPPED = False
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_SCALE = 1.0
    base.RUNTIME_HARD_CLEARANCE_BEFORE_M = None
    base.RUNTIME_HARD_CLEARANCE_AFTER_M = None
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_ACTIVE = False
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_STEP_DEG = 0.0
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_BEFORE_M = None
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_AFTER_M = None
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_PRIMARY_DRIFT_M = 0.0

    def guarded_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if model is None or data is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7:
            return original_solver(*args, **kwargs)

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        start_q = data.qpos[qpos_ids].copy()
        before = _clearance(model, data, context, structural_neighbor_distance)
        start_wrist = None
        if position_body is not None:
            start_wrist = data.xpos[int(position_body)].copy()

        result = original_solver(*args, **kwargs)
        candidate_q = data.qpos[qpos_ids].copy()
        after_candidate = _clearance(model, data, context, structural_neighbor_distance)

        recovery_active = before < HARD_CLEARANCE_FLOOR_M
        reverted = False
        boundary_clipped = False
        boundary_scale = 1.0
        accepted_after = after_candidate
        boundary_escape_active = False
        boundary_escape_step_deg = 0.0
        boundary_escape_before = None
        boundary_escape_after = None
        boundary_escape_primary_drift = 0.0

        if recovery_active:
            if after_candidate <= before + RECOVERY_IMPROVEMENT_EPS_M:
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                reverted = True
                boundary_scale = 0.0
                accepted_after = before
        elif after_candidate < HARD_CLEARANCE_FLOOR_M:
            # The full Cartesian solution crosses the safety floor. Restore the
            # last safe configuration and first try to move only along a proximal
            # Cartesian null-space direction that increases robot clearance.
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            escaped = False

            if dof_ids.size >= 4 and position_body is not None:
                gradient = _proximal_clearance_gradient(
                    base,
                    model,
                    data,
                    context,
                    qpos_ids,
                    start_q,
                    structural_neighbor_distance,
                )
                gradient_norm = float(np.linalg.norm(gradient))
                if gradient_norm > 1e-10:
                    jacp = np.zeros((3, model.nv))
                    jacr = np.zeros((3, model.nv))
                    mujoco.mj_jacBody(model, data, jacp, jacr, int(position_body))
                    projector = _exact_nullspace_projector(jacp[:, dof_ids[:4]])
                    direction = projector @ (gradient / gradient_norm)
                    direction_norm = float(np.linalg.norm(direction))
                    if direction_norm > 1e-8:
                        direction /= direction_norm
                        max_component = float(np.max(np.abs(direction)))
                        step = (
                            direction
                            / max(max_component, 1e-12)
                            * BOUNDARY_ESCAPE_MAX_STEP_RAD
                        )
                        step[3] = float(
                            np.clip(
                                step[3],
                                -BOUNDARY_ESCAPE_ELBOW_MAX_STEP_RAD,
                                BOUNDARY_ESCAPE_ELBOW_MAX_STEP_RAD,
                            )
                        )
                        for line_index in range(BOUNDARY_ESCAPE_LINE_SEARCH_STEPS):
                            scale = 0.5 ** line_index
                            data.qpos[qpos_ids[:4]] = start_q[:4] + scale * step
                            data.qpos[qpos_ids[4:]] = start_q[4:]
                            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                            mujoco.mj_forward(model, data)
                            trial_clearance = _clearance(
                                model, data, context, structural_neighbor_distance
                            )
                            if base.has_right_arm_core_contact(model, data, context):
                                continue
                            primary_drift = 0.0
                            if start_wrist is not None:
                                primary_drift = float(
                                    np.linalg.norm(
                                        data.xpos[int(position_body)] - start_wrist
                                    )
                                )
                            if (
                                trial_clearance > before + RECOVERY_IMPROVEMENT_EPS_M
                                and primary_drift <= BOUNDARY_ESCAPE_MAX_PRIMARY_DRIFT_M
                            ):
                                escaped = True
                                boundary_escape_active = True
                                boundary_escape_before = before
                                boundary_escape_after = trial_clearance
                                boundary_escape_step_deg = float(
                                    np.linalg.norm(
                                        np.degrees(data.qpos[qpos_ids[:4]] - start_q[:4])
                                    )
                                )
                                boundary_escape_primary_drift = primary_drift
                                accepted_after = trial_clearance
                                boundary_scale = 0.0
                                if position_body is not None:
                                    result = data.xpos[int(position_body)].copy()
                                break

            if not escaped:
                # Fallback: clip the unsafe full update at an adaptive boundary.
                # The reserve margin may never consume essentially all of the
                # clearance headroom, which previously caused scale=0 freezes.
                delta_q = candidate_q - start_q
                low = 0.0
                high = 1.0
                headroom = max(before - HARD_CLEARANCE_FLOOR_M, 0.0)
                adaptive_margin = min(BOUNDARY_MARGIN_M, 0.25 * headroom)
                target_clearance = HARD_CLEARANCE_FLOOR_M + adaptive_margin

                for _ in range(BOUNDARY_BISECTION_STEPS):
                    mid = 0.5 * (low + high)
                    data.qpos[qpos_ids] = start_q + mid * delta_q
                    mujoco.mj_forward(model, data)
                    clearance_mid = _clearance(
                        model, data, context, structural_neighbor_distance
                    )
                    if clearance_mid >= target_clearance:
                        low = mid
                    else:
                        high = mid

                if low > 1e-9:
                    data.qpos[qpos_ids] = start_q + low * delta_q
                    mujoco.mj_forward(model, data)
                    accepted_after = _clearance(
                        model, data, context, structural_neighbor_distance
                    )
                    boundary_clipped = True
                    boundary_scale = float(low)
                    if position_body is not None:
                        result = data.xpos[int(position_body)].copy()
                else:
                    data.qpos[qpos_ids] = start_q
                    mujoco.mj_forward(model, data)
                    reverted = True
                    boundary_scale = 0.0
                    accepted_after = before

        base.RUNTIME_HARD_CLEARANCE_REVERTED = bool(reverted)
        base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE = bool(recovery_active)
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_CLIPPED = bool(boundary_clipped)
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_SCALE = float(boundary_scale)
        base.RUNTIME_HARD_CLEARANCE_BEFORE_M = None if math.isinf(before) else before
        base.RUNTIME_HARD_CLEARANCE_AFTER_M = (
            None if math.isinf(accepted_after) else float(accepted_after)
        )
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_ACTIVE = bool(boundary_escape_active)
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_STEP_DEG = float(boundary_escape_step_deg)
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_BEFORE_M = boundary_escape_before
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_AFTER_M = boundary_escape_after
        base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_PRIMARY_DRIFT_M = float(
            boundary_escape_primary_drift
        )

        context["hard_clearance_floor_m"] = HARD_CLEARANCE_FLOOR_M
        context["hard_clearance_reverted"] = bool(reverted)
        context["hard_clearance_recovery_active"] = bool(recovery_active)
        context["hard_clearance_boundary_clipped"] = bool(boundary_clipped)
        context["hard_clearance_boundary_scale"] = float(boundary_scale)
        context["hard_clearance_boundary_escape_active"] = bool(boundary_escape_active)
        return result

    base.solve_right_arm_target = guarded_solver
    base._HARD_CLEARANCE_FLOOR_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_HARD_CLEARANCE_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["hard_clearance_floor_m"] = HARD_CLEARANCE_FLOOR_M
            enriched["hard_clearance_reverted"] = bool(
                base.RUNTIME_HARD_CLEARANCE_REVERTED
            )
            enriched["hard_clearance_recovery_active"] = bool(
                base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE
            )
            enriched["hard_clearance_boundary_clipped"] = bool(
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_CLIPPED
            )
            enriched["hard_clearance_boundary_scale"] = float(
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_SCALE
            )
            enriched["hard_clearance_before_m"] = base.RUNTIME_HARD_CLEARANCE_BEFORE_M
            enriched["hard_clearance_after_m"] = base.RUNTIME_HARD_CLEARANCE_AFTER_M
            enriched["hard_clearance_boundary_escape_active"] = bool(
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_ACTIVE
            )
            enriched["hard_clearance_boundary_escape_step_deg"] = float(
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_STEP_DEG
            )
            enriched["hard_clearance_boundary_escape_before_m"] = (
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_BEFORE_M
            )
            enriched["hard_clearance_boundary_escape_after_m"] = (
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_AFTER_M
            )
            enriched["hard_clearance_boundary_escape_primary_drift_m"] = float(
                base.RUNTIME_HARD_CLEARANCE_BOUNDARY_ESCAPE_PRIMARY_DRIFT_M
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._HARD_CLEARANCE_STATUS_INSTALLED = True
