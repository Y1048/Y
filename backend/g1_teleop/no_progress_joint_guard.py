"""Reject large proximal joint motion that does not improve Cartesian tracking.

This guard is intentionally installed outside the normal geometry-aware solver
but inside emergency/collision recovery layers. It protects against IK branch
wandering when a difficult target causes shoulder/elbow motion without meaningful
wrist-position progress. Safety recovery remains authoritative near obstacles.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


TRACKING_ERROR_ENABLE_M = 0.030
MIN_PROXIMAL_STEP_DEG = 0.40
MIN_ERROR_IMPROVEMENT_M = 0.00010
SAFETY_BYPASS_CLEARANCE_M = 0.015
LINE_SEARCH_STEPS = 6


def install_no_progress_joint_guard(base: ModuleType) -> None:
    if getattr(base, "_NO_PROGRESS_JOINT_GUARD_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target

    base.RUNTIME_NO_PROGRESS_GUARD_ACTIVE = False
    base.RUNTIME_NO_PROGRESS_GUARD_REVERTED = False
    base.RUNTIME_NO_PROGRESS_GUARD_SCALE = 1.0
    base.RUNTIME_NO_PROGRESS_GUARD_START_ERROR_M = None
    base.RUNTIME_NO_PROGRESS_GUARD_CANDIDATE_ERROR_M = None
    base.RUNTIME_NO_PROGRESS_GUARD_AFTER_ERROR_M = None
    base.RUNTIME_NO_PROGRESS_GUARD_PROXIMAL_STEP_DEG = 0.0
    base.RUNTIME_NO_PROGRESS_GUARD_CLEARANCE_M = None
    base.RUNTIME_NO_PROGRESS_GUARD_BLOCKED_REASON = None

    def guarded_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]
        if model is None or data is None or target is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        if qpos_ids.size < 7 or position_body is None:
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        mujoco.mj_forward(model, data)
        start_q = data.qpos[qpos_ids].copy()
        start_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))

        result = original_solver(*args, **kwargs)
        mujoco.mj_forward(model, data)
        candidate_q = data.qpos[qpos_ids].copy()
        candidate_error = float(np.linalg.norm(target_position - data.xpos[int(position_body)]))
        proximal_step_deg = float(
            np.linalg.norm(np.degrees(candidate_q[:4] - start_q[:4]))
        )

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        clearance = dangerous_contact_clearance_m(
            model,
            data,
            context,
            structural_neighbor_distance=structural_neighbor_distance,
        )
        clearance_value = None if clearance is None else float(clearance)

        large_error = start_error >= TRACKING_ERROR_ENABLE_M
        large_joint_motion = proximal_step_deg >= MIN_PROXIMAL_STEP_DEG
        improvement = start_error - candidate_error
        insufficient_progress = improvement < MIN_ERROR_IMPROVEMENT_M
        safety_bypass = (
            clearance_value is not None
            and clearance_value <= SAFETY_BYPASS_CLEARANCE_M
        )

        active = bool(
            large_error
            and large_joint_motion
            and insufficient_progress
            and not safety_bypass
        )
        reverted = False
        accepted_scale = 1.0
        after_error = candidate_error
        blocked_reason = None

        if active:
            delta_q = candidate_q - start_q
            best_scale = 0.0
            best_error = start_error
            for line_index in range(1, LINE_SEARCH_STEPS + 1):
                scale = 0.5 ** line_index
                data.qpos[qpos_ids] = start_q + scale * delta_q
                base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)
                trial_error = float(
                    np.linalg.norm(target_position - data.xpos[int(position_body)])
                )
                if start_error - trial_error >= MIN_ERROR_IMPROVEMENT_M:
                    best_scale = float(scale)
                    best_error = trial_error
                    break

            if best_scale > 0.0:
                accepted_scale = best_scale
                after_error = best_error
                result = data.xpos[int(position_body)].copy()
                blocked_reason = "scaled_for_tracking_progress"
            else:
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                accepted_scale = 0.0
                after_error = start_error
                reverted = True
                result = data.xpos[int(position_body)].copy()
                blocked_reason = "no_cartesian_progress"

        base.RUNTIME_NO_PROGRESS_GUARD_ACTIVE = active
        base.RUNTIME_NO_PROGRESS_GUARD_REVERTED = reverted
        base.RUNTIME_NO_PROGRESS_GUARD_SCALE = float(accepted_scale)
        base.RUNTIME_NO_PROGRESS_GUARD_START_ERROR_M = float(start_error)
        base.RUNTIME_NO_PROGRESS_GUARD_CANDIDATE_ERROR_M = float(candidate_error)
        base.RUNTIME_NO_PROGRESS_GUARD_AFTER_ERROR_M = float(after_error)
        base.RUNTIME_NO_PROGRESS_GUARD_PROXIMAL_STEP_DEG = float(proximal_step_deg)
        base.RUNTIME_NO_PROGRESS_GUARD_CLEARANCE_M = clearance_value
        base.RUNTIME_NO_PROGRESS_GUARD_BLOCKED_REASON = blocked_reason

        context["no_progress_guard_active"] = active
        context["no_progress_guard_reverted"] = reverted
        context["no_progress_guard_scale"] = float(accepted_scale)
        context["no_progress_guard_after_error_m"] = float(after_error)
        return result

    base.solve_right_arm_target = guarded_solver
    base._NO_PROGRESS_JOINT_GUARD_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_NO_PROGRESS_JOINT_GUARD_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["no_progress_guard_active"] = bool(base.RUNTIME_NO_PROGRESS_GUARD_ACTIVE)
            enriched["no_progress_guard_reverted"] = bool(base.RUNTIME_NO_PROGRESS_GUARD_REVERTED)
            enriched["no_progress_guard_scale"] = float(base.RUNTIME_NO_PROGRESS_GUARD_SCALE)
            enriched["no_progress_guard_start_error_m"] = base.RUNTIME_NO_PROGRESS_GUARD_START_ERROR_M
            enriched["no_progress_guard_candidate_error_m"] = base.RUNTIME_NO_PROGRESS_GUARD_CANDIDATE_ERROR_M
            enriched["no_progress_guard_after_error_m"] = base.RUNTIME_NO_PROGRESS_GUARD_AFTER_ERROR_M
            enriched["no_progress_guard_proximal_step_deg"] = float(base.RUNTIME_NO_PROGRESS_GUARD_PROXIMAL_STEP_DEG)
            enriched["no_progress_guard_clearance_m"] = base.RUNTIME_NO_PROGRESS_GUARD_CLEARANCE_M
            enriched["no_progress_guard_tracking_error_enable_m"] = TRACKING_ERROR_ENABLE_M
            enriched["no_progress_guard_min_proximal_step_deg"] = MIN_PROXIMAL_STEP_DEG
            enriched["no_progress_guard_min_error_improvement_m"] = MIN_ERROR_IMPROVEMENT_M
            enriched["no_progress_guard_safety_bypass_clearance_m"] = SAFETY_BYPASS_CLEARANCE_M
            enriched["no_progress_guard_blocked_reason"] = base.RUNTIME_NO_PROGRESS_GUARD_BLOCKED_REASON
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._NO_PROGRESS_JOINT_GUARD_STATUS_INSTALLED = True
