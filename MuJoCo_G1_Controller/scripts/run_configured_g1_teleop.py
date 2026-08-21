"""Load config/teleop.json, apply it, then start the projected teleoperation runtime."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import (  # noqa: E402
    apply_to_base_module,
    apply_to_projected_runtime,
    load_teleop_config,
)
from g1_teleop.ik_emergency import (  # noqa: E402
    install_severe_ik_fallback_trigger,
    load_severe_ik_fallback_settings,
)
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
    """Keep position clutch-relative but use the VR wrist orientation absolutely.

    Engagement captures only the translational zero point. The incoming Quest
    wrist quaternion is converted directly into the robot frame instead of
    applying a rotation delta relative to the engagement pose. The established
    rotation-reference rate limiter remains active so absolute orientation does
    not create unbounded per-frame wrist commands.
    """

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


def main() -> None:
    config = load_teleop_config(TELEOP_CONFIG_PATH)
    fallback_settings = load_ik_fallback_settings(TELEOP_CONFIG_PATH)
    severe_fallback_settings = load_severe_ik_fallback_settings(TELEOP_CONFIG_PATH)
    apply_to_base_module(base, config)
    install_runtime_collision_policy(base, config)
    inspection_machine = install_inspection_contact_monitor(base, config)
    fallback_supervisor = install_coupled_ik_fallback(base, fallback_settings)
    install_severe_ik_fallback_trigger(base, severe_fallback_settings)
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
        strategy = "decoupled primary + coupled 7-DoF fallback"
        if fallback_supervisor.settings.multiseed.enabled:
            strategy += " + multi-seed search"
        strategy += " + immediate severe-error trigger + primary-task descent guard"
        print(f"IK strategy: {strategy}")
    else:
        print("IK strategy: decoupled only (fallback disabled)")
    runtime.main()


if __name__ == "__main__":
    main()
