"""Configuration-aware workspace override for the torso-front elbow pre-pose."""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np


def install_torso_front_workspace_override(runtime_module: ModuleType, base: ModuleType) -> None:
    """Bypass the wrist-only voxel map only in the explicit torso-front zone.

    The offline voxel map classifies Cartesian wrist positions without preserving
    which elbow/shoulder configuration made a sample safe. A torso-center wrist
    point can therefore be rejected because a straight-arm branch collides even
    though the two-stage elbow-up pre-pose can reach the same point safely.

    In that narrow front-center region, pass operator intent through unchanged and
    let the live joint-level collision policy remain authoritative. The projector's
    internal last-safe voxel anchor is intentionally left untouched, so leaving the
    override region resumes normal voxel projection from the last map-valid point.
    """
    projector_type = getattr(runtime_module, "WorkspaceTargetProjector", None)
    projection_type = getattr(runtime_module, "WorkspaceProjection", None)
    if projector_type is None:
        raise RuntimeError("runtime WorkspaceTargetProjector is unavailable")
    if projection_type is None:
        # Runtime imports WorkspaceTargetProjector directly but may not expose the
        # dataclass; import it from the backend package in that case.
        from g1_teleop import WorkspaceProjection as projection_type

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

        return projection_type(
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
