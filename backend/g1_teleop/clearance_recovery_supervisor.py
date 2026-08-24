"""Stateful safety recovery supervisor for right-arm teleoperation.

Normal tracking owns the arm while robot clearance is healthy. If the final
solver path approaches the robot closer than the entry threshold, this outer
supervisor latches a recovery state. During recovery it rejects unsafe tracking
results, holds all three wrist joints, and moves only shoulder/elbow
configuration along a clearance-improving direction for several bounded steps
per control cycle. Tracking resumes only when both the current pose and a fresh
tracking candidate satisfy the release clearance, preventing recovery/re-entry
chatter while the operator continues commanding an unsafe target.
"""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import mujoco
import numpy as np

from .runtime_collision import dangerous_contact_clearance_m


RECOVERY_ENTER_CLEARANCE_M = 0.012
RECOVERY_RELEASE_CLEARANCE_M = 0.018
FINITE_DIFFERENCE_RAD = math.radians(0.5)
RECOVERY_PROXIMAL_STEP_RAD = math.radians(0.30)
RECOVERY_ELBOW_STEP_RAD = math.radians(0.20)
RECOVERY_SUBSTEPS_PER_CYCLE = 4
RECOVERY_LINE_SEARCH_STEPS = 7
RECOVERY_MIN_IMPROVEMENT_M = 1e-8
RECOVERY_MAX_WRIST_DRIFT_PER_CYCLE_M = 0.004


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


def _clearance_gradient(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    structural_neighbor_distance: int,
) -> np.ndarray:
    """Finite-difference gradient for the four proximal right-arm joints."""
    gradient = np.zeros(4, dtype=float)
    saved_q = data.qpos[qpos_ids].copy()
    try:
        for index in range(4):
            samples: list[tuple[float, float]] = []
            for sign in (-1.0, 1.0):
                data.qpos[qpos_ids] = saved_q
                data.qpos[int(qpos_ids[index])] = (
                    saved_q[index] + sign * FINITE_DIFFERENCE_RAD
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
                clearance = min(clearance, RECOVERY_RELEASE_CLEARANCE_M)
                samples.append((actual, clearance))
            denominator = samples[1][0] - samples[0][0]
            if abs(denominator) > 1e-9:
                gradient[index] = (samples[1][1] - samples[0][1]) / denominator
    finally:
        data.qpos[qpos_ids] = saved_q
        mujoco.mj_forward(model, data)
    return gradient


def install_clearance_recovery_supervisor(base: ModuleType) -> None:
    """Install hysteretic clearance recovery outside the normal solver stack."""
    if getattr(base, "_CLEARANCE_RECOVERY_SUPERVISOR_INSTALLED", False):
        return

    original_solver = base.solve_right_arm_target
    recovery_latched = False

    base.RUNTIME_SAFETY_RECOVERY_LATCHED = False
    base.RUNTIME_SAFETY_RECOVERY_BEFORE_M = None
    base.RUNTIME_SAFETY_RECOVERY_AFTER_M = None
    base.RUNTIME_SAFETY_RECOVERY_CANDIDATE_CLEARANCE_M = None
    base.RUNTIME_SAFETY_RECOVERY_RELEASE_BLOCKED_BY_CANDIDATE = False
    base.RUNTIME_SAFETY_RECOVERY_STEP_DEG = 0.0
    base.RUNTIME_SAFETY_RECOVERY_SUBSTEPS = 0
    base.RUNTIME_SAFETY_RECOVERY_WRIST_DRIFT_M = 0.0
    base.RUNTIME_SAFETY_RECOVERY_BLOCKED_REASON = None
    base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = False

    def supervised_solver(*args: Any, **kwargs: Any):
        nonlocal recovery_latched

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
        cycle_start_q = data.qpos[qpos_ids].copy()
        cycle_start_wrist = data.xpos[int(position_body)].copy()
        before = _clearance(
            model,
            data,
            context,
            structural_neighbor_distance,
        )

        # Always evaluate one fresh normal-tracking candidate. While latched this
        # candidate is only a probe: it is accepted only if it is itself safely
        # outside the release threshold. Otherwise the complete candidate is
        # discarded so tracking cannot pull the robot straight back into danger.
        result = original_solver(*args, **kwargs)
        mujoco.mj_forward(model, data)
        candidate_clearance = _clearance(
            model,
            data,
            context,
            structural_neighbor_distance,
        )

        if not recovery_latched and min(before, candidate_clearance) <= RECOVERY_ENTER_CLEARANCE_M:
            recovery_latched = True

        total_step = np.zeros(4, dtype=float)
        accepted_substeps = 0
        blocked_reason = None
        wrist_drift = 0.0
        release_blocked_by_candidate = False

        # A latched supervisor may release only when BOTH the current accepted
        # pose and the newly proposed tracking candidate are safely outside the
        # release threshold. This prevents 18 mm -> unsafe candidate -> 18 mm
        # oscillation when the operator keeps commanding through the torso.
        release_candidate_safe = (
            recovery_latched
            and before >= RECOVERY_RELEASE_CLEARANCE_M
            and candidate_clearance >= RECOVERY_RELEASE_CLEARANCE_M
        )

        if release_candidate_safe:
            recovery_latched = False
            final_clearance = candidate_clearance
            context["safety_recovery_wrist_hold"] = False
        elif recovery_latched:
            if before >= RECOVERY_RELEASE_CLEARANCE_M:
                release_blocked_by_candidate = True

            # Reject the tracking/orientation result for this cycle. Recovery
            # starts from the last accepted pose and keeps all wrist joints fixed.
            data.qpos[qpos_ids] = cycle_start_q
            mujoco.mj_forward(model, data)

            for _ in range(RECOVERY_SUBSTEPS_PER_CYCLE):
                current_clearance = _clearance(
                    model,
                    data,
                    context,
                    structural_neighbor_distance,
                )

                # Once enough clearance has been recovered, stop moving farther
                # away but KEEP THE LATCH. The next cycles continue probing the
                # operator candidate while holding this safe pose until the
                # commanded target itself becomes safe.
                if current_clearance >= RECOVERY_RELEASE_CLEARANCE_M:
                    break

                gradient = _clearance_gradient(
                    base,
                    model,
                    data,
                    context,
                    qpos_ids,
                    structural_neighbor_distance,
                )
                gradient_norm = float(np.linalg.norm(gradient))
                if gradient_norm <= 1e-10:
                    blocked_reason = "no_clearance_gradient"
                    break

                direction = gradient / gradient_norm
                max_component = float(np.max(np.abs(direction)))
                if max_component <= 1e-10:
                    blocked_reason = "no_escape_direction"
                    break

                step = direction / max_component * RECOVERY_PROXIMAL_STEP_RAD
                step[3] = float(
                    np.clip(
                        step[3],
                        -RECOVERY_ELBOW_STEP_RAD,
                        RECOVERY_ELBOW_STEP_RAD,
                    )
                )

                substep_start_q = data.qpos[qpos_ids].copy()
                accepted = False
                for line_index in range(RECOVERY_LINE_SEARCH_STEPS):
                    scale = 0.5 ** line_index
                    data.qpos[qpos_ids[:4]] = substep_start_q[:4] + scale * step
                    data.qpos[qpos_ids[4:]] = cycle_start_q[4:]
                    base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
                    mujoco.mj_forward(model, data)

                    if base.has_right_arm_core_contact(model, data, context):
                        continue

                    trial_clearance = _clearance(
                        model,
                        data,
                        context,
                        structural_neighbor_distance,
                    )
                    trial_wrist_drift = float(
                        np.linalg.norm(
                            data.xpos[int(position_body)] - cycle_start_wrist
                        )
                    )
                    if (
                        trial_clearance > current_clearance + RECOVERY_MIN_IMPROVEMENT_M
                        and trial_wrist_drift <= RECOVERY_MAX_WRIST_DRIFT_PER_CYCLE_M
                    ):
                        accepted = True
                        accepted_step = data.qpos[qpos_ids[:4]] - substep_start_q[:4]
                        total_step += accepted_step
                        accepted_substeps += 1
                        wrist_drift = trial_wrist_drift
                        break

                if not accepted:
                    data.qpos[qpos_ids] = substep_start_q
                    mujoco.mj_forward(model, data)
                    blocked_reason = "no_improving_bounded_step"
                    break

            final_clearance = _clearance(
                model,
                data,
                context,
                structural_neighbor_distance,
            )

            if hasattr(base, "RUNTIME_WRIST_ORIENTATION_WEIGHT"):
                base.RUNTIME_WRIST_ORIENTATION_WEIGHT = 0.0
            if hasattr(base, "RUNTIME_WRIST_ORIENTATION_STEP_DEG"):
                base.RUNTIME_WRIST_ORIENTATION_STEP_DEG = 0.0
            context["wrist_orientation_weight"] = 0.0
            context["wrist_orientation_step_deg"] = 0.0
            context["safety_recovery_wrist_hold"] = True
            result = data.xpos[int(position_body)].copy()
        else:
            final_clearance = candidate_clearance
            context["safety_recovery_wrist_hold"] = False

        base.RUNTIME_SAFETY_RECOVERY_LATCHED = bool(recovery_latched)
        base.RUNTIME_SAFETY_RECOVERY_BEFORE_M = None if math.isinf(before) else float(before)
        base.RUNTIME_SAFETY_RECOVERY_AFTER_M = (
            None if math.isinf(final_clearance) else float(final_clearance)
        )
        base.RUNTIME_SAFETY_RECOVERY_CANDIDATE_CLEARANCE_M = (
            None if math.isinf(candidate_clearance) else float(candidate_clearance)
        )
        base.RUNTIME_SAFETY_RECOVERY_RELEASE_BLOCKED_BY_CANDIDATE = bool(
            release_blocked_by_candidate
        )
        base.RUNTIME_SAFETY_RECOVERY_STEP_DEG = float(
            np.linalg.norm(np.degrees(total_step))
        )
        base.RUNTIME_SAFETY_RECOVERY_SUBSTEPS = int(accepted_substeps)
        base.RUNTIME_SAFETY_RECOVERY_WRIST_DRIFT_M = float(wrist_drift)
        base.RUNTIME_SAFETY_RECOVERY_BLOCKED_REASON = blocked_reason
        base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD = bool(recovery_latched)

        context["safety_recovery_latched"] = bool(recovery_latched)
        context["safety_recovery_before_m"] = base.RUNTIME_SAFETY_RECOVERY_BEFORE_M
        context["safety_recovery_after_m"] = base.RUNTIME_SAFETY_RECOVERY_AFTER_M
        context["safety_recovery_candidate_clearance_m"] = (
            base.RUNTIME_SAFETY_RECOVERY_CANDIDATE_CLEARANCE_M
        )
        context["safety_recovery_release_blocked_by_candidate"] = bool(
            release_blocked_by_candidate
        )
        context["safety_recovery_step_deg"] = base.RUNTIME_SAFETY_RECOVERY_STEP_DEG
        context["safety_recovery_substeps"] = int(accepted_substeps)
        return result

    base.solve_right_arm_target = supervised_solver
    base._CLEARANCE_RECOVERY_SUPERVISOR_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_CLEARANCE_RECOVERY_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["safety_recovery_latched"] = bool(
                base.RUNTIME_SAFETY_RECOVERY_LATCHED
            )
            enriched["safety_recovery_enter_clearance_m"] = RECOVERY_ENTER_CLEARANCE_M
            enriched["safety_recovery_release_clearance_m"] = RECOVERY_RELEASE_CLEARANCE_M
            enriched["safety_recovery_before_m"] = base.RUNTIME_SAFETY_RECOVERY_BEFORE_M
            enriched["safety_recovery_after_m"] = base.RUNTIME_SAFETY_RECOVERY_AFTER_M
            enriched["safety_recovery_candidate_clearance_m"] = (
                base.RUNTIME_SAFETY_RECOVERY_CANDIDATE_CLEARANCE_M
            )
            enriched["safety_recovery_release_blocked_by_candidate"] = bool(
                base.RUNTIME_SAFETY_RECOVERY_RELEASE_BLOCKED_BY_CANDIDATE
            )
            enriched["safety_recovery_step_deg"] = float(
                base.RUNTIME_SAFETY_RECOVERY_STEP_DEG
            )
            enriched["safety_recovery_substeps"] = int(
                base.RUNTIME_SAFETY_RECOVERY_SUBSTEPS
            )
            enriched["safety_recovery_wrist_drift_m"] = float(
                base.RUNTIME_SAFETY_RECOVERY_WRIST_DRIFT_M
            )
            enriched["safety_recovery_wrist_hold"] = bool(
                base.RUNTIME_SAFETY_RECOVERY_WRIST_HOLD
            )
            enriched["safety_recovery_blocked_reason"] = (
                base.RUNTIME_SAFETY_RECOVERY_BLOCKED_REASON
            )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._CLEARANCE_RECOVERY_STATUS_INSTALLED = True
