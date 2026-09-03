#!/usr/bin/env python3
"""Compare G1 startup postures against the active Mink collision geometry."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_initial_pose_collision.json"
DETECTION_DISTANCE_M = 0.04
ZERO_DISTANCE_TOLERANCE_M = 1e-12
ZERO_DISTANCE_PROBE_RAD = 1e-7


def _joint_pose(model, data, controller, values_rad: np.ndarray) -> None:
    data.qpos[:] = model.qpos0.copy()
    for name, value in zip(controller.g1.RIGHT_ARM_JOINTS, values_rad):
        controller.g1.set_joint(model, data, name, float(value))
    for name, value in zip(
        controller.g1.LEFT_ARM_JOINTS,
        np.radians(controller.g1.LEFT_ARM_READY_DEGREES),
    ):
        controller.g1.set_joint(model, data, name, float(value))
    mujoco.mj_forward(model, data)


def _has_exact_geom_contact(data, first_geom: int, second_geom: int) -> bool:
    expected = {int(first_geom), int(second_geom)}
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        if {int(contact.geom1), int(contact.geom2)} == expected:
            return True
    return False


def _probe_zero_mesh_distance(
    model,
    data,
    controller,
    first_geom: int,
    second_geom: int,
    max_distance_m: float,
) -> float:
    """Resolve an isolated MuJoCo mesh-distance zero without hiding contact.

    MuJoCo can return exactly zero for a mesh pair at a single floating-point
    posture even though adjacent postures are centimetres apart and no contact
    exists. Every left- and right-arm joint is probed in both directions by
    1e-7 rad. The startup precheck evaluates both arms, so probing only the
    right arm cannot resolve an isolated zero involving a left-arm mesh. The
    minimum nonzero result is retained, so a real contact or near-contact
    remains below the safety margin. If no probe resolves the result, zero is
    returned conservatively.
    """

    original_qpos = data.qpos.copy()
    probe_distances: list[float] = []
    fromto = np.zeros(6, dtype=float)
    try:
        arm_joint_names = tuple(
            dict.fromkeys(
                tuple(controller.g1.RIGHT_ARM_JOINTS)
                + tuple(controller.g1.LEFT_ARM_JOINTS)
            )
        )
        for joint_name in arm_joint_names:
            joint_id = controller._joint_id(model, joint_name)
            qpos_id = int(model.jnt_qposadr[joint_id])
            original_value = float(original_qpos[qpos_id])
            for direction in (-1.0, 1.0):
                data.qpos[:] = original_qpos
                data.qpos[qpos_id] = (
                    original_value + direction * ZERO_DISTANCE_PROBE_RAD
                )
                mujoco.mj_forward(model, data)
                distance = float(
                    mujoco.mj_geomDistance(
                        model,
                        data,
                        int(first_geom),
                        int(second_geom),
                        max_distance_m,
                        fromto,
                    )
                )
                if (
                    math.isfinite(distance)
                    and abs(distance) > ZERO_DISTANCE_TOLERANCE_M
                ):
                    probe_distances.append(distance)
    finally:
        data.qpos[:] = original_qpos
        mujoco.mj_forward(model, data)

    if not probe_distances:
        return 0.0
    return min(probe_distances)


def _robust_geom_distance(
    model,
    data,
    controller,
    first_geom: int,
    second_geom: int,
    max_distance_m: float,
    fromto: np.ndarray,
) -> float:
    distance = float(
        mujoco.mj_geomDistance(
            model,
            data,
            int(first_geom),
            int(second_geom),
            max_distance_m,
            fromto,
        )
    )
    if abs(distance) > ZERO_DISTANCE_TOLERANCE_M:
        return distance
    if _has_exact_geom_contact(data, first_geom, second_geom):
        return distance
    return _probe_zero_mesh_distance(
        model,
        data,
        controller,
        first_geom,
        second_geom,
        max_distance_m,
    )


def _nearby_pairs(model, data, controller, geom_pairs) -> list[dict[str, object]]:
    nearby = []
    fromto = np.zeros(6, dtype=float)
    for first, second in geom_pairs:
        distance = _robust_geom_distance(
            model,
            data,
            controller,
            int(first),
            int(second),
            DETECTION_DISTANCE_M,
            fromto,
        )
        if distance >= DETECTION_DISTANCE_M:
            continue
        first_body = int(model.geom_bodyid[first])
        second_body = int(model.geom_bodyid[second])
        nearby.append(
            {
                "distance_m": distance,
                "first_geom": mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_GEOM, int(first)
                ),
                "second_geom": mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_GEOM, int(second)
                ),
                "first_body": mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_BODY, first_body
                ),
                "second_body": mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_BODY, second_body
                ),
            }
        )
    return sorted(nearby, key=lambda item: float(item["distance_m"]))


def main() -> int:
    os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    import run_mink_g1_right_arm_prototype as controller

    captured = np.asarray(
        json.loads(STATE_PATH.read_text(encoding="utf-8"))["right_arm_q_rad"],
        dtype=float,
    )
    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    data = mujoco.MjData(model)
    _, geom_pairs = controller._build_collision_pairs(model)

    postures = {
        "captured_hardware": captured,
        "configured_ready": np.radians(
            controller.g1.DEFAULT_RIGHT_ARM_READY_DEGREES
        ),
        "all_zero": np.zeros(7, dtype=float),
    }
    result = {
        "command_output_enabled": False,
        "detection_distance_m": DETECTION_DISTANCE_M,
        "collision_pair_count": len(geom_pairs),
        "postures": {},
    }
    for name, pose in postures.items():
        _joint_pose(model, data, controller, pose)
        nearby = _nearby_pairs(model, data, controller, geom_pairs)
        result["postures"][name] = {
            "q_rad": pose.tolist(),
            "nearby_pair_count": len(nearby),
            "inside_minimum_count": sum(
                float(item["distance_m"]) < controller.COLLISION_MIN_DISTANCE_M
                for item in nearby
            ),
            "pairs": nearby,
        }

    path_samples = []
    initial_inside_pairs = {
        tuple(sorted((item["first_body"], item["second_body"])))
        for item in result["postures"]["captured_hardware"]["pairs"]
        if float(item["distance_m"]) < controller.COLLISION_MIN_DISTANCE_M
    }
    new_inside_pairs = set()
    ready = postures["configured_ready"]
    for fraction in np.linspace(0.0, 1.0, 101):
        pose = captured + float(fraction) * (ready - captured)
        _joint_pose(model, data, controller, pose)
        nearby = _nearby_pairs(model, data, controller, geom_pairs)
        inside = [
            item
            for item in nearby
            if float(item["distance_m"]) < controller.COLLISION_MIN_DISTANCE_M
        ]
        for item in inside:
            pair = tuple(sorted((item["first_body"], item["second_body"])))
            if pair not in initial_inside_pairs:
                new_inside_pairs.add(pair)
        path_samples.append(
            {
                "fraction": float(fraction),
                "inside_minimum_count": len(inside),
                "nearest_distance_m": (
                    None if not nearby else float(nearby[0]["distance_m"])
                ),
            }
        )

    clear_fraction = None
    for index, sample in enumerate(path_samples):
        if all(
            later["inside_minimum_count"] == 0
            for later in path_samples[index:]
        ):
            clear_fraction = sample["fraction"]
            break
    result["captured_to_configured_ready"] = {
        "sample_count": len(path_samples),
        "first_permanently_clear_fraction": clear_fraction,
        "maximum_inside_minimum_count": max(
            sample["inside_minimum_count"] for sample in path_samples
        ),
        "new_inside_body_pairs": [list(pair) for pair in sorted(new_inside_pairs)],
        "samples": path_samples,
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(RESULT_PATH)

    print("G1 startup collision comparison -- READ ONLY")
    for name, posture in result["postures"].items():
        nearest = posture["pairs"][0] if posture["pairs"] else None
        if nearest is None:
            summary = "clear beyond detection distance"
        else:
            summary = (
                f"{nearest['distance_m'] * 1000.0:.2f} mm, "
                f"{nearest['first_body']} <-> {nearest['second_body']}"
            )
        print(
            f"{name}: inside_min={posture['inside_minimum_count']} "
            f"nearby={posture['nearby_pair_count']} nearest={summary}"
        )
    path = result["captured_to_configured_ready"]
    print(
        "captured -> configured_ready: "
        f"clear_from={path['first_permanently_clear_fraction']} "
        f"new_inside_pairs={len(path['new_inside_body_pairs'])}"
    )
    print("Robot command: NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
