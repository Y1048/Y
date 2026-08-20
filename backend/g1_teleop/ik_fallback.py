"""Real-time coupled 7-DoF fallback for the right-arm teleoperation IK.

The legacy decoupled solver remains the primary controller. This module observes
its pose error, enters fallback only after persistent failure, and compares a
single coupled 7-DoF DLS candidate against the decoupled result from the same
starting joint state. The coupled candidate is accepted only when it is safer
and measurably better, so switching does not create a joint-space jump.
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
class IKFallbackSettings:
    enabled: bool
    position_error_enter_m: float
    rotation_error_enter_rad: float
    position_error_exit_m: float
    rotation_error_exit_rad: float
    enter_frames: int
    inspection_enter_frames: int
    exit_frames: int
    damping: float
    orientation_weight_m_per_rad: float
    min_improvement_ratio: float
    allow_during_inspection_contact: bool


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return result


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return int(value)


def load_ik_fallback_settings(path: str | Path) -> IKFallbackSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        raw = payload["ik"]["fallback"]
    except (KeyError, TypeError) as exc:
        raise ValueError("ik.fallback config is required") from exc
    if not isinstance(raw, dict):
        raise ValueError("ik.fallback must be an object")
    enabled = raw.get("enabled")
    allow_contact = raw.get("allow_during_inspection_contact")
    if not isinstance(enabled, bool):
        raise ValueError("ik.fallback.enabled must be a boolean")
    if not isinstance(allow_contact, bool):
        raise ValueError("ik.fallback.allow_during_inspection_contact must be a boolean")

    enter_pos = _positive_number(raw.get("position_error_enter_m"), "ik.fallback.position_error_enter_m")
    exit_pos = _positive_number(raw.get("position_error_exit_m"), "ik.fallback.position_error_exit_m")
    enter_rot_deg = _positive_number(raw.get("rotation_error_enter_deg"), "ik.fallback.rotation_error_enter_deg")
    exit_rot_deg = _positive_number(raw.get("rotation_error_exit_deg"), "ik.fallback.rotation_error_exit_deg")
    if exit_pos >= enter_pos:
        raise ValueError("ik.fallback.position_error_exit_m must be lower than enter threshold")
    if exit_rot_deg >= enter_rot_deg:
        raise ValueError("ik.fallback.rotation_error_exit_deg must be lower than enter threshold")
    improvement = _positive_number(raw.get("min_improvement_ratio"), "ik.fallback.min_improvement_ratio")
    if improvement > 1.0:
        raise ValueError("ik.fallback.min_improvement_ratio must be <= 1")

    return IKFallbackSettings(
        enabled=enabled,
        position_error_enter_m=enter_pos,
        rotation_error_enter_rad=math.radians(enter_rot_deg),
        position_error_exit_m=exit_pos,
        rotation_error_exit_rad=math.radians(exit_rot_deg),
        enter_frames=_positive_int(raw.get("enter_frames"), "ik.fallback.enter_frames"),
        inspection_enter_frames=_positive_int(raw.get("inspection_enter_frames"), "ik.fallback.inspection_enter_frames"),
        exit_frames=_positive_int(raw.get("exit_frames"), "ik.fallback.exit_frames"),
        damping=_positive_number(raw.get("damping"), "ik.fallback.damping"),
        orientation_weight_m_per_rad=_positive_number(raw.get("orientation_weight_m_per_rad"), "ik.fallback.orientation_weight_m_per_rad"),
        min_improvement_ratio=improvement,
        allow_during_inspection_contact=allow_contact,
    )


@dataclass(frozen=True)
class IKFallbackTransition:
    active: bool
    changed: bool
    reason: str
    bad_frames: int
    good_frames: int


class IKFallbackSupervisor:
    def __init__(self, settings: IKFallbackSettings) -> None:
        self.settings = settings
        self.active = False
        self.bad_frames = 0
        self.good_frames = 0

    def update(self, position_error_m: float, rotation_error_rad: float, *, inspection_contact: bool) -> IKFallbackTransition:
        previous = self.active
        if not self.settings.enabled:
            self.active = False
            self.bad_frames = 0
            self.good_frames = 0
            return IKFallbackTransition(False, previous, "disabled", 0, 0)

        bad = (
            position_error_m >= self.settings.position_error_enter_m
            or rotation_error_rad >= self.settings.rotation_error_enter_rad
        )
        good = (
            position_error_m <= self.settings.position_error_exit_m
            and rotation_error_rad <= self.settings.rotation_error_exit_rad
        )

        if self.active:
            self.bad_frames = 0
            self.good_frames = self.good_frames + 1 if good else 0
            if self.good_frames >= self.settings.exit_frames:
                self.active = False
                self.good_frames = 0
                reason = "decoupled_recovered"
            else:
                reason = "fallback_active"
        else:
            self.good_frames = 0
            self.bad_frames = self.bad_frames + 1 if bad else 0
            required = self.settings.inspection_enter_frames if inspection_contact else self.settings.enter_frames
            if self.bad_frames >= required:
                self.active = True
                self.bad_frames = 0
                reason = "persistent_pose_error"
            else:
                reason = "decoupled_primary"

        return IKFallbackTransition(
            self.active,
            previous != self.active,
            reason,
            self.bad_frames,
            self.good_frames,
        )


def _pose_errors(base: ModuleType, data: Any, context: dict[str, Any], target_position: np.ndarray, target_rotation: np.ndarray) -> tuple[float, float]:
    position_error = float(np.linalg.norm(np.asarray(target_position) - data.xpos[context["position_body"]]))
    current_rotation = data.xmat[context["orientation_body"]].reshape(3, 3)
    rotation_error = float(np.linalg.norm(base.calculate_rotation_error(target_rotation, current_rotation)))
    return position_error, rotation_error


def _normalized_score(settings: IKFallbackSettings, position_error_m: float, rotation_error_rad: float) -> float:
    return (
        position_error_m / settings.position_error_exit_m
        + rotation_error_rad / settings.rotation_error_exit_rad
    )


def _inspection_contact_state(base: ModuleType, context: dict[str, Any]) -> bool:
    state = str(getattr(base, "RUNTIME_INSPECTION_STATE", "free_space"))
    return bool(
        context.get("task_contact_active", False)
        or state in {"contact_acquire", "inspection_contact", "surface_follow"}
    )


def _coupled_candidate(
    base: ModuleType,
    model: Any,
    data: Any,
    context: dict[str, Any],
    start_q: np.ndarray,
    target_position: np.ndarray,
    target_rotation: np.ndarray,
    settings: IKFallbackSettings,
) -> tuple[np.ndarray | None, float, float]:
    import mujoco

    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    dof_ids = np.asarray(context["right_dof_ids"], dtype=int)
    data.qpos[qpos_ids] = start_q
    mujoco.mj_forward(model, data)

    jacp = np.zeros((3, model.nv))
    jacr_dummy = np.zeros((3, model.nv))
    orientation_jacp_dummy = np.zeros((3, model.nv))
    orientation_jacr = np.zeros((3, model.nv))
    mujoco.mj_jacBody(model, data, jacp, jacr_dummy, int(context["position_body"]))
    mujoco.mj_jacBody(model, data, orientation_jacp_dummy, orientation_jacr, int(context["orientation_body"]))

    position_error_vector = np.asarray(target_position, dtype=float) - data.xpos[context["position_body"]]
    current_rotation = data.xmat[context["orientation_body"]].reshape(3, 3)
    rotation_error_vector = np.asarray(base.calculate_rotation_error(target_rotation, current_rotation), dtype=float)
    weight = settings.orientation_weight_m_per_rad
    jacobian = np.vstack((jacp[:, dof_ids], weight * orientation_jacr[:, dof_ids]))
    error = np.concatenate((position_error_vector, weight * rotation_error_vector))

    damping_matrix = (settings.damping ** 2) * np.eye(6)
    try:
        step = jacobian.T @ np.linalg.solve(jacobian @ jacobian.T + damping_matrix, error)
    except np.linalg.LinAlgError:
        data.qpos[qpos_ids] = start_q
        mujoco.mj_forward(model, data)
        return None, math.inf, math.inf

    step *= float(getattr(base, "IK_STEP_GAIN", 1.0))
    max_step = float(getattr(base, "IK_MAX_STEP_RADIANS", math.radians(1.5)))
    step = np.clip(step, -max_step, max_step)
    data.qpos[qpos_ids] = start_q + step
    base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
    mujoco.mj_forward(model, data)

    if base.has_right_arm_core_contact(model, data, context):
        data.qpos[qpos_ids] = start_q
        mujoco.mj_forward(model, data)
        return None, math.inf, math.inf

    candidate_q = data.qpos[qpos_ids].copy()
    position_error_m, rotation_error_rad = _pose_errors(
        base, data, context, target_position, target_rotation
    )
    return candidate_q, position_error_m, rotation_error_rad


def install_coupled_ik_fallback(base: ModuleType, settings: IKFallbackSettings) -> IKFallbackSupervisor:
    supervisor = IKFallbackSupervisor(settings)
    base.IK_FALLBACK_SUPERVISOR = supervisor
    base.RUNTIME_IK_MODE = "decoupled"
    base.RUNTIME_IK_FALLBACK_ACTIVE = False
    base.RUNTIME_IK_POSITION_ERROR_M = None
    base.RUNTIME_IK_ROTATION_ERROR_RAD = None
    base.RUNTIME_IK_COUPLED_SCORE = None
    base.RUNTIME_IK_DECOUPLED_SCORE = None

    original_solver = getattr(base, "solve_right_arm_target", None)
    if callable(original_solver) and not getattr(base, "_COUPLED_IK_FALLBACK_INSTALLED", False):
        def supervised_solver(*args: Any, **kwargs: Any):
            model = args[0] if len(args) > 0 else kwargs.get("model")
            data = args[1] if len(args) > 1 else kwargs.get("data")
            target_position = args[4] if len(args) > 4 else kwargs.get("target_position", kwargs.get("target"))
            target_rotation = kwargs.get("target_rotation")
            context = kwargs.get("context")
            if context is None and len(args) > 7:
                context = args[7]
            if (
                model is None
                or data is None
                or target_position is None
                or target_rotation is None
                or not isinstance(context, dict)
            ):
                return original_solver(*args, **kwargs)

            qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
            start_q = data.qpos[qpos_ids].copy()
            result = original_solver(*args, **kwargs)
            decoupled_q = data.qpos[qpos_ids].copy()
            dec_position_error, dec_rotation_error = _pose_errors(
                base,
                data,
                context,
                np.asarray(target_position, dtype=float),
                np.asarray(target_rotation, dtype=float),
            )
            inspection_contact = _inspection_contact_state(base, context)
            transition = supervisor.update(
                dec_position_error,
                dec_rotation_error,
                inspection_contact=inspection_contact,
            )
            decoupled_score = _normalized_score(settings, dec_position_error, dec_rotation_error)
            base.RUNTIME_IK_FALLBACK_ACTIVE = transition.active
            base.RUNTIME_IK_POSITION_ERROR_M = dec_position_error
            base.RUNTIME_IK_ROTATION_ERROR_RAD = dec_rotation_error
            base.RUNTIME_IK_DECOUPLED_SCORE = decoupled_score
            base.RUNTIME_IK_COUPLED_SCORE = None
            base.RUNTIME_IK_MODE = "decoupled"
            context["ik_mode"] = "decoupled"

            collision_busy = getattr(base, "RUNTIME_COLLISION_NEAREST_STATUS", None) is not None
            contact_blocked = inspection_contact and not settings.allow_during_inspection_contact
            if not transition.active or collision_busy or contact_blocked:
                return result

            coupled_q, coupled_position_error, coupled_rotation_error = _coupled_candidate(
                base,
                model,
                data,
                context,
                start_q,
                np.asarray(target_position, dtype=float),
                np.asarray(target_rotation, dtype=float),
                settings,
            )
            coupled_score = _normalized_score(
                settings, coupled_position_error, coupled_rotation_error
            )
            base.RUNTIME_IK_COUPLED_SCORE = (
                coupled_score if math.isfinite(coupled_score) else None
            )

            if (
                coupled_q is not None
                and coupled_score <= decoupled_score * settings.min_improvement_ratio
            ):
                data.qpos[qpos_ids] = coupled_q
                import mujoco
                mujoco.mj_forward(model, data)
                base.RUNTIME_IK_MODE = "coupled_fallback"
                base.RUNTIME_IK_POSITION_ERROR_M = coupled_position_error
                base.RUNTIME_IK_ROTATION_ERROR_RAD = coupled_rotation_error
                context["ik_mode"] = "coupled_fallback"
                return data.xpos[context["position_body"]].copy()

            data.qpos[qpos_ids] = decoupled_q
            import mujoco
            mujoco.mj_forward(model, data)
            return result

        base.solve_right_arm_target = supervised_solver
        base._COUPLED_IK_FALLBACK_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_IK_FALLBACK_STATUS_INSTALLED", False):
        def ik_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["ik_mode"] = base.RUNTIME_IK_MODE
            enriched["ik_fallback_active"] = bool(base.RUNTIME_IK_FALLBACK_ACTIVE)
            enriched["ik_position_error_m"] = base.RUNTIME_IK_POSITION_ERROR_M
            rotation_error = base.RUNTIME_IK_ROTATION_ERROR_RAD
            enriched["ik_rotation_error_deg"] = (
                math.degrees(rotation_error) if rotation_error is not None else None
            )
            enriched["ik_decoupled_score"] = base.RUNTIME_IK_DECOUPLED_SCORE
            enriched["ik_coupled_score"] = base.RUNTIME_IK_COUPLED_SCORE
            enriched["ik_fallback_bad_frames"] = supervisor.bad_frames
            enriched["ik_fallback_good_frames"] = supervisor.good_frames
            original_status_writer(enriched)

        base.write_runtime_status = ik_status_writer
        base._IK_FALLBACK_STATUS_INSTALLED = True

    return supervisor
