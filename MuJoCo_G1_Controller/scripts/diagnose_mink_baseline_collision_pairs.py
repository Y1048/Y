"""Diagnose nominal/baseline collision pairs used by the G1 Mink controller.

No Unity, Quest, UDP, DDS, or robot hardware is required. This script does not
change the controller. It evaluates the exact collision-pair builder used by the
live Mink controller at several representative right-arm starting postures and
reports pairs that are already inside the detection/minimum distance at baseline.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import mujoco
import numpy as np
import mink

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parents[1]
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_mink_baseline_collision_pairs.json"

sys.path.insert(0, str(THIS_DIR))
import run_mink_g1_right_arm_prototype as base  # noqa: E402
import test_mink_virtual_wrist_center_sweep as sweep  # noqa: E402


def _name(model, obj, index: int, fallback: str) -> str:
    value = mujoco.mj_id2name(model, obj, int(index))
    return value or fallback


def _pair_distance(model, data, pair: tuple[int, int], distmax: float = 0.20) -> float:
    fromto = np.zeros(6, dtype=float)
    return float(
        mujoco.mj_geomDistance(
            model,
            data,
            int(pair[0]),
            int(pair[1]),
            distmax,
            fromto,
        )
    )


def _state_for_posture(start_deg: list[float]):
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)

    data = mujoco.MjData(model)
    data.qpos[:] = base._initial_configuration(model)
    for joint_name, angle_deg in zip(base.g1.RIGHT_ARM_JOINTS, start_deg):
        base.g1.set_joint(model, data, joint_name, math.radians(angle_deg))
    base.g1.clamp_joint_angles(model, data, base.g1.RIGHT_ARM_JOINTS)
    mujoco.mj_forward(model, data)

    _, geom_pairs = base._build_collision_pairs(model)
    return model, data, geom_pairs


def main() -> None:
    occurrence: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "postures_inside_min": [],
            "postures_inside_detection": [],
            "distances_m": {},
            "body_names": None,
            "body_graph_distance": None,
        }
    )

    total_pairs = None
    posture_rows = []

    print("G1 Mink baseline collision-pair diagnostic")
    print("------------------------------------------")
    print("No controller changes. No VR/hardware required.\n")

    for posture_name, posture_deg in sweep.START_POSTURES.items():
        model, data, geom_pairs = _state_for_posture(posture_deg)
        if total_pairs is None:
            total_pairs = len(geom_pairs)

        inside_min = []
        inside_detection = []
        for geom1, geom2 in geom_pairs:
            d = _pair_distance(model, data, (geom1, geom2))
            if d >= 0.20:
                continue

            geom1_name = _name(model, mujoco.mjtObj.mjOBJ_GEOM, geom1, f"geom#{geom1}")
            geom2_name = _name(model, mujoco.mjtObj.mjOBJ_GEOM, geom2, f"geom#{geom2}")
            key = tuple(sorted((geom1_name, geom2_name)))

            body1 = int(model.geom_bodyid[int(geom1)])
            body2 = int(model.geom_bodyid[int(geom2)])
            body1_name = _name(model, mujoco.mjtObj.mjOBJ_BODY, body1, f"body#{body1}")
            body2_name = _name(model, mujoco.mjtObj.mjOBJ_BODY, body2, f"body#{body2}")

            row = occurrence[key]
            row["distances_m"][posture_name] = d
            row["body_names"] = [body1_name, body2_name]
            row["body_graph_distance"] = base._body_distance(model, body1, body2)

            if d <= base.COLLISION_DETECTION_DISTANCE_M:
                row["postures_inside_detection"].append(posture_name)
                inside_detection.append((d, key, body1_name, body2_name))
            if d <= base.COLLISION_MIN_DISTANCE_M:
                row["postures_inside_min"].append(posture_name)
                inside_min.append((d, key, body1_name, body2_name))

        inside_min.sort(key=lambda item: item[0])
        inside_detection.sort(key=lambda item: item[0])
        posture_rows.append(
            {
                "posture": posture_name,
                "inside_min_count": len(inside_min),
                "inside_detection_count": len(inside_detection),
            }
        )

        print(
            f"[{posture_name:12s}] <=12mm: {len(inside_min):3d}   "
            f"<=40mm: {len(inside_detection):3d}"
        )
        for d, key, body1_name, body2_name in inside_min[:8]:
            print(
                f"  {d*1000:7.3f} mm  {key[0]} <-> {key[1]}  "
                f"({body1_name} <-> {body2_name})"
            )

    repeated = []
    for pair, row in occurrence.items():
        count = len(row["postures_inside_min"])
        if count:
            repeated.append((count, pair, row))
    repeated.sort(key=lambda item: (-item[0], min(item[2]["distances_m"].values())))

    print("\n[REPEATED BASELINE <=12mm PAIRS]")
    if not repeated:
        print("  none")
    else:
        for count, pair, row in repeated[:30]:
            minimum = min(row["distances_m"].values())
            print(
                f"  {count}/{len(sweep.START_POSTURES)} postures  "
                f"min={minimum*1000:7.3f} mm  {pair[0]} <-> {pair[1]}  "
                f"bodies={row['body_names']} graph={row['body_graph_distance']}"
            )

    payload = {
        "suite": "g1_mink_baseline_collision_pairs",
        "collision_min_distance_m": base.COLLISION_MIN_DISTANCE_M,
        "collision_detection_distance_m": base.COLLISION_DETECTION_DISTANCE_M,
        "total_collision_pairs": total_pairs,
        "postures": posture_rows,
        "pairs": [
            {
                "geom_names": list(pair),
                "body_names": row["body_names"],
                "body_graph_distance": row["body_graph_distance"],
                "postures_inside_min": row["postures_inside_min"],
                "postures_inside_detection": row["postures_inside_detection"],
                "distances_m": row["distances_m"],
            }
            for _, pair, row in repeated
        ],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n[INFO] Detailed JSON: {RESULT_PATH}")
    print("[PASS] Baseline collision diagnostic completed; no controller files were modified.")


if __name__ == "__main__":
    main()
