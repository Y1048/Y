"""Final swept-path collision guard for right-arm teleoperation.

This layer is intentionally installed outside all normal IK, redundancy,
safe-progress, bounded-reconfigure, and wrist-orientation layers. It validates
the actually requested joint-space update from the currently accepted pose to
the final candidate pose. Intermediate configurations are sampled adaptively;
if the first unsafe segment is found, a local bisection keeps only the last safe
fraction of the motion. The existing endpoint safety layers remain unchanged.

This is dense discrete swept-path validation, not analytic continuous collision
detection. Its purpose is to catch unsafe intermediate configurations that an
endpoint-only check could miss.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


SWEPT_PATH_FLOOR_M = 0.005
SWEPT_PATH_BOUNDARY_MARGIN_M = 0.00005
SAMPLE_JOINT_STEP_DEG = 0.15
MIN_SAMPLES = 2
MAX_SAMPLES = 48
BOUNDARY_BISECTION_STEPS = 12
RECOVERY_REGRESSION_TOLERANCE_M = 1e-7


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


def _sample_count(delta_q: np.ndarray) -> tuple[int, float]:
    if delta_q.size == 0:
        return MIN_SAMPLES, 0.0
    max_joint_delta_deg = float(np.max(np.abs(np.degrees(delta_q))))
    requested = int(math.ceil(max_joint_delta_deg / SAMPLE_JOINT_STEP_DEG))
    return int(np.clip(requested, MIN_SAMPLES, MAX_SAMPLES)), max_joint_delta_deg


def install_swept_path_collision_guard(base: ModuleType) -> None:
    """Install adaptive intermediate-configuration validation as the final gate."""
    if getattr(base, "_SWEPT_PATH_COLLISION_GUARD_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target

    base.RUNTIME_SWEPT_PATH_CHECKED = False
    base.RUNTIME_SWEPT_PATH_CLIPPED = False
    base.RUNTIME_SWEPT_PATH_SCALE = 1.0
    base.RUNTIME_SWEPT_PATH_SAMPLES = 0
    base.RUNTIME_SWEPT_PATH_MAX_JOINT_DELTA_DEG = 0.0
    base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M = None
    base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_CLEARANCE_M = None
    base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_FRACTION = None
    base.RUNTIME_SWEPT_PATH_BEFORE_M = None
    base.RUNTIME_SWEPT_PATH_CANDIDATE_M = None
    base.RUNTIME_SWEPT_PATH_AFTER_M = None
    base.RUNTIME_SWEPT_PATH_BLOCKED_REASON = None

    def guarded_solver(*args: Any, **kwargs: Any):
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

        delta_q = candidate_q - start_q
        samples, max_joint_delta_deg = _sample_count(delta_q)
        min_clearance = before
        first_unsafe_clearance = None
        first_unsafe_fraction = None
        clipped = False
        accepted_scale = 1.0
        blocked_reason = None

        # Restore the accepted start pose before traversing the requested motion.
        data.qpos[qpos_ids] = start_q
        mujoco.mj_forward(model, data)

        start_inside_floor = before < SWEPT_PATH_FLOOR_M
        previous_fraction = 0.0
        previous_clearance = before
        last_safe_fraction = 0.0

        for sample_index in range(1, samples + 1):
            fraction = sample_index / samples
            data.qpos[qpos_ids] = start_q + fraction * delta_q
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            clearance = _clearance(
                model, data, context, structural_neighbor_distance
            )
            min_clearance = min(min_clearance, clearance)

            core_contact = base.has_right_arm_core_contact(model, data, context)
            if start_inside_floor:
                # Do not prevent emergency recovery when the cycle begins inside
                # the floor. The path is allowed only when it does not regress
                # farther into danger and ultimately improves clearance.
                unsafe = (
                    core_contact
                    or clearance
                    < before - RECOVERY_REGRESSION_TOLERANCE_M
                )
            else:
                unsafe = core_contact or clearance < SWEPT_PATH_FLOOR_M

            if unsafe:
                first_unsafe_clearance = clearance
                first_unsafe_fraction = fraction

                low = last_safe_fraction
                high = fraction
                target_clearance = (
                    before - RECOVERY_REGRESSION_TOLERANCE_M
                    if start_inside_floor
                    else SWEPT_PATH_FLOOR_M + SWEPT_PATH_BOUNDARY_MARGIN_M
                )
                for _ in range(BOUNDARY_BISECTION_STEPS):
                    mid = 0.5 * (low + high)
                    data.qpos[qpos_ids] = start_q + mid * delta_q
                    base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                    mujoco.mj_forward(model, data)
                    mid_clearance = _clearance(
                        model, data, context, structural_neighbor_distance
                    )
                    mid_contact = base.has_right_arm_core_contact(model, data, context)
                    if mid_clearance >= target_clearance and not mid_contact:
                        low = mid
                    else:
                        high = mid

                accepted_scale = float(low)
                clipped = True
                break

            last_safe_fraction = fraction
            previous_fraction = fraction
            previous_clearance = clearance

        if clipped:
            data.qpos[qpos_ids] = start_q + accepted_scale * delta_q
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            after = _clearance(model, data, context, structural_neighbor_distance)
            result = data.xpos[int(position_body)].copy()
            if accepted_scale <= 1e-9:
                blocked_reason = "unsafe_intermediate_path_no_safe_progress"
        else:
            data.qpos[qpos_ids] = candidate_q
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            after = _clearance(model, data, context, structural_neighbor_distance)

            if start_inside_floor and after <= before + RECOVERY_REGRESSION_TOLERANCE_M:
                # A path beginning inside the hard floor must actually recover,
                # not merely avoid further regression.
                data.qpos[qpos_ids] = start_q
                mujoco.mj_forward(model, data)
                after = before
                accepted_scale = 0.0
                clipped = True
                blocked_reason = "inside_floor_without_recovery"
                result = data.xpos[int(position_body)].copy()

        base.RUNTIME_SWEPT_PATH_CHECKED = True
        base.RUNTIME_SWEPT_PATH_CLIPPED = bool(clipped)
        base.RUNTIME_SWEPT_PATH_SCALE = float(accepted_scale)
        base.RUNTIME_SWEPT_PATH_SAMPLES = int(samples)
        base.RUNTIME_SWEPT_PATH_MAX_JOINT_DELTA_DEG = float(max_joint_delta_deg)
        base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M = (
            None if math.isinf(min_clearance) else float(min_clearance)
        )
        base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_CLEARANCE_M = (
            None
            if first_unsafe_clearance is None or math.isinf(first_unsafe_clearance)
            else float(first_unsafe_clearance)
        )
        base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_FRACTION = first_unsafe_fraction
        base.RUNTIME_SWEPT_PATH_BEFORE_M = None if math.isinf(before) else float(before)
        base.RUNTIME_SWEPT_PATH_CANDIDATE_M = (
            None if math.isinf(candidate_clearance) else float(candidate_clearance)
        )
        base.RUNTIME_SWEPT_PATH_AFTER_M = None if math.isinf(after) else float(after)
        base.RUNTIME_SWEPT_PATH_BLOCKED_REASON = blocked_reason

        context["swept_path_checked"] = True
        context["swept_path_clipped"] = bool(clipped)
        context["swept_path_scale"] = float(accepted_scale)
        context["swept_path_samples"] = int(samples)
        context["swept_path_min_clearance_m"] = base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M
        context["swept_path_after_m"] = base.RUNTIME_SWEPT_PATH_AFTER_M
        return result

    base.solve_right_arm_target = guarded_solver
    base._SWEPT_PATH_COLLISION_GUARD_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_SWEPT_PATH_COLLISION_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["swept_path_checked"] = bool(base.RUNTIME_SWEPT_PATH_CHECKED)
            enriched["swept_path_floor_m"] = SWEPT_PATH_FLOOR_M
            enriched["swept_path_boundary_margin_m"] = SWEPT_PATH_BOUNDARY_MARGIN_M
            enriched["swept_path_sample_joint_step_deg"] = SAMPLE_JOINT_STEP_DEG
            enriched["swept_path_clipped"] = bool(base.RUNTIME_SWEPT_PATH_CLIPPED)
            enriched["swept_path_scale"] = float(base.RUNTIME_SWEPT_PATH_SCALE)
            enriched["swept_path_samples"] = int(base.RUNTIME_SWEPT_PATH_SAMPLES)
            enriched["swept_path_max_joint_delta_deg"] = float(
                base.RUNTIME_SWEPT_PATH_MAX_JOINT_DELTA_DEG
            )
            enriched["swept_path_min_clearance_m"] = (
                base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M
            )
            enriched["swept_path_first_unsafe_clearance_m"] = (
                base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_CLEARANCE_M
            )
            enriched["swept_path_first_unsafe_fraction"] = (
                base.RUNTIME_SWEPT_PATH_FIRST_UNSAFE_FRACTION
            )
            enriched["swept_path_before_m"] = base.RUNTIME_SWEPT_PATH_BEFORE_M
            enriched["swept_path_candidate_m"] = base.RUNTIME_SWEPT_PATH_CANDIDATE_M
            enriched["swept_path_after_m"] = base.RUNTIME_SWEPT_PATH_AFTER_M
            enriched["swept_path_blocked_reason"] = base.RUNTIME_SWEPT_PATH_BLOCKED_REASON
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._SWEPT_PATH_COLLISION_STATUS_INSTALLED = True
