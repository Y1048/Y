"""Immediate severe-error trigger layered on top of the normal IK fallback.

Normal pose errors still use the configured frame-count hysteresis. A severe
tracking error restores the cycle's starting joint state, arms the existing
fallback supervisor, and reruns the same configured solver stack once so a
coupled or multi-seed candidate can be considered immediately.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SevereIKFallbackSettings:
    position_error_m: float
    rotation_error_rad: float


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return result


def load_severe_ik_fallback_settings(path: str | Path) -> SevereIKFallbackSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        raw = payload["ik"]["fallback"]
    except (KeyError, TypeError) as exc:
        raise ValueError("ik.fallback config is required") from exc
    if not isinstance(raw, dict):
        raise ValueError("ik.fallback must be an object")

    normal_position = _positive_number(
        raw.get("position_error_enter_m"),
        "ik.fallback.position_error_enter_m",
    )
    normal_rotation_deg = _positive_number(
        raw.get("rotation_error_enter_deg"),
        "ik.fallback.rotation_error_enter_deg",
    )
    severe_position = _positive_number(
        raw.get("severe_position_error_m"),
        "ik.fallback.severe_position_error_m",
    )
    severe_rotation_deg = _positive_number(
        raw.get("severe_rotation_error_deg"),
        "ik.fallback.severe_rotation_error_deg",
    )
    if severe_position <= normal_position:
        raise ValueError(
            "ik.fallback.severe_position_error_m must exceed the normal enter threshold"
        )
    if severe_rotation_deg <= normal_rotation_deg:
        raise ValueError(
            "ik.fallback.severe_rotation_error_deg must exceed the normal enter threshold"
        )
    return SevereIKFallbackSettings(
        position_error_m=severe_position,
        rotation_error_rad=math.radians(severe_rotation_deg),
    )


def install_severe_ik_fallback_trigger(
    base: ModuleType,
    settings: SevereIKFallbackSettings,
) -> None:
    """Trigger the already-installed coupled fallback immediately on severe error."""
    original_solver = getattr(base, "solve_right_arm_target", None)
    supervisor = getattr(base, "IK_FALLBACK_SUPERVISOR", None)
    if not callable(original_solver) or supervisor is None:
        raise RuntimeError("install the coupled IK fallback before the severe trigger")
    if getattr(base, "_SEVERE_IK_FALLBACK_INSTALLED", False):
        return

    base.RUNTIME_IK_SEVERE_TRIGGERED = False
    base.RUNTIME_IK_SEVERE_REASON = None

    def severe_supervised_solver(*args: Any, **kwargs: Any):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 7:
            context = args[7]

        qpos_ids = None
        start_q = None
        if data is not None and isinstance(context, dict):
            qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
            if qpos_ids.size:
                start_q = data.qpos[qpos_ids].copy()

        base.RUNTIME_IK_SEVERE_TRIGGERED = False
        base.RUNTIME_IK_SEVERE_REASON = None
        result = original_solver(*args, **kwargs)

        if start_q is None or qpos_ids is None or supervisor.active:
            return result

        position_error = getattr(base, "RUNTIME_IK_POSITION_ERROR_M", None)
        rotation_error = getattr(base, "RUNTIME_IK_ROTATION_ERROR_RAD", None)
        severe_position = (
            position_error is not None
            and math.isfinite(float(position_error))
            and float(position_error) >= settings.position_error_m
        )
        severe_rotation = (
            rotation_error is not None
            and math.isfinite(float(rotation_error))
            and float(rotation_error) >= settings.rotation_error_rad
        )
        if not (severe_position or severe_rotation):
            return result

        # Re-evaluate from the same cycle start. This prevents the emergency path
        # from stacking an extra joint step on top of the decoupled candidate.
        data.qpos[qpos_ids] = start_q
        try:
            import mujoco
            mujoco.mj_forward(model, data)
        except (ImportError, TypeError):
            pass

        supervisor.active = True
        supervisor.bad_frames = 0
        supervisor.good_frames = 0
        base.RUNTIME_IK_SEVERE_TRIGGERED = True
        if severe_position and severe_rotation:
            base.RUNTIME_IK_SEVERE_REASON = "position_and_rotation"
        elif severe_position:
            base.RUNTIME_IK_SEVERE_REASON = "position"
        else:
            base.RUNTIME_IK_SEVERE_REASON = "rotation"
        return original_solver(*args, **kwargs)

    base.solve_right_arm_target = severe_supervised_solver
    base._SEVERE_IK_FALLBACK_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(
        base, "_SEVERE_IK_STATUS_INSTALLED", False
    ):
        def severe_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["ik_severe_fallback_triggered"] = bool(
                base.RUNTIME_IK_SEVERE_TRIGGERED
            )
            enriched["ik_severe_fallback_reason"] = base.RUNTIME_IK_SEVERE_REASON
            enriched["ik_severe_position_threshold_m"] = float(
                settings.position_error_m
            )
            enriched["ik_severe_rotation_threshold_deg"] = math.degrees(
                settings.rotation_error_rad
            )
            original_status_writer(enriched)

        base.write_runtime_status = severe_status_writer
        base._SEVERE_IK_STATUS_INSTALLED = True
