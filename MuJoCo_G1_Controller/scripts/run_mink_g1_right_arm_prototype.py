"""Mink-based right-arm-only G1 teleoperation controller.

Unity keeps sending the existing UDP target format on port 5005; this script
solves one 7-DoF right-arm QP using Mink. Shared G1 model/joint/frame utilities
live in g1_right_arm_common and no legacy IK implementation is imported here.

QP structure:
- full 6D right wrist FrameTask,
- posture regularization,
- proximal-vs-wrist damping to prefer local wrist motion during rotation,
- hard MuJoCo joint-position limits,
- right-arm velocity limits,
- MuJoCo geometry CollisionAvoidanceLimit,
- exact zero-velocity equality constraints on every non-right-arm DOF.
"""

from __future__ import annotations

import json
import math
import socket
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

try:
    import mink
except ImportError as exc:  # pragma: no cover - operator setup path
    raise SystemExit(
        "Mink is not installed for this Python. Run: py -3.11 -m pip install mink daqp"
    ) from exc

try:
    import qpsolvers
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "qpsolvers is missing. Run: py -3.11 -m pip install mink daqp"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
RUNTIME_STATUS_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_mink_status.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g1_right_arm_common as g1  # noqa: E402


CONTROL_HZ = 60.0
DT = 1.0 / CONTROL_HZ
UDP_HOST = "0.0.0.0"
UDP_PORT = 5005
UNITY_STATE_HOST = "127.0.0.1"
UNITY_STATE_PORT = 5006
SAFETY_DRY_RUN_HOST = "127.0.0.1"
SAFETY_DRY_RUN_PORT = 5008
INPUT_TIMEOUT_S = 0.75

POSITION_COST = 8.0
ORIENTATION_COST = 2.0
POSTURE_COST = 0.04
FRAME_GAIN = 0.35
LM_DAMPING = 1e-5
QP_DAMPING = 1e-8

COLLISION_MIN_DISTANCE_M = 0.012
COLLISION_DETECTION_DISTANCE_M = 0.040
COLLISION_GAIN = 0.85
STRUCTURAL_NEIGHBOR_DISTANCE = 2
RIGHT_ARM_MAX_VELOCITY_RAD_S = math.radians(75.0)

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


def _prepare_mink_xml() -> None:
    """Generate the fixed-base demo and name its collision-enabled robot geoms."""
    g1.make_demo_xml("control")
    tree = ET.parse(g1.DEMO_XML)
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

    tree.write(g1.DEMO_XML, encoding="unicode")


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


def _build_collision_pairs(model: mujoco.MjModel) -> tuple[list[tuple[list[str], list[str]]], list[tuple[int, int]]]:
    right_arm_body_ids = {
        g1.get_body_id(model, body_name)
        for body_name in g1.RIGHT_ARM_BODY_NAMES
        if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name) >= 0
    }
    records = _collision_geom_records(model)
    pairs: list[tuple[list[str], list[str]]] = []
    geom_id_pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for index, (body1, geom1_name) in enumerate(records):
        for body2, geom2_name in records[index + 1 :]:
            if not (body1 in right_arm_body_ids or body2 in right_arm_body_ids):
                continue
            distance = _body_distance(model, body1, body2)
            if distance is not None and distance <= STRUCTURAL_NEIGHBOR_DISTANCE:
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
    raise RuntimeError("No supported QP backend found. Install DAQP: py -3.11 -m pip install daqp")


def _matrix_to_se3(rotation: np.ndarray, position: np.ndarray):
    matrix = np.eye(4)
    matrix[:3, :3] = np.asarray(rotation, dtype=float)
    matrix[:3, 3] = np.asarray(position, dtype=float)
    return mink.SE3.from_matrix(matrix)


def _rotation_error_radians(target: np.ndarray, current: np.ndarray) -> float:
    delta = np.asarray(target, dtype=float) @ np.asarray(current, dtype=float).T
    cosine = float(np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0))
    return math.acos(cosine)


def _min_pair_distance(model: mujoco.MjModel, data: mujoco.MjData, geom_pairs: list[tuple[int, int]], distmax: float = 0.20) -> float | None:
    nearest: float | None = None
    fromto = np.zeros(6, dtype=float)
    for geom1, geom2 in geom_pairs:
        distance = float(mujoco.mj_geomDistance(model, data, geom1, geom2, distmax, fromto))
        if distance >= distmax:
            continue
        if nearest is None or distance < nearest:
            nearest = distance
    return nearest


def _open_udp_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.setblocking(False)
    return sock


def _receive_latest(sock: socket.socket, fallback_pos: np.ndarray, fallback_rot: np.ndarray, fallback_valid: bool):
    latest_pos, latest_rot, latest_valid = fallback_pos, fallback_rot, fallback_valid
    received = 0
    while True:
        try:
            payload, _ = sock.recvfrom(4096)
        except BlockingIOError:
            break
        try:
            msg = json.loads(payload.decode("utf-8"))
            right = msg.get("right")
            if not isinstance(right, dict):
                continue
            valid = right.get("valid") is True
            if valid:
                pos = np.asarray(right.get("pos"), dtype=float)
                rot = np.asarray(right.get("rot"), dtype=float)
                if pos.shape != (3,) or rot.shape != (4,):
                    continue
                if not np.all(np.isfinite(pos)) or not np.all(np.isfinite(rot)):
                    continue
                latest_pos = pos
                latest_rot = g1.normalize_quaternion_xyzw(rot)
            latest_valid = valid
            received += 1
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return latest_pos, latest_rot, latest_valid, received


def _state_packet(configuration, right_qpos_ids, active, target_position, reference_position, collision_limited):
    data = configuration.data
    wrist_body = g1.get_body_id(configuration.model, "right_wrist_yaw_link")
    wrist_position = data.xpos[wrist_body].copy()
    if active and reference_position is not None:
        wrist_delta = wrist_position - reference_position
        target_delta = target_position - reference_position
    else:
        wrist_delta = np.zeros(3)
        target_delta = np.zeros(3)
    return {
        "right_arm": {
            "joints": [float(configuration.q[index]) for index in right_qpos_ids],
            "active": bool(active),
            "wrist_delta": wrist_delta.tolist(),
            "target_delta": target_delta.tolist(),
            "wrist_position": wrist_position.tolist(),
            "target_position": np.asarray(target_position, dtype=float).tolist(),
            "position_error": float(np.linalg.norm(target_position - wrist_position)),
            "workspace_limited": False,
            "collision_limited": bool(collision_limited),
        },
        "timestamp": time.time(),
    }


def _send_state(sock, packet, host, port) -> None:
    sock.sendto(json.dumps(packet, separators=(",", ":")).encode("utf-8"), (host, port))


def _write_status(payload: dict) -> None:
    RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = RUNTIME_STATUS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(RUNTIME_STATUS_PATH)


def main() -> None:
    _prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(g1.DEMO_XML))
    _apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    configuration.update(_initial_configuration(model))
    data = configuration.data

    right_dofs = _right_arm_dof_indices(model)
    right_qpos_ids = [int(model.jnt_qposadr[_joint_id(model, name)]) for name in g1.RIGHT_ARM_JOINTS]
    frozen_dofs = _frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_ids = _build_collision_pairs(model)

    wrist_task = mink.FrameTask(
        frame_name="right_wrist_yaw_link",
        frame_type="body",
        position_cost=POSITION_COST,
        orientation_cost=ORIENTATION_COST,
        gain=FRAME_GAIN,
        lm_damping=LM_DAMPING,
    )
    wrist_task.set_target_from_configuration(configuration)
    posture_task = mink.PostureTask(model, cost=POSTURE_COST)
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(model, cost=_damping_costs(model))

    velocity_limits = {name: RIGHT_ARM_MAX_VELOCITY_RAD_S for name in g1.RIGHT_ARM_JOINTS}
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
        mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=COLLISION_MIN_DISTANCE_M,
            collision_detection_distance=COLLISION_DETECTION_DISTANCE_M,
            gain=COLLISION_GAIN,
            broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)]
    solver = _select_solver()

    target_mocap_id = int(model.body("udp_target").mocapid[0])
    udp = _open_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dry_run_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    raw_target = data.xpos[g1.get_body_id(model, "right_wrist_yaw_link")].copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    raw_valid = False
    last_packet_time = float("-inf")
    clutch_reference = None
    last_active = False
    received_total = 0
    next_status = time.monotonic()
    next_state = time.monotonic()
    cycle_times: list[float] = []
    target_rotation = configuration.get_transform_frame_to_world(
        "right_wrist_yaw_link", "body"
    ).rotation().as_matrix().copy()

    print("Mink G1 right-arm controller")
    print("----------------------------")
    print(f"UDP input: {UDP_HOST}:{UDP_PORT}")
    print(f"QP solver: {solver}")
    print(f"Frozen non-right-arm DOFs: {len(frozen_dofs)}")
    print(f"Collision geom pairs: {len(collision_pairs)}")
    print(
        f"Collision limit: min={COLLISION_MIN_DISTANCE_M*1000:.1f} mm, "
        f"detect={COLLISION_DETECTION_DISTANCE_M*1000:.1f} mm"
    )
    print(
        f"Proximal/wrist damping: {PROXIMAL_DAMPING_COST:.3f} / "
        f"{WRIST_DAMPING_COST:.3f}"
    )
    print("Orientation mapping: clutch-relative Quest rotation -> G1 wrist-yaw frame.")
    print("Hardware output: disabled in this process.")
    print(f"Safety dry-run mirror: udp://{SAFETY_DRY_RUN_HOST}:{SAFETY_DRY_RUN_PORT}")

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                cycle_start = time.perf_counter()
                now = time.monotonic()
                raw_target, raw_rotation, raw_valid, received = _receive_latest(
                    udp, raw_target, raw_rotation, raw_valid
                )
                if received:
                    received_total += received
                    last_packet_time = now

                active = bool(raw_valid and now - last_packet_time < INPUT_TIMEOUT_S)
                wrist_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                if active and not last_active:
                    input_rotation = g1.operator_rotation_to_robot_matrix(raw_rotation)
                    clutch_reference = {
                        "input_position": raw_target.copy(),
                        "input_rotation": input_rotation.copy(),
                        "robot_position": wrist_pose.translation().copy(),
                        "robot_rotation": wrist_pose.rotation().as_matrix().copy(),
                    }
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    posture_task.set_target(configuration.q.copy())
                    print("\nMink clutch engaged without position or orientation jump.")

                if active and clutch_reference is not None:
                    target_position = (
                        clutch_reference["robot_position"]
                        + raw_target
                        - clutch_reference["input_position"]
                    )
                    input_rotation = g1.operator_rotation_to_robot_matrix(raw_rotation)
                    rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
                    target_rotation = rotation_delta @ clutch_reference["robot_rotation"]

                    wrist_task.set_target(_matrix_to_se3(target_rotation, target_position))
                    velocity = mink.solve_ik(
                        configuration=configuration,
                        tasks=[wrist_task, posture_task, damping_task],
                        dt=DT,
                        solver=solver,
                        damping=QP_DAMPING,
                        limits=limits,
                        constraints=constraints,
                    )
                    configuration.integrate_inplace(velocity, DT)
                    data = configuration.data
                    data.mocap_pos[target_mocap_id] = target_position
                else:
                    target_position = wrist_pose.translation().copy()
                    target_rotation = wrist_pose.rotation().as_matrix().copy()
                    clutch_reference = None
                    wrist_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    data.mocap_pos[target_mocap_id] = target_position

                mujoco.mj_fwdPosition(model, data)
                min_clearance = _min_pair_distance(model, data, collision_geom_ids)
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance <= COLLISION_DETECTION_DISTANCE_M
                )

                if now >= next_state:
                    packet = _state_packet(
                        configuration,
                        right_qpos_ids,
                        active,
                        target_position,
                        None if clutch_reference is None else clutch_reference["robot_position"],
                        collision_limited,
                    )
                    _send_state(state_sock, packet, UNITY_STATE_HOST, UNITY_STATE_PORT)
                    _send_state(
                        dry_run_sock,
                        packet,
                        SAFETY_DRY_RUN_HOST,
                        SAFETY_DRY_RUN_PORT,
                    )
                    next_state = now + DT

                cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
                cycle_times.append(cycle_ms)
                if len(cycle_times) > 600:
                    del cycle_times[:-600]

                if now >= next_status:
                    current_pose = configuration.get_transform_frame_to_world(
                        "right_wrist_yaw_link", "body"
                    )
                    current_rotation = current_pose.rotation().as_matrix()
                    position_error = float(
                        np.linalg.norm(target_position - current_pose.translation())
                    )
                    orientation_error_deg = math.degrees(
                        _rotation_error_radians(target_rotation, current_rotation)
                    )
                    stats = np.asarray(cycle_times, dtype=float)
                    _write_status(
                        {
                            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "controller": "mink_right_arm_qp",
                            "input_active": active,
                            "received_packets": received_total,
                            "solver": solver,
                            "collision_pair_count": len(collision_pairs),
                            "collision_min_distance_m": COLLISION_MIN_DISTANCE_M,
                            "collision_detection_distance_m": COLLISION_DETECTION_DISTANCE_M,
                            "minimum_clearance_m": min_clearance,
                            "collision_limit_nearby": collision_limited,
                            "target_position": target_position.tolist(),
                            "wrist_position": current_pose.translation().tolist(),
                            "position_error_m": position_error,
                            "orientation_error_deg": orientation_error_deg,
                            "orientation_mapping": "clutch_relative",
                            "proximal_damping_cost": PROXIMAL_DAMPING_COST,
                            "wrist_damping_cost": WRIST_DAMPING_COST,
                            "right_arm_q_deg": np.degrees(
                                configuration.q[right_qpos_ids]
                            ).tolist(),
                            "cycle_last_ms": cycle_ms,
                            "cycle_mean_ms": float(np.mean(stats)),
                            "cycle_p95_ms": float(np.percentile(stats, 95)),
                            "cycle_p99_ms": float(np.percentile(stats, 99)),
                            "cycle_worst_ms": float(np.max(stats)),
                        }
                    )
                    next_status = now + 0.5

                last_active = active
                viewer.sync()
                elapsed = time.perf_counter() - cycle_start
                if elapsed < DT:
                    time.sleep(DT - elapsed)
    finally:
        udp.close()
        state_sock.close()
        dry_run_sock.close()


if __name__ == "__main__":
    main()
