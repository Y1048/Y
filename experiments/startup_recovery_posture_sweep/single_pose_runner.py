#!/usr/bin/env python3
"""Run the existing Startup Recovery once with an isolated synthetic pose."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import sys
import tempfile
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


@contextmanager
def UseIsolatedModel(controller):
    """Keep legacy recovery model hooks local to this offline process."""
    original_path = controller.g1.DEMO_XML
    original_prepare = controller._prepare_mink_xml
    with tempfile.TemporaryDirectory(prefix="g1_sweep_model_") as directory:
        model_path = Path(directory) / "scene.xml"
        original_prepare(output_path=model_path)
        try:
            controller.g1.DEMO_XML = model_path
            controller._prepare_mink_xml = lambda: model_path
            yield model_path
        finally:
            controller.g1.DEMO_XML = original_path
            controller._prepare_mink_xml = original_prepare


def Main() -> int:
    args = ParseArguments()
    sys.path.insert(0, str(SCRIPTS_DIR))
    sys.path.insert(0, str(BRIDGE_DIR))

    import run_mink_g1_right_arm_prototype as controller

    import simulate_startup_recovery as recovery

    recovery.STATE_PATH = args.state.resolve()
    recovery.RESULT_PATH = args.result.resolve()
    recovery.ESCAPE_OFFSET_ROBOT_M = np.asarray(args.escape, dtype=float)
    with UseIsolatedModel(controller):
        return int(recovery.main())


if __name__ == "__main__":
    raise SystemExit(Main())
