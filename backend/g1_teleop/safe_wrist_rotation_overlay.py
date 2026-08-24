"""Preserve Quest wrist rotation while safe-progress reconfigures the proximal arm.

The safe-progress supervisor may replace an unsafe Cartesian candidate with a
shoulder/elbow reconfiguration step. That correctly preserves collision
clearance, but it also discards the three wrist-joint rotation changes that the
inner orientation solver had already computed. This module captures that inner
wrist intent before reconfiguration and reapplies as much of it as is safe after
the final proximal pose has been selected.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


WRIST_OVERLAY_SOFT_CLEARANCE_M = 0.01225
WRIST_OVERLAY_BISECTION_STEPS = 12
WRIST_OVERLAY_MIN_SCALE = 1e-4


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


def install_wrist_intent_capture(base: ModuleType) -> None:
    """Capture the inner solver's wrist-joint candidate before outer reconfiguration."""
    if getattr(base, "_SAFE_WRIST_INTENT_CAPTURE_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_SAFE_WRIST_INTENT_Q = None

    def capture_solver(*args: Any, **kwargs: Any):
        result = original_solver(*args, **kwargs)
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if data is not None and isinstance(context, dict):
            qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
            if qpos_ids.size >= 7:
                base.RUNTIME_SAFE_WRIST_INTENT_Q = data.qpos[qpos_ids[4:7]].copy()
        return result

    base.solve_right_arm_target = capture_solver
    base._SAFE_WRIST_INTENT_CAPTURE_INSTALLED = True


def install_safe_wrist_rotation_overlay(base: ModuleType) -> None:
    """Reapply captured wrist rotation after safe-progress reconfiguration."""
    if getattr(base, "_SAFE_WRIST_ROTATION_OVERLAY_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target

    base.RUNTIME_SAFE_WRIST_OVERLAY_ACTIVE = False
    base.RUNTIME_SAFE_WRIST_OVERLAY_SCALE = 0.0
    base.RUNTIME_SAFE_WRIST_OVERLAY_REQUESTED_STEP_DEG = 0.0
    base.RUNTIME_SAFE_WRIST_OVERLAY_APPLIED_STEP_DEG = 0.0
    base.RUNTIME_SAFE_WRIST_OVERLAY_BEFORE_M = None
    base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M = None
    base.RUNTIME_SAFE_WRIST_OVERLAY_BLOCKED = False

    def overlay_solver(*args: Any, **kwargs: Any):
        result = original_solver(*args, **kwargs)

        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        base.RUNTIME_SAFE_WRIST_OVERLAY_ACTIVE = False
        base.RUNTIME_SAFE_WRIST_OVERLAY_SCALE = 0.0
        base.RUNTIME_SAFE_WRIST_OVERLAY_REQUESTED_STEP_DEG = 0.0
        base.RUNTIME_SAFE_WRIST_OVERLAY_APPLIED_STEP_DEG = 0.0
        base.RUNTIME_SAFE_WRIST_OVERLAY_BEFORE_M = None
        base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M = None
        base.RUNTIME_SAFE_WRIST_OVERLAY_BLOCKED = False

        if model is None or data is None or not isinstance(context, dict):
            return result

        exact_reconfigure = bool(
            getattr(base, "RUNTIME_SAFE_PROGRESS_RECONFIGURE_ACTIVE", False)
        )
        bounded_reconfigure = bool(
            getattr(base, "RUNTIME_SAFE_PROGRESS_BOUNDED_RECONFIGURE_ACTIVE", False)
        )
        if not (exact_reconfigure or bounded_reconfigure):
            return result

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        intent_q = getattr(base, "RUNTIME_SAFE_WRIST_INTENT_Q", None)
        if qpos_ids.size < 7 or position_body is None or intent_q is None:
            return result

        intent_q = np.asarray(intent_q, dtype=float)
        if intent_q.shape != (3,):
            return result

        structural_neighbor_distance = int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        mujoco.mj_forward(model, data)
        start_wrist_q = data.qpos[qpos_ids[4:7]].copy()
        before = _clearance(model, data, context, structural_neighbor_distance)
        delta = intent_q - start_wrist_q
        requested_step_deg = float(np.linalg.norm(np.degrees(delta)))

        base.RUNTIME_SAFE_WRIST_OVERLAY_REQUESTED_STEP_DEG = requested_step_deg
        base.RUNTIME_SAFE_WRIST_OVERLAY_BEFORE_M = None if math.isinf(before) else before

        if requested_step_deg <= 1e-8:
            base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M = (
                None if math.isinf(before) else before
            )
            return result

        # Never demand more clearance than the reconfigured pose currently has,
        # but do not allow wrist rotation to cross below the normal 12.25 mm
        # soft reserve when that reserve is already available.
        required_clearance = min(before, WRIST_OVERLAY_SOFT_CLEARANCE_M)
        low = 0.0
        high = 1.0

        for _ in range(WRIST_OVERLAY_BISECTION_STEPS):
            mid = 0.5 * (low + high)
            data.qpos[qpos_ids[4:7]] = start_wrist_q + mid * delta
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            clearance_mid = _clearance(
                model, data, context, structural_neighbor_distance
            )
            if (
                clearance_mid >= required_clearance
                and not base.has_right_arm_core_contact(model, data, context)
            ):
                low = mid
            else:
                high = mid

        if low < WRIST_OVERLAY_MIN_SCALE:
            data.qpos[qpos_ids[4:7]] = start_wrist_q
            mujoco.mj_forward(model, data)
            base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M = (
                None if math.isinf(before) else before
            )
            base.RUNTIME_SAFE_WRIST_OVERLAY_BLOCKED = True
            return result

        data.qpos[qpos_ids[4:7]] = start_wrist_q + low * delta
        base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
        mujoco.mj_forward(model, data)
        after = _clearance(model, data, context, structural_neighbor_distance)
        applied_step_deg = float(
            np.linalg.norm(
                np.degrees(data.qpos[qpos_ids[4:7]] - start_wrist_q)
            )
        )

        base.RUNTIME_SAFE_WRIST_OVERLAY_ACTIVE = True
        base.RUNTIME_SAFE_WRIST_OVERLAY_SCALE = float(low)
        base.RUNTIME_SAFE_WRIST_OVERLAY_APPLIED_STEP_DEG = applied_step_deg
        base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M = None if math.isinf(after) else after

        # Keep final-pose collision reporting synchronized with the wrist overlay.
        if not math.isinf(after):
            base.RUNTIME_SAFE_PROGRESS_AFTER_M = float(after)
        if hasattr(base, "RUNTIME_WRIST_ORIENTATION_STEP_DEG"):
            base.RUNTIME_WRIST_ORIENTATION_STEP_DEG = applied_step_deg
        if hasattr(base, "RUNTIME_WRIST_ORIENTATION_WEIGHT"):
            base.RUNTIME_WRIST_ORIENTATION_WEIGHT = float(low)
        context["wrist_orientation_step_deg"] = applied_step_deg
        context["wrist_orientation_weight"] = float(low)
        context["safe_wrist_overlay_active"] = True
        context["safe_wrist_overlay_scale"] = float(low)
        return data.xpos[int(position_body)].copy()

    base.solve_right_arm_target = overlay_solver
    base._SAFE_WRIST_ROTATION_OVERLAY_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_SAFE_WRIST_ROTATION_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["safe_wrist_overlay_active"] = bool(
                base.RUNTIME_SAFE_WRIST_OVERLAY_ACTIVE
            )
            enriched["safe_wrist_overlay_scale"] = float(
                base.RUNTIME_SAFE_WRIST_OVERLAY_SCALE
            )
            enriched["safe_wrist_overlay_requested_step_deg"] = float(
                base.RUNTIME_SAFE_WRIST_OVERLAY_REQUESTED_STEP_DEG
            )
            enriched["safe_wrist_overlay_applied_step_deg"] = float(
                base.RUNTIME_SAFE_WRIST_OVERLAY_APPLIED_STEP_DEG
            )
            enriched["safe_wrist_overlay_before_m"] = (
                base.RUNTIME_SAFE_WRIST_OVERLAY_BEFORE_M
            )
            enriched["safe_wrist_overlay_after_m"] = (
                base.RUNTIME_SAFE_WRIST_OVERLAY_AFTER_M
            )
            enriched["safe_wrist_overlay_blocked"] = bool(
                base.RUNTIME_SAFE_WRIST_OVERLAY_BLOCKED
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._SAFE_WRIST_ROTATION_STATUS_INSTALLED = True
