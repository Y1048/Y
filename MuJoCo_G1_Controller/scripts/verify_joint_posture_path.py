"""Verify the captured right-arm posture path in MuJoCo configuration space."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import mujoco
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import g1_right_arm_udp_ik_demo as base  # noqa: E402

PROFILE_PATH = PROJECT_ROOT / "config" / "joint_postures.json"
SAMPLES = 121


def load_path() -> tuple[np.ndarray, np.ndarray]:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    arm = payload["right_arm"]
    ready = np.radians(np.asarray(arm["ready_deg"], dtype=float))
    torso_raw = arm.get("torso_front_deg")
    if torso_raw is None:
        raise RuntimeError("right_arm.torso_front_deg is null; capture a posture first")
    torso = np.radians(np.asarray(torso_raw, dtype=float))
    if ready.shape != (7,) or torso.shape != (7,):
        raise RuntimeError("ready_deg and torso_front_deg must each contain 7 values")
    return ready, torso


def joint_limit_violation(model, context, q: np.ndarray) -> list[str]:
    violations: list[str] = []
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    for name, qpos_id, value in zip(base.RIGHT_ARM_JOINTS, qpos_ids, q):
        joint_id = model.qpos_jntid[int(qpos_id)]
        if joint_id < 0:
            continue
        if not model.jnt_limited[joint_id]:
            continue
        low, high = model.jnt_range[joint_id]
        if value < low - 1e-9 or value > high + 1e-9:
            violations.append(
                f"{name}: {math.degrees(value):.2f} deg outside "
                f"[{math.degrees(low):.2f}, {math.degrees(high):.2f}]"
            )
    return violations


def main() -> int:
    ready, torso = load_path()
    model, data, initial_qpos, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)

    first_collision = None
    collision_samples: list[tuple[int, float, np.ndarray]] = []
    limit_samples: list[tuple[int, float, list[str]]] = []
    wrist_points: list[np.ndarray] = []

    for index, alpha in enumerate(np.linspace(0.0, 1.0, SAMPLES)):
        q = (1.0 - alpha) * ready + alpha * torso
        data.qpos[:] = initial_qpos
        data.qpos[qpos_ids] = q
        base.freeze_non_arm_joints(model, data, initial_qpos)
        base.set_left_arm_ready(model, data)
        mujoco.mj_forward(model, data)

        limits = joint_limit_violation(model, context, q)
        if limits:
            limit_samples.append((index, float(alpha), limits))

        collision = bool(base.has_right_arm_core_contact(model, data, context))
        if collision:
            item = (index, float(alpha), np.degrees(q).copy())
            collision_samples.append(item)
            if first_collision is None:
                first_collision = item

        wrist_points.append(data.xpos[int(context["position_body"])].copy())

    wrist_points_arr = np.asarray(wrist_points)
    wrist_step = np.linalg.norm(np.diff(wrist_points_arr, axis=0), axis=1)
    path_length = float(np.sum(wrist_step)) if wrist_step.size else 0.0

    print("G1 JOINT-SPACE POSTURE PATH VERIFICATION")
    print("========================================")
    print(f"samples: {SAMPLES}")
    print("ready deg:       " + np.array2string(np.degrees(ready), precision=2))
    print("torso-front deg: " + np.array2string(np.degrees(torso), precision=2))
    print(f"Cartesian wrist path length from posture interpolation: {path_length*100:.1f} cm")
    print(f"joint-limit violating samples: {len(limit_samples)}")
    print(f"self/core-collision samples: {len(collision_samples)}")

    if first_collision is not None:
        _, alpha, q_deg = first_collision
        print(f"FIRST COLLISION: alpha={alpha:.3f} q_deg={np.round(q_deg, 2).tolist()}")

    if limit_samples:
        _, alpha, details = limit_samples[0]
        print(f"FIRST JOINT-LIMIT VIOLATION: alpha={alpha:.3f}")
        for detail in details:
            print("  - " + detail)

    safe = not collision_samples and not limit_samples
    print("RESULT: " + ("PASS - straight joint-space interpolation is feasible" if safe else "FAIL - use one or more C-space waypoints"))
    return 0 if safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
