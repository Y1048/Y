"""Motion-quality helpers for configured G1 right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_PREFERRED_ELBOW_DEG = 55.0
TORSO_FRONT_PREFERRED_ELBOW_DEG = 90.0
TORSO_FRONT_FULL_X_M = 0.18
TORSO_FRONT_RELEASE_X_M = 0.26
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
    return float(t * t * (3.0 - 2.0 * t))


def install_target_aware_elbow_pole(base: ModuleType) -> None:
    """Lift the right elbow when the wrist target approaches the torso front."""
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
    """Feed a target-aware bent-elbow preference into the position IK while moving."""

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
    """Compatibility no-op.

    Cartesian speed limiting, the 60 Hz no-catchup reference, and one IK substep
    already bound the configured motion. A second joint velocity/acceleration
    limiter caused the arm to lag behind reachable targets and produced visible
    stop-go motion when collision/fallback candidates changed. Keep this entry
    point for callers, but deliberately do not wrap ``solve_right_arm_target``.
    """
    del proximal_max_step_deg, wrist_max_step_deg
    del proximal_max_accel_step_deg, wrist_max_accel_step_deg
    if getattr(base, "_JOINT_COMMAND_SMOOTHER_INSTALLED", False):
        return
    base.RUNTIME_JOINT_SMOOTHER_APPLIED = False
    base.RUNTIME_JOINT_SMOOTHER_RAW_STEP_DEG = 0.0
    base.RUNTIME_JOINT_SMOOTHER_APPLIED_STEP_DEG = 0.0
    base.RUNTIME_JOINT_SMOOTHER_BLOCKED = False
    base._JOINT_COMMAND_SMOOTHER_INSTALLED = True
