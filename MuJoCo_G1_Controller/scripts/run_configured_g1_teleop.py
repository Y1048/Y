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


def install_direct_position_reference(base_module) -> None:
    """Use responsive adaptive smoothing instead of a fixed Cartesian speed limit.

    Small hand jitter is low-pass filtered, while deliberate motion rapidly approaches
    direct feasible-target tracking. Workspace projection, collision handling, and the
    IK joint-step limiter remain authoritative safety layers.
    """

    small_motion_tau_s = 0.040
    large_motion_tau_s = 0.008
    direct_follow_distance_m = 0.050

    def direct_position_reference(current_position, desired_position, delta_time):
        current = np.asarray(current_position, dtype=float)
        desired = np.asarray(desired_position, dtype=float)
        safe_dt = max(float(delta_time), 1e-4)
        error_distance = float(np.linalg.norm(desired - current))

        motion_ratio = min(
            1.0,
            error_distance / direct_follow_distance_m,
        )
        smooth_ratio = motion_ratio * motion_ratio * (3.0 - 2.0 * motion_ratio)
        tau_s = (
            small_motion_tau_s
            + (large_motion_tau_s - small_motion_tau_s) * smooth_ratio
        )
        alpha = 1.0 - math.exp(-safe_dt / max(tau_s, 1e-4))
        return current + alpha * (desired - current)

    base_module.update_safe_position_reference = direct_position_reference


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
    install_direct_position_reference(base)

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
        "Position reference: adaptive low-latency smoothing "
        "(8-40 ms response; workspace/collision/IK joint-step safety retained)"
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
