"""Run G1 teleoperation with runtime joint-space geometry as workspace authority.

The legacy wrist-only voxel map is retained as a diagnostic hint, but it no
longer projects the operator target. Actual MuJoCo collision geometry, joint
limits, adaptive redundancy, and the hard clearance floor own feasibility.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.workspace_map import WorkspaceProjection, WorkspaceTargetProjector  # noqa: E402
import g1_right_arm_udp_ik_demo as base  # noqa: E402
import run_geometry_g1_teleop as geometry  # noqa: E402


_LAST_VOXEL_HINT_PROJECTED = False
_LAST_VOXEL_HINT_DISTANCE_M = 0.0
_LAST_VOXEL_HINT_TARGET = None


def install_diagnostic_only_voxel_workspace() -> None:
    """Keep the voxel map as a hint while passing operator XYZ through unchanged."""
    global _LAST_VOXEL_HINT_PROJECTED
    global _LAST_VOXEL_HINT_DISTANCE_M
    global _LAST_VOXEL_HINT_TARGET

    projector_type = WorkspaceTargetProjector
    if getattr(projector_type, "_DIAGNOSTIC_ONLY_VOXEL_WORKSPACE_INSTALLED", False):
        return

    original_update = projector_type.update

    def diagnostic_only_update(self, operator_target_m):
        global _LAST_VOXEL_HINT_PROJECTED
        global _LAST_VOXEL_HINT_DISTANCE_M
        global _LAST_VOXEL_HINT_TARGET

        target = np.asarray(operator_target_m, dtype=float)
        try:
            hint = original_update(self, target)
            _LAST_VOXEL_HINT_PROJECTED = bool(hint.projected)
            _LAST_VOXEL_HINT_DISTANCE_M = float(hint.distance_m)
            _LAST_VOXEL_HINT_TARGET = np.asarray(hint.feasible_target, dtype=float).tolist()
        except Exception:
            # A diagnostic hint must never become a control-path failure.
            _LAST_VOXEL_HINT_PROJECTED = False
            _LAST_VOXEL_HINT_DISTANCE_M = 0.0
            _LAST_VOXEL_HINT_TARGET = None

        return WorkspaceProjection(
            operator_target=target.copy(),
            feasible_target=target.copy(),
            projected=False,
            distance_m=0.0,
        )

    projector_type.update = diagnostic_only_update
    projector_type._DIAGNOSTIC_ONLY_VOXEL_WORKSPACE_INSTALLED = True
    # Prevent the older center-region posture wrapper from replacing this global
    # diagnostic-only policy. Geometry/joint-space collision checks are now the
    # sole feasibility authority throughout the right-arm workspace.
    projector_type._GEOMETRY_REDUNDANCY_WORKSPACE_INSTALLED = True


def install_configuration_workspace_status() -> None:
    """Expose the true authority and the legacy voxel result separately."""
    if getattr(base, "_CONFIGURATION_WORKSPACE_STATUS_INSTALLED", False):
        return

    original_writer = base.write_runtime_status

    def status_writer(status_value):
        enriched = dict(status_value)
        enriched["workspace_source"] = "configuration_aware_runtime_geometry"
        enriched["workspace_projection_distance_m"] = 0.0
        enriched["workspace_limited"] = False
        enriched["voxel_workspace_authority"] = False
        enriched["runtime_geometry_workspace_authority"] = True
        enriched["voxel_workspace_hint_projected"] = bool(_LAST_VOXEL_HINT_PROJECTED)
        enriched["voxel_workspace_hint_projection_distance_m"] = float(
            _LAST_VOXEL_HINT_DISTANCE_M
        )
        enriched["voxel_workspace_hint_target"] = _LAST_VOXEL_HINT_TARGET
        original_writer(enriched)

    base.write_runtime_status = status_writer
    base._CONFIGURATION_WORKSPACE_STATUS_INSTALLED = True


def main() -> None:
    # Install before geometry.main() so the old center-only voxel bypass is
    # suppressed and the voxel map remains diagnostic-only everywhere.
    install_diagnostic_only_voxel_workspace()
    install_configuration_workspace_status()
    print("Workspace authority: configuration-aware MuJoCo runtime geometry")
    print("Voxel workspace: diagnostic hint only; no Cartesian projection")
    geometry.main()


if __name__ == "__main__":
    main()
