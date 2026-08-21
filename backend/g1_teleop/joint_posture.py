"""Joint-space posture scheduling for redundant right-arm Cartesian IK."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "config" / "joint_postures.json"


def _smoothstep(value: float) -> float:
    t = float(np.clip(value, 0.0, 1.0))
    return t * t * (3.0 - 2.0 * t)


def load_right_arm_posture_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    arm = payload["right_arm"]
    ready = np.asarray(arm["ready_deg"], dtype=float)
    torso_raw = arm.get("torso_front_deg")
    torso = None if torso_raw is None else np.asarray(torso_raw, dtype=float)
    if ready.shape != (7,):
        raise ValueError("right_arm.ready_deg must contain 7 joint angles")
    if torso is not None and torso.shape != (7,):
        raise ValueError("right_arm.torso_front_deg must contain 7 joint angles or null")
    return {
        "ready_rad": np.radians(ready),
        "torso_rad": None if torso is None else np.radians(torso),
        "blend": dict(arm["blend"]),
    }


def posture_blend(target_position: np.ndarray, blend_cfg: dict[str, Any]) -> float:
    """Blend from side/ready posture to torso-front posture using robot-space geometry."""
    x, y, z = (float(v) for v in np.asarray(target_position, dtype=float))
    x_min = float(blend_cfg["front_x_min_m"])
    x_max = float(blend_cfg["front_x_max_m"])
    z_min = float(blend_cfg["z_min_m"])
    z_max = float(blend_cfg["z_max_m"])
    if not (x_min <= x <= x_max and z_min <= z <= z_max):
        return 0.0

    enter = float(blend_cfg["centerline_enter_abs_y_m"])
    release = float(blend_cfg["centerline_release_abs_y_m"])
    if release <= enter:
        raise ValueError("centerline_release_abs_y_m must be greater than enter")
    ay = abs(y)
    if ay <= enter:
        return 1.0
    if ay >= release:
        return 0.0
    linear = (release - ay) / (release - enter)
    return _smoothstep(linear)


def install_joint_space_posture_scheduler(
    base: ModuleType,
    *,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> None:
    """Feed a blended joint-space posture into the existing Cartesian IK null space.

    Wrist Cartesian position remains the primary task. The existing solver's
    ``preferred`` null-space term receives a robot-space posture reference that
    blends continuously between the ready posture and a captured torso-front
    posture. Wrist orientation remains owned by the dedicated wrist-only overlay.
    """
    if getattr(base, "_JOINT_SPACE_POSTURE_SCHEDULER_INSTALLED", False):
        return

    profile = load_right_arm_posture_profile(profile_path)
    ready = profile["ready_rad"]
    torso = profile["torso_rad"]
    blend_cfg = profile["blend"]
    original_solver = getattr(base, "solve_right_arm_target", None)
    if not callable(original_solver):
        raise RuntimeError("solve_right_arm_target must exist before posture scheduler install")

    base.RUNTIME_JOINT_POSTURE_ENABLED = torso is not None
    base.RUNTIME_JOINT_POSTURE_BLEND = 0.0
    base.RUNTIME_JOINT_POSTURE_TARGET_DEG = None

    def scheduled_solver(*args: Any, **kwargs: Any):
        preferred = args[3] if len(args) > 3 else kwargs.get("preferred")
        target = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]
        if preferred is None or target is None or not isinstance(context, dict):
            return original_solver(*args, **kwargs)

        preferred_value = np.asarray(preferred, dtype=float).copy()
        if preferred_value.size < 7:
            return original_solver(*args, **kwargs)

        target_position = np.asarray(target, dtype=float)
        alpha = 0.0 if torso is None else posture_blend(target_position, blend_cfg)
        if torso is not None:
            # Proximal joints define arm shape. Keep wrist posture neutral here;
            # orientation is repaired afterwards by the wrist-only overlay.
            scheduled = (1.0 - alpha) * ready + alpha * torso
            preferred_value[:4] = scheduled[:4]
            preferred_value[4:7] = np.asarray(preferred, dtype=float)[4:7]
        else:
            scheduled = np.asarray(preferred, dtype=float).copy()

        base.RUNTIME_JOINT_POSTURE_ENABLED = torso is not None
        base.RUNTIME_JOINT_POSTURE_BLEND = float(alpha)
        base.RUNTIME_JOINT_POSTURE_TARGET_DEG = np.degrees(scheduled).tolist()
        context["joint_posture_enabled"] = bool(torso is not None)
        context["joint_posture_blend"] = float(alpha)
        context["joint_posture_target_deg"] = list(base.RUNTIME_JOINT_POSTURE_TARGET_DEG)

        if len(args) > 3:
            adjusted_args = list(args)
            adjusted_args[3] = preferred_value
            return original_solver(*adjusted_args, **kwargs)

        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["preferred"] = preferred_value
        return original_solver(*args, **adjusted_kwargs)

    base.solve_right_arm_target = scheduled_solver
    base._JOINT_SPACE_POSTURE_SCHEDULER_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_JOINT_POSTURE_STATUS_INSTALLED", False):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["joint_posture_enabled"] = bool(base.RUNTIME_JOINT_POSTURE_ENABLED)
            enriched["joint_posture_blend"] = float(base.RUNTIME_JOINT_POSTURE_BLEND)
            enriched["joint_posture_target_deg"] = base.RUNTIME_JOINT_POSTURE_TARGET_DEG
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._JOINT_POSTURE_STATUS_INSTALLED = True
