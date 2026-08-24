"""Continuous collision-safe progress supervisor for right-arm teleoperation.

The previous recovery latch could freeze tracking whenever a full IK candidate
crossed the safety region. This supervisor instead keeps the largest safe
fraction of every candidate update. It therefore preserves continuous motion
while preventing a single control cycle from stepping deeply toward the robot.
The existing 5 mm hard floor remains the final emergency guard.
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


def install_clearance_recovery_supervisor(base: ModuleType) -> None:
    """Install continuous safe-progress clipping outside the normal solver stack."""
    if getattr(base, "_CLEARANCE_RECOVERY_SUPERVISOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target

    base.RUNTIME_SAFE_PROGRESS_ACTIVE = False
    base.RUNTIME_SAFE_PROGRESS_BEFORE_M = None
    base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M = None
    base.RUNTIME_SAFE_PROGRESS_AFTER_M = None
    base.RUNTIME_SAFE_PROGRESS_SCALE = 1.0
    base.RUNTIME_SAFE_PROGRESS_JOINT_STEP_DEG = 0.0
    base.RUNTIME_SAFE_PROGRESS_BLOCKED = False

    # Legacy status names are kept so dashboards do not break, but there is no
    # longer a latched hold state.
    base.RUNTIME_SAFETY_RECOVERY_LATCHED = False
    base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = False

    def supervised_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if model is None or data is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or position_body is None:
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

        # Above the soft floor, an unsafe full candidate is clipped continuously
        # rather than rejected. Below the floor, only clearance-improving motion
        # is accepted so the existing emergency layers can recover naturally.
        if before >= SAFE_PROGRESS_CLEARANCE_M and candidate_clearance < SAFE_PROGRESS_CLEARANCE_M:
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
                # No meaningful inward progress is safe this cycle. Keep the
                # current pose instead of toggling between tracking and recovery.
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                accepted_q = start_q.copy()
                accepted_clearance = before
                scale = 0.0
                blocked = True
                result = data.xpos[int(position_body)].copy()

        elif before < SAFE_PROGRESS_CLEARANCE_M:
            if candidate_clearance <= before:
                active = True
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                accepted_q = start_q.copy()
                accepted_clearance = before
                scale = 0.0
                blocked = True
                result = data.xpos[int(position_body)].copy()

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
        base.RUNTIME_SAFETY_RECOVERY_LATCHED = False
        base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = False

        context["safe_progress_active"] = bool(active)
        context["safe_progress_before_m"] = base.RUNTIME_SAFE_PROGRESS_BEFORE_M
        context["safe_progress_candidate_m"] = base.RUNTIME_SAFE_PROGRESS_CANDIDATE_M
        context["safe_progress_after_m"] = base.RUNTIME_SAFE_PROGRESS_AFTER_M
        context["safe_progress_scale"] = float(scale)
        context["safe_progress_blocked"] = bool(blocked)
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
            enriched["safety_recovery_latched"] = False
            enriched["safety_recovery_wrist_hold"] = False
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._CLEARANCE_RECOVERY_STATUS_INSTALLED = True
