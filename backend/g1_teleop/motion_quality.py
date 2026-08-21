"""Motion-quality helpers for configured G1 right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_PREFERRED_ELBOW_DEG = 55.0
TORSO_FRONT_PREFERRED_ELBOW_DEG = 90.0
TORSO_FRONT_FULL_X_M = 0.16
TORSO_FRONT_RELEASE_X_M = 0.30
TORSO_FRONT_ELBOW_POLE_DIRECTION = np.array([0.0, -0.55, 0.835], dtype=float)
DEFAULT_TARGET_MOTION_THRESHOLD_M = 0.00005
DEFAULT_PROXIMAL_MAX_STEP_DEG = 0.30
DEFAULT_WRIST_MAX_STEP_DEG = 0.45
DEFAULT_PROXIMAL_MAX_ACCEL_STEP_DEG = 0.07
DEFAULT_WRIST_MAX_ACCEL_STEP_DEG = 0.10


def _torso_front_blend(target_position: np.ndarray) -> float:
    """Return 1 near the torso front and 0 in the normal forward workspace."""
    x = float(np.asarray(target_position, dtype=float)[0])
    if x <= TORSO_FRONT_FULL_X_M:
        return 1.0
    if x >= TORSO_FRONT_RELEASE_X_M:
        return 0.0
    t = (TORSO_FRONT_RELEASE_X_M - x) / (
        TORSO_FRONT_RELEASE_X_M - TORSO_FRONT_FULL_X_M
    )
    # Smoothstep avoids an elbow-pole discontinuity while crossing the region.
    return float(t * t * (3.0 - 2.0 * t))


def install_target_aware_elbow_pole(base: ModuleType) -> None:
    """Lift the right elbow when the wrist target approaches the torso front.

    The legacy clutch captures one elbow-pole direction at engagement and keeps it
    for the entire clutch session. That is useful in free space but can preserve a
    downward elbow branch even when a torso-front wrist target requires a bent,
    lifted elbow. This wrapper blends the captured pole toward an upward/outward
    right-arm pole as the robot-space wrist target approaches the torso.
    """
    if getattr(base, "_TARGET_AWARE_ELBOW_POLE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before elbow-pole install")

    desired_pole = TORSO_FRONT_ELBOW_POLE_DIRECTION.copy()
    desired_pole /= max(float(np.linalg.norm(desired_pole)), 1e-12)

    def pole_solver(*args: Any, **kwargs: Any):
        target = args[4] if len(args) > 4 else kwargs.get(
            "target_position", kwargs.get("target")
        )
        pole_reference = kwargs.get("elbow_pole_reference")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]

        if target is None or not isinstance(pole_reference, dict):
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        if target_position.shape != (3,) or not np.all(np.isfinite(target_position)):
            return original_solver(*args, **kwargs)

        original_direction = np.asarray(
            pole_reference.get("pole_direction", desired_pole), dtype=float
        )
        if original_direction.shape != (3,) or not np.all(np.isfinite(original_direction)):
            return original_solver(*args, **kwargs)
        original_norm = float(np.linalg.norm(original_direction))
        if original_norm < 1e-12:
            original_direction = desired_pole.copy()
        else:
            original_direction = original_direction / original_norm

        blend = _torso_front_blend(target_position)
        blended_direction = (1.0 - blend) * original_direction + blend * desired_pole
        blended_norm = float(np.linalg.norm(blended_direction))
        if blended_norm < 1e-12:
            blended_direction = desired_pole.copy()
        else:
            blended_direction /= blended_norm

        adjusted_pole = dict(pole_reference)
        adjusted_pole["pole_direction"] = blended_direction
        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = adjusted_pole

        base.RUNTIME_TORSO_FRONT_ELBOW_BLEND = float(blend)
        base.RUNTIME_TORSO_FRONT_ELBOW_POLE = blended_direction.copy()
        if isinstance(context, dict):
            context["torso_front_elbow_blend"] = float(blend)
            context["torso_front_elbow_pole"] = blended_direction.tolist()

        return original_solver(*args, **adjusted_kwargs)

    base.RUNTIME_TORSO_FRONT_ELBOW_BLEND = 0.0
    base.RUNTIME_TORSO_FRONT_ELBOW_POLE = None
    base.solve_right_arm_target = pole_solver
    base._TARGET_AWARE_ELBOW_POLE_INSTALLED = True


def install_motion_gated_elbow_preference(
    base: ModuleType,
    *,
    preferred_elbow_deg: float = DEFAULT_PREFERRED_ELBOW_DEG,
    target_motion_threshold_m: float = DEFAULT_TARGET_MOTION_THRESHOLD_M,
) -> None:
    """Feed a target-aware bent-elbow preference into the position IK while moving.

    In ordinary free space the preferred elbow angle remains 55 degrees. As the
    wrist target approaches the torso front, the preferred bend increases smoothly
    toward 90 degrees so the arm forms the required L-shaped posture instead of
    reaching inward with a nearly straight elbow. When the Cartesian target is
    stationary, the current elbow angle is held to preserve wrist-only isolation.
    """

    if getattr(base, "_MOTION_GATED_ELBOW_PREFERENCE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before elbow preference install")

    normal_preferred_elbow_rad = math.radians(float(preferred_elbow_deg))
    torso_preferred_elbow_rad = math.radians(TORSO_FRONT_PREFERRED_ELBOW_DEG)

    def preferred_solver(*args: Any, **kwargs: Any):
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
        torso_blend = _torso_front_blend(target_position)

        if target_moving:
            preferred_value[3] = (
                (1.0 - torso_blend) * normal_preferred_elbow_rad
                + torso_blend * torso_preferred_elbow_rad
            )
        else:
            preferred_value[3] = float(data.qpos[qpos_ids[3]])

        context["preferred_elbow_target_deg"] = math.degrees(float(preferred_value[3]))
        context["preferred_elbow_target_moving"] = bool(target_moving)
        context["preferred_elbow_target_motion_m"] = float(target_motion)
        context["torso_front_elbow_preference_blend"] = float(torso_blend)

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
    """Rate/acceleration limit the final seven-joint command written to qpos."""
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
