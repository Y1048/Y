"""Start configured G1 teleoperation with geometry-aware redundancy resolution."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.geometry_redundancy import install_geometry_aware_redundancy_resolver  # noqa: E402
from g1_teleop.runtime_collision import dangerous_contact_clearance_m  # noqa: E402
import run_configured_g1_teleop as configured  # noqa: E402


WRIST_CLEARANCE_REGRESSION_TOLERANCE_M = 0.0001


def install_geometry_instead_of_manual_posture(base_module, *, profile_path):
    install_geometry_aware_redundancy_resolver(base_module, profile_path=profile_path)


def install_absolute_vr_wrist_orientation(base_module) -> None:
    """Keep clutched translation, but use the mapped Quest wrist orientation absolutely."""
    def absolute_clutched_target(reference, input_position, input_rotation):
        target_position = reference["robot_position"] + input_position - reference["input_position"]
        target_rotation = base_module.operator_rotation_to_robot_matrix(input_rotation)
        return target_position, target_rotation

    base_module.calculate_clutched_target = absolute_clutched_target
    base_module.RUNTIME_WRIST_ORIENTATION_REFERENCE_MODE = "absolute_mapped_hand"


def install_absolute_safe_wrist_overlay(base_module) -> None:
    """Apply absolute Quest wrist orientation as a collision-safe tertiary task."""
    if getattr(base_module, "_GEOMETRY_ABSOLUTE_WRIST_OVERLAY_INSTALLED", False):
        return

    original_solver = base_module.solve_right_arm_target
    wrist_max_step_rad = math.radians(configured.WRIST_MAX_STEP_DEG_PER_CYCLE)
    base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT = 1.0
    base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED = False
    base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG = 0.0
    base_module.RUNTIME_WRIST_ORIENTATION_REFERENCE_MODE = "absolute_mapped_hand"

    def smooth_wrist_solver(*args, **kwargs):
        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["substeps"] = configured.CONFIGURED_IK_SUBSTEPS

        requested_rotation = adjusted_kwargs.get("target_rotation")
        if requested_rotation is None and len(args) > 5:
            requested_rotation = args[5]
        adjusted_kwargs["target_rotation"] = None
        adjusted_args = list(args)
        if len(adjusted_args) > 5:
            adjusted_args[5] = None

        result = original_solver(*adjusted_args, **adjusted_kwargs)

        model = adjusted_args[0] if len(adjusted_args) > 0 else adjusted_kwargs.get("model")
        data = adjusted_args[1] if len(adjusted_args) > 1 else adjusted_kwargs.get("data")
        context = adjusted_kwargs.get("context")
        if context is None and len(adjusted_args) > 8:
            context = adjusted_args[8]
        if model is None or data is None or requested_rotation is None or not isinstance(context, dict):
            return result

        right_dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        right_qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        orientation_body = context.get("orientation_body")
        if right_dof_ids.size < 7 or right_qpos_ids.size < 7 or orientation_body is None:
            return result

        import mujoco

        structural_neighbor_distance = int(
            getattr(base_module, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        )
        safe_distance = max(
            float(getattr(base_module, "RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M", 0.015)),
            1e-4,
        )
        clearance_before_raw = dangerous_contact_clearance_m(
            model,
            data,
            context,
            structural_neighbor_distance=structural_neighbor_distance,
        )
        clearance_before = safe_distance if clearance_before_raw is None else float(clearance_before_raw)

        mujoco.mj_forward(model, data)
        current_rotation = data.xmat[int(orientation_body)].reshape(3, 3)
        rotation_error = np.asarray(
            base_module.calculate_rotation_error(
                np.asarray(requested_rotation, dtype=float), current_rotation
            ),
            dtype=float,
        )

        base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT = 1.0
        base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED = False
        base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG = 0.0
        context["wrist_orientation_weight"] = 1.0
        context["wrist_orientation_reference_mode"] = "absolute_mapped_hand"

        if float(np.linalg.norm(rotation_error)) < 1e-7:
            context["wrist_orientation_overlay_blocked"] = False
            context["wrist_orientation_step_deg"] = 0.0
            return result

        jacp_dummy = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp_dummy, jacr, int(orientation_body))
        wrist_dof_ids = right_dof_ids[4:7]
        wrist_qpos_ids = right_qpos_ids[4:7]
        wrist_jacobian = jacr[:, wrist_dof_ids]
        wrist_pseudoinverse = base_module.damped_pseudoinverse(
            wrist_jacobian, float(base_module.ORIENTATION_DAMPING)
        )
        wrist_delta = wrist_pseudoinverse @ rotation_error
        wrist_delta = np.clip(wrist_delta, -wrist_max_step_rad, wrist_max_step_rad)

        start_wrist_q = data.qpos[wrist_qpos_ids].copy()
        accepted = False
        accepted_step = np.zeros(3, dtype=float)
        for line_search_index in range(7):
            scale = 0.5 ** line_search_index
            data.qpos[wrist_qpos_ids] = start_wrist_q + scale * wrist_delta
            base_module.clamp_joint_angles(model, data, base_module.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)

            if base_module.has_right_arm_core_contact(model, data, context):
                continue
            trial_raw = dangerous_contact_clearance_m(
                model,
                data,
                context,
                structural_neighbor_distance=structural_neighbor_distance,
            )
            trial_clearance = safe_distance if trial_raw is None else float(trial_raw)
            if trial_clearance < clearance_before - WRIST_CLEARANCE_REGRESSION_TOLERANCE_M:
                continue

            accepted = True
            accepted_step = data.qpos[wrist_qpos_ids] - start_wrist_q
            break

        if not accepted:
            data.qpos[wrist_qpos_ids] = start_wrist_q
            mujoco.mj_forward(model, data)
            base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED = True
            context["wrist_orientation_overlay_blocked"] = True
        else:
            step_deg = float(np.linalg.norm(np.degrees(accepted_step)))
            base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG = step_deg
            context["wrist_orientation_overlay_blocked"] = False
            context["wrist_orientation_step_deg"] = step_deg

        return data.xpos[int(context["position_body"])].copy()

    base_module.solve_right_arm_target = smooth_wrist_solver
    base_module._GEOMETRY_ABSOLUTE_WRIST_OVERLAY_INSTALLED = True

    original_status_writer = getattr(base_module, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base_module, "_GEOMETRY_ABSOLUTE_WRIST_STATUS_INSTALLED", False):
        def wrist_status_writer(status_value):
            enriched = dict(status_value)
            enriched["wrist_orientation_weight"] = float(base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT)
            enriched["wrist_orientation_overlay_blocked"] = bool(
                base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED
            )
            enriched["wrist_orientation_step_deg"] = float(
                base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG
            )
            enriched["wrist_orientation_reference_mode"] = (
                base_module.RUNTIME_WRIST_ORIENTATION_REFERENCE_MODE
            )
            original_status_writer(enriched)

        base_module.write_runtime_status = wrist_status_writer
        base_module._GEOMETRY_ABSOLUTE_WRIST_STATUS_INSTALLED = True


def main() -> None:
    configured.install_joint_space_posture_scheduler = install_geometry_instead_of_manual_posture
    configured.install_calibrated_vr_wrist_orientation = install_absolute_vr_wrist_orientation
    configured.install_smooth_cycle_and_wrist_overlay = install_absolute_safe_wrist_overlay
    print("Redundancy mode: automatic G1 geometry / clearance + joint-limit cost")
    print("Manual torso_front_deg: baseline only, not a live joint target")
    print("Wrist orientation: absolute mapped Quest hand pose, collision-safe tertiary")
    configured.main()


if __name__ == "__main__":
    main()
