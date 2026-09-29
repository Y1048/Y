"""Shared G1 Mink model, collision, and math helpers for bilateral IK.

No transport, CLI, motor output, or standalone controller lives in this module.
The few right-arm-specific helpers are retained only for the historical
single-arm parity regression used by the bilateral test suite.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np
import mink
import qpsolvers

import g1_arm_common as g1


CONTROL_HZ = 60.0
DT = 1.0 / CONTROL_HZ


POSITION_COST = 8.0


ORIENTATION_COST = 2.0


POSTURE_COST = 0.04


FRAME_GAIN = 0.35


LM_DAMPING = 1e-5


QP_DAMPING = 1e-8


ZERO_DISTANCE_TOLERANCE_M = 1e-12


ZERO_DISTANCE_PROBE_RAD = 1e-7


STRUCTURAL_NEIGHBOR_DISTANCE = 2


COLLISION_BODY_PAIR_EXEMPTIONS = {
    frozenset(("right_elbow_link", "right_wrist_yaw_link")),
}


RIGHT_ARM_MAX_JERK_RAD_S3 = 1.28


PROXIMAL_DAMPING_COST = 0.25


WRIST_DAMPING_COST = 0.015


RIGHT_HAND_COLLISION_NAME = "mink_right_rubber_hand_collision"


def _find_body(element: ET.Element, name: str) -> ET.Element | None:
    if element.tag == "body" and element.get("name") == name:
        return element
    for child in element:
        found = _find_body(child, name)
        if found is not None:
            return found
    return None


def _prepare_mink_xml(show_inspection_scene: bool = False, *, output_path: Path | None = None) -> Path:
    """Generate the fixed-base demo and name its collision-enabled robot geoms."""
    destination = g1.make_demo_xml(
        "control",
        show_inspection_scene=show_inspection_scene,
        output_path=output_path,
    )
    tree = ET.parse(destination)
    root = tree.getroot()
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise RuntimeError("worldbody missing from generated G1 model")

    robot_body = worldbody.find("body")
    if robot_body is None:
        raise RuntimeError("G1 root body missing from generated model")

    right_wrist = _find_body(robot_body, "right_wrist_yaw_link")
    if right_wrist is None:
        raise RuntimeError("right_wrist_yaw_link missing from generated model")

    if right_wrist.find(f"geom[@name='{RIGHT_HAND_COLLISION_NAME}']") is None:
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": RIGHT_HAND_COLLISION_NAME,
                "type": "mesh",
                "mesh": "right_rubber_hand",
                "pos": "0.0415 -0.003 0",
                "density": "0",
                "contype": "1",
                "conaffinity": "1",
                "group": "3",
                "rgba": "0 0 0 0",
            },
        )

    name_counter = 0
    for body in robot_body.iter("body"):
        body_name = body.get("name") or "body"
        local_index = 0
        for geom in body.findall("geom"):
            contype = geom.get("contype", "1")
            conaffinity = geom.get("conaffinity", "1")
            if contype == "0" or conaffinity == "0":
                continue
            if not geom.get("name"):
                geom.set("name", f"mink_collision_{body_name}_{local_index}_{name_counter}")
            local_index += 1
            name_counter += 1

    tree.write(destination, encoding="unicode")
    return destination


def _joint_id(model: mujoco.MjModel, joint_name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if value < 0:
        raise RuntimeError(f"joint not found: {joint_name}")
    return int(value)


def _apply_operational_joint_limits(model: mujoco.MjModel) -> None:
    for joint_name, limits_deg in g1.RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES.items():
        joint_id = _joint_id(model, joint_name)
        low_deg, high_deg = limits_deg
        model.jnt_range[joint_id, 0] = math.radians(low_deg)
        model.jnt_range[joint_id, 1] = math.radians(high_deg)
        model.jnt_limited[joint_id] = 1


def _body_distance(model: mujoco.MjModel, first: int, second: int) -> int | None:
    def ancestors(body_id: int) -> dict[int, int]:
        result: dict[int, int] = {}
        current = int(body_id)
        distance = 0
        while current not in result and current >= 0:
            result[current] = distance
            if current == 0:
                break
            parent = int(model.body_parentid[current])
            if parent == current or parent < 0:
                break
            current = parent
            distance += 1
        return result

    first_a = ancestors(first)
    second_a = ancestors(second)
    common = set(first_a).intersection(second_a)
    if not common:
        return None
    return min(first_a[item] + second_a[item] for item in common)


def _collision_geom_records(model: mujoco.MjModel) -> list[tuple[int, str]]:
    records: list[tuple[int, str]] = []
    for geom_id in range(int(model.ngeom)):
        if int(model.geom_contype[geom_id]) == 0 or int(model.geom_conaffinity[geom_id]) == 0:
            continue
        geom_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
        if not geom_name:
            continue
        body_id = int(model.geom_bodyid[geom_id])
        if body_id == 0:
            continue
        records.append((body_id, str(geom_name)))
    return records


def _build_collision_pairs(
    model: mujoco.MjModel,
    controlled_body_names: set[str] | None = None,
) -> tuple[list[tuple[list[str], list[str]]], list[tuple[int, int]]]:
    if controlled_body_names is None:
        controlled_body_names = g1.RIGHT_ARM_BODY_NAMES
    controlled_body_ids = {
        g1.get_body_id(model, body_name)
        for body_name in controlled_body_names
        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name) >= 0
    }
    records = _collision_geom_records(model)
    pairs: list[tuple[list[str], list[str]]] = []
    geom_id_pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for index, (body1, geom1_name) in enumerate(records):
        for body2, geom2_name in records[index + 1 :]:
            if not (body1 in controlled_body_ids or body2 in controlled_body_ids):
                continue
            distance = _body_distance(model, body1, body2)
            if distance is not None and distance <= STRUCTURAL_NEIGHBOR_DISTANCE:
                continue
            body1_name = mujoco.mj_id2name(
                model, mujoco.mjtObj.mjOBJ_BODY, body1
            )
            body2_name = mujoco.mj_id2name(
                model, mujoco.mjtObj.mjOBJ_BODY, body2
            )
            if frozenset((body1_name, body2_name)) in COLLISION_BODY_PAIR_EXEMPTIONS:
                continue
            geom1_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom1_name)
            geom2_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom2_name)
            key = tuple(sorted((int(geom1_id), int(geom2_id))))
            if key in seen:
                continue
            seen.add(key)
            pairs.append(([geom1_name], [geom2_name]))
            geom_id_pairs.append(key)
    return pairs, geom_id_pairs


def _right_arm_dof_indices(model: mujoco.MjModel) -> list[int]:
    return [int(model.jnt_dofadr[_joint_id(model, name)]) for name in g1.RIGHT_ARM_JOINTS]


def _frozen_dof_indices(model: mujoco.MjModel, right_dofs: list[int]) -> list[int]:
    right_set = set(right_dofs)
    return [index for index in range(int(model.nv)) if index not in right_set]


def _damping_costs(model: mujoco.MjModel) -> np.ndarray:
    costs = np.zeros(int(model.nv), dtype=float)
    for index, name in enumerate(g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[_joint_id(model, name)])
        costs[dof] = PROXIMAL_DAMPING_COST if index < 4 else WRIST_DAMPING_COST
    return costs


def _initial_configuration(model: mujoco.MjModel) -> np.ndarray:
    data = mujoco.MjData(model)
    data.qpos[:] = model.qpos0.copy()
    for name, value in zip(g1.RIGHT_ARM_JOINTS, np.radians(g1.RIGHT_ARM_READY_DEGREES)):
        g1.set_joint(model, data, name, float(value))
    for name, value in zip(g1.LEFT_ARM_JOINTS, np.radians(g1.LEFT_ARM_READY_DEGREES)):
        g1.set_joint(model, data, name, float(value))
    g1.clamp_joint_angles(model, data, g1.RIGHT_ARM_JOINTS)
    mujoco.mj_forward(model, data)
    return data.qpos.copy()


def _select_solver() -> str:
    available = set(getattr(qpsolvers, "available_solvers", []))
    for candidate in ("daqp", "proxqp", "quadprog", "osqp"):
        if candidate in available:
            return candidate
    raise RuntimeError("No supported QP backend found in bundled runtime; restore runtime/python.")


def _matrix_to_se3(rotation: np.ndarray, position: np.ndarray):
    matrix = np.eye(4)
    matrix[:3, :3] = np.asarray(rotation, dtype=float)
    matrix[:3, 3] = np.asarray(position, dtype=float)
    return mink.SE3.from_matrix(matrix)


def _rotation_error_radians(target: np.ndarray, current: np.ndarray) -> float:
    delta = np.asarray(target, dtype=float) @ np.asarray(current, dtype=float).T
    cosine = float(np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0))
    return math.acos(cosine)


def _nearest_pair_distance(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    geom_pairs: list[tuple[int, int]],
    distmax: float = 0.20,
) -> tuple[float, int, int] | None:
    nearest: tuple[float, int, int] | None = None
    fromto = np.zeros(6, dtype=float)
    for geom1, geom2 in geom_pairs:
        distance = _robust_geom_distance(
            model,
            data,
            geom1,
            geom2,
            distmax,
            fromto,
        )
        if distance >= distmax:
            continue
        if nearest is None or distance < nearest[0]:
            nearest = (distance, int(geom1), int(geom2))
    return nearest


def _has_exact_geom_contact(
    data: mujoco.MjData,
    first_geom: int,
    second_geom: int,
) -> bool:
    expected = {int(first_geom), int(second_geom)}
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        if {int(contact.geom1), int(contact.geom2)} == expected:
            return True
    return False


def _probe_zero_mesh_distance(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    first_geom: int,
    second_geom: int,
    distmax: float,
) -> float:
    """Resolve an isolated mesh-distance zero without hiding real contact."""
    original_qpos = data.qpos.copy()
    probe_distances: list[float] = []
    fromto = np.zeros(6, dtype=float)
    try:
        arm_joint_names = tuple(
            dict.fromkeys(tuple(g1.RIGHT_ARM_JOINTS) + tuple(g1.LEFT_ARM_JOINTS))
        )
        for joint_name in arm_joint_names:
            joint_id = _joint_id(model, joint_name)
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
                        distmax,
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
    model: mujoco.MjModel,
    data: mujoco.MjData,
    first_geom: int,
    second_geom: int,
    distmax: float,
    fromto: np.ndarray,
) -> float:
    distance = float(
        mujoco.mj_geomDistance(
            model,
            data,
            int(first_geom),
            int(second_geom),
            distmax,
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
        first_geom,
        second_geom,
        distmax,
    )
