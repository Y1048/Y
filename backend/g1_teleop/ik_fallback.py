"""Real-time coupled and multi-seed 7-DoF fallback for right-arm teleoperation IK.

The legacy decoupled solver remains primary. Persistent pose error first enables a
coupled 7-DoF candidate from the current state. If that is not good enough, the
same cycle may explore multiple internal seeds, but the final command is always
clipped back to one normal IK joint step from the actual current state.
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
class MultiSeedSettings:
    enabled: bool
    iterations_per_seed: int
    shoulder_yaw_offset_rad: float
    elbow_offset_rad: float
    ready_seed_enabled: bool
    joint_motion_weight: float
    joint_margin_weight: float
    min_improvement_ratio: float


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
    multiseed: MultiSeedSettings


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")
    return result


def _nonnegative_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")
    return result


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return int(value)


def _ratio(value: Any, name: str) -> float:
    result = _positive_number(value, name)
    if result > 1.0:
        raise ValueError(f"{name} must be <= 1")
    return result


def load_ik_fallback_settings(path: str | Path) -> IKFallbackSettings:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        raw = payload["ik"]["fallback"]
        multi = raw["multiseed"]
    except (KeyError, TypeError) as exc:
        raise ValueError("ik.fallback and ik.fallback.multiseed config are required") from exc
    if not isinstance(raw, dict) or not isinstance(multi, dict):
        raise ValueError("ik.fallback and multiseed must be objects")

    enabled = raw.get("enabled")
    allow_contact = raw.get("allow_during_inspection_contact")
    multi_enabled = multi.get("enabled")
    ready_seed_enabled = multi.get("ready_seed_enabled")
    for value, name in (
        (enabled, "ik.fallback.enabled"),
        (allow_contact, "ik.fallback.allow_during_inspection_contact"),
        (multi_enabled, "ik.fallback.multiseed.enabled"),
        (ready_seed_enabled, "ik.fallback.multiseed.ready_seed_enabled"),
    ):
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be a boolean")

    enter_pos = _positive_number(raw.get("position_error_enter_m"), "ik.fallback.position_error_enter_m")
    exit_pos = _positive_number(raw.get("position_error_exit_m"), "ik.fallback.position_error_exit_m")
    enter_rot_deg = _positive_number(raw.get("rotation_error_enter_deg"), "ik.fallback.rotation_error_enter_deg")
    exit_rot_deg = _positive_number(raw.get("rotation_error_exit_deg"), "ik.fallback.rotation_error_exit_deg")
    if exit_pos >= enter_pos:
        raise ValueError("ik.fallback.position_error_exit_m must be lower than enter threshold")
    if exit_rot_deg >= enter_rot_deg:
        raise ValueError("ik.fallback.rotation_error_exit_deg must be lower than enter threshold")

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
        min_improvement_ratio=_ratio(raw.get("min_improvement_ratio"), "ik.fallback.min_improvement_ratio"),
        allow_during_inspection_contact=allow_contact,
        multiseed=MultiSeedSettings(
            enabled=multi_enabled,
            iterations_per_seed=_positive_int(multi.get("iterations_per_seed"), "ik.fallback.multiseed.iterations_per_seed"),
            shoulder_yaw_offset_rad=math.radians(_positive_number(multi.get("shoulder_yaw_offset_deg"), "ik.fallback.multiseed.shoulder_yaw_offset_deg")),
            elbow_offset_rad=math.radians(_positive_number(multi.get("elbow_offset_deg"), "ik.fallback.multiseed.elbow_offset_deg")),
            ready_seed_enabled=ready_seed_enabled,
            joint_motion_weight=_nonnegative_number(multi.get("joint_motion_weight"), "ik.fallback.multiseed.joint_motion_weight"),
            joint_margin_weight=_nonnegative_number(multi.get("joint_margin_weight"), "ik.fallback.multiseed.joint_margin_weight"),
            min_improvement_ratio=_ratio(multi.get("min_improvement_ratio"), "ik.fallback.multiseed.min_improvement_ratio"),
        ),
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

        bad = position_error_m >= self.settings.position_error_enter_m or rotation_error_rad >= self.settings.rotation_error_enter_rad
        good = position_error_m <= self.settings.position_error_exit_m and rotation_error_rad <= self.settings.rotation_error_exit_rad

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

        return IKFallbackTransition(self.active, previous != self.active, reason, self.bad_frames, self.good_frames)


def _pose_errors(base: ModuleType, data: Any, context: dict[str, Any], target_position: np.ndarray, target_rotation: np.ndarray) -> tuple[float, float]:
    position_error = float(np.linalg.norm(np.asarray(target_position) - data.xpos[context["position_body"]]))
    current_rotation = data.xmat[context["orientation_body"]].reshape(3, 3)
    rotation_error = float(np.linalg.norm(base.calculate_rotation_error(target_rotation, current_rotation)))
    return position_error, rotation_error


def _normalized_score(settings: IKFallbackSettings, position_error_m: float, rotation_error_rad: float) -> float:
    return position_error_m / settings.position_error_exit_m + rotation_error_rad / settings.rotation_error_exit_rad


def _inspection_contact_state(base: ModuleType, context: dict[str, Any]) -> bool:
    state = str(getattr(base, "RUNTIME_INSPECTION_STATE", "free_space"))
    return bool(context.get("task_contact_active", False) or state in {"contact_acquire", "inspection_contact", "surface_follow"})


def _dls_step(base: ModuleType, model: Any, data: Any, context: dict[str, Any], target_position: np.ndarray, target_rotation: np.ndarray, settings: IKFallbackSettings) -> np.ndarray | None:
    import mujoco

    dof_ids = np.asarray(context["right_dof_ids"], dtype=int)
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
        return jacobian.T @ np.linalg.solve(jacobian @ jacobian.T + damping_matrix, error)
    except np.linalg.LinAlgError:
        return None


def _apply_operational_clamp(base: ModuleType, model: Any, data: Any) -> None:
    base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)


def _single_coupled_candidate(base: ModuleType, model: Any, data: Any, context: dict[str, Any], start_q: np.ndarray, target_position: np.ndarray, target_rotation: np.ndarray, settings: IKFallbackSettings) -> tuple[np.ndarray | None, float, float]:
    import mujoco

    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    data.qpos[qpos_ids] = start_q
    mujoco.mj_forward(model, data)
    step = _dls_step(base, model, data, context, target_position, target_rotation, settings)
    if step is None:
        return None, math.inf, math.inf
    step *= float(getattr(base, "IK_STEP_GAIN", 1.0))
    max_step = float(getattr(base, "IK_MAX_STEP_RADIANS", math.radians(1.5)))
    step = np.clip(step, -max_step, max_step)
    data.qpos[qpos_ids] = start_q + step
    _apply_operational_clamp(base, model, data)
    mujoco.mj_forward(model, data)
    if base.has_right_arm_core_contact(model, data, context):
        data.qpos[qpos_ids] = start_q
        mujoco.mj_forward(model, data)
        return None, math.inf, math.inf
    candidate_q = data.qpos[qpos_ids].copy()
    position_error_m, rotation_error_rad = _pose_errors(base, data, context, target_position, target_rotation)
    return candidate_q, position_error_m, rotation_error_rad


def _seed_candidates(base: ModuleType, start_q: np.ndarray, settings: IKFallbackSettings) -> list[tuple[str, np.ndarray]]:
    seeds: list[tuple[str, np.ndarray]] = [("current", start_q.copy())]
    multi = settings.multiseed
    yaw_index = 2
    elbow_index = 3

    for label, index, offset in (
        ("shoulder_yaw_plus", yaw_index, multi.shoulder_yaw_offset_rad),
        ("shoulder_yaw_minus", yaw_index, -multi.shoulder_yaw_offset_rad),
        ("elbow_plus", elbow_index, multi.elbow_offset_rad),
        ("elbow_minus", elbow_index, -multi.elbow_offset_rad),
    ):
        seed = start_q.copy()
        seed[index] += offset
        seeds.append((label, seed))

    if multi.ready_seed_enabled and hasattr(base, "RIGHT_ARM_READY_DEGREES"):
        ready = np.radians(np.asarray(base.RIGHT_ARM_READY_DEGREES, dtype=float))
        if ready.shape == start_q.shape:
            seeds.append(("ready", ready.copy()))
    return seeds


def _joint_limit_margin(model: Any, base: ModuleType, q: np.ndarray) -> float:
    margins: list[float] = []
    for index, joint_name in enumerate(base.RIGHT_ARM_JOINTS):
        joint_id = base.mujoco.mj_name2id(model, base.mujoco.mjtObj.mjOBJ_JOINT, joint_name) if hasattr(base, "mujoco") else -1
        if joint_id < 0 or not model.jnt_limited[joint_id]:
            continue
        low, high = model.jnt_range[joint_id]
        width = float(high - low)
        if width <= 1e-9:
            continue
        margins.append(min(float(q[index] - low), float(high - q[index])) / width)
    return min(margins) if margins else 1.0


def _candidate_score(settings: IKFallbackSettings, model: Any, base: ModuleType, start_q: np.ndarray, candidate_q: np.ndarray, position_error_m: float, rotation_error_rad: float) -> float:
    pose = _normalized_score(settings, position_error_m, rotation_error_rad)
    motion = float(np.linalg.norm(candidate_q - start_q))
    margin = _joint_limit_margin(model, base, candidate_q)
    return pose + settings.multiseed.joint_motion_weight * motion + settings.multiseed.joint_margin_weight * (1.0 - margin)


def _multiseed_candidate(base: ModuleType, model: Any, data: Any, context: dict[str, Any], start_q: np.ndarray, target_position: np.ndarray, target_rotation: np.ndarray, settings: IKFallbackSettings) -> tuple[np.ndarray | None, float, float, str | None, list[dict[str, Any]]]:
    import mujoco

    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    max_step = float(getattr(base, "IK_MAX_STEP_RADIANS", math.radians(1.5)))
    diagnostics: list[dict[str, Any]] = []
    best: tuple[float, np.ndarray, float, float, str] | None = None

    for seed_name, seed_q in _seed_candidates(base, start_q, settings):
        data.qpos[qpos_ids] = seed_q
        _apply_operational_clamp(base, model, data)
        mujoco.mj_forward(model, data)
        rejected = None
        for _ in range(settings.multiseed.iterations_per_seed):
            step = _dls_step(base, model, data, context, target_position, target_rotation, settings)
            if step is None:
                rejected = "singular"
                break
            step *= float(getattr(base, "IK_STEP_GAIN", 1.0))
            step = np.clip(step, -max_step, max_step)
            data.qpos[qpos_ids] += step
            _apply_operational_clamp(base, model, data)
            mujoco.mj_forward(model, data)
            if base.has_right_arm_core_contact(model, data, context):
                rejected = "collision"
                break

        if rejected is not None:
            diagnostics.append({"seed": seed_name, "accepted": False, "reason": rejected})
            continue

        solution_q = data.qpos[qpos_ids].copy()
        final_delta = np.clip(solution_q - start_q, -max_step, max_step)
        data.qpos[qpos_ids] = start_q + final_delta
        _apply_operational_clamp(base, model, data)
        mujoco.mj_forward(model, data)
        if base.has_right_arm_core_contact(model, data, context):
            diagnostics.append({"seed": seed_name, "accepted": False, "reason": "collision_after_step_limit"})
            continue

        candidate_q = data.qpos[qpos_ids].copy()
        pos_error, rot_error = _pose_errors(base, data, context, target_position, target_rotation)
        score = _candidate_score(settings, model, base, start_q, candidate_q, pos_error, rot_error)
        diagnostics.append({
            "seed": seed_name,
            "accepted": True,
            "score": float(score),
            "position_error_m": float(pos_error),
            "rotation_error_deg": float(math.degrees(rot_error)),
        })
        if best is None or score < best[0]:
            best = (score, candidate_q, pos_error, rot_error, seed_name)

    data.qpos[qpos_ids] = start_q
    mujoco.mj_forward(model, data)
    if best is None:
        return None, math.inf, math.inf, None, diagnostics
    return best[1], best[2], best[3], best[4], diagnostics


def install_coupled_ik_fallback(base: ModuleType, settings: IKFallbackSettings) -> IKFallbackSupervisor:
    supervisor = IKFallbackSupervisor(settings)
    base.IK_FALLBACK_SUPERVISOR = supervisor
    base.RUNTIME_IK_MODE = "decoupled"
    base.RUNTIME_IK_FALLBACK_ACTIVE = False
    base.RUNTIME_IK_POSITION_ERROR_M = None
    base.RUNTIME_IK_ROTATION_ERROR_RAD = None
    base.RUNTIME_IK_COUPLED_SCORE = None
    base.RUNTIME_IK_DECOUPLED_SCORE = None
    base.RUNTIME_IK_MULTI_SEED_SCORE = None
    base.RUNTIME_IK_SELECTED_SEED = None
    base.RUNTIME_IK_SEED_DIAGNOSTICS = []

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
            if model is None or data is None or target_position is None or target_rotation is None or not isinstance(context, dict):
                return original_solver(*args, **kwargs)

            target_position = np.asarray(target_position, dtype=float)
            target_rotation = np.asarray(target_rotation, dtype=float)
            qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
            start_q = data.qpos[qpos_ids].copy()
            result = original_solver(*args, **kwargs)
            decoupled_q = data.qpos[qpos_ids].copy()
            dec_pos, dec_rot = _pose_errors(base, data, context, target_position, target_rotation)
            inspection_contact = _inspection_contact_state(base, context)
            transition = supervisor.update(dec_pos, dec_rot, inspection_contact=inspection_contact)
            dec_score = _normalized_score(settings, dec_pos, dec_rot)

            base.RUNTIME_IK_FALLBACK_ACTIVE = transition.active
            base.RUNTIME_IK_POSITION_ERROR_M = dec_pos
            base.RUNTIME_IK_ROTATION_ERROR_RAD = dec_rot
            base.RUNTIME_IK_DECOUPLED_SCORE = dec_score
            base.RUNTIME_IK_COUPLED_SCORE = None
            base.RUNTIME_IK_MULTI_SEED_SCORE = None
            base.RUNTIME_IK_SELECTED_SEED = None
            base.RUNTIME_IK_SEED_DIAGNOSTICS = []
            base.RUNTIME_IK_MODE = "decoupled"
            context["ik_mode"] = "decoupled"

            collision_status = getattr(base, "RUNTIME_COLLISION_NEAREST_STATUS", None)
            # Near-contact margins around the robot are early-warning signals, not
            # a reason to disable IK recovery entirely. Environment obstacle
            # avoidance keeps priority because its tangential target projection
            # must not be overwritten by a fallback solving the original target.
            collision_busy = collision_status == "environment_obstacle"
            contact_blocked = inspection_contact and not settings.allow_during_inspection_contact
            if not transition.active or collision_busy or contact_blocked:
                return result

            coupled_q, coupled_pos, coupled_rot = _single_coupled_candidate(base, model, data, context, start_q, target_position, target_rotation, settings)
            coupled_score = _normalized_score(settings, coupled_pos, coupled_rot)
            base.RUNTIME_IK_COUPLED_SCORE = coupled_score if math.isfinite(coupled_score) else None

            best_q = None
            best_pos = math.inf
            best_rot = math.inf
            best_score = math.inf
            best_mode = None
            best_seed = None

            if coupled_q is not None and coupled_score <= dec_score * settings.min_improvement_ratio:
                best_q, best_pos, best_rot, best_score = coupled_q, coupled_pos, coupled_rot, coupled_score
                best_mode = "coupled_fallback"

            if settings.multiseed.enabled:
                multi_q, multi_pos, multi_rot, seed_name, diagnostics = _multiseed_candidate(
                    base, model, data, context, start_q, target_position, target_rotation, settings
                )
                base.RUNTIME_IK_SEED_DIAGNOSTICS = diagnostics
                if multi_q is not None:
                    multi_score = _candidate_score(settings, model, base, start_q, multi_q, multi_pos, multi_rot)
                    base.RUNTIME_IK_MULTI_SEED_SCORE = multi_score
                    reference_score = best_score if math.isfinite(best_score) else dec_score
                    if multi_score <= reference_score * settings.multiseed.min_improvement_ratio:
                        best_q, best_pos, best_rot, best_score = multi_q, multi_pos, multi_rot, multi_score
                        best_mode = "multiseed_fallback"
                        best_seed = seed_name

            if best_q is not None:
                data.qpos[qpos_ids] = best_q
                import mujoco
                mujoco.mj_forward(model, data)
                base.RUNTIME_IK_MODE = best_mode
                base.RUNTIME_IK_POSITION_ERROR_M = best_pos
                base.RUNTIME_IK_ROTATION_ERROR_RAD = best_rot
                base.RUNTIME_IK_SELECTED_SEED = best_seed
                context["ik_mode"] = best_mode
                context["ik_selected_seed"] = best_seed
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
            enriched["ik_rotation_error_deg"] = math.degrees(rotation_error) if rotation_error is not None else None
            enriched["ik_decoupled_score"] = base.RUNTIME_IK_DECOUPLED_SCORE
            enriched["ik_coupled_score"] = base.RUNTIME_IK_COUPLED_SCORE
            enriched["ik_multiseed_score"] = base.RUNTIME_IK_MULTI_SEED_SCORE
            enriched["ik_selected_seed"] = base.RUNTIME_IK_SELECTED_SEED
            enriched["ik_seed_diagnostics"] = base.RUNTIME_IK_SEED_DIAGNOSTICS
            enriched["ik_fallback_bad_frames"] = supervisor.bad_frames
            enriched["ik_fallback_good_frames"] = supervisor.good_frames
            original_status_writer(enriched)

        base.write_runtime_status = ik_status_writer
        base._IK_FALLBACK_STATUS_INSTALLED = True

    return supervisor
