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

import g1_right_arm_udp_ik_demo as base  # noqa: E402


TELEOP_CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"


def main() -> None:
    config = load_teleop_config(TELEOP_CONFIG_PATH)
    apply_to_base_module(base, config)

    # Import only after base tuning values are applied so runtime defaults that
    # reference base constants observe the validated configuration.
    import g1_right_arm_udp_ik_runtime as runtime

    apply_to_projected_runtime(runtime, config, PROJECT_ROOT)
    print(f"Teleop config: {TELEOP_CONFIG_PATH}")
    runtime.main()


if __name__ == "__main__":
    main()
