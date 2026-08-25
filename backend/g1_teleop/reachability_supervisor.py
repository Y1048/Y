"""Gross reachability pre-gate for configuration-aware G1 teleoperation.

The voxel workspace remains diagnostic during normal motion. It only becomes a
coarse pre-gate when the requested Cartesian target is far outside the sampled
reachable set. This prevents an obviously unreachable target from continuously
driving IK/redundancy while preserving runtime geometry as the normal authority.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np

from .workspace_map import WorkspaceProjection, WorkspaceTargetProjector


REACHABILITY_ENTER_DISTANCE_M = 0.050
REACHABILITY_RELEASE_DISTANCE_M = 0.025


def install_reachability_supervisor(base: ModuleType) -> None:
    """Install a hysteretic gross-reachability gate ahead of the IK solver."""
    projector_type = WorkspaceTargetProjector
    if getattr(projector_type, "_REACHABILITY_SUPERVISOR_INSTALLED", False):
        return

    original_update = projector_type.update

    base.RUNTIME_REACHABILITY_GATE_ACTIVE = False
    base.RUNTIME_REACHABILITY_HINT_PROJECTED = False
    base.RUNTIME_REACHABILITY_PROJECTION_DISTANCE_M = 0.0
    base.RUNTIME_REACHABILITY_HINT_REPORTED_DISTANCE_M = 0.0
    base.RUNTIME_REACHABILITY_FEASIBLE_TARGET = None
    base.RUNTIME_REACHABILITY_INPUT_TARGET = None
    base.RUNTIME_REACHABILITY_ENTER_DISTANCE_M = REACHABILITY_ENTER_DISTANCE_M
    base.RUNTIME_REACHABILITY_RELEASE_DISTANCE_M = REACHABILITY_RELEASE_DISTANCE_M
    base.RUNTIME_REACHABILITY_BLOCKED_REASON = None

    def supervised_update(self: WorkspaceTargetProjector, operator_target_m: Any):
        target = np.asarray(operator_target_m, dtype=float)
        try:
            hint = original_update(self, target)
        except Exception as exc:
            base.RUNTIME_REACHABILITY_GATE_ACTIVE = False
            base.RUNTIME_REACHABILITY_HINT_PROJECTED = False
            base.RUNTIME_REACHABILITY_PROJECTION_DISTANCE_M = 0.0
            base.RUNTIME_REACHABILITY_HINT_REPORTED_DISTANCE_M = 0.0
            base.RUNTIME_REACHABILITY_FEASIBLE_TARGET = None
            base.RUNTIME_REACHABILITY_INPUT_TARGET = target.tolist()
            base.RUNTIME_REACHABILITY_BLOCKED_REASON = (
                "workspace_hint_error:" + type(exc).__name__
            )
            return WorkspaceProjection(
                operator_target=target.copy(),
                feasible_target=target.copy(),
                projected=False,
                distance_m=0.0,
            )

        feasible_target = np.asarray(hint.feasible_target, dtype=float)
        distance_m = float(np.linalg.norm(feasible_target - target))
        hint_reported_distance_m = float(hint.distance_m)
        projected = bool(hint.projected or distance_m > 1e-9)
        was_active = bool(base.RUNTIME_REACHABILITY_GATE_ACTIVE)

        if was_active:
            active = projected and distance_m > REACHABILITY_RELEASE_DISTANCE_M
        else:
            active = projected and distance_m >= REACHABILITY_ENTER_DISTANCE_M

        base.RUNTIME_REACHABILITY_GATE_ACTIVE = bool(active)
        base.RUNTIME_REACHABILITY_HINT_PROJECTED = projected
        base.RUNTIME_REACHABILITY_PROJECTION_DISTANCE_M = distance_m
        base.RUNTIME_REACHABILITY_HINT_REPORTED_DISTANCE_M = hint_reported_distance_m
        base.RUNTIME_REACHABILITY_FEASIBLE_TARGET = feasible_target.tolist()
        base.RUNTIME_REACHABILITY_INPUT_TARGET = target.tolist()
        base.RUNTIME_REACHABILITY_BLOCKED_REASON = (
            "gross_workspace_excursion" if active else None
        )

        if active:
            return WorkspaceProjection(
                operator_target=target.copy(),
                feasible_target=feasible_target.copy(),
                projected=True,
                distance_m=distance_m,
            )

        self.operator_target = target.copy()
        self.feasible_target = target.copy()
        self.projection_distance_m = 0.0
        self.workspace_limited = False
        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=target.copy(),
            projected=False,
            distance_m=0.0,
        )

    projector_type.update = supervised_update
    projector_type._REACHABILITY_SUPERVISOR_INSTALLED = True

    # Runtime status was already gate-aware, but Unity receives a separate 5006
    # state packet. Mirror the same gate into that packet so its target marker
    # can turn orange whenever the backend is limiting gross reachability.
    original_send_robot_state = getattr(base, "send_robot_state", None)
    if callable(original_send_robot_state) and not getattr(
        base, "_REACHABILITY_UNITY_STATE_INSTALLED", False
    ):
        def send_robot_state_with_reachability(*args: Any, **kwargs: Any):
            gate_active = bool(base.RUNTIME_REACHABILITY_GATE_ACTIVE)
            if "workspace_limited" in kwargs:
                adjusted_kwargs = dict(kwargs)
                adjusted_kwargs["workspace_limited"] = bool(
                    adjusted_kwargs["workspace_limited"] or gate_active
                )
                return original_send_robot_state(*args, **adjusted_kwargs)

            adjusted_args = list(args)
            if len(adjusted_args) > 8:
                adjusted_args[8] = bool(adjusted_args[8] or gate_active)
            return original_send_robot_state(*adjusted_args, **kwargs)

        base.send_robot_state = send_robot_state_with_reachability
        base._REACHABILITY_UNITY_STATE_INSTALLED = True

    original_writer = getattr(base, "write_runtime_status", None)
    if callable(original_writer) and not getattr(
        base, "_REACHABILITY_SUPERVISOR_STATUS_INSTALLED", False
    ):
        def status_writer(status_value: dict[str, Any]) -> None:
            enriched = dict(status_value)
            active = bool(base.RUNTIME_REACHABILITY_GATE_ACTIVE)
            distance_m = float(base.RUNTIME_REACHABILITY_PROJECTION_DISTANCE_M)
            enriched["reachability_gate_active"] = active
            enriched["reachability_enter_distance_m"] = REACHABILITY_ENTER_DISTANCE_M
            enriched["reachability_release_distance_m"] = REACHABILITY_RELEASE_DISTANCE_M
            enriched["reachability_projection_distance_m"] = distance_m
            enriched["reachability_hint_reported_distance_m"] = float(
                base.RUNTIME_REACHABILITY_HINT_REPORTED_DISTANCE_M
            )
            enriched["reachability_input_target"] = base.RUNTIME_REACHABILITY_INPUT_TARGET
            enriched["reachability_feasible_target"] = (
                base.RUNTIME_REACHABILITY_FEASIBLE_TARGET
            )
            enriched["reachability_blocked_reason"] = (
                base.RUNTIME_REACHABILITY_BLOCKED_REASON
            )
            if active:
                enriched["workspace_limited"] = True
                enriched["workspace_projection_distance_m"] = distance_m
                enriched["workspace_source"] = (
                    "configuration_aware_runtime_geometry+gross_reachability_gate"
                )
            original_writer(enriched)

        base.write_runtime_status = status_writer
        base._REACHABILITY_SUPERVISOR_STATUS_INSTALLED = True
