"""Load config/teleop.json, apply it, then start the projected teleoperation runtime."""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import apply_to_base_module, apply_to_projected_runtime, load_teleop_config  # noqa: E402
from g1_teleop.ik_branch_search import install_position_only_candidate_scoring  # noqa: E402
from g1_teleop.ik_emergency import load_severe_ik_fallback_settings  # noqa: E402
from g1_teleop.ik_fallback import install_coupled_ik_fallback, load_ik_fallback_settings  # noqa: E402
import g1_teleop.ik_fallback as ik_fallback_module  # noqa: E402
from g1_teleop.ik_primary_guard import install_primary_task_guard  # noqa: E402
from g1_teleop.inspection_contact import install_inspection_contact_monitor  # noqa: E402
from g1_teleop.joint_posture import install_joint_space_posture_scheduler  # noqa: E402
from g1_teleop.motion_quality import install_joint_command_smoother  # noqa: E402
from g1_teleop.runtime_collision import install_runtime_collision_policy  # noqa: E402

import g1_right_arm_udp_ik_demo as base  # noqa: E402


TELEOP_CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"
JOINT_POSTURE_PROFILE_PATH = PROJECT_ROOT / "config" / "joint_postures.json"
CONFIGURED_IK_SUBSTEPS = 1
WRIST_MAX_STEP_DEG_PER_CYCLE = 0.5
REFERENCE_MAX_DT_S = 1.0 / 60.0
PRIMARY_GUARD_TOLERANCE_M = 0.0005
STAGNATION_POSITION_ERROR_M = 0.015
STAGNATION_MIN_IMPROVEMENT_M = 0.00025
STAGNATION_FRAMES = 8


def install_calibrated_vr_wrist_orientation(base_module) -> None:
    def calibrated_clutched_target(reference, input_position, input_rotation):
        target_position = reference["robot_position"] + input_position - reference["input_position"]
        current_input_rotation = base_module.operator_rotation_to_robot_matrix(input_rotation)
        rotation_delta = current_input_rotation @ reference["input_rotation"].T
        target_rotation = rotation_delta @ reference["robot_rotation"]
        return target_position, target_rotation
    base_module.calculate_clutched_target = calibrated_clutched_target


def install_no_catchup_position_reference(base_module) -> None:
    original_update = base_module.update_safe_position_reference
    if getattr(base_module, "_NO_CATCHUP_POSITION_REFERENCE_INSTALLED", False):
        return

    def no_catchup_update(current_position, desired_position, delta_time):
        bounded_dt = min(max(float(delta_time), 1e-4), REFERENCE_MAX_DT_S)
        return original_update(current_position, desired_position, bounded_dt)

    base_module.update_safe_position_reference = no_catchup_update
    base_module._NO_CATCHUP_POSITION_REFERENCE_INSTALLED = True


def install_position_only_fallback_policy(supervisor) -> None:
    original_update = supervisor.update
    previous_error = None
    stagnant_frames = 0

    def position_only_update(position_error_m, rotation_error_rad, *, inspection_contact):
        nonlocal previous_error, stagnant_frames
        del rotation_error_rad
        position_error = float(position_error_m)
        transition = original_update(position_error, 0.0, inspection_contact=inspection_contact)
        improvement = math.inf if previous_error is None else previous_error - position_error
        previous_error = position_error
        can_recover = (
            supervisor.settings.enabled
            and not supervisor.active
            and not inspection_contact
            and position_error >= STAGNATION_POSITION_ERROR_M
        )
        if can_recover and improvement < STAGNATION_MIN_IMPROVEMENT_M:
            stagnant_frames += 1
        else:
            stagnant_frames = 0
        if stagnant_frames >= STAGNATION_FRAMES:
            supervisor.active = True
            supervisor.bad_frames = 0
            supervisor.good_frames = 0
            stagnant_frames = 0
            return type(transition)(True, True, "position_stagnation", 0, 0)
        return transition

    supervisor.update = position_only_update


def install_position_only_severe_trigger(base_module, supervisor, settings) -> None:
    original_solver = base_module.solve_right_arm_target
    base_module.RUNTIME_IK_SEVERE_TRIGGERED = False
    base_module.RUNTIME_IK_SEVERE_REASON = None

    def position_severe_solver(*args, **kwargs):
        model = args[0] if len(args) > 0 else kwargs.get("model")
        data = args[1] if len(args) > 1 else kwargs.get("data")
        context = kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        qpos_ids = None
        start_q = None
        if data is not None and isinstance(context, dict):
            qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
            if qpos_ids.size:
                start_q = data.qpos[qpos_ids].copy()
        base_module.RUNTIME_IK_SEVERE_TRIGGERED = False
        base_module.RUNTIME_IK_SEVERE_REASON = None
        result = original_solver(*args, **kwargs)
        if start_q is None or qpos_ids is None or supervisor.active:
            return result
        position_error = getattr(base_module, "RUNTIME_IK_POSITION_ERROR_M", None)
        severe_position = (
            position_error is not None
            and math.isfinite(float(position_error))
            and float(position_error) >= settings.position_error_m
        )
        if not severe_position:
            return result
        data.qpos[qpos_ids] = start_q
        try:
            import mujoco
            mujoco.mj_forward(model, data)
        except (ImportError, TypeError):
            pass
        supervisor.active = True
        supervisor.bad_frames = 0
        supervisor.good_frames = 0
        base_module.RUNTIME_IK_SEVERE_TRIGGERED = True
        base_module.RUNTIME_IK_SEVERE_REASON = "position"
        return original_solver(*args, **kwargs)

    base_module.solve_right_arm_target = position_severe_solver


def install_smooth_cycle_and_wrist_overlay(base_module) -> None:
    """Keep XYZ primary, 7-DOF posture secondary, Quest orientation tertiary."""
    if getattr(base_module, "_SMOOTH_CYCLE_WRIST_OVERLAY_INSTALLED", False):
        return

    original_solver = base_module.solve_right_arm_target
    wrist_max_step_rad = math.radians(WRIST_MAX_STEP_DEG_PER_CYCLE)
    base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT = 1.0
    base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED = False
    base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG = 0.0

    def smooth_wrist_solver(*args, **kwargs):
        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["substeps"] = CONFIGURED_IK_SUBSTEPS

        # Position and the seven-joint posture own higher priorities. Prevent the
        # base solver from also rotating the wrist; Quest orientation is applied
        # exactly once below as the tertiary task.
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

        posture_blend = float(np.clip(context.get("joint_posture_blend", 0.0), 0.0, 1.0))
        orientation_weight = 1.0 - posture_blend
        base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT = orientation_weight
        base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED = False
        base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG = 0.0
        context["wrist_orientation_weight"] = orientation_weight

        if orientation_weight <= 1e-6:
            context["wrist_orientation_overlay_blocked"] = False
            context["wrist_orientation_step_deg"] = 0.0
            return result

        import mujoco
        mujoco.mj_forward(model, data)
        current_rotation = data.xmat[int(orientation_body)].reshape(3, 3)
        rotation_error = np.asarray(
            base_module.calculate_rotation_error(
                np.asarray(requested_rotation, dtype=float), current_rotation
            ),
            dtype=float,
        ) * orientation_weight
        if float(np.linalg.norm(rotation_error)) < 1e-7:
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
        for line_search_index in range(5):
            scale = 0.5 ** line_search_index
            data.qpos[wrist_qpos_ids] = start_wrist_q + scale * wrist_delta
            base_module.clamp_joint_angles(model, data, base_module.RIGHT_ARM_JOINTS)
            mujoco.mj_forward(model, data)
            if not base_module.has_right_arm_core_contact(model, data, context):
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
    base_module._SMOOTH_CYCLE_WRIST_OVERLAY_INSTALLED = True

    original_status_writer = getattr(base_module, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base_module, "_WRIST_TERTIARY_STATUS_INSTALLED", False):
        def wrist_status_writer(status_value):
            enriched = dict(status_value)
            enriched["wrist_orientation_weight"] = float(base_module.RUNTIME_WRIST_ORIENTATION_WEIGHT)
            enriched["wrist_orientation_overlay_blocked"] = bool(
                base_module.RUNTIME_WRIST_ORIENTATION_OVERLAY_BLOCKED
            )
            enriched["wrist_orientation_step_deg"] = float(
                base_module.RUNTIME_WRIST_ORIENTATION_STEP_DEG
            )
            original_status_writer(enriched)

        base_module.write_runtime_status = wrist_status_writer
        base_module._WRIST_TERTIARY_STATUS_INSTALLED = True


def main() -> None:
    config = load_teleop_config(TELEOP_CONFIG_PATH)
    fallback_settings = load_ik_fallback_settings(TELEOP_CONFIG_PATH)
    fallback_settings = replace(
        fallback_settings,
        multiseed=replace(fallback_settings.multiseed, enabled=False),
    )
    severe_fallback_settings = load_severe_ik_fallback_settings(TELEOP_CONFIG_PATH)

    apply_to_base_module(base, config)
    install_no_catchup_position_reference(base)
    install_runtime_collision_policy(base, config)
    inspection_machine = install_inspection_contact_monitor(base, config)
    install_position_only_candidate_scoring(ik_fallback_module)
    fallback_supervisor = install_coupled_ik_fallback(base, fallback_settings)
    install_position_only_fallback_policy(fallback_supervisor)
    install_position_only_severe_trigger(base, fallback_supervisor, severe_fallback_settings)
    install_primary_task_guard(base, tolerance_m=PRIMARY_GUARD_TOLERANCE_M)
    install_calibrated_vr_wrist_orientation(base)
    install_joint_space_posture_scheduler(base, profile_path=JOINT_POSTURE_PROFILE_PATH)
    install_smooth_cycle_and_wrist_overlay(base)
    install_joint_command_smoother(base)

    import g1_right_arm_udp_ik_runtime as runtime
    apply_to_projected_runtime(runtime, config, PROJECT_ROOT)

    print(f"Teleop config: {TELEOP_CONFIG_PATH}")
    print(f"Joint posture profile: {JOINT_POSTURE_PROFILE_PATH}")
    print(
        "Collision authority: TaskAwareRightArmCollisionPolicy "
        f"(structural_neighbor_distance={config.collision.structural_neighbor_distance})"
    )
    print(
        "Inspection contact state: "
        + ("enabled (monitor-only foundation)" if inspection_machine.enabled else "disabled")
    )
    print(
        "Position reference: fixed Cartesian speed limit "
        f"({config.motion.position_max_speed_mps:.2f} m/s; 60 Hz step cap={REFERENCE_MAX_DT_S*1000.0:.1f} ms)"
    )
    print(f"Primary guard: bounded one-cycle worsening <= {PRIMARY_GUARD_TOLERANCE_M*1000.0:.1f} mm")
    print("Joint command smoothing: disabled")
    print("IK recovery: coupled position recovery only; live multi-seed search disabled")
    print(
        "Task priority: Cartesian wrist XYZ primary -> captured 7-DOF posture secondary -> "
        "Quest wrist orientation tertiary"
    )
    print(
        "Wrist orientation: engagement-calibrated Quest hand-to-G1 wrist frame, "
        "faded out as torso posture blend approaches 1"
    )
    runtime.main()


if __name__ == "__main__":
    main()
