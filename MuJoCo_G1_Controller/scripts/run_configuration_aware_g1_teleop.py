"""Run G1 teleoperation with runtime joint-space geometry as workspace authority.

The legacy wrist-only voxel map is retained as a diagnostic hint, but it no
longer projects the operator target. Actual MuJoCo collision geometry, joint
limits, adaptive redundancy, emergency escape, a hard clearance boundary,
continuous safe-progress reconfiguration, safe wrist rotation, and a final
swept-path collision guard own feasibility.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.bounded_reconfigure_escape import (  # noqa: E402
    install_bounded_reconfigure_escape,
)
from g1_teleop.clearance_recovery_supervisor import (  # noqa: E402
    install_clearance_recovery_supervisor,
)
from g1_teleop.controller_cycle_benchmark import (  # noqa: E402
    install_controller_cycle_benchmark,
)
from g1_teleop.emergency_clearance_escape import (  # noqa: E402
    install_emergency_clearance_escape,
)
from g1_teleop.hard_clearance_boundary_guard import (  # noqa: E402
    install_boundary_hard_clearance_floor,
)
from g1_teleop.safe_wrist_rotation_overlay import (  # noqa: E402
    install_safe_wrist_rotation_overlay,
    install_wrist_intent_capture,
)
from g1_teleop.swept_path_collision_guard import (  # noqa: E402
    install_swept_path_collision_guard,
)
from g1_teleop.workspace_map import WorkspaceProjection, WorkspaceTargetProjector  # noqa: E402
import g1_right_arm_udp_ik_demo as base  # noqa: E402
import run_geometry_g1_teleop as geometry  # noqa: E402


_LAST_VOXEL_HINT_PROJECTED = False
_LAST_VOXEL_HINT_DISTANCE_M = 0.0
_LAST_VOXEL_HINT_TARGET = None
_RIGHT_HAND_COLLISION_PROXY_ENABLED = False


def install_right_hand_collision_proxy_generation() -> None:
    """Add collision geometry for the stock visual-only G1 rubber hand."""
    global _RIGHT_HAND_COLLISION_PROXY_ENABLED

    if getattr(base, "_RIGHT_HAND_COLLISION_PROXY_GENERATOR_INSTALLED", False):
        return

    original_make_demo_xml = base.make_demo_xml

    def make_demo_xml_with_hand_collision(scene_name):
        global _RIGHT_HAND_COLLISION_PROXY_ENABLED

        original_make_demo_xml(scene_name)
        tree = ET.parse(base.DEMO_XML)
        root = tree.getroot()
        worldbody = root.find("worldbody")
        robot_body = None if worldbody is None else worldbody.find("body")
        right_wrist = (
            None
            if robot_body is None
            else base.find_body(robot_body, "right_wrist_yaw_link")
        )
        if right_wrist is None:
            raise RuntimeError("right_wrist_yaw_link not found while adding hand collision proxy")

        existing = right_wrist.find("geom[@name='right_rubber_hand_collision']")
        if existing is None:
            ET.SubElement(
                right_wrist,
                "geom",
                {
                    "name": "right_rubber_hand_collision",
                    "type": "mesh",
                    "mesh": "right_rubber_hand",
                    "pos": "0.0415 -0.003 0",
                    "density": "0",
                    "contype": "1",
                    "conaffinity": "1",
                    "group": "3",
                    "rgba": "0 0 0 0",
                },
            )
            tree.write(base.DEMO_XML, encoding="unicode")

        _RIGHT_HAND_COLLISION_PROXY_ENABLED = True

    base.make_demo_xml = make_demo_xml_with_hand_collision
    base._RIGHT_HAND_COLLISION_PROXY_GENERATOR_INSTALLED = True


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
    projector_type._GEOMETRY_REDUNDANCY_WORKSPACE_INSTALLED = True


def _final_collision_step_scale(clearance_m: float | None, slowdown_distance_m: float) -> float:
    if clearance_m is None or clearance_m >= slowdown_distance_m:
        return 1.0
    if clearance_m <= 0.0:
        return 0.0
    alpha = float(np.clip(clearance_m / slowdown_distance_m, 0.0, 1.0))
    return alpha * alpha * (3.0 - 2.0 * alpha)


def install_configuration_workspace_status() -> None:
    """Expose the actually accepted final collision state and workspace authority."""
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
        enriched["right_hand_collision_proxy_enabled"] = bool(
            _RIGHT_HAND_COLLISION_PROXY_ENABLED
        )

        inner_clearance = enriched.get("collision_clearance_m")
        enriched["inner_solver_collision_clearance_m"] = inner_clearance

        swept_clearance = getattr(base, "RUNTIME_SWEPT_PATH_AFTER_M", None)
        safe_progress_clearance = getattr(base, "RUNTIME_SAFE_PROGRESS_AFTER_M", None)
        supervisor_clearance = getattr(base, "RUNTIME_SAFETY_RECOVERY_AFTER_M", None)
        hard_guard_clearance = getattr(base, "RUNTIME_HARD_CLEARANCE_AFTER_M", None)
        final_clearance = (
            swept_clearance
            if swept_clearance is not None
            else safe_progress_clearance
            if safe_progress_clearance is not None
            else supervisor_clearance
            if supervisor_clearance is not None
            else hard_guard_clearance
        )
        if final_clearance is not None:
            final_clearance = float(final_clearance)
            enriched["collision_clearance_m"] = final_clearance
            slowdown_distance = float(
                getattr(base, "RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M", 0.015)
            )
            enriched["collision_step_scale"] = _final_collision_step_scale(
                final_clearance,
                slowdown_distance,
            )
            if swept_clearance is not None:
                enriched["collision_clearance_source"] = "swept_path_final_pose"
            elif safe_progress_clearance is not None:
                enriched["collision_clearance_source"] = "safe_progress_final_pose"
            elif supervisor_clearance is not None:
                enriched["collision_clearance_source"] = "safety_recovery_supervisor_pose"
            else:
                enriched["collision_clearance_source"] = "final_hard_guard_pose"
        else:
            enriched["collision_clearance_source"] = "inner_distance_aware_solver"

        enriched["voxel_workspace_hint_projected"] = bool(_LAST_VOXEL_HINT_PROJECTED)
        enriched["voxel_workspace_hint_projection_distance_m"] = float(
            _LAST_VOXEL_HINT_DISTANCE_M
        )
        enriched["voxel_workspace_hint_target"] = _LAST_VOXEL_HINT_TARGET
        original_writer(enriched)

    base.write_runtime_status = status_writer
    base._CONFIGURATION_WORKSPACE_STATUS_INSTALLED = True


def install_geometry_with_emergency_escape(base_module, *, profile_path) -> None:
    geometry.install_geometry_aware_redundancy_resolver(
        base_module,
        profile_path=profile_path,
    )
    install_emergency_clearance_escape(base_module)


def install_hard_guard_then_supervisor(base_module) -> None:
    """Install safety layers from inner endpoint checks to final timing instrumentation."""
    install_boundary_hard_clearance_floor(base_module)
    install_wrist_intent_capture(base_module)
    install_clearance_recovery_supervisor(base_module)
    install_bounded_reconfigure_escape(base_module)
    install_safe_wrist_rotation_overlay(base_module)
    install_swept_path_collision_guard(base_module)
    # Install last so one timing sample covers the complete solver/safety chain.
    install_controller_cycle_benchmark(base_module)


def main() -> None:
    install_right_hand_collision_proxy_generation()
    install_diagnostic_only_voxel_workspace()
    install_configuration_workspace_status()

    geometry.install_geometry_instead_of_manual_posture = install_geometry_with_emergency_escape
    geometry.install_hard_clearance_floor = install_hard_guard_then_supervisor

    print("Workspace authority: configuration-aware MuJoCo runtime geometry")
    print("Voxel workspace: diagnostic hint only; no Cartesian projection")
    print("Right rubber hand collision proxy: enabled")
    print("Emergency clearance recovery: enabled below 5 mm")
    print("Hard clearance guard: joint-space boundary clipping at 5 mm")
    print("Safe progress: 12 mm soft boundary with null-space + bounded reconfiguration")
    print("Wrist rotation: safe overlay remains active during reconfiguration")
    print("Swept-path guard: adaptive intermediate collision validation at 5 mm")
    print("Controller benchmark: rolling full-chain latency instrumentation enabled")
    geometry.main()


if __name__ == "__main__":
    main()
