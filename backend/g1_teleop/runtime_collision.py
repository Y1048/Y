"""Install the shared right-arm collision policy into the live IK runtime."""

from __future__ import annotations

from types import ModuleType
from typing import Any

from .collision_policy import RightArmCollisionPolicy
from .config import TeleopConfig


_POLICY_CACHE_KEY = "_right_arm_collision_policy"
_POLICY_MODEL_KEY = "_right_arm_collision_policy_model_id"


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
    """Use the same dangerous-contact definition as offline workspace sampling."""
    policy = get_runtime_collision_policy(
        model,
        context,
        structural_neighbor_distance=structural_neighbor_distance,
    )
    return policy.has_collision(model, data)


def install_runtime_collision_policy(base: ModuleType, config: TeleopConfig) -> None:
    """Replace the legacy core-only IK contact guard with the shared policy.

    The existing solver already calls ``base.has_right_arm_core_contact`` for
    every line-search candidate. Replacing that hook keeps the solver flow and
    performance characteristics intact while making its collision acceptance
    rule identical to the offline workspace analyzer.
    """
    structural_neighbor_distance = config.collision.structural_neighbor_distance

    def shared_collision_guard(model: Any, data: Any, context: dict[str, Any]) -> bool:
        return has_runtime_right_arm_collision(
            model,
            data,
            context,
            structural_neighbor_distance=structural_neighbor_distance,
        )

    base.has_right_arm_core_contact = shared_collision_guard
    base.RUNTIME_COLLISION_POLICY = "RightArmCollisionPolicy"
    base.RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE = structural_neighbor_distance
