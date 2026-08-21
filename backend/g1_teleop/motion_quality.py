"""Motion-quality helpers for configured G1 right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_PREFERRED_ELBOW_DEG = 55.0
DEFAULT_TARGET_MOTION_THRESHOLD_M = 0.00005
DEFAULT_PROXIMAL_MAX_STEP_DEG = 0.30
DEFAULT_WRIST_MAX_STEP_DEG = 0.45
DEFAULT_PROXIMAL_MAX_ACCEL_STEP_DEG = 0.07
DEFAULT_WRIST_MAX_ACCEL_STEP_DEG = 0.10


def install_motion_gated_elbow_preference(
    base: ModuleType,
    *,
    preferred_elbow_deg: float = DEFAULT_PREFERRED_ELBOW_DEG,
    target_motion_threshold_m: float = DEFAULT_TARGET_MOTION_THRESHOLD_M,
) -> None:
    """Feed a bent-elbow preference into the existing position IK only while moving.

    This deliberately does not apply a second post-solve elbow correction. The
    existing solver already contains wrist-position null-space posture and an
    elbow-pole task. Supplying the desired elbow angle through ``preferred`` lets
    those objectives be solved together instead of competing in separate wrappers.

    When the Cartesian reference is stationary, the current elbow angle becomes
    the temporary preference so wrist-only rotation cannot slowly re-pose the
    shoulder/elbow.
    """

    if getattr(base, "_MOTION_GATED_ELBOW_PREFERENCE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before elbow preference install")

    preferred_elbow_rad = math.radians(float(preferred_elbow_deg))

    def preferred_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        preferred = args[3] if len(args) > 3 else kwargs.get("preferred")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        if (
            data is None
            or preferred is None
            or target is None
            or not isinstance(context, dict)
        ):
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        preferred_value = np.asarray(preferred, dtype=float).copy()
        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        if target_position.shape != (3,) or preferred_value.size < 4 or qpos_ids.size < 4:
            return original_solver(*args, **kwargs)

        previous_target = context.get("_preferred_elbow_previous_target")
        context["_preferred_elbow_previous_target"] = target_position.copy()
        target_motion = 0.0 if previous_target is None else float(
            np.linalg.norm(target_position - np.asarray(previous_target, dtype=float))
        )
        target_moving = target_motion > float(target_motion_threshold_m)

        if target_moving:
            preferred_value[3] = preferred_elbow_rad
        else:
            preferred_value[3] = float(data.qpos[qpos_ids[3]])

        context["preferred_elbow_target_deg"] = math.degrees(float(preferred_value[3]))
        context["preferred_elbow_target_moving"] = bool(target_moving)
        context["preferred_elbow_target_motion_m"] = float(target_motion)

        if len(args) > 3:
            adjusted_args = list(args)
            adjusted_args[3] = preferred_value
            return original_solver(*adjusted_args, **kwargs)

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["preferred"] = preferred_value
        return original_solver(*args, **adjusted_kwargs)

    base.solve_right_arm_target = preferred_solver
    base._MOTION_GATED_ELBOW_PREFERENCE_INSTALLED = True


def install_joint_command_smoother(
    base: ModuleType,
    *,
    proximal_max_step_deg: float = DEFAULT_PROXIMAL_MAX_STEP_DEG,
    wrist_max_step_deg: float = DEFAULT_WRIST_MAX_STEP_DEG,
    proximal_max_accel_step_deg: float = DEFAULT_PROXIMAL_MAX_ACCEL_STEP_DEG,
    wrist_max_accel_step_deg: float = DEFAULT_WRIST_MAX_ACCEL_STEP_DEG,
) -> None:
    """Rate/acceleration limit the final seven-joint command written to qpos.

    The teleoperation stack uses direct qpos IK rather than actuator dynamics, so
    even collision-free IK candidates can look stair-stepped. This wrapper keeps
    the solver's desired candidate but limits the amount and change of joint motion
    per control call. A collision check is repeated after smoothing.
    """

    if getattr(base, "_JOINT_COMMAND_SMOOTHER_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before joint smoother install")

    max_step = np.radians(np.array(
        [proximal_max_step_deg] * 4 + [wrist_max_step_deg] * 3,
        dtype=float,
    ))
    max_accel_step = np.radians(np.array(
        [proximal_max_accel_step_deg] * 4 + [wrist_max_accel_step_deg] * 3,
        dtype=float,
    ))

    base.RUNTIME_JOINT_SMOOTHER_APPLIED = False
    base.RUNTIME_JOINT_SMOOTHER_RAW_STEP_DEG = 0.0
    base.RUNTIME_JOINT_SMOOTHER_APPLIED_STEP_DEG = 0.0
    base.RUNTIME_JOINT_SMOOTHER_BLOCKED = False

    def smooth_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        if model is None or data is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        if qpos_ids.size != 7:
            return original_solver(*args, **kwargs)

        import mujoco

        start_q = data.qpos[qpos_ids].copy()
        result = original_solver(*args, **kwargs)
        desired_q = data.qpos[qpos_ids].copy()
        raw_step = desired_q - start_q

        previous_step = np.asarray(
            context.get("_joint_smoother_previous_step", np.zeros(7)),
            dtype=float,
        )
        velocity_limited = np.clip(raw_step, -max_step, max_step)
        accel_delta = np.clip(
            velocity_limited - previous_step,
            -max_accel_step,
            max_accel_step,
        )
        applied_step = previous_step + accel_delta
        applied_step = np.clip(applied_step, -max_step, max_step)

        base.RUNTIME_JOINT_SMOOTHER_RAW_STEP_DEG = math.degrees(
            float(np.linalg.norm(raw_step))
        )
        base.RUNTIME_JOINT_SMOOTHER_APPLIED_STEP_DEG = math.degrees(
            float(np.linalg.norm(applied_step))
        )
        base.RUNTIME_JOINT_SMOOTHER_APPLIED = bool(
            np.linalg.norm(applied_step - raw_step) > 1e-10
        )
        base.RUNTIME_JOINT_SMOOTHER_BLOCKED = False

        accepted = False
        candidate_step = applied_step.copy()
        for line_search_index in range(6):
            scale = 0.5 ** line_search_index
            data.qpos[qpos_ids] = start_q + scale * candidate_step
            base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            if not base.has_right_arm_core_contact(model, data, context):
                applied_step = data.qpos[qpos_ids].copy() - start_q
                accepted = True
                break

        if not accepted:
            data.qpos[qpos_ids] = start_q
            applied_step = np.zeros(7)
            base.RUNTIME_JOINT_SMOOTHER_BLOCKED = True
            mujoco.mj_forward(model, data)

        context["_joint_smoother_previous_step"] = applied_step.copy()
        context["joint_smoother_applied"] = bool(base.RUNTIME_JOINT_SMOOTHER_APPLIED)
        context["joint_smoother_blocked"] = bool(base.RUNTIME_JOINT_SMOOTHER_BLOCKED)
        context["joint_smoother_step_deg"] = float(
            base.RUNTIME_JOINT_SMOOTHER_APPLIED_STEP_DEG
        )

        position_body = context.get("position_body")
        if position_body is None:
            return result
        return data.xpos[int(position_body)].copy()

    base.solve_right_arm_target = smooth_solver
    base._JOINT_COMMAND_SMOOTHER_INSTALLED = True
