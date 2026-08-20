"""Primary-task monotonicity guard for the configured right-arm IK stack.

The operator hand-follow lag is already represented by the filtered safe target.
This guard prevents the IK solver itself from adding extra lag by accepting a
joint update that moves the controlled wrist farther away from that safe target.
When the decoupled branch produces such a step, the guard may immediately arm
the already-installed coupled/multi-seed fallback and retry from the same cycle
start instead of waiting for the normal error hysteresis.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


PRIMARY_TASK_WORSENING_TOLERANCE_M = 1e-6


def should_reject_primary_step(
    start_error_m: float,
    final_error_m: float,
    *,
    tolerance_m: float = PRIMARY_TASK_WORSENING_TOLERANCE_M,
) -> bool:
    """Return True when a solver cycle worsens the primary position task."""
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
    # Environment obstacle handling owns the target while tangential avoidance
    # is active. Do not let IK branch recovery overwrite that authority.
    if getattr(base, "RUNTIME_COLLISION_NEAREST_STATUS", None) == "environment_obstacle":
        return False
    return True


def install_primary_task_guard(
    base: ModuleType,
    *,
    tolerance_m: float = PRIMARY_TASK_WORSENING_TOLERANCE_M,
) -> None:
    """Reject primary-task-worsening cycles and immediately try fallback once.

    Install this after collision, coupled/multi-seed fallback, and severe-error
    wrappers. The guard evaluates the final configured candidate. If the primary
    wrist-position task worsens while fallback is still inactive, it restores the
    cycle start, arms the existing fallback supervisor, and reruns the underlying
    configured stack once from exactly the same joint state.
    """
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

        if (
            model is None
            or data is None
            or target is None
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

        if not should_reject_primary_step(
            start_error,
            candidate_error,
            tolerance_m=tolerance_m,
        ):
            return result

        # Restore the exact cycle start before either holding or trying another
        # IK branch. This guarantees that fallback is not stacked on top of the
        # rejected decoupled joint update.
        data.qpos[qpos_ids] = start_q
        import mujoco

        mujoco.mj_forward(model, data)
        base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = True
        context["ik_primary_guard_reverted"] = True

        if _can_escalate_to_fallback(base, context):
            supervisor = base.IK_FALLBACK_SUPERVISOR
            supervisor.active = True
            supervisor.bad_frames = 0
            supervisor.good_frames = 0
            base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED = True
            context["ik_primary_guard_fallback_triggered"] = True

            recovery_result = original_solver(*args, **kwargs)
            recovery_error = float(
                np.linalg.norm(target_position - data.xpos[position_body])
            )
            base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M = recovery_error
            if not should_reject_primary_step(
                start_error,
                recovery_error,
                tolerance_m=tolerance_m,
            ):
                # The coupled/multi-seed retry recovered the primary task. Keep
                # its runtime IK mode/score diagnostics intact.
                base.RUNTIME_IK_PRIMARY_GUARD_REVERTED = False
                context["ik_primary_guard_reverted"] = False
                return recovery_result

            # Fallback also failed to descend. Preserve safety and continuity by
            # holding the original cycle state.
            data.qpos[qpos_ids] = start_q
            mujoco.mj_forward(model, data)

        restored_error = float(np.linalg.norm(target_position - data.xpos[position_body]))
        base.RUNTIME_IK_POSITION_ERROR_M = restored_error
        return data.xpos[position_body].copy()

    base.solve_right_arm_target = guarded_solver
    base._PRIMARY_TASK_GUARD_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(
        base, "_PRIMARY_TASK_GUARD_STATUS_INSTALLED", False
    ):
        def primary_guard_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["ik_primary_guard_reverted"] = bool(
                base.RUNTIME_IK_PRIMARY_GUARD_REVERTED
            )
            enriched["ik_primary_guard_fallback_triggered"] = bool(
                base.RUNTIME_IK_PRIMARY_GUARD_FALLBACK_TRIGGERED
            )
            enriched["ik_primary_guard_start_error_m"] = (
                base.RUNTIME_IK_PRIMARY_GUARD_START_ERROR_M
            )
            enriched["ik_primary_guard_candidate_error_m"] = (
                base.RUNTIME_IK_PRIMARY_GUARD_CANDIDATE_ERROR_M
            )
            enriched["ik_primary_guard_recovery_error_m"] = (
                base.RUNTIME_IK_PRIMARY_GUARD_RECOVERY_ERROR_M
            )
            enriched["ik_primary_guard_tolerance_m"] = float(tolerance_m)
            original_status_writer(enriched)

        base.write_runtime_status = primary_guard_status_writer
        base._PRIMARY_TASK_GUARD_STATUS_INSTALLED = True
