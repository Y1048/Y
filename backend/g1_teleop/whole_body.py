"""Joint-group ownership and whole-body target composition for Unitree G1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


G1_DOF_COUNT = 29
JOINT_GROUP_SLICES = {
    "left_leg": slice(0, 6),
    "right_leg": slice(6, 12),
    "torso": slice(12, 15),
    "left_arm": slice(15, 22),
    "right_arm": slice(22, 29),
}


@dataclass(frozen=True)
class JointOwnership:
    left_leg: str = "lower_body_policy"
    right_leg: str = "lower_body_policy"
    torso: str = "lower_body_policy"
    left_arm: str = "lower_body_policy"
    right_arm: str = "arm_teleop"

    def owner_for(self, group: str) -> str:
        if group not in JOINT_GROUP_SLICES:
            raise KeyError(f"unknown joint group: {group}")
        return getattr(self, group)


def _target29(value: object, field_name: str = "target") -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (G1_DOF_COUNT,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{field_name} must contain {G1_DOF_COUNT} finite values")
    return result.copy()


def compose_whole_body_target(
    base_target: object,
    group_overrides: Mapping[str, object],
) -> np.ndarray:
    """Overlay controller-owned joint groups onto one canonical 29-DoF target."""
    result = _target29(base_target, "base_target")
    for group, values in group_overrides.items():
        joint_slice = JOINT_GROUP_SLICES.get(group)
        if joint_slice is None:
            raise KeyError(f"unknown joint group: {group}")
        expected = joint_slice.stop - joint_slice.start
        override = np.asarray(values, dtype=float)
        if override.shape != (expected,) or not np.all(np.isfinite(override)):
            raise ValueError(f"{group} override must contain {expected} finite values")
        result[joint_slice] = override
    return result
