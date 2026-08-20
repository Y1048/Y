"""Task-aware right-arm collision policy and distance-aware avoidance."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import numpy as np

from .collision_policy import RightArmCollisionPolicy
from .config import TeleopConfig


_POLICY_CACHE_KEY = "_right_arm_collision_policy"
_POLICY_MODEL_KEY = "_right_arm_collision_policy_model_id"
_ROBOT_DANGEROUS_STATUSES = {"right_arm_self_collision", "right_arm_robot_collision"}
_RUNTIME_DANGEROUS_STATUSES = _ROBOT_DANGEROUS_STATUSES | {"environment_obstacle"}


@dataclass(frozen=True)
class RuntimeContactInfo:
    status: str
    clearance_m: float
    first_body: int
    second_body: int
    geom1: int
    geom2: int
    arm_normal_toward_other: np.ndarray | None


def get_runtime_collision_policy(model: Any, context: dict[str, Any], *, structural_neighbor_distance: int) -> RightArmCollisionPolicy:
    model_identity = id(model)
    cached = context.get(_POLICY_CACHE_KEY)
    cached_model_identity = context.get(_POLICY_MODEL_KEY)
    if isinstance(cached, RightArmCollisionPolicy) and cached_model_identity == model_identity and cached.structural_neighbor_distance == structural_neighbor_distance:
        return cached
    policy = RightArmCollisionPolicy.from_model(model, context["right_arm_body_ids"], structural_neighbor_distance=structural_neighbor_distance)
    context[_POLICY_CACHE_KEY] = policy
    context[_POLICY_MODEL_KEY] = model_identity
    return policy


def _object_name(model: Any, kind: str, object_id: int) -> str | None:
    fallback = getattr(model, f"{kind}_names", None)
    if fallback is not None and 0 <= int(object_id) < len(fallback):
        value = fallback[int(object_id)]
        return str(value) if value is not None else None
    try:
        import mujoco
        object_type = mujoco.mjtObj.mjOBJ_BODY if kind == "body" else mujoco.mjtObj.mjOBJ_GEOM
        return mujoco.mj_id2name(model, object_type, int(object_id))
    except (ImportError, TypeError, ValueError):
        return None


def _task_contact(model: Any, policy: RightArmCollisionPolicy, contact: Any, config: TeleopConfig) -> bool:
    collision = config.collision
    if not collision.task_contact_enabled:
        return False
    geom1 = int(contact.geom1)
    geom2 = int(contact.geom2)
    body1 = int(model.geom_bodyid[geom1])
    body2 = int(model.geom_bodyid[geom2])
    body1_name = _object_name(model, "body", body1)
    body2_name = _object_name(model, "body", body2)
    geom1_name = _object_name(model, "geom", geom1)
    geom2_name = _object_name(model, "geom", geom2)
    tools = set(collision.task_contact_tool_body_names)
    targets = set(collision.task_contact_target_geom_names)
    first_is_tool = body1 in policy.right_arm_body_ids and body1_name in tools
    second_is_tool = body2 in policy.right_arm_body_ids and body2_name in tools
    return bool((first_is_tool and geom2_name in targets) or (second_is_tool and geom1_name in targets))


def classify_runtime_contact(model: Any, contact: Any, policy: RightArmCollisionPolicy, config: TeleopConfig) -> str:
    geom1 = int(contact.geom1)
    geom2 = int(contact.geom2)
    body1 = int(model.geom_bodyid[geom1])
    body2 = int(model.geom_bodyid[geom2])
    base_status = policy.classify_body_pair(body1, body2)
    if base_status != "environment":
        return base_status
    if _task_contact(model, policy, contact, config):
        return "task_contact"
    if config.collision.environment_obstacles_enabled:
        return "environment_obstacle"
    return "environment"


def _contact_arm_normal(model: Any, contact: Any, policy: RightArmCollisionPolicy, status: str) -> np.ndarray | None:
    if status == "right_arm_self_collision":
        return None
    frame = np.asarray(getattr(contact, "frame", []), dtype=float).reshape(-1)
    if len(frame) < 3 or not np.all(np.isfinite(frame[:3])):
        return None
    normal = frame[:3].copy()
    norm = float(np.linalg.norm(normal))
    if norm < 1e-9:
        return None
    normal /= norm
    geom1 = int(contact.geom1)
    geom2 = int(contact.geom2)
    body1 = int(model.geom_bodyid[geom1])
    body2 = int(model.geom_bodyid[geom2])
    first_is_arm = body1 in policy.right_arm_body_ids
    second_is_arm = body2 in policy.right_arm_body_ids
    if first_is_arm and not second_is_arm:
        return normal
    if second_is_arm and not first_is_arm:
        return -normal
    return None


def scan_runtime_contacts(model: Any, data: Any, context: dict[str, Any], config: TeleopConfig) -> tuple[RuntimeContactInfo | None, bool]:
    policy = get_runtime_collision_policy(model, context, structural_neighbor_distance=config.collision.structural_neighbor_distance)
    nearest: RuntimeContactInfo | None = None
    task_contact_active = False
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        status = classify_runtime_contact(model, contact, policy, config)
        if status == "task_contact":
            task_contact_active = True
            continue
        if status not in _RUNTIME_DANGEROUS_STATUSES:
            continue
        distance = float(getattr(contact, "dist", 0.0))
        if not math.isfinite(distance):
            continue
        info = RuntimeContactInfo(status=status, clearance_m=distance, first_body=int(model.geom_bodyid[int(contact.geom1)]), second_body=int(model.geom_bodyid[int(contact.geom2)]), geom1=int(contact.geom1), geom2=int(contact.geom2), arm_normal_toward_other=_contact_arm_normal(model, contact, policy, status))
        if nearest is None or info.clearance_m < nearest.clearance_m:
            nearest = info
    return nearest, task_contact_active


def has_runtime_right_arm_collision(model: Any, data: Any, context: dict[str, Any], *, structural_neighbor_distance: int) -> bool:
    policy = get_runtime_collision_policy(model, context, structural_neighbor_distance=structural_neighbor_distance)
    return policy.has_collision(model, data)


def dangerous_contact_clearance_m(model: Any, data: Any, context: dict[str, Any], *, structural_neighbor_distance: int) -> float | None:
    policy = get_runtime_collision_policy(model, context, structural_neighbor_distance=structural_neighbor_distance)
    nearest: float | None = None
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        first_body = int(model.geom_bodyid[contact.geom1])
        second_body = int(model.geom_bodyid[contact.geom2])
        if policy.classify_body_pair(first_body, second_body) not in _ROBOT_DANGEROUS_STATUSES:
            continue
        distance = float(getattr(contact, "dist", 0.0))
        if not math.isfinite(distance):
            continue
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def collision_step_scale(clearance_m: float | None, slowdown_distance_m: float) -> float:
    if slowdown_distance_m <= 0.0:
        raise ValueError("slowdown_distance_m must be positive")
    if clearance_m is None or clearance_m >= slowdown_distance_m:
        return 1.0
    if clearance_m <= 0.0:
        return 0.0
    alpha = max(0.0, min(1.0, clearance_m / slowdown_distance_m))
    return alpha * alpha * (3.0 - 2.0 * alpha)


def slide_target_along_contact(current_position: np.ndarray, target_position: np.ndarray, contact: RuntimeContactInfo | None, inward_scale: float) -> np.ndarray:
    current = np.asarray(current_position, dtype=float)
    target = np.asarray(target_position, dtype=float)
    if contact is None or contact.arm_normal_toward_other is None:
        return target.copy()
    normal = np.asarray(contact.arm_normal_toward_other, dtype=float)
    delta = target - current
    inward_distance = float(np.dot(delta, normal))
    if inward_distance <= 0.0:
        return target.copy()
    tangent = delta - inward_distance * normal
    return current + tangent + inward_distance * float(inward_scale) * normal


def install_runtime_collision_policy(base: ModuleType, config: TeleopConfig) -> None:
    slowdown_distance_m = config.collision.margin_m

    def scan(model: Any, data: Any, context: dict[str, Any]):
        return scan_runtime_contacts(model, data, context, config)

    def shared_collision_guard(model: Any, data: Any, context: dict[str, Any]) -> bool:
        nearest, task_contact_active = scan(model, data, context)
        context["task_contact_active"] = task_contact_active
        return nearest is not None and nearest.clearance_m <= 0.0

    base.has_right_arm_core_contact = shared_collision_guard
    base.RUNTIME_COLLISION_POLICY = "TaskAwareRightArmCollisionPolicy"
    base.RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE = config.collision.structural_neighbor_distance
    base.RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M = slowdown_distance_m
    base.RUNTIME_COLLISION_CLEARANCE_M = None
    base.RUNTIME_COLLISION_STEP_SCALE = 1.0
    base.RUNTIME_COLLISION_NEAREST_STATUS = None
    base.RUNTIME_TASK_CONTACT_ACTIVE = False

    original_solver = getattr(base, "solve_right_arm_target", None)
    if callable(original_solver) and not getattr(base, "_DISTANCE_AWARE_SOLVER_INSTALLED", False):
        def distance_aware_solver(*args: Any, **kwargs: Any):
            model = args[0] if len(args) > 0 else kwargs.get("model")
            data = args[1] if len(args) > 1 else kwargs.get("data")
            context = kwargs.get("context")
            if context is None and len(args) > 7:
                context = args[7]
            nearest = None
            task_contact_active = False
            scale = 1.0
            adjusted_args = list(args)
            adjusted_kwargs = dict(kwargs)
            if model is not None and data is not None and isinstance(context, dict):
                nearest, task_contact_active = scan(model, data, context)
                clearance = nearest.clearance_m if nearest is not None else None
                scale = collision_step_scale(clearance, slowdown_distance_m)
                context["collision_clearance_m"] = clearance
                context["collision_step_scale"] = scale
                context["collision_nearest_status"] = nearest.status if nearest is not None else None
                context["task_contact_active"] = task_contact_active
                if config.collision.tangential_slide_enabled and nearest is not None and nearest.status != "right_arm_self_collision" and context.get("position_body") is not None:
                    current_position = np.asarray(data.xpos[context["position_body"]], dtype=float)
                    if len(adjusted_args) > 4:
                        adjusted_args[4] = slide_target_along_contact(current_position, np.asarray(adjusted_args[4], dtype=float), nearest, scale)
                    elif "target" in adjusted_kwargs:
                        adjusted_kwargs["target"] = slide_target_along_contact(current_position, np.asarray(adjusted_kwargs["target"], dtype=float), nearest, scale)
            base.RUNTIME_COLLISION_CLEARANCE_M = nearest.clearance_m if nearest is not None else None
            base.RUNTIME_COLLISION_STEP_SCALE = scale
            base.RUNTIME_COLLISION_NEAREST_STATUS = nearest.status if nearest is not None else None
            base.RUNTIME_TASK_CONTACT_ACTIVE = task_contact_active
            nominal_gain = float(getattr(base, "IK_STEP_GAIN", 1.0))
            gain_scale = scale if nearest is not None and (nearest.status == "right_arm_self_collision" or nearest.arm_normal_toward_other is None or not config.collision.tangential_slide_enabled) else 1.0
            try:
                base.IK_STEP_GAIN = nominal_gain * gain_scale
                result = original_solver(*adjusted_args, **adjusted_kwargs)
            finally:
                base.IK_STEP_GAIN = nominal_gain
            if model is not None and data is not None and isinstance(context, dict):
                post_nearest, post_task_contact = scan(model, data, context)
                post_clearance = post_nearest.clearance_m if post_nearest is not None else None
                post_scale = collision_step_scale(post_clearance, slowdown_distance_m)
                context["collision_clearance_m"] = post_clearance
                context["collision_step_scale"] = post_scale
                context["collision_nearest_status"] = post_nearest.status if post_nearest is not None else None
                context["task_contact_active"] = post_task_contact
                base.RUNTIME_COLLISION_CLEARANCE_M = post_clearance
                base.RUNTIME_COLLISION_STEP_SCALE = post_scale
                base.RUNTIME_COLLISION_NEAREST_STATUS = post_nearest.status if post_nearest is not None else None
                base.RUNTIME_TASK_CONTACT_ACTIVE = post_task_contact
            return result
        base.solve_right_arm_target = distance_aware_solver
        base._DISTANCE_AWARE_SOLVER_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_COLLISION_STATUS_WRITER_INSTALLED", False):
        def collision_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["collision_clearance_m"] = base.RUNTIME_COLLISION_CLEARANCE_M
            enriched["collision_step_scale"] = float(base.RUNTIME_COLLISION_STEP_SCALE)
            enriched["collision_slowdown_distance_m"] = float(base.RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M)
            enriched["collision_nearest_status"] = base.RUNTIME_COLLISION_NEAREST_STATUS
            enriched["task_contact_active"] = bool(base.RUNTIME_TASK_CONTACT_ACTIVE)
            enriched["environment_obstacles_enabled"] = bool(config.collision.environment_obstacles_enabled)
            enriched["tangential_slide_enabled"] = bool(config.collision.tangential_slide_enabled)
            original_status_writer(enriched)
        base.write_runtime_status = collision_status_writer
        base._COLLISION_STATUS_WRITER_INSTALLED = True
