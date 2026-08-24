import argparse
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


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop import (  # noqa: E402
    G1_D435I_CAMERA_NAME,
    SessionSequenceWatchdog,
    UnitreeSimImageWriter,
    WorkspaceExitDebounce,
    WorkspaceFaultLatch,
    add_g1_d435i_camera,
    create_head_camera_source,
    load_camera_profile,
    save_bgr_bmp,
)


G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"
DEMO_XML = G1_DIR / "_generated_g1_right_arm_udp_ik.xml"
CAMERA_PROFILE_PATH = PROJECT_ROOT / "config" / "camera_profile.json"
RUNTIME_STATUS_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_controller_status.json"
UDP_HOST = "0.0.0.0"
UDP_PORT = 5005
UNITY_STATE_HOST = "127.0.0.1"
UNITY_STATE_PORT = 5006
UNITY_STATE_HZ = 60.0
RUNTIME_STATUS_HZ = 2.0
HEAD_CAMERA_FPS = 30.0
NEUTRAL_SOLVE_ITERATIONS = 600
POSITION_MAX_SPEED = 0.08
ROTATION_MAX_SPEED = math.radians(70.0)
INPUT_TIMEOUT_SECONDS = 0.75
WORKSPACE_EXIT_CONFIRM_SECONDS = 0.80
POSTURE_GAIN = 0.08
ELBOW_POLE_GAIN = 0.65
ELBOW_POLE_DAMPING = 0.08
POSITION_DAMPING = 0.045
ORIENTATION_DAMPING = 0.035
ELBOW_AVOIDANCE_WEIGHT = 0.85
IK_STEP_GAIN = 0.50
IK_MAX_STEP_RADIANS = math.radians(1.5)
COLLISION_MARGIN = 0.015
RIGHT_ELBOW_LATERAL_LIMIT = -0.30
RIGHT_WRIST_LATERAL_LIMIT = -0.30
TORSO_KEEP_OUT_X = (-0.18, 0.22)
TORSO_KEEP_OUT_Z = (0.45, 1.30)

# The neutral teleoperation posture keeps both arms beside the torso with a
# small elbow bend. Right shoulder roll is mirrored across the sagittal plane.
LEFT_ARM_READY_DEGREES = np.array([10.0, 22.0, 0.0, 55.0, 0.0, 0.0, 0.0])
RIGHT_ARM_READY_DEGREES = np.array([10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0])

# The mechanical elbow range permits reverse bending, but that branch is not
# appropriate for human-like teleoperation or the inspection demonstration.
RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES = {
    "right_elbow_joint": (5.0, 120.0),
}

# Limit operator motion relative to the pose captured at clutch engagement.
# Relative limits preserve a zero-jump engagement even when the ready wrist is
# outside the old absolute panel workspace.
CLUTCH_POSITION_DELTA_MIN = np.array([-0.20, -0.30, -0.28])
CLUTCH_POSITION_DELTA_MAX = np.array([0.20, 0.45, 0.34])

# Unity operator frame: +X right, +Y up, +Z forward.
# MuJoCo G1 frame: +X forward, +Y left, +Z up.
OPERATOR_TO_ROBOT_BASIS = np.array(
    [
        [0.0, 0.0, 1.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
)
IDENTITY_QUATERNION_XYZW = np.array([0.0, 0.0, 0.0, 1.0])

SCENES = {
    "control": {
        "panel_pos": (0.46, 0.0, 1.08),
        "panel_size": (0.025, 0.48, 0.34),
        "target_pos": (0.42, -0.16, 1.05),
    },
    "camera_validation": {
        # A reachable inspection setup that keeps the panel, tool, and target
        # visible from the official fixed G1 D435i mount.
        "panel_pos": (0.58, 0.0, 0.78),
        "panel_size": (0.025, 0.20, 0.16),
        "target_pos": (0.51, -0.10, 0.86),
    },
}

RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]

LEFT_ARM_JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
]

RIGHT_ARM_BODY_NAMES = {
    "right_shoulder_pitch_link",
    "right_shoulder_roll_link",
    "right_shoulder_yaw_link",
    "right_elbow_link",
    "right_wrist_roll_link",
    "right_wrist_pitch_link",
    "right_wrist_yaw_link",
    "inspection_tool_tip_body",
}

CORE_BODY_NAMES = {
    "pelvis",
    "waist_yaw_link",
    "waist_roll_link",
    "torso_link",
}


def find_body(element, name):
    if element.tag == "body" and element.get("name") == name:
        return element
    for child in element:
        found = find_body(child, name)
        if found is not None:
            return found
    return None


def make_demo_xml(scene_name):
    if scene_name not in SCENES:
        raise ValueError(f"unknown scene: {scene_name}")
    scene = SCENES[scene_name]

    tree = ET.parse(G1_XML)
    root = tree.getroot()

    worldbody = root.find("worldbody")
    robot_body = worldbody.find("body")

    for joint in list(robot_body.findall("freejoint")):
        robot_body.remove(joint)
    robot_body.set("pos", "0 0 0.78")
    add_g1_d435i_camera(robot_body)

    option = root.find("option")
    if option is None:
        option = ET.SubElement(root, "option")
    option.set("gravity", "0 0 0")

    ET.SubElement(worldbody, "light", {"pos": "0 -3 4", "dir": "0 1 -1", "diffuse": "0.9 0.9 0.9"})
    ET.SubElement(worldbody, "light", {"pos": "0 3 3", "dir": "0 -1 -1", "diffuse": "0.5 0.5 0.5"})
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "demo_floor",
            "type": "plane",
            "size": "4 4 0.05",
            "rgba": "0.74 0.82 0.88 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "inspection_panel",
            "type": "box",
            "pos": " ".join(str(value) for value in scene["panel_pos"]),
            "size": " ".join(str(value) for value in scene["panel_size"]),
            "rgba": "0.16 0.18 0.20 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    ET.SubElement(
        worldbody,
        "body",
        {
            "name": "udp_target",
            "mocap": "true",
            "pos": " ".join(str(value) for value in scene["target_pos"]),
        },
    ).append(
        ET.Element(
            "geom",
            {
                "type": "sphere",
                "size": "0.035",
                "rgba": "0.05 1.0 0.10 1",
                "contype": "0",
                "conaffinity": "0",
            },
        )
    )

    right_wrist = find_body(robot_body, "right_wrist_yaw_link")
    if right_wrist is not None:
        # The stock G1 rubber-hand mesh is visual-only (contype=0,
        # conaffinity=0), so the visible hand can otherwise pass through the
        # torso while the wrist collision mesh still reports safe clearance.
        # Add a transparent collision copy on the same wrist body. MuJoCo uses
        # the mesh convex hull for contact generation; the original visual geom
        # remains unchanged.
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "right_rubber_hand_collision",
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
        ET.SubElement(
            right_wrist,
            "body",
            {"name": "inspection_tool_tip_body", "pos": "0.105 0.029 0.200"},
        ).append(
            ET.Element(
                "geom",
                {
                    "name": "inspection_tool_tip",
                    "type": "sphere",
                    "size": "0.035",
                    "rgba": "0.9 0.18 0.08 1",
                    "density": "0",
                    "contype": "0",
                    "conaffinity": "0",
                },
            )
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_grip",
                "type": "cylinder",
                "pos": "0.105 0.029 0.040",
                "size": "0.017 0.05",
                "rgba": "0.05 0.05 0.05 1",
                "density": "0",
                "contype": "0",
                "conaffinity": "0",
            },
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_probe",
                "type": "cylinder",
                "pos": "0.105 0.029 0.145",
                "size": "0.010 0.055",
                "rgba": "0.18 0.20 0.22 1",
                "density": "0",
                "contype": "0",
                "conaffinity": "0",
            },
        )

    tree.write(DEMO_XML, encoding="unicode")


def parse_args():
    parser = argparse.ArgumentParser(description="G1 right-arm UDP IK and head-camera simulation")
    parser.add_argument(
        "--scene",
        choices=tuple(SCENES),
        default="control",
        help="control preserves the original demo; camera_validation is the head-camera test fixture",
    )
    parser.add_argument(
        "--view",
        choices=("overview", "head"),
        default="overview",
        help="MuJoCo viewer camera; head uses the simulated G1 D435i",
    )
    parser.add_argument(
        "--publish-head-camera",
        action="store_true",
        help="publish 640x480 BGR frames using Unitree simulator shared memory",
    )
    parser.add_argument(
        "--camera-fps",
        type=float,
        default=HEAD_CAMERA_FPS,
        help="simulated head-camera publication rate",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="save one simulated head-camera frame as BMP and exit",
    )
    return parser.parse_args()


def joint_qpos_addr(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    return model.jnt_qposadr[joint_id]


def joint_dof_addr(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    return model.jnt_dofadr[joint_id]


def set_joint(model, data, joint_name, value):
    data.qpos[joint_qpos_addr(model, joint_name)] = value


def freeze_non_arm_joints(model, data, initial_qpos):
    keep = set(RIGHT_ARM_JOINTS + LEFT_ARM_JOINTS)
    for i in range(model.njnt):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        if name not in keep:
            data.qpos[model.jnt_qposadr[i]] = initial_qpos[model.jnt_qposadr[i]]
    data.qvel[:] = 0.0


def set_left_arm_ready(model, data):
    for name, value in zip(LEFT_ARM_JOINTS, np.radians(LEFT_ARM_READY_DEGREES)):
        set_joint(model, data, name, value)


def clamp_joint_angles(model, data, joint_names):
    for name in joint_names:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        adr = model.jnt_qposadr[joint_id]
        if model.jnt_limited[joint_id]:
            low, high = model.jnt_range[joint_id]
            data.qpos[adr] = np.clip(data.qpos[adr], low, high)
        if name in RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES:
            low_degrees, high_degrees = RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES[name]
            data.qpos[adr] = np.clip(
                data.qpos[adr],
                math.radians(low_degrees),
                math.radians(high_degrees),
            )


def get_body_id(model, body_name):
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if body_id < 0:
        raise RuntimeError(f"MuJoCo body not found: {body_name}")
    return body_id


def create_context(model):
    right_joint_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in RIGHT_ARM_JOINTS])
    right_qpos_ids = np.array([model.jnt_qposadr[joint_id] for joint_id in right_joint_ids])
    right_dof_ids = np.array([model.jnt_dofadr[joint_id] for joint_id in right_joint_ids])
    right_body_ids = {get_body_id(model, name) for name in RIGHT_ARM_BODY_NAMES}
    core_body_ids = {get_body_id(model, name) for name in CORE_BODY_NAMES}
    return {
        "right_joint_ids": right_joint_ids,
        "right_qpos_ids": right_qpos_ids,
        "right_dof_ids": right_dof_ids,
        "right_arm_body_ids": right_body_ids,
        "core_body_ids": core_body_ids,
        "position_body": get_body_id(model, "right_wrist_yaw_link"),
        "orientation_body": get_body_id(model, "right_wrist_yaw_link"),
        "enforce_torso_safety": True,
    }


def calculate_rotation_error(target_rotation, current_rotation):
    rotation_error_matrix = target_rotation @ current_rotation.T
    quaternion = np.empty(4)
    mujoco.mju_mat2Quat(quaternion, rotation_error_matrix.reshape(-1))
    angle_axis = np.zeros(3)
    mujoco.mju_quat2Vel(angle_axis, quaternion, 1.0)
    return angle_axis


def damped_pseudoinverse(jacobian, damping):
    j = np.asarray(jacobian, dtype=float)
    return j.T @ np.linalg.inv(j @ j.T + (float(damping) ** 2) * np.eye(j.shape[0]))


def has_right_arm_core_contact(model, data, context):
    right_body_ids = context["right_arm_body_ids"]
    core_body_ids = context["core_body_ids"]
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        body1 = model.geom_bodyid[contact.geom1]
        body2 = model.geom_bodyid[contact.geom2]
        if (
            (body1 in right_body_ids and body2 in core_body_ids)
            or (body2 in right_body_ids and body1 in core_body_ids)
        ):
            return True
    return False


def get_right_arm_ids(model):
    joint_ids = [mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name) for name in RIGHT_ARM_JOINTS]
    qpos_ids = np.array([model.jnt_qposadr[joint_id] for joint_id in joint_ids])
    dof_ids = np.array([model.jnt_dofadr[joint_id] for joint_id in joint_ids])
    return qpos_ids, dof_ids


def get_operational_joint_bounds(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise RuntimeError(f"MuJoCo joint not found: {joint_name}")
    if model.jnt_limited[joint_id]:
        low, high = (float(value) for value in model.jnt_range[joint_id])
    else:
        low, high = -math.pi, math.pi
    if joint_name in RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES:
        op_low, op_high = RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES[joint_name]
        low = max(low, math.radians(op_low))
        high = min(high, math.radians(op_high))
    return low, high


def build_joint_bounds(model, joint_names):
    return np.array([get_operational_joint_bounds(model, name) for name in joint_names], dtype=float)


def clamp_vector_to_joint_bounds(values, bounds):
    values = np.asarray(values, dtype=float)
    return np.minimum(np.maximum(values, bounds[:, 0]), bounds[:, 1])


def joint_limit_penalty(values, bounds):
    values = np.asarray(values, dtype=float)
    centers = 0.5 * (bounds[:, 0] + bounds[:, 1])
    half_ranges = np.maximum(0.5 * (bounds[:, 1] - bounds[:, 0]), 1e-6)
    normalized = (values - centers) / half_ranges
    return float(np.sum(normalized * normalized))


def sample_multiseed_offsets(base_values, bounds, *, shoulder_step_degrees=15.0, elbow_step_degrees=20.0):
    base_values = np.asarray(base_values, dtype=float)
    shoulder_step = math.radians(float(shoulder_step_degrees))
    elbow_step = math.radians(float(elbow_step_degrees))
    seeds = [base_values.copy()]
    for shoulder_roll_delta in (-shoulder_step, shoulder_step):
        seed = base_values.copy()
        seed[1] += shoulder_roll_delta
        seeds.append(clamp_vector_to_joint_bounds(seed, bounds))
    for elbow_delta in (-elbow_step, elbow_step):
        seed = base_values.copy()
        seed[3] += elbow_delta
        seeds.append(clamp_vector_to_joint_bounds(seed, bounds))
    return seeds


def score_ik_candidate(position_error, rotation_error, q, bounds):
    return float(position_error) + 0.02 * float(rotation_error) + 0.001 * joint_limit_penalty(q, bounds)


def solve_right_arm_target(model, data, target_body, preferred, target_position, target_rotation, substeps=10, elbow_pole_reference=None, context=None):
    right_qpos, right_dofs = get_right_arm_ids(model)
    context = context or create_context(model)
    position_body = context.get("position_body", target_body)
    orientation_body = context.get("orientation_body", target_body)
    enforce_torso_safety = context.get("enforce_torso_safety", True)

    if not hasattr(solve_right_arm_target, "_runtime_previous_right_q"):
        solve_right_arm_target._runtime_previous_right_q = data.qpos[right_qpos].copy()

    target_position = np.asarray(target_position, dtype=float)
    target_rotation = None if target_rotation is None else np.asarray(target_rotation, dtype=float)
    preferred = np.asarray(preferred, dtype=float)

    for _ in range(substeps):
        mujoco.mj_forward(model, data)
        position_error = target_position - data.xpos[position_body]
        jacp = np.zeros((3, model.nv))
        jacr = np.zeros((3, model.nv))
        mujoco.mj_jacBody(model, data, jacp, jacr, target_body)
        position_jacobian = jacp[:, right_dofs]
        position_delta = damped_pseudoinverse(position_jacobian, POSITION_DAMPING) @ position_error
        dq = position_delta

        if target_rotation is not None:
            rotation_error = calculate_rotation_error(target_rotation, data.xmat[orientation_body].reshape(3, 3))
            orientation_jacobian = jacr[:, right_dofs]
            rotation_delta = damped_pseudoinverse(orientation_jacobian, ORIENTATION_DAMPING) @ rotation_error
            dq = dq + rotation_delta

        null_projector = np.eye(len(right_dofs)) - damped_pseudoinverse(position_jacobian, POSITION_DAMPING) @ position_jacobian
        posture_delta = preferred - data.qpos[right_qpos]
        dq = dq + POSTURE_GAIN * (null_projector @ posture_delta)

        if elbow_pole_reference is not None:
            elbow_body = get_body_id(model, "right_elbow_link")
            elbow_position = data.xpos[elbow_body]
            shoulder_body = get_body_id(model, "right_shoulder_roll_link")
            shoulder_position = data.xpos[shoulder_body]
            wrist_position = data.xpos[position_body]
            axis = wrist_position - shoulder_position
            axis_norm = np.linalg.norm(axis)
            if axis_norm > 1e-6:
                axis /= axis_norm
                desired = np.asarray(elbow_pole_reference, dtype=float) - shoulder_position
                desired -= np.dot(desired, axis) * axis
                actual = elbow_position - shoulder_position
                actual -= np.dot(actual, axis) * axis
                desired_norm = np.linalg.norm(desired)
                actual_norm = np.linalg.norm(actual)
                if desired_norm > 1e-6 and actual_norm > 1e-6:
                    desired /= desired_norm
                    actual /= actual_norm
                    pole_axis = np.cross(actual, desired)
                    pole_error = np.dot(pole_axis, axis)
                    elbow_jacp = np.zeros((3, model.nv))
                    elbow_jacr = np.zeros((3, model.nv))
                    mujoco.mj_jacBody(model, data, elbow_jacp, elbow_jacr, elbow_body)
                    elbow_jacobian = elbow_jacp[:, right_dofs]
                    pole_gradient = elbow_jacobian.T @ np.cross(axis, elbow_position - shoulder_position)
                    pole_gradient_norm = np.linalg.norm(pole_gradient)
                    if pole_gradient_norm > 1e-8:
                        pole_gradient /= pole_gradient_norm
                        dq = dq + ELBOW_POLE_GAIN * pole_error * (null_projector @ pole_gradient)

        max_abs = np.max(np.abs(dq))
        if max_abs > IK_MAX_STEP_RADIANS:
            dq *= IK_MAX_STEP_RADIANS / max_abs
        start_q = data.qpos[right_qpos].copy()
        candidate_q = start_q + IK_STEP_GAIN * dq
        data.qpos[right_qpos] = candidate_q
        clamp_joint_angles(model, data, RIGHT_ARM_JOINTS)
        mujoco.mj_forward(model, data)

        if enforce_torso_safety and has_right_arm_core_contact(model, data, context):
            data.qpos[right_qpos] = start_q
            mujoco.mj_forward(model, data)
            break

        solve_right_arm_target._runtime_previous_right_q = data.qpos[right_qpos].copy()

    return data.xpos[position_body].copy()


def select_best_seed(model, data, target_body, preferred, target_position, target_rotation, elbow_pole_reference=None, context=None):
    right_qpos, _ = get_right_arm_ids(model)
    start_q = data.qpos[right_qpos].copy()
    bounds = build_joint_bounds(model, RIGHT_ARM_JOINTS)
    seeds = sample_multiseed_offsets(start_q, bounds)
    best = None
    for seed_index, seed in enumerate(seeds):
        data.qpos[right_qpos] = seed
        mujoco.mj_forward(model, data)
        solve_right_arm_target(
            model,
            data,
            target_body,
            preferred,
            target_position,
            target_rotation,
            substeps=12,
            elbow_pole_reference=elbow_pole_reference,
            context=context,
        )
        position_error = np.linalg.norm(np.asarray(target_position, dtype=float) - data.xpos[context.get("position_body", target_body)])
        rotation_error = 0.0
        if target_rotation is not None:
            rotation_error = np.linalg.norm(calculate_rotation_error(np.asarray(target_rotation, dtype=float), data.xmat[context.get("orientation_body", target_body)].reshape(3, 3)))
        q = data.qpos[right_qpos].copy()
        score = score_ik_candidate(position_error, rotation_error, q, bounds)
        if best is None or score < best[0]:
            best = (score, q, seed_index)
    data.qpos[right_qpos] = start_q if best is None else best[1]
    mujoco.mj_forward(model, data)
    return None if best is None else best


def parse_udp_payload(payload):
    if isinstance(payload, list) and len(payload) == 3:
        return np.asarray(payload, dtype=float), IDENTITY_QUATERNION_XYZW.copy(), True
    if isinstance(payload, dict):
        position = payload.get("position")
        rotation = payload.get("rotation")
        active = payload.get("active", True)
        if isinstance(position, list) and len(position) == 3:
            if isinstance(rotation, list) and len(rotation) == 4:
                return np.asarray(position, dtype=float), np.asarray(rotation, dtype=float), bool(active)
            return np.asarray(position, dtype=float), IDENTITY_QUATERNION_XYZW.copy(), bool(active)
    raise ValueError("unsupported UDP payload")


def receive_target(sock):
    raw, _address = sock.recvfrom(4096)
    return parse_udp_payload(json.loads(raw.decode("utf-8")))


def send_unity_state(sock, address, wrist_position, target_position, active, *, workspace_limited=False, workspace_projection_distance_m=0.0):
    payload = {
        "wrist": np.asarray(wrist_position, dtype=float).tolist(),
        "target": np.asarray(target_position, dtype=float).tolist(),
        "active": bool(active),
        "workspace_limited": bool(workspace_limited),
        "workspace_projection_distance_m": float(workspace_projection_distance_m),
    }
    sock.sendto(json.dumps(payload).encode("utf-8"), address)


def write_runtime_status(status):
    RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = RUNTIME_STATUS_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    temporary_path.replace(RUNTIME_STATUS_PATH)


def target_pose_from_payload(reference, input_position, input_rotation):
    target_position = reference["robot_position"] + input_position - reference["input_position"]
    target_rotation = np.asarray(reference["robot_rotation"], dtype=float)
    return target_position, target_rotation


def operator_rotation_to_robot_matrix(operator_quaternion_xyzw):
    quaternion = np.asarray(operator_quaternion_xyzw, dtype=float)
    if quaternion.shape != (4,):
        raise ValueError("operator quaternion must be [x, y, z, w]")
    norm = float(np.linalg.norm(quaternion))
    if norm < 1e-8:
        raise ValueError("operator quaternion has zero norm")
    quaternion /= norm
    x, y, z, w = quaternion
    rotation = np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=float,
    )
    return OPERATOR_TO_ROBOT_BASIS @ rotation @ OPERATOR_TO_ROBOT_BASIS.T


def main():
    args = parse_args()
    make_demo_xml(args.scene)
    model = mujoco.MjModel.from_xml_path(str(DEMO_XML))
    data = mujoco.MjData(model)
    context = create_context(model)

    initial_qpos = data.qpos.copy()
    set_left_arm_ready(model, data)
    preferred = np.radians(RIGHT_ARM_READY_DEGREES)
    for name, value in zip(RIGHT_ARM_JOINTS, preferred):
        set_joint(model, data, name, value)
    mujoco.mj_forward(model, data)

    target_body = get_body_id(model, "right_wrist_yaw_link")
    udp_target_body = get_body_id(model, "udp_target")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.settimeout(0.01)

    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_address = (UNITY_STATE_HOST, UNITY_STATE_PORT)

    latest_position = data.xpos[target_body].copy()
    latest_rotation = IDENTITY_QUATERNION_XYZW.copy()
    latest_active = False
    last_packet_time = 0.0
    received_packets = 0
    state_period = 1.0 / UNITY_STATE_HZ
    next_state_time = time.monotonic()
    status_period = 1.0 / RUNTIME_STATUS_HZ
    next_status_time = time.monotonic()
    last_loop_time = time.monotonic()
    current_target_position = latest_position.copy()
    current_target_rotation = data.xmat[target_body].reshape(3, 3).copy()
    reference = None

    with mujoco.viewer.launch_passive(model, data) as viewer:
        if args.view == "head":
            viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
            viewer.cam.fixedcamid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, G1_D435I_CAMERA_NAME)
        while viewer.is_running():
            now = time.monotonic()
            dt = min(max(now - last_loop_time, 1e-4), 1.0 / 30.0)
            last_loop_time = now

            try:
                latest_position, latest_rotation, latest_active = receive_target(sock)
                received_packets += 1
                last_packet_time = now
            except socket.timeout:
                pass
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                pass

            packets_fresh = now - last_packet_time <= INPUT_TIMEOUT_SECONDS
            input_valid = received_packets > 0 and packets_fresh
            if not input_valid:
                latest_active = False

            if latest_active and reference is None:
                reference = {
                    "input_position": latest_position.copy(),
                    "robot_position": data.xpos[target_body].copy(),
                    "robot_rotation": data.xmat[target_body].reshape(3, 3).copy(),
                }
            elif not latest_active:
                reference = None

            if latest_active and reference is not None:
                desired_position, desired_rotation = target_pose_from_payload(reference, latest_position, latest_rotation)
                desired_delta = desired_position - current_target_position
                max_position_step = POSITION_MAX_SPEED * dt
                desired_distance = float(np.linalg.norm(desired_delta))
                if desired_distance > max_position_step > 0.0:
                    desired_delta *= max_position_step / desired_distance
                current_target_position = current_target_position + desired_delta
                current_target_rotation = desired_rotation

                solve_right_arm_target(
                    model,
                    data,
                    target_body,
                    preferred,
                    current_target_position,
                    current_target_rotation,
                    substeps=10,
                    context=context,
                )

            freeze_non_arm_joints(model, data, initial_qpos)
            mujoco.mj_forward(model, data)
            data.mocap_pos[model.body_mocapid[udp_target_body]] = current_target_position
            viewer.sync()

            if now >= next_state_time:
                send_unity_state(
                    state_sock,
                    state_address,
                    data.xpos[target_body],
                    current_target_position,
                    latest_active,
                )
                next_state_time = now + state_period

            if now >= next_status_time:
                write_runtime_status(
                    {
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "received_packets": received_packets,
                        "packets_fresh": packets_fresh,
                        "input_valid": input_valid,
                        "input_active": bool(latest_active),
                        "clutch_active": reference is not None,
                        "raw_target": latest_position.tolist(),
                        "operator_target": current_target_position.tolist(),
                        "feasible_target": current_target_position.tolist(),
                        "safe_target": current_target_position.tolist(),
                        "g1_wrist": data.xpos[target_body].tolist(),
                        "workspace_projection_distance_m": 0.0,
                        "safe_reference_lag_m": 0.0,
                        "tracking_error_m": float(np.linalg.norm(current_target_position - data.xpos[target_body])),
                        "workspace_limited": False,
                        "workspace_source": "none",
                        "workspace_exit_pending_s": 0.0,
                        "collision_limited": False,
                    }
                )
                next_status_time = now + status_period
