"""Configuration-aware workspace override for the torso-front elbow pre-pose."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np

from .workspace_map import WorkspaceProjection, WorkspaceTargetProjector


def install_torso_front_workspace_override(base: ModuleType) -> None:
    """Bypass the wrist-only voxel map only in the explicit torso-front zone.

    The offline voxel map classifies wrist positions without preserving the arm
    configuration that made each sample safe. In the narrow front-center region,
    pass operator intent through unchanged and keep live joint-level collision
    checks authoritative. The projector's internal last-safe voxel anchor is left
    untouched so normal voxel projection resumes from a map-valid point on exit.
    """
    projector_type = WorkspaceTargetProjector
    if getattr(projector_type, "_TORSO_FRONT_OVERRIDE_INSTALLED", False):
        return

    original_update = projector_type.update
    base.RUNTIME_TORSO_WORKSPACE_BYPASS = False

    def update_with_torso_override(self: Any, operator_target_m: np.ndarray):
        target = np.asarray(operator_target_m, dtype=float)
        predicate = getattr(base, "is_torso_front_target", None)
        bypass = bool(callable(predicate) and predicate(target))
        base.RUNTIME_TORSO_WORKSPACE_BYPASS = bypass
        if not bypass:
            return original_update(self, target)
        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=target.copy(),
            projected=False,
            distance_m=0.0,
        )

    projector_type.update = update_with_torso_override
    projector_type._TORSO_FRONT_OVERRIDE_INSTALLED = True

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(
        base, "_TORSO_WORKSPACE_OVERRIDE_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            enriched["torso_workspace_bypass"] = bool(
                base.RUNTIME_TORSO_WORKSPACE_BYPASS
            )
            original_status_writer(enriched)

        base.write_runtime_status = status_writer
        base._TORSO_WORKSPACE_OVERRIDE_STATUS_INSTALLED = True
