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

    Wrist orientation is intentionally owned by the decoupled three-wrist-joint
    task. Rotation error must not arm a whole-arm fallback or keep one active.
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
        if context is None and len(args) > 7:
            context = args[7]

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
        "Wrist orientation: absolute Quest hand-tracking orientation "
        f"with {config.motion.rotation_max_speed_deg_s:.0f} deg/s reference limit"
    )
    if fallback_supervisor.settings.enabled:
        strategy = "decoupled wrist orientation + position-only coupled 7-DoF fallback"
        if fallback_supervisor.settings.multiseed.enabled:
            strategy += " + multi-seed search"
        strategy += " + position-only severe trigger + primary-task descent guard"
        print(f"IK strategy: {strategy}")
    else:
        print("IK strategy: decoupled only (fallback disabled)")
    runtime.main()


if __name__ == "__main__":
    main()
