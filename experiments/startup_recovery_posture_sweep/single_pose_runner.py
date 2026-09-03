#!/usr/bin/env python3
"""Run the existing Startup Recovery once with an isolated synthetic pose."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DIR = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--escape", type=float, nargs=3, default=(0.0, -0.18, 0.08))
    return parser.parse_args()


def Main() -> int:
    args = ParseArguments()
    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.path.insert(0, str(BRIDGE_DIR))

    import run_mink_g1_right_arm_prototype as controller

    if os.environ.get("G1_SWEEP_MODEL_PREPARED") == "1":
        if not controller.g1.DEMO_XML.exists():
            raise RuntimeError("Prepared MuJoCo model is missing")
        controller._prepare_mink_xml = lambda: None

    import simulate_startup_recovery as recovery

    recovery.STATE_PATH = args.state.resolve()
    recovery.RESULT_PATH = args.result.resolve()
    recovery.ESCAPE_OFFSET_ROBOT_M = np.asarray(args.escape, dtype=float)
    return int(recovery.main())


if __name__ == "__main__":
    raise SystemExit(Main())
