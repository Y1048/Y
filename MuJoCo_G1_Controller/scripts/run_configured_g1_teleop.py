"""Load config/teleop.json, apply it, then start the projected teleoperation runtime."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import (  # noqa: E402
    apply_to_base_module,
    apply_to_projected_runtime,
    load_teleop_config,
)
from g1_teleop.ik_branch_search import (  # noqa: E402
    install_expanded_multiseed_branches,
    install_position_only_candidate_scoring,
)
from g1_teleop.ik_emergency import load_severe_ik_fallback_settings  # noqa: E402
from g1_teleop.ik_fallback import (  # noqa: E402
    install_coupled_ik_fallback,
    load_ik_fallback_settings,
)
import g1_teleop.ik_fallback as ik_fallback_module  # noqa: E402
from g1_teleop.ik_primary_guard import install_primary_task_guard  # noqa: E402
from g1_teleop.inspection_contact import install_inspection_contact_monitor  # noqa: E402
from g1_teleop.motion_quality import (  # noqa: E402
    DEFAULT_PREFERRED_ELBOW_DEG as PREFERRED_ELBOW_DEG,
    DEFAULT_PROXIMAL_MAX_STEP_DEG,
    DEFAULT_WRIST_MAX_STEP_DEG,
    TORSO_FRONT_PREFERRED_ELBOW_DEG,
    install_joint_command_smoother,
    install_motion_gated_elbow_preference,
    install_target_aware_elbow_pole,
)
from g1_teleop.runtime_collision import install_runtime_collision_policy  # noqa: E402

import g1_right_arm_udp_ik_demo as base  # noqa: E402


TELEOP_CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"
CONFIGURED_IK_SUBSTEPS = 1
WRIST_MAX_STEP_DEG_PER_CYCLE = 0.5
REFERENCE_MAX_DT_S = 1.0 / 60.0
STAGNATION_POSITION_ERROR_M = 0.015
STAGNATION_MIN_IMPROVEMENT_M = 0.00025
STAGNATION_FRAMES = 8


def install_calibrated_vr_wrist_orientation(base_module) -> None:
    """Calibrate Quest hand frame to the current G1 wrist frame at engagement."""

    def calibrated_clutched_target(reference, input_position, input_rotation):
        target_position = (
            reference["robot_position"]
            + input_position
            - reference["input_position"]
        )
        current_input_rotation = base_module.operator_rotation_to_robot_matrix(
            input_rotation
        )
        rotation_delta = current_input_rotation @ reference["input_rotation"].T
        target_rotation = rotation_delta @ reference["robot_rotation"]
        return target_position, target_rotation

    base_module.calculate_clutched_target = calibrated_clutched_target


def install_no_catchup_position_reference(base_module) -> None:
    """Prevent delayed viewer cycles from creating Cartesian catch-up bursts."""

    original_update = base_module.update_safe_position_reference
    if getattr(base_module, "_NO_CATCHUP_POSITION_REFERENCE_INSTALLED", False):
        return

    def no_catchup_update(current_position, desired_position, delta_time):
        bounded_dt = min(max(float(delta_time), 1e-4), REFERENCE_MAX_DT_S)
        return original_update(current_position, desired_position, bounded_dt)

    base_module.update_safe_position_reference = no_catchup_update
    base_module._NO_CATCHUP_POSITION_REFERENCE_INSTALLED = True


def install_position_only_fallback_policy(supervisor) -> None:
    """Use position-only fallback activation, including local-minimum recovery."""

    original_update = supervisor.update
    previous_error = None
    stagnant_frames = 0

    def position_only_update(position_error_m, rotation_error_rad, *, inspection_contact):
        nonlocal previous_error, stagnant_frames
        del rotation_error_rad
        position_error = float(position_error_m)
        transition = original_update(
            position_error,
            0.0,
            inspection_contact=inspection_contact,
        )

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
            return type(transition)(
                active=True,
                changed=True,
                reason="position_stagnation",
                bad_frames=0,
                good_frames=0,
            )
        return transition

    supervisor.update = position_only_update


def install_position_only_severe_trigger(base_module, supervisor, settings) -> None:
    """Escalate immediately only for severe Cartesian position error."""

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
    """Use one position-IK substep, coherent elbow preference, and wrist-only DLS."""

    if getattr(base_module, "_SMOOTH_CYCLE_WRIST_OVERLAY_INSTALLED", False):
        return

    install_motion_gated_elbow_preference(base_module)
    original_solver = base_module.solve_right_arm_target
    wrist_max_step_rad = math.radians(WRIST_MAX_STEP_DEG_PER_CYCLE)

    def smooth_wrist_solver(*args, **kwargs):
        adjusted_kwargs = dict(kwargs)
        adjusted_kwargs["substeps"] = CONFIGURED_IK_SUBSTEPS
        result = original_solver(*args, **adjusted_kwargs)

        model = args[0] if len(args) > 0 else adjusted_kwargs.get("model")
        data = args[1] if len(args) > 1 else adjusted_kwargs.get("data")
        target_rotation = adjusted_kwargs.get("target_rotation")
        context = adjusted_kwargs.get("context")
        if context is None and len(args) > 8:
            context = args[8]
        if (
            model is None
            or data is None
            or target_rotation is None
            or not isinstance(context, dict)
        ):
            return result

        right_dof_ids = np.asarray(context.get("right_dof_ids", []), dtype=int)
        right_qpos_ids = np.asarray(context.get("right_qpos_ids", []), dtype=int)
        orientation_body = context.get("orientation_body")
        if right_dof_ids.size < 7 or right_qpos_ids.size < 7 or orientation_body is None:
            return result

        import mujoco

        mujoco.mj_forward(model, data)
        current_rotation = data.xmat[int(orientation_body)].reshape(3, 3)
        rotation_error = np.asarray(
            base_module.calculate_rotation_error(
                np.asarray(target_rotation, dtype=float),
                current_rotation,
            ),
            dtype=float,
        )
        if float(np.linalg.norm(rotation_error)) < 1e-7:
            return result

        jacp_dummy = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(
            model,
            data,
            jacp_dummy,
            jacr,
            int(orientation_body),
        )
        wrist_dof_ids = right_dof_ids[4:7]
        wrist_qpos_ids = right_qpos_ids[4:7]
        wrist_jacobian = jacr[:, wrist_dof_ids]
        wrist_pseudoinverse = base_module.damped_pseudoinverse(
            wrist_jacobian,
            float(base_module.ORIENTATION_DAMPING),
        )
        wrist_delta = wrist_pseudoinverse @ rotation_error
        wrist_delta = np.clip(
            wrist_delta,
            -wrist_max_step_rad,
            wrist_max_step_rad,
        )

        start_wrist_q = data.qpos[wrist_qpos_ids].copy()
        accepted = False
        for line_search_index in range(5):
            scale = 0.5 ** line_search_index
            data.qpos[wrist_qpos_ids] = start_wrist_q + scale * wrist_delta
            base_module.clamp_joint_angles(
                model,
                data,
                base_module.RIGHT_ARM_JOINTS,
            )
            mujoco.mj_forward(model, data)
            if not base_module.has_right_arm_core_contact(model, data, context):
                accepted = True
                break

        if not accepted:
            data.qpos[wrist_qpos_ids] = start_wrist_q
            mujoco.mj_forward(model, data)
            context["wrist_orientation_overlay_blocked"] = True
        else:
            context["wrist_orientation_overlay_blocked"] = False

        return data.xpos[int(context["position_body"])].copy()

    base_module.solve_right_arm_target = smooth_wrist_solver
    base_module._SMOOTH_CYCLE_WRIST_OVERLAY_INSTALLED = True


def main() -> None:
    config = load_teleop_config(TELEOP_CONFIG_PATH)
    fallback_settings = load_ik_fallback_settings(TELEOP_CONFIG_PATH)
    severe_fallback_settings = load_severe_ik_fallback_settings(TELEOP_CONFIG_PATH)
    apply_to_base_module(base, config)
    install_no_catchup_position_reference(base)
    install_runtime_collision_policy(base, config)
    inspection_machine = install_inspection_contact_monitor(base, config)
    # Put target-aware elbow geometry inside the fallback stack so the primary
    # decoupled IK sees the lifted elbow pole before branch recovery is considered.
    install_target_aware_elbow_pole(base)
    install_expanded_multiseed_branches(ik_fallback_module)
    install_position_only_candidate_scoring(ik_fallback_module)
    fallback_supervisor = install_coupled_ik_fallback(base, fallback_settings)
    install_position_only_fallback_policy(fallback_supervisor)
    install_position_only_severe_trigger(
        base,
        fallback_supervisor,
        severe_fallback_settings,
    )
    install_primary_task_guard(base)
    install_calibrated_vr_wrist_orientation(base)
    install_smooth_cycle_and_wrist_overlay(base)
    install_joint_command_smoother(base)

    import g1_right_arm_udp_ik_runtime as runtime

    apply_to_projected_runtime(runtime, config, PROJECT_ROOT)
    print(f"Teleop config: {TELEOP_CONFIG_PATH}")
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
        f"({config.motion.position_max_speed_mps:.2f} m/s; no adaptive acceleration, "
        f"dt cap={REFERENCE_MAX_DT_S * 1000.0:.1f} ms)"
    )
    print(
        "Joint command smoothing: proximal <= "
        f"{DEFAULT_PROXIMAL_MAX_STEP_DEG:.2f} deg/cycle, wrist <= "
        f"{DEFAULT_WRIST_MAX_STEP_DEG:.2f} deg/cycle with acceleration limiting"
    )
    print(
        "Elbow posture: target-aware pole + bend preference "
        f"({PREFERRED_ELBOW_DEG:.0f} deg free-space -> "
        f"{TORSO_FRONT_PREFERRED_ELBOW_DEG:.0f} deg near torso front)"
    )
    print(
        "Wrist orientation: engagement-calibrated Quest hand-to-G1 wrist frame "
        f"with {config.motion.rotation_max_speed_deg_s:.0f} deg/s reference limit"
    )
    print(
        "IK recovery: position-only activation/scoring + stagnation trigger + "
        "shoulder pitch/roll/yaw and elbow multi-seed branches"
    )
    if fallback_supervisor.settings.enabled:
        strategy = "wrist-only orientation + position-only coupled 7-DoF fallback"
        if fallback_supervisor.settings.multiseed.enabled:
            strategy += " + expanded multi-seed search"
        strategy += " + position-only severe trigger + primary-task descent guard"
        print(f"IK strategy: {strategy}")
    else:
        print("IK strategy: decoupled only (fallback disabled)")
    runtime.main()


if __name__ == "__main__":
    main()
