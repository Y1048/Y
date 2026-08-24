"""Start configured G1 teleoperation with geometry-aware redundancy resolution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.geometry_redundancy import install_geometry_aware_redundancy_resolver  # noqa: E402
import run_configured_g1_teleop as configured  # noqa: E402


def install_geometry_instead_of_manual_posture(base_module, *, profile_path):
    install_geometry_aware_redundancy_resolver(base_module, profile_path=profile_path)


def main() -> None:
    # Preserve the proven configured runtime stack, but replace the manually
    # captured posture scheduler with automatic geometry-aware redundancy.
    configured.install_joint_space_posture_scheduler = install_geometry_instead_of_manual_posture
    print("Redundancy mode: automatic G1 geometry / collision-clearance gradient")
    print("Manual torso_front_deg: baseline only, not a live joint target")
    configured.main()


if __name__ == "__main__":
    main()
