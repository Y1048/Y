"""Two-stage torso-front arm preparation for stable right-arm teleoperation."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

import numpy as np


TORSO_FRONT_ENTER_X_M = 0.20
TORSO_FRONT_EXIT_X_M = 0.24
TORSO_FRONT_LATERAL_ABS_Y_M = 0.26
TORSO_FRONT_ELBOW_TARGET_DEG = 90.0
TORSO_FRONT_ELBOW_READY_DEG = 75.0


def install_torso_front_prepose(base: ModuleType) -> None:
    """Prepare a bent elbow before allowing the wrist to move into torso-front space.

    Simultaneously moving the wrist inward and changing the elbow branch made the
    configured IK stack oscillate between primary/fallback solutions. This wrapper
    instead uses the arm's one positional null-space DoF explicitly:

    1. when the requested wrist target enters the torso-front region, hold the
       current wrist position;
    2. temporarily prefer a 90 degree elbow and disable the engagement-captured
       elbow pole so the arm can re-pose without fighting the old elbow plane;
    3. once the elbow reaches 75 degrees, release the requested wrist target while
       keeping the 90 degree elbow preference inside the torso-front region.

    Collision handling remains inside the existing solver stack and is not relaxed.
    """
    if getattr(base, "_TORSO_FRONT_PREPOSE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before torso pre-pose install")

    elbow_target_rad = math.radians(TORSO_FRONT_ELBOW_TARGET_DEG)
    elbow_ready_rad = math.radians(TORSO_FRONT_ELBOW_READY_DEG)

    base.RUNTIME_TORSO_PREPOSE_ACTIVE = False
    base.RUNTIME_TORSO_PREPOSE_HOLDING_WRIST = False
    base.RUNTIME_TORSO_PREPOSE_ELBOW_DEG = None

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
        if target_position.shape != (3,) or qpos_ids.size < 4 or position_body is None:
            return original_solver(*args, **kwargs)

        active_previous = bool(context.get("_torso_prepose_region_active", False))
        within_lateral = abs(float(target_position[1])) <= TORSO_FRONT_LATERAL_ABS_Y_M
        if active_previous:
            region_active = within_lateral and float(target_position[0]) < TORSO_FRONT_EXIT_X_M
        else:
            region_active = within_lateral and float(target_position[0]) <= TORSO_FRONT_ENTER_X_M
        context["_torso_prepose_region_active"] = region_active

        current_elbow = float(data.qpos[qpos_ids[3]])
        current_elbow_deg = math.degrees(current_elbow)
        holding_wrist = bool(region_active and current_elbow < elbow_ready_rad)

        base.RUNTIME_TORSO_PREPOSE_ACTIVE = region_active
        base.RUNTIME_TORSO_PREPOSE_HOLDING_WRIST = holding_wrist
        base.RUNTIME_TORSO_PREPOSE_ELBOW_DEG = current_elbow_deg
        context["torso_prepose_active"] = region_active
        context["torso_prepose_holding_wrist"] = holding_wrist
        context["torso_prepose_elbow_deg"] = current_elbow_deg

        if not region_active:
            return original_solver(*args, **kwargs)

        preferred_value = np.asarray(preferred, dtype=float).copy()
        if preferred_value.size >= 4:
            preferred_value[3] = elbow_target_rad

        adjusted_target = target_position.copy()
        if holding_wrist:
            adjusted_target = np.asarray(data.xpos[int(position_body)], dtype=float).copy()

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = None

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
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._TORSO_PREPOSE_STATUS_INSTALLED = True
