"""Smooth secondary elbow-flexion preference for right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_PREFERRED_ELBOW_DEG = 55.0
DEFAULT_GAIN = 0.08
DEFAULT_MAX_STEP_DEG_PER_CYCLE = 0.25
DEFAULT_POSITION_TOLERANCE_M = 0.0002
DEFAULT_TARGET_MOTION_THRESHOLD_M = 0.00005


def _clamp_vector_norm(vector: np.ndarray, maximum_norm: float) -> np.ndarray:
    value = np.asarray(vector, dtype=float)
    magnitude = float(np.linalg.norm(value))
    if magnitude <= maximum_norm or magnitude < 1e-12:
        return value
    return value * (maximum_norm / magnitude)


def install_smooth_elbow_posture(
    base: ModuleType,
    *,
    preferred_elbow_deg: float = DEFAULT_PREFERRED_ELBOW_DEG,
    gain: float = DEFAULT_GAIN,
    max_step_deg_per_cycle: float = DEFAULT_MAX_STEP_DEG_PER_CYCLE,
    position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
    target_motion_threshold_m: float = DEFAULT_TARGET_MOTION_THRESHOLD_M,
) -> None:
    """Add a bounded elbow-flexion objective while the position reference moves.

    The wrist Cartesian position remains the primary task. A small secondary
    correction prefers a bent elbow when redundant freedom is available. The
    correction is continuous, bounded per control cycle, collision checked, and
    rejected if it noticeably worsens the primary wrist-position error.

    Elbow posture adaptation is intentionally paused when the Cartesian target is
    stationary. This preserves proximal joint pose during wrist-only orientation
    commands: rotating the operator hand must not slowly re-pose the shoulder or
    elbow simply because a posture preference exists.
    """

    if getattr(base, "_SMOOTH_ELBOW_POSTURE_INSTALLED", False):
        return
    if not math.isfinite(preferred_elbow_deg):
        raise ValueError("preferred_elbow_deg must be finite")
    if not math.isfinite(gain) or gain < 0.0:
        raise ValueError("gain must be finite and >= 0")
    if not math.isfinite(max_step_deg_per_cycle) or max_step_deg_per_cycle <= 0.0:
        raise ValueError("max_step_deg_per_cycle must be finite and > 0")
    if not math.isfinite(position_tolerance_m) or position_tolerance_m < 0.0:
        raise ValueError("position_tolerance_m must be finite and >= 0")
    if not math.isfinite(target_motion_threshold_m) or target_motion_threshold_m < 0.0:
        raise ValueError("target_motion_threshold_m must be finite and >= 0")

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before elbow posture install")

    preferred_elbow_rad = math.radians(preferred_elbow_deg)
    max_step_rad = math.radians(max_step_deg_per_cycle)

    base.RUNTIME_ELBOW_POSTURE_APPLIED = False
    base.RUNTIME_ELBOW_POSTURE_STEP_DEG = 0.0
    base.RUNTIME_ELBOW_POSTURE_ERROR_DEG = 0.0
    base.RUNTIME_ELBOW_POSTURE_BLOCKED = False
    base.RUNTIME_ELBOW_POSTURE_TARGET_MOTION_M = 0.0
    base.RUNTIME_ELBOW_POSTURE_TARGET_MOVING = False

    def elbow_posture_solver(*args: Any, **kwargs: Any):
        result = original_solver(*args, **kwargs)

        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        target = args[4] if len(args) > 4 else kwargs.get(
            "target_position", kwargs.get("target")
        )
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        base.RUNTIME_ELBOW_POSTURE_APPLIED = False
        base.RUNTIME_ELBOW_POSTURE_STEP_DEG = 0.0
        base.RUNTIME_ELBOW_POSTURE_BLOCKED = False
        base.RUNTIME_ELBOW_POSTURE_TARGET_MOTION_M = 0.0
        base.RUNTIME_ELBOW_POSTURE_TARGET_MOVING = False

        if (
            model is None
            or data is None
            or target is None
            or not isinstance(context, dict)
        ):
            return result

        right_dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        right_qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        position_joint_count = int(context.get("position_joint_count", 0))
        if (
            position_body is None
            or right_dof_ids.size < 4
            or right_qpos_ids.size < 4
            or position_joint_count < 4
        ):
            return result

        target_position = np.asarray(target, dtype=float)
        if target_position.shape != (3,) or not np.all(np.isfinite(target_position)):
            return result

        previous_target = context.get("_elbow_posture_previous_target")
        context["_elbow_posture_previous_target"] = target_position.copy()
        if previous_target is None:
            return result

        previous_target = np.asarray(previous_target, dtype=float)
        target_motion = float(np.linalg.norm(target_position - previous_target))
        base.RUNTIME_ELBOW_POSTURE_TARGET_MOTION_M = target_motion
        base.RUNTIME_ELBOW_POSTURE_TARGET_MOVING = (
            target_motion > target_motion_threshold_m
        )
        if not base.RUNTIME_ELBOW_POSTURE_TARGET_MOVING:
            return result

        import mujoco

        mujoco.mj_forward(model, data)
        position_body = int(position_body)
        position_dof_ids = right_dof_ids[:position_joint_count]
        position_qpos_ids = right_qpos_ids[:position_joint_count]
        elbow_index = 3

        current_elbow = float(data.qpos[position_qpos_ids[elbow_index]])
        elbow_error = preferred_elbow_rad - current_elbow
        base.RUNTIME_ELBOW_POSTURE_ERROR_DEG = math.degrees(elbow_error)
        if abs(elbow_error) < math.radians(0.05) or gain <= 0.0:
            return result

        jacp = np.zeros((3, model.nv))
        jacr_dummy = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp, jacr_dummy, position_body)
        position_jacobian = jacp[:, position_dof_ids]
        pseudoinverse = base.damped_pseudoinverse(
            position_jacobian,
            float(base.POSITION_DAMPING),
        )
        nullspace = (
            np.eye(position_joint_count)
            - pseudoinverse @ position_jacobian
        )

        posture_command = np.zeros(position_joint_count)
        posture_command[elbow_index] = gain * elbow_error
        correction = nullspace @ posture_command
        correction = _clamp_vector_norm(correction, max_step_rad)
        if float(np.linalg.norm(correction)) < 1e-10:
            return result

        start_q = data.qpos[position_qpos_ids].copy()
        start_position_error = float(
            np.linalg.norm(target_position - data.xpos[position_body])
        )
        accepted = False
        applied = np.zeros_like(correction)

        for line_search_index in range(6):
            scale = 0.5 ** line_search_index
            candidate_delta = scale * correction
            data.qpos[position_qpos_ids] = start_q + candidate_delta
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)

            candidate_position_error = float(
                np.linalg.norm(target_position - data.xpos[position_body])
            )
            collision = bool(base.has_right_arm_core_contact(model, data, context))
            position_ok = (
                candidate_position_error
                <= start_position_error + position_tolerance_m
            )
            if not collision and position_ok:
                accepted = True
                applied = candidate_delta
                break

        if not accepted:
            data.qpos[position_qpos_ids] = start_q
            mujoco.mj_forward(model, data)
            base.RUNTIME_ELBOW_POSTURE_BLOCKED = True
            context["elbow_posture_blocked"] = True
            return result

        base.RUNTIME_ELBOW_POSTURE_APPLIED = True
        base.RUNTIME_ELBOW_POSTURE_STEP_DEG = math.degrees(
            float(np.linalg.norm(applied))
        )
        context["elbow_posture_blocked"] = False
        context["elbow_posture_step_deg"] = base.RUNTIME_ELBOW_POSTURE_STEP_DEG
        return data.xpos[position_body].copy()

    base.solve_right_arm_target = elbow_posture_solver
    base._SMOOTH_ELBOW_POSTURE_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(
        base, "_ELBOW_POSTURE_STATUS_INSTALLED", False
    ):
        def elbow_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["elbow_posture_preferred_deg"] = float(preferred_elbow_deg)
            enriched["elbow_posture_error_deg"] = float(
                base.RUNTIME_ELBOW_POSTURE_ERROR_DEG
            )
            enriched["elbow_posture_step_deg"] = float(
                base.RUNTIME_ELBOW_POSTURE_STEP_DEG
            )
            enriched["elbow_posture_applied"] = bool(
                base.RUNTIME_ELBOW_POSTURE_APPLIED
            )
            enriched["elbow_posture_blocked"] = bool(
                base.RUNTIME_ELBOW_POSTURE_BLOCKED
            )
            enriched["elbow_posture_target_motion_m"] = float(
                base.RUNTIME_ELBOW_POSTURE_TARGET_MOTION_M
            )
            enriched["elbow_posture_target_moving"] = bool(
                base.RUNTIME_ELBOW_POSTURE_TARGET_MOVING
            )
            original_status_writer(enriched)

        base.write_runtime_status = elbow_status_writer
        base._ELBOW_POSTURE_STATUS_INSTALLED = True
