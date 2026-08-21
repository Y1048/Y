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
from g1_teleop.ik_emergency import load_severe_ik_fallback_settings  # noqa: E402
from g1_teleop.ik_fallback import (  # noqa: E402
    install_coupled_ik_fallback,
    load_ik_fallback_settings,
)
from g1_teleop.ik_primary_guard import install_primary_task_guard  # noqa: E402
from g1_teleop.inspection_contact import install_inspection_contact_monitor  # noqa: E402
from g1_teleop.runtime_collision import install_runtime_collision_policy  # noqa: E402

import g1_right_arm_udp_ik_demo as base  # noqa: E402


TELEOP_CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"
CONFIGURED_IK_SUBSTEPS = 1
WRIST_MAX_STEP_DEG_PER_CYCLE = 0.5


def install_absolute_vr_wrist_orientation(base_module) -> None:
    """Keep position clutch-relative but use the VR wrist orientation absolutely."""

    def absolute_clutched_target(reference, input_position, input_rotation):
        target_position = (
            reference["robot_position"]
            + input_position
            - reference["input_position"]
        )
        target_rotation = base_module.operator_rotation_to_robot_matrix(
            input_rotation
        )
        return target_position, target_rotation

    base_module.calculate_clutched_target = absolute_clutched_target


def install_position_only_fallback_policy(supervisor) -> None:
    """Allow coupled 7-DoF fallback to react to position error only.

    Wrist orientation is intentionally owned by the three wrist joints.
    Rotation error must not arm a whole-arm fallback or keep one active.
    """

    original_update = supervisor.update

    def position_only_update(position_error_m, rotation_error_rad, *, inspection_contact):
        del rotation_error_rad
        return original_update(
            position_error_m,
            0.0,
            inspection_contact=inspection_contact,
        )

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
    """Limit whole-arm IK work to one substep and guarantee wrist-only orientation.

    The Cartesian reference already advances at 0.08 m/s. Running four IK
    substeps per viewer cycle can nevertheless change qpos several times in one
    frame, which looks fast and stair-stepped because this simulator writes qpos
    directly instead of using actuator dynamics. The configured runtime therefore
    performs one whole-arm IK substep per cycle.

    After that position solve, the remaining orientation error is handled by a
    dedicated DLS step on the three wrist joints only. This prevents shoulder and
    elbow motion from being used to chase hand orientation and avoids losing a
    valid wrist step inside the configured wrapper stack.
    """

    original_solver = base_module.solve_right_arm_target
    if getattr(base_module, "_SMOOTH_CYCLE_WRIST_OVERLAY_INSTALLED", False):
        return

    wrist_max_step_rad = math.radians(WRIST_MAX_STEP_DEG_PER_CYCLE)

    def smooth_wrist_solver(*args, **kwargs):
        adjusted_kwargs = dict(kwargs)
        # The live runtime does not explicitly pass substeps. Force the configured
        # stack to one qpos update opportunity per control cycle.
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
    install_runtime_collision_policy(base, config)
    inspection_machine = install_inspection_contact_monitor(base, config)
    fallback_supervisor = install_coupled_ik_fallback(base, fallback_settings)
    install_position_only_fallback_policy(fallback_supervisor)
    install_position_only_severe_trigger(
        base,
        fallback_supervisor,
        severe_fallback_settings,
    )
    install_primary_task_guard(base)
    install_absolute_vr_wrist_orientation(base)
    install_smooth_cycle_and_wrist_overlay(base)

    # Import only after tuning and safety/IK hooks are applied so the projected
    # runtime observes one configured policy stack.
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
        f"({config.motion.position_max_speed_mps:.2f} m/s; no adaptive acceleration)"
    )
    print(
        "Joint motion: one configured IK substep per control cycle "
        f"(wrist overlay <= {WRIST_MAX_STEP_DEG_PER_CYCLE:.1f} deg/cycle)"
    )
    print(
        "Wrist orientation: absolute Quest hand-tracking orientation "
        f"with {config.motion.rotation_max_speed_deg_s:.0f} deg/s reference limit"
    )
    if fallback_supervisor.settings.enabled:
        strategy = "wrist-only orientation + position-only coupled 7-DoF fallback"
        if fallback_supervisor.settings.multiseed.enabled:
            strategy += " + multi-seed search"
        strategy += " + position-only severe trigger + primary-task descent guard"
        print(f"IK strategy: {strategy}")
    else:
        print("IK strategy: decoupled only (fallback disabled)")
    runtime.main()


if __name__ == "__main__":
    main()
