"""Load config/teleop.json, apply it, then start the projected teleoperation runtime."""

from __future__ import annotations

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


def install_lagged_position_reference(base_module) -> None:
    """Restore deliberate lag without allowing large command-delay buildup.

    Small errors move slowly for smoothness, while larger errors progressively
    increase the Cartesian catch-up speed. Workspace projection, collision
    handling, and the IK joint-step limiter remain authoritative safety layers.
    """

    min_speed_mps = 0.10
    max_speed_mps = 0.35
    full_catchup_error_m = 0.08

    def lagged_position_reference(current_position, desired_position, delta_time):
        current = np.asarray(current_position, dtype=float)
        desired = np.asarray(desired_position, dtype=float)
        safe_dt = max(float(delta_time), 1e-4)
        error = desired - current
        error_distance = float(np.linalg.norm(error))

        if error_distance < 1e-9:
            return desired.copy()

        speed_ratio = min(1.0, error_distance / full_catchup_error_m)
        smooth_ratio = speed_ratio * speed_ratio * (3.0 - 2.0 * speed_ratio)
        speed_mps = min_speed_mps + (max_speed_mps - min_speed_mps) * smooth_ratio
        max_step = speed_mps * safe_dt

        if error_distance <= max_step:
            return desired.copy()

        return current + error * (max_step / error_distance)

    base_module.update_safe_position_reference = lagged_position_reference


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
    install_lagged_position_reference(base)

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
        "Position reference: smooth lagged follow "
        "(0.10-0.35 m/s adaptive catch-up; workspace/collision/IK safety retained)"
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
