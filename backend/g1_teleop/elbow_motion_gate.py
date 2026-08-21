"""Motion gate for elbow-pole tasks in configured right-arm teleoperation."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_TARGET_MOTION_THRESHOLD_M = 0.00005


def install_elbow_pole_motion_gate(
    base: ModuleType,
    *,
    target_motion_threshold_m: float = DEFAULT_TARGET_MOTION_THRESHOLD_M,
) -> None:
    """Disable elbow-pole adaptation while Cartesian position is stationary.

    Torso-front elbow shaping should occur while the wrist reference is moving.
    Once position holds, removing the pole task preserves the achieved proximal
    posture so wrist-only orientation does not slowly re-pose the shoulder/elbow.
    """
    if getattr(base, "_ELBOW_POLE_MOTION_GATE_INSTALLED", False):
        return

    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before elbow pole gate")

    def gated_solver(*args: Any, **kwargs: Any):
        target = args[4] if len(args) > 4 else kwargs.get(
            "target_position", kwargs.get("target")
        )
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if target is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        if target_position.shape != (3,) or not np.all(np.isfinite(target_position)):
            return original_solver(*args, **kwargs)

        previous = context.get("_elbow_pole_gate_previous_target")
        context["_elbow_pole_gate_previous_target"] = target_position.copy()
        motion = 0.0 if previous is None else float(
            np.linalg.norm(target_position - np.asarray(previous, dtype=float))
        )
        moving = motion > float(target_motion_threshold_m)
        context["elbow_pole_target_moving"] = bool(moving)
        context["elbow_pole_target_motion_m"] = float(motion)

        if moving:
            return original_solver(*args, **kwargs)

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["elbow_pole_reference"] = None
        return original_solver(*args, **adjusted_kwargs)

    base.solve_right_arm_target = gated_solver
    base._ELBOW_POLE_MOTION_GATE_INSTALLED = True
