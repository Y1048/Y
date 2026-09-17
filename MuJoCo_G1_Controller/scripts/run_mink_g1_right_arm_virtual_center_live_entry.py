#!/usr/bin/env python3
"""Supported virtual-center live entrypoint with explicit command provenance."""

from __future__ import annotations

# An explicit simulation launcher pin; physical/default entry stays unchanged.
import os
from pathlib import Path
import sys

_runtime = os.environ.get("G1_MINK_SIM_MUJOCO_ROOT")
if _runtime:
    if "--simulation-arm-cycle" not in sys.argv and "--live-cycle-candidate" not in sys.argv:
        raise RuntimeError("isolated MuJoCo pin requires explicit cycle mode")
    _root = Path(_runtime).resolve()
    if not (_root / "mujoco" / "__init__.py").is_file():
        raise RuntimeError("isolated simulation MuJoCo runtime missing")
    sys.path.insert(0, str(_root))
    import mujoco
    if mujoco.__version__ != "3.12.0" or Path(mujoco.__file__).resolve().parent.parent != _root:
        raise RuntimeError("simulation runtime must resolve to the pinned MuJoCo 3.12.0")
    if "--check-simulation-runtime" in sys.argv:
        print(f"SIMULATION runtime verified: MuJoCo {mujoco.__version__} at {mujoco.__file__}; no controller started")
        raise SystemExit(0)
elif "--check-simulation-runtime" in sys.argv:
    raise RuntimeError("simulation runtime pin is missing")

import g1_mink_command_provenance as provenance
import run_mink_g1_right_arm_prototype as base
import run_mink_g1_right_arm_virtual_center_live as controller


def main() -> None:
    if not getattr(base, "_live_mink_provenance_wrapper_installed", False):
        base._state_packet = provenance.wrap_state_packet_factory(base._state_packet)
        base._live_mink_provenance_wrapper_installed = True
    controller.main()


if __name__ == "__main__":
    main()
