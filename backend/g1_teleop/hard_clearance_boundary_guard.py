"""Hard right-arm clearance guard with boundary line search.

When a solver update would cross from the safe side of the 5 mm robot-clearance
floor into the unsafe side, keep the largest joint-space fraction of that update
that remains on the safe boundary instead of reverting the whole cycle. If the
arm is already inside the floor, only strictly clearance-improving recovery steps
are accepted.
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


def install_boundary_hard_clearance_floor(base: ModuleType) -> None:
    """Install a 5 mm floor that clips unsafe updates instead of freezing them."""
    if getattr(base, "_HARD_CLEARANCE_FLOOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    base.RUNTIME_HARD_CLEARANCE_REVERTED = False
    base.RUNTIME_HARD_CLEARANCE_RECOVERY_ACTIVE = False
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_CLIPPED = False
    base.RUNTIME_HARD_CLEARANCE_BOUNDARY_SCALE = 1.0
    base.RUNTIME_HARD_CLEARANCE_BEFORE_M = None
    base.RUNTIME_HARD_CLEARANCE_AFTER_M = None

    def guarded_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
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
        candidate_q = data.qpos[qpos_ids].copy()
        after_candidate = _clearance(
            model, data, context, structural_neighbor_distance
        )

        recovery_active = before < HARD_CLEARANCE_FLOOR_M
        reverted = False
        boundary_clipped = False
        boundary_scale = 1.0
        accepted_after = after_candidate

        if recovery_active:
            # Once inside the emergency region, never reject a measurable move
            # outward merely because the floor has not been fully recovered yet.
            if after_candidate <= before + RECOVERY_IMPROVEMENT_EPS_M:
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                reverted = True
                boundary_scale = 0.0
                accepted_after = before
        elif after_candidate < HARD_CLEARANCE_FLOOR_M:
            # The full solver update crosses the floor. Find the largest fraction
            # of the complete 7-DOF update that remains just outside the floor.
            delta_q = candidate_q - start_q
            low = 0.0
            high = 1.0
            target_clearance = HARD_CLEARANCE_FLOOR_M + BOUNDARY_MARGIN_M

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

            if low > 1e-6:
                data.qpos[qpos_ids] = start_q + low * delta_q
                mujoco.mj_forward(model, data)
                accepted_after = _clearance(
                    model, data, context, structural_neighbor_distance
                )
                boundary_clipped = True
                boundary_scale = float(low)
                if context.get("position_body") is not None:
                    result = data.xpos[int(context["position_body"])].copy()
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

        context["hard_clearance_floor_m"] = HARD_CLEARANCE_FLOOR_M
        context["hard_clearance_reverted"] = bool(reverted)
        context["hard_clearance_recovery_active"] = bool(recovery_active)
        context["hard_clearance_boundary_clipped"] = bool(boundary_clipped)
        context["hard_clearance_boundary_scale"] = float(boundary_scale)
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
            enriched["hard_clearance_before_m"] = (
                base.RUNTIME_HARD_CLEARANCE_BEFORE_M
            )
            enriched["hard_clearance_after_m"] = (
                base.RUNTIME_HARD_CLEARANCE_AFTER_M
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._HARD_CLEARANCE_STATUS_INSTALLED = True
