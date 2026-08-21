"""Primary-task monotonicity guard for the configured right-arm IK stack."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


PRIMARY_TASK_WORSENING_TOLERANCE_M = 1e-6
TORSO_PREPOSE_DEFAULT_MAX_WRIST_DRIFT_M = 0.005


def should_reject_primary_step(
    start_error_m: float,
    final_error_m: float,
    *,
    tolerance_m: float = PRIMARY_TASK_WORSENING_TOLERANCE_M,
) -> bool:
    if not math.isfinite(start_error_m) or not math.isfinite(final_error_m):
        return True
    if tolerance_m < 0.0 or not math.isfinite(tolerance_m):
        raise ValueError("tolerance_m must be finite and >= 0")
    return final_error_m > start_error_m + tolerance_m


def _inspection_contact_blocks_fallback(base: ModuleType, context: dict[str, Any]) -> bool:
    supervisor = getattr(base, "IK_FALLBACK_SUPERVISOR", None)
    settings = getattr(supervisor, "settings", None)
    if settings is None or bool(getattr(settings, "allow_during_inspection_contact", False)):
        return False
    state = str(getattr(base, "RUNTIME_INSPECTION_STATE", "free_space"))
    return bool(
        context.get("task_contact_active", False)
        or state in {"contact_acquire", "inspection_contact", "surface_follow"}
    )


def _can_escalate_to_fallback(base: ModuleType, context: dict[str, Any]) -> bool:
    supervisor = getattr(base, "IK_FALLBACK_SUPERVISOR", None)
    settings = getattr(supervisor, "settings", None)
    if supervisor is None or settings is None or not bool(getattr(settings, "enabled", False)):
        return False
    if bool(getattr(supervisor, "active", False)):
        return False
    if _inspection_contact_blocks_fallback(base, context):
        return False
    if getattr(base, "RUNTIME_COLLISION_NEAREST_STATUS", None) == "environment_obstacle":
        return False
    return True


def _prepose_candidate_within_anchor_limit(
    data: Any,
    context: dict[str, Any],
) -> tuple[bool, float | None, float | None]:
    """Check absolute wrist drift from the fixed torso-prepose anchor.

    The pre-pose is allowed to trade a few millimeters of wrist position for a
    large elbow configuration change, but the allowance is absolute from the
    entry anchor rather than additive per cycle. This prevents cumulative wrist
    migration while still allowing the elbow null-space task to make progress.
    """
    if not bool(context.get("torso_prepose_holding_wrist", False)):
        return False, None, None
    anchor = context.get("torso_prepose_wrist_anchor")
    position_body = context.get("position_body")
    if anchor is None or position_body is None:
        return False, None, None
    anchor_value = np.asarray(anchor, dtype=float)
    if anchor_value.shape != (3,) or not np.all(np.isfinite(anchor_value)):
        return False, None, None
    max_drift = float(
        context.get(
            "torso_prepose_max_wrist_drift_m",
            TORSO_PREPOSE_DEFAULT_MAX_WRIST_DRIFT_M,
        )
    )
    wrist = np.asarray(data.xpos[int(position_body)], dtype=float)
    drift = float(np.linalg.norm(wrist - anchor_value))
    return True, drift, max_drift


def install_primary_task_guard(
    base: ModuleType,
    *,
    tolerance_m: float = PRIMARY_TASK_WORSENING_TOLERANCE_M,
) -> None:
    if tolerance_m < 0.0 or not math.isfinite(tolerance_m):
        raise ValueError("tolerance_m must be finite and >= 0")

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before installing guard")
    if getattr(base, "_PRIMARY_TASK_GUARD_INSTALLED", False):
        return

    base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = False
    base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED = False
    base.RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M = None
    base.RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M = None
    base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M = None
    base.RUNTIME_IK_PRIMARY_GUARD_APPLIED_TOLERANCE_M = float(tolerance_m)
    base.RUNTIME_IK_PRIMARY_GUARD_PREPOSE_DRIFT_M = None

    def guarded_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]

        base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = False
        base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED = False
        base.RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M = None
        base.RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M = None
        base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M = None
        base.RUNTIME_IK_PRIMARY_GUARD_APPLIED_TOLERANCE_M = float(tolerance_m)
        base.RUNTIME_IK_PRIMARY_GUARD_PREPOSE_DRIFT_M = None

        if (
            model is None or data is None or target is None
            or not isinstance(context, dict)
            or context.get("position_body") is None
            or context.get("right_qpos_ids") is None
        ):
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        if target_position.shape != (3,) or not np.all(np.isfinite(target_position)):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
        position_body = int(context["position_body"])
        start_q = data.qpos[qpos_ids].copy()
        start_error = float(np.linalg.norm(target_position - data.xpos[position_body]))

        result = original_solver(*args, **kwargs)
        candidate_error = float(np.linalg.norm(target_position - data.xpos[position_body]))
        base.RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M = start_error
        base.RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M = candidate_error

        prepose_check, prepose_drift, max_prepose_drift = _prepose_candidate_within_anchor_limit(
            data, context
        )
        if prepose_check:
            base.RUNTIME_IK_PRIMARY_GUARD_APPLIED_TOLERANCE_M = float(max_prepose_drift)
            base.RUNTIME_IK_PRIMARY_GUARD_PREPOSE_DRIFT_M = float(prepose_drift)
            context["ik_primary_guard_applied_tolerance_m"] = float(max_prepose_drift)
            context["ik_primary_guard_prepose_drift_m"] = float(prepose_drift)
            # Keep any collision authority strict. This special acceptance only
            # replaces primary-task monotonicity while the wrist is deliberately
            # held for elbow pre-positioning.
            collision_now = False
            try:
                collision_now = bool(base.has_right_arm_core_contact(model, data, context))
            except Exception:
                collision_now = True
            if (
                not collision_now
                and not bool(context.get("collision_limited", False))
                and float(prepose_drift) <= float(max_prepose_drift) + 1e-9
            ):
                return result
        else:
            context["ik_primary_guard_applied_tolerance_m"] = float(tolerance_m)

        if not should_reject_primary_step(start_error, candidate_error, tolerance_m=tolerance_m):
            return result

        data.qpos[qpos_ids] = start_q
        import mujoco
        mujoco.mj_forward(model, data)
        base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = True
        context["ik_primary_guard_reverted"] = True

        # Do not trigger coupled recovery during the deliberate elbow pre-pose.
        # The whole point of this state is to reconfigure the elbow while holding
        # the fixed wrist anchor; a coupled retry would undo that posture task.
        if not prepose_check and _can_escalate_to_fallback(base, context):
            supervisor = base.IK_FALLBACK_SUPERVISOR
            supervisor.active = True
            supervisor.bad_frames = 0
            supervisor.good_frames = 0
            base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED = True
            context["ik_primary_guard_fallback_triggered"] = True

            recovery_result = original_solver(*args, **kwargs)
            recovery_error = float(np.linalg.norm(target_position - data.xpos[position_body]))
            base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M = recovery_error
            if not should_reject_primary_step(start_error, recovery_error, tolerance_m=tolerance_m):
                base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = False
                context["ik_primary_guard_reverted"] = False
                return recovery_result

            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)

        restored_error = float(np.linalg.norm(target_position - data.xpos[position_body]))
        base.RUNTIME_IK_POSITION_ERROR_M = restored_error
        return data.xpos[position_body].copy()

    base.solve_right_arm_target = guarded_solver
    base._PRIMARY_TASK_GUARD_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_PRIMARY_TASK_GUARD_STATUS_INSTALLED", False):
        def primary_guard_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["ik_primary_guard_reverted"] = bool(base.RUNTIME_IK_PRIMARY_GUARD_REVERTED)
            enriched["ik_primary_guard_fallback_triggered"] = bool(base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED)
            enriched["ik_primary_guard_start_error_m"] = base.RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M
            enriched["ik_primary_guard_candidate_error_m"] = base.RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M
            enriched["ik_primary_guard_recovery_error_m"] = base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M
            enriched["ik_primary_guard_tolerance_m"] = float(tolerance_m)
            enriched["ik_primary_guard_applied_tolerance_m"] = float(
                base.RUNTIME_IK_PRIMARY_GUARD_APPLIED_TOLERANCE_M
            )
            enriched["ik_primary_guard_prepose_drift_m"] = (
                base.RUNTIME_IK_PRIMARY_GUARD_PREPOSE_DRIFT_M
            )
            original_status_writer(enriched)

        base.write_runtime_status = primary_guard_status_writer
        base._PRIMARY_TASK_GUARD_STATUS_INSTALLED = True
