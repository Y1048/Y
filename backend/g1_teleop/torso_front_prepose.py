"""Two-stage torso-front arm preparation for stable right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


TORSO_FRONT_ENTER_X_MIN_M = 0.08
TORSO_FRONT_ENTER_X_MAX_M = 0.28
TORSO_FRONT_EXIT_X_MIN_M = 0.05
TORSO_FRONT_EXIT_X_MAX_M = 0.32
TORSO_FRONT_ENTER_ABS_Y_M = 0.18
TORSO_FRONT_EXIT_ABS_Y_M = 0.22
TORSO_FRONT_Z_MIN_M = 0.72
TORSO_FRONT_Z_MAX_M = 1.15
TORSO_FRONT_ELBOW_TARGET_DEG = 90.0
TORSO_FRONT_ELBOW_READY_DEG = 75.0
# MuJoCo G1 frame: +X forward, +Y left, +Z up. For the right arm, outward is -Y.
# Bias the elbow strongly upward and moderately outward so torso-front motion forms
# the intended L-shaped arm instead of choosing an arbitrary elbow plane.
TORSO_FRONT_ELBOW_POLE_DIRECTION = np.array([0.0, -0.45, 0.89], dtype=float)


def _in_torso_front_region(target_position: np.ndarray, *, active_previous: bool) -> bool:
    x, y, z = (float(value) for value in np.asarray(target_position, dtype=float))
    if active_previous:
        return (
            TORSO_FRONT_EXIT_X_MIN_M <= x <= TORSO_FRONT_EXIT_X_MAX_M
            and abs(y) <= TORSO_FRONT_EXIT_ABS_Y_M
            and TORSO_FRONT_Z_MIN_M <= z <= TORSO_FRONT_Z_MAX_M
        )
    return (
        TORSO_FRONT_ENTER_X_MIN_M <= x <= TORSO_FRONT_ENTER_X_MAX_M
        and abs(y) <= TORSO_FRONT_ENTER_ABS_Y_M
        and TORSO_FRONT_Z_MIN_M <= z <= TORSO_FRONT_Z_MAX_M
    )


def install_torso_front_prepose(base: ModuleType) -> None:
    """Prepare a bent, upward/outward elbow before torso-front wrist motion.

    The wrist is held while the elbow is first bent toward 90 degrees. Unlike the
    previous version, the elbow plane is not left unconstrained: an explicit pole
    direction sends the right elbow upward (+Z) and outward (-Y). After the elbow
    reaches 75 degrees the requested wrist target is released while the same elbow
    pole and 90 degree bend preference remain active inside the torso-front region.
    """
    if getattr(base, "_TORSO_FRONT_PREPOSE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before torso pre-pose install")

    elbow_target_rad = math.radians(TORSO_FRONT_ELBOW_TARGET_DEG)
    elbow_ready_rad = math.radians(TORSO_FRONT_ELBOW_READY_DEG)
    desired_pole = TORSO_FRONT_ELBOW_POLE_DIRECTION.copy()
    desired_pole /= max(float(np.linalg.norm(desired_pole)), 1e-12)

    base.RUNTIME_TORSO_PREPOSE_ACTIVE = False
    base.RUNTIME_TORSO_PREPOSE_HOLDING_WRIST = False
    base.RUNTIME_TORSO_PREPOSE_ELBOW_DEG = None
    base.RUNTIME_TORSO_PREPOSE_ELBOW_POSITION = None
    base.RUNTIME_TORSO_PREPOSE_ELBOW_TARGET = None
    base.RUNTIME_TORSO_PREPOSE_POLE_DIRECTION = desired_pole.copy()

    def prepose_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        preferred = args[3] if len(args) > 3 else kwargs.get("preferred")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]

        if (
            model is None
            or data is None
            or preferred is None
            or target is None
            or not isinstance(context, dict)
        ):
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        position_body = context.get("position_body")
        shoulder_body = context.get("shoulder_body")
        elbow_body = context.get("elbow_body")
        if (
            target_position.shape != (3,)
            or qpos_ids.size < 4
            or position_body is None
            or shoulder_body is None
            or elbow_body is None
        ):
            return original_solver(*args, **kwargs)

        active_previous = bool(context.get("_torso_prepose_region_active", False))
        region_active = _in_torso_front_region(
            target_position,
            active_previous=active_previous,
        )
        context["_torso_prepose_region_active"] = region_active

        current_elbow = float(data.qpos[qpos_ids[3]])
        current_elbow_deg = math.degrees(current_elbow)
        holding_wrist = bool(region_active and current_elbow < elbow_ready_rad)

        elbow_position = np.asarray(data.xpos[int(elbow_body)], dtype=float).copy()
        base.RUNTIME_TORSO_PREPOSE_ACTIVE = region_active
        base.RUNTIME_TORSO_PREPOSE_HOLDING_WRIST = holding_wrist
        base.RUNTIME_TORSO_PREPOSE_ELBOW_DEG = current_elbow_deg
        base.RUNTIME_TORSO_PREPOSE_ELBOW_POSITION = elbow_position.copy()
        base.RUNTIME_TORSO_PREPOSE_ELBOW_TARGET = None
        context["torso_prepose_active"] = region_active
        context["torso_prepose_holding_wrist"] = holding_wrist
        context["torso_prepose_elbow_deg"] = current_elbow_deg
        context["torso_prepose_elbow_position"] = elbow_position.tolist()

        if not region_active:
            return original_solver(*args, **kwargs)

        preferred_value = np.asarray(preferred, dtype=float).copy()
        if preferred_value.size >= 4:
            preferred_value[3] = elbow_target_rad

        adjusted_target = target_position.copy()
        if holding_wrist:
            adjusted_target = np.asarray(data.xpos[int(position_body)], dtype=float).copy()

        source_pole = kwargs.get("elbow_pole_reference")
        if isinstance(source_pole, dict):
            adjusted_pole = dict(source_pole)
        else:
            # Fall back to the current geometry only if a clutch pole is unavailable.
            adjusted_pole = base.capture_elbow_pole_reference(
                data,
                int(shoulder_body),
                int(elbow_body),
                int(position_body),
            )
        adjusted_pole["pole_direction"] = desired_pole.copy()

        elbow_target = np.asarray(
            base.calculate_elbow_pole_target(
                np.asarray(data.xpos[int(shoulder_body)], dtype=float),
                adjusted_target,
                adjusted_pole,
            ),
            dtype=float,
        )
        base.RUNTIME_TORSO_PREPOSE_ELBOW_TARGET = elbow_target.copy()
        context["torso_prepose_elbow_target"] = elbow_target.tolist()
        context["torso_prepose_pole_direction"] = desired_pole.tolist()

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = adjusted_pole

        if len(args) > 4:
            adjusted_args = list(args)
            adjusted_args[3] = preferred_value
            adjusted_args[4] = adjusted_target
            return original_solver(*adjusted_args, **adjusted_kwargs)

        adjusted_kwargs["preferred"] = preferred_value
        adjusted_kwargs["target_position"] = adjusted_target
        adjusted_kwargs.pop("target", None)
        return original_solver(*args, **adjusted_kwargs)

    base.solve_right_arm_target = prepose_solver
    base._TORSO_FRONT_PREPOSE_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_TORSO_PREPOSE_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["torso_prepose_active"] = bool(base.RUNTIME_TORSO_PREPOSE_ACTIVE)
            enriched["torso_prepose_holding_wrist"] = bool(base.RUNTIME_TORSO_PREPOSE_HOLDING_WRIST)
            enriched["torso_prepose_elbow_deg"] = base.RUNTIME_TORSO_PREPOSE_ELBOW_DEG
            elbow_position_value = base.RUNTIME_TORSO_PREPOSE_ELBOW_POSITION
            elbow_target_value = base.RUNTIME_TORSO_PREPOSE_ELBOW_TARGET
            enriched["torso_prepose_elbow_position"] = (
                elbow_position_value.tolist() if isinstance(elbow_position_value, np.ndarray) else elbow_position_value
            )
            enriched["torso_prepose_elbow_target"] = (
                elbow_target_value.tolist() if isinstance(elbow_target_value, np.ndarray) else elbow_target_value
            )
            enriched["torso_prepose_pole_direction"] = base.RUNTIME_TORSO_PREPOSE_POLE_DIRECTION.tolist()
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._TORSO_PREPOSE_STATUS_INSTALLED = True
