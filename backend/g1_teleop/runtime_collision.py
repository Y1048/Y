"""Install shared right-arm collision policy and distance-aware avoidance."""

from __future__ import annotations

import math
from types import ModuleType
from typing import Any

from .collision_policy import RightArmCollisionPolicy
from .config import TeleopConfig


_POLICY_CACHE_KEY = "_right_arm_collision_policy"
_POLICY_MODEL_KEY = "_right_arm_collision_policy_model_id"
_DANGEROUS_STATUSES = {"right_arm_self_collision", "right_arm_robot_collision"}


def get_runtime_collision_policy(
    model: Any,
    context: dict[str, Any],
    *,
    structural_neighbor_distance: int,
) -> RightArmCollisionPolicy:
    """Return a context-local policy matching the offline workspace analyzer."""
    model_identity = id(model)
    cached = context.get(_POLICY_CACHE_KEY)
    cached_model_identity = context.get(_POLICY_MODEL_KEY)
    if (
        isinstance(cached, RightArmCollisionPolicy)
        and cached_model_identity == model_identity
        and cached.structural_neighbor_distance == structural_neighbor_distance
    ):
        return cached

    policy = RightArmCollisionPolicy.from_model(
        model,
        context["right_arm_body_ids"],
        structural_neighbor_distance=structural_neighbor_distance,
    )
    context[_POLICY_CACHE_KEY] = policy
    context[_POLICY_MODEL_KEY] = model_identity
    return policy


def has_runtime_right_arm_collision(
    model: Any,
    data: Any,
    context: dict[str, Any],
    *,
    structural_neighbor_distance: int,
) -> bool:
    """Return whether any dangerous right-arm pair is present in contact data."""
    policy = get_runtime_collision_policy(
        model,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    return policy.has_collision(model, data)


def dangerous_contact_clearance_m(
    model: Any,
    data: Any,
    context: dict[str, Any],
    *,
    structural_neighbor_distance: int,
) -> float | None:
    """Return the smallest MuJoCo contact distance for a dangerous body pair.

    MuJoCo emits positive-distance contacts inside a geom margin. Those positive
    distances are used as an early-warning clearance signal; zero or negative
    distance means physical contact/penetration and is treated as a hard stop.
    """
    policy = get_runtime_collision_policy(
        model,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    nearest: float | None = None
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        first_body = int(model.geom_bodyid[contact.geom1])
        second_body = int(model.geom_bodyid[contact.geom2])
        if policy.classify_body_pair(first_body, second_body) not in _DANGEROUS_STATUSES:
            continue
        distance = float(getattr(contact, "dist", 0.0))
        if not math.isfinite(distance):
            continue
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def collision_step_scale(clearance_m: float | None, slowdown_distance_m: float) -> float:
    """Map clearance to a smooth IK step scale in [0, 1].

    No dangerous near-contact means full speed. At physical contact (<=0 m),
    motion stops. Between 0 and slowdown_distance_m, a smoothstep profile avoids
    abrupt gain changes while preserving the user's intentional follow lag.
    """
    if slowdown_distance_m <= 0.0:
        raise ValueError("slowdown_distance_m must be positive")
    if clearance_m is None or clearance_m >= slowdown_distance_m:
        return 1.0
    if clearance_m <= 0.0:
        return 0.0
    alpha = max(0.0, min(1.0, clearance_m / slowdown_distance_m))
    return alpha * alpha * (3.0 - 2.0 * alpha)


def install_runtime_collision_policy(base: ModuleType, config: TeleopConfig) -> None:
    """Install shared collision classification plus distance-aware step scaling.

    ``collision.margin_m`` is both the MuJoCo near-contact generation margin and
    the slowdown distance, so no second hidden safety distance is introduced.
    The existing contact line search remains the final hard-stop safety net.
    """
    structural_neighbor_distance = config.collision.structural_neighbor_distance
    slowdown_distance_m = config.collision.margin_m

    def clearance(model: Any, data: Any, context: dict[str, Any]) -> float | None:
        return dangerous_contact_clearance_m(
            model,
            data,
            context,
            structural_neighbor_distance=structural_neighbor_distance,
        )

    def shared_collision_guard(model: Any, data: Any, context: dict[str, Any]) -> bool:
        nearest = clearance(model, data, context)
        return nearest is not None and nearest <= 0.0

    base.has_right_arm_core_contact = shared_collision_guard
    base.RUNTIME_COLLISION_POLICY = "RightArmCollisionPolicy"
    base.RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE = structural_neighbor_distance
    base.RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M = slowdown_distance_m
    base.RUNTIME_COLLISION_CLEARANCE_M = None
    base.RUNTIME_COLLISION_STEP_SCALE = 1.0

    original_solver = getattr(base, "solve_right_arm_target", None)
    if callable(original_solver) and not getattr(base, "_DISTANCE_AWARE_SOLVER_INSTALLED", False):
        def distance_aware_solver(*args: Any, **kwargs: Any):
            model = args[0] if len(args) > 0 else kwargs.get("model")
            data = args[1] if len(args) > 1 else kwargs.get("data")
            context = kwargs.get("context")
            if context is None and len(args) > 7:
                context = args[7]

            nearest = None
            scale = 1.0
            if model is not None and data is not None and isinstance(context, dict):
                nearest = clearance(model, data, context)
                scale = collision_step_scale(nearest, slowdown_distance_m)
                context["collision_clearance_m"] = nearest
                context["collision_step_scale"] = scale

            base.RUNTIME_COLLISION_CLEARANCE_M = nearest
            base.RUNTIME_COLLISION_STEP_SCALE = scale

            if scale <= 0.0 and isinstance(context, dict):
                context["collision_limited"] = True
                position_body = context.get("position_body")
                if position_body is not None:
                    return data.xpos[position_body].copy()

            nominal_gain = float(getattr(base, "IK_STEP_GAIN", 1.0))
            try:
                base.IK_STEP_GAIN = nominal_gain * scale
                result = original_solver(*args, **kwargs)
            finally:
                base.IK_STEP_GAIN = nominal_gain

            if model is not None and data is not None and isinstance(context, dict):
                post_clearance = clearance(model, data, context)
                post_scale = collision_step_scale(post_clearance, slowdown_distance_m)
                context["collision_clearance_m"] = post_clearance
                context["collision_step_scale"] = post_scale
                base.RUNTIME_COLLISION_CLEARANCE_M = post_clearance
                base.RUNTIME_COLLISION_STEP_SCALE = post_scale
            return result

        base.solve_right_arm_target = distance_aware_solver
        base._DISTANCE_AWARE_SOLVER_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_COLLISION_STATUS_WRITER_INSTALLED", False):
        def collision_status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["collision_clearance_m"] = base.RUNTIME_COLLISION_CLEARANCE_M
            enriched["collision_step_scale"] = float(base.RUNTIME_COLLISION_STEP_SCALE)
            enriched["collision_slowdown_distance_m"] = float(
                base.RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M
            )
            original_status_writer(enriched)

        base.write_runtime_status = collision_status_writer
        base._COLLISION_STATUS_WRITER_INSTALLED = True
