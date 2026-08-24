"""Production-aligned wrapper for the intermediate-only swept-path stress test.

The original targeted diagnostic generated endpoints from raw MuJoCo joint
ranges and its reference pose setter did not apply the controller's operational
joint limits. Production swept-path validation *does* call
``base.clamp_joint_angles`` at every intermediate configuration. That mismatch
can create false diagnostic failures for paths the live controller can never
execute (notably right elbow angles below the 5 deg operational minimum).

This wrapper reuses the existing search/test implementation but replaces its
joint-range and pose-set helpers so the dense reference and production guard
traverse the same clamped C-space path.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import g1_right_arm_udp_ik_demo as base  # noqa: E402
import stress_test_intermediate_only_swept_path as diagnostic  # noqa: E402


def production_joint_ranges(model: Any) -> tuple[np.ndarray, np.ndarray]:
    """Return MuJoCo ranges intersected with live operational limits."""
    lows: list[float] = []
    highs: list[float] = []
    operational = getattr(base, "RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES", {})

    for name in base.RIGHT_ARM_JOINTS:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError(f"missing joint in MuJoCo model: {name}")

        if bool(model.jnt_limited[joint_id]):
            low, high = [float(v) for v in model.jnt_range[joint_id]]
        else:
            low, high = -math.pi, math.pi

        if name in operational:
            op_low_deg, op_high_deg = operational[name]
            low = max(low, math.radians(float(op_low_deg)))
            high = min(high, math.radians(float(op_high_deg)))

        if low > high:
            raise RuntimeError(f"empty operational range for {name}")
        lows.append(low)
        highs.append(high)

    return np.asarray(lows, dtype=float), np.asarray(highs, dtype=float)


def production_set_pose(
    model: Any,
    data: Any,
    initial_qpos: np.ndarray,
    qpos_ids: np.ndarray,
    q: np.ndarray,
) -> None:
    """Set a reference pose exactly as the production guard constrains it."""
    data.qpos[:] = initial_qpos
    data.qpos[qpos_ids] = np.asarray(q, dtype=float)
    base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
    base.freeze_non_arm_joints(model, data, initial_qpos)
    base.set_left_arm_ready(model, data)
    mujoco.mj_forward(model, data)


def main() -> int:
    diagnostic._joint_ranges = production_joint_ranges
    diagnostic._set_pose = production_set_pose
    print("Reference alignment: production joint ranges + operational clamping")
    return diagnostic.main()


if __name__ == "__main__":
    raise SystemExit(main())
