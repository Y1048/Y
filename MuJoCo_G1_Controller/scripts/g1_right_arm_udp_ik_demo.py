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


def create_right_arm_ik_context(
    model,
    position_body_name="right_wrist_roll_link",
    orientation_body_name="right_wrist_yaw_link",
    position_joint_count=4,
):
    if position_joint_count < 1 or position_joint_count > len(RIGHT_ARM_JOINTS):
        raise ValueError("position_joint_count must be between 1 and 7")

    right_arm_body_ids = {
        get_body_id(model, body_name) for body_name in RIGHT_ARM_BODY_NAMES
    }
    core_body_ids = {
        get_body_id(model, body_name) for body_name in CORE_BODY_NAMES
    }

    protected_body_ids = right_arm_body_ids | core_body_ids
    for geom_id in range(model.ngeom):
        if (
            int(model.geom_bodyid[geom_id]) in protected_body_ids
            and model.geom_contype[geom_id]
            and model.geom_conaffinity[geom_id]
        ):
            model.geom_margin[geom_id] = max(
                float(model.geom_margin[geom_id]),
                COLLISION_MARGIN,
            )

    return {
        "right_dof_ids": np.array(
            [joint_dof_addr(model, name) for name in RIGHT_ARM_JOINTS]
        ),
        "right_qpos_ids": np.array(
            [joint_qpos_addr(model, name) for name in RIGHT_ARM_JOINTS]
        ),
        "position_body": get_body_id(model, position_body_name),
        "orientation_body": get_body_id(model, orientation_body_name),
        "shoulder_body": get_body_id(model, "right_shoulder_pitch_link"),
        "enforce_torso_safety": position_body_name == "right_wrist_roll_link",
        "elbow_body": get_body_id(model, "right_elbow_link"),
        "position_joint_count": position_joint_count,
        "right_arm_body_ids": right_arm_body_ids,
        "core_body_ids": core_body_ids,
        "jacp": np.zeros((3, model.nv)),
        "jacr": np.zeros((3, model.nv)),
        "orientation_jacp": np.zeros((3, model.nv)),
        "orientation_jacr": np.zeros((3, model.nv)),
        "elbow_jacp": np.zeros((3, model.nv)),
        "elbow_jacr": np.zeros((3, model.nv)),
        "collision_limited": False,
        "workspace_limited": False,
    }


def damped_pseudoinverse(jacobian, damping):
    task_dimension = jacobian.shape[0]
    regularized_matrix = (
        jacobian @ jacobian.T
        + damping * damping * np.eye(task_dimension)
    )
    return jacobian.T @ np.linalg.solve(
        regularized_matrix,
        np.eye(task_dimension),
    )


def is_right_wrist_target_safe(target):
    target_position = np.asarray(target, dtype=float)
    if target_position.shape != (3,) or not np.all(np.isfinite(target_position)):
        return False

    within_torso_depth = TORSO_KEEP_OUT_X[0] <= target_position[0] <= TORSO_KEEP_OUT_X[1]
    within_torso_height = TORSO_KEEP_OUT_Z[0] <= target_position[2] <= TORSO_KEEP_OUT_Z[1]
    enters_torso_keep_out = (
        within_torso_depth
        and within_torso_height
        and target_position[1] > RIGHT_WRIST_LATERAL_LIMIT
    )
    return not enters_torso_keep_out


def is_clutch_delta_within_workspace(delta):
    requested_delta = np.asarray(delta, dtype=float)
    return bool(
        requested_delta.shape == (3,)
        and np.all(np.isfinite(requested_delta))
        and np.all(requested_delta >= CLUTCH_POSITION_DELTA_MIN)
        and np.all(requested_delta <= CLUTCH_POSITION_DELTA_MAX)
    )


def clamp_to_clutch_workspace(target_position, reference_position):
    target_position = np.asarray(target_position, dtype=float)
    reference_position = np.asarray(reference_position, dtype=float)
    requested_delta = target_position - reference_position
    clamped_delta = np.clip(
        requested_delta,
        CLUTCH_POSITION_DELTA_MIN,
        CLUTCH_POSITION_DELTA_MAX,
    )
    return reference_position + clamped_delta


def capture_elbow_pole_reference(data, shoulder_body, elbow_body, wrist_body):
    shoulder_position = data.xpos[shoulder_body].copy()
    elbow_position = data.xpos[elbow_body].copy()
    wrist_position = data.xpos[wrist_body].copy()
    shoulder_to_wrist = wrist_position - shoulder_position
    shoulder_to_wrist_length = float(np.linalg.norm(shoulder_to_wrist))
    if shoulder_to_wrist_length < 1e-8:
        pole_direction = np.array([0.0, -1.0, 0.0])
    else:
        arm_axis = shoulder_to_wrist / shoulder_to_wrist_length
        elbow_projection = (
            shoulder_position
            + arm_axis * np.dot(elbow_position - shoulder_position, arm_axis)
        )
        pole_direction = elbow_position - elbow_projection
        pole_length = float(np.linalg.norm(pole_direction))
        if pole_length < 1e-8:
            pole_direction = np.array([0.0, -1.0, 0.0])
        else:
            pole_direction /= pole_length

    return {
        "pole_direction": pole_direction,
        "upper_arm_length": float(np.linalg.norm(elbow_position - shoulder_position)),
        "forearm_length": float(np.linalg.norm(wrist_position - elbow_position)),
    }


def calculate_elbow_pole_target(shoulder_position, wrist_target, pole_reference):
    shoulder_to_wrist = wrist_target - shoulder_position
    requested_length = float(np.linalg.norm(shoulder_to_wrist))
    if requested_length < 1e-8:
        return shoulder_position.copy()

    arm_axis = shoulder_to_wrist / requested_length
    upper_arm_length = pole_reference["upper_arm_length"]
    forearm_length = pole_reference["forearm_length"]
    minimum_length = abs(upper_arm_length - forearm_length) + 1e-6
    maximum_length = upper_arm_length + forearm_length - 1e-6
    solved_length = float(np.clip(requested_length, minimum_length, maximum_length))
    center_distance = (
        upper_arm_length * upper_arm_length
        - forearm_length * forearm_length
        + solved_length * solved_length
    ) / (2.0 * solved_length)
    elbow_radius = math.sqrt(
        max(0.0, upper_arm_length * upper_arm_length - center_distance * center_distance)
    )
    circle_center = shoulder_position + arm_axis * center_distance

    pole_direction = pole_reference["pole_direction"]
    projected_pole = pole_direction - arm_axis * np.dot(pole_direction, arm_axis)
    projected_length = float(np.linalg.norm(projected_pole))
    if projected_length < 1e-8:
        fallback_pole = np.array([0.0, -1.0, -0.25])
        projected_pole = fallback_pole - arm_axis * np.dot(fallback_pole, arm_axis)
        projected_length = max(float(np.linalg.norm(projected_pole)), 1e-8)

    return circle_center + elbow_radius * projected_pole / projected_length


def has_right_arm_core_contact(model, data, context):
    right_arm_body_ids = context["right_arm_body_ids"]
    core_body_ids = context["core_body_ids"]
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        first_body = int(model.geom_bodyid[contact.geom1])
        second_body = int(model.geom_bodyid[contact.geom2])
        if (
            first_body in right_arm_body_ids
            and second_body in core_body_ids
        ) or (
            second_body in right_arm_body_ids
            and first_body in core_body_ids
        ):
            return True
    return False


def setup_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.setblocking(False)
    return sock


def send_robot_state(
    sock,
    data,
    right_qpos_ids,
    active,
    position_body,
    target_position,
    clutch_reference,
    ik_context,
    workspace_limited,
):
    wrist_position = data.xpos[position_body].copy()
    if active and clutch_reference is not None:
        reference_position = clutch_reference["robot_position"]
        wrist_delta = wrist_position - reference_position
        target_delta = target_position - reference_position
    else:
        wrist_delta = np.zeros(3)
        target_delta = np.zeros(3)

    packet = {
        "right_arm": {
            "joints": [float(value) for value in data.qpos[right_qpos_ids]],
            "active": bool(active),
            "wrist_delta": [float(value) for value in wrist_delta],
            "target_delta": [float(value) for value in target_delta],
            "position_error": float(np.linalg.norm(target_position - wrist_position)),
            "workspace_limited": bool(workspace_limited),
            "collision_limited": bool(ik_context["collision_limited"]),
        },
        "timestamp": time.time(),
    }
    sock.sendto(
        json.dumps(packet, separators=(",", ":")).encode("utf-8"),
        (UNITY_STATE_HOST, UNITY_STATE_PORT),
    )


def normalize_quaternion_xyzw(quaternion):
    quaternion = np.asarray(quaternion, dtype=float)
    quaternion_norm = np.linalg.norm(quaternion)
    if quaternion_norm < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0])
    return quaternion / quaternion_norm


def quaternion_xyzw_to_matrix(quaternion):
    x_value, y_value, z_value, w_value = normalize_quaternion_xyzw(quaternion)
    return np.array(
        [
            [
                1.0 - 2.0 * (y_value * y_value + z_value * z_value),
                2.0 * (x_value * y_value - z_value * w_value),
                2.0 * (x_value * z_value + y_value * w_value),
            ],
            [
                2.0 * (x_value * y_value + z_value * w_value),
                1.0 - 2.0 * (x_value * x_value + z_value * z_value),
                2.0 * (y_value * z_value - x_value * w_value),
            ],
            [
                2.0 * (x_value * z_value - y_value * w_value),
                2.0 * (y_value * z_value + x_value * w_value),
                1.0 - 2.0 * (x_value * x_value + y_value * y_value),
            ],
        ]
    )


def slerp_quaternion_xyzw(start_quaternion, end_quaternion, blend_value):
    start_value = normalize_quaternion_xyzw(start_quaternion)
    end_value = normalize_quaternion_xyzw(end_quaternion)
    dot_value = float(np.dot(start_value, end_value))
    if dot_value < 0.0:
        end_value = -end_value
        dot_value = -dot_value

    dot_value = float(np.clip(dot_value, -1.0, 1.0))
    if dot_value > 0.9995:
        return normalize_quaternion_xyzw(
            start_value + blend_value * (end_value - start_value)
        )

    angle_value = math.acos(dot_value)
    sine_value = math.sin(angle_value)
    start_weight = math.sin((1.0 - blend_value) * angle_value) / sine_value
    end_weight = math.sin(blend_value * angle_value) / sine_value
    return start_weight * start_value + end_weight * end_value


def clamp_vector_magnitude(vector_value, maximum_magnitude):
    vector_norm = float(np.linalg.norm(vector_value))
    if vector_norm <= maximum_magnitude or vector_norm < 1e-9:
        return vector_value
    return vector_value * (maximum_magnitude / vector_norm)


def update_safe_position_reference(
    current_position,
    desired_position,
    delta_time,
):
    safe_delta_time = max(float(delta_time), 1e-4)
    position_error = desired_position - current_position
    maximum_step = POSITION_MAX_SPEED * safe_delta_time
    position_step = clamp_vector_magnitude(position_error, maximum_step)
    return current_position + position_step


def update_safe_rotation_reference(
    current_rotation,
    desired_rotation,
    delta_time,
):
    current_value = normalize_quaternion_xyzw(current_rotation)
    desired_value = normalize_quaternion_xyzw(desired_rotation)
    dot_value = float(np.dot(current_value, desired_value))
    if dot_value < 0.0:
        desired_value = -desired_value
        dot_value = -dot_value

    angle_error = 2.0 * math.acos(float(np.clip(dot_value, -1.0, 1.0)))
    safe_delta_time = max(float(delta_time), 1e-4)
    angle_step = min(angle_error, ROTATION_MAX_SPEED * safe_delta_time)
    if angle_error < 1e-8 or angle_step >= angle_error:
        return desired_value

    blend_value = angle_step / angle_error
    return slerp_quaternion_xyzw(current_value, desired_value, blend_value)


def operator_rotation_to_robot_matrix(operator_quaternion):
    operator_rotation = quaternion_xyzw_to_matrix(operator_quaternion)
    return (
        OPERATOR_TO_ROBOT_BASIS
        @ operator_rotation
        @ OPERATOR_TO_ROBOT_BASIS.T
    )


def calculate_rotation_error(target_rotation, current_rotation):
    return 0.5 * sum(
        np.cross(current_rotation[:, axis_index], target_rotation[:, axis_index])
        for axis_index in range(3)
    )


def receive_target(
    sock,
    packet_watchdog,
    position_fallback,
    rotation_fallback,
    valid_fallback,
):
    latest_position = position_fallback
    latest_rotation = rotation_fallback
    latest_valid = valid_fallback
    received = 0
    accepted_workspace_exit = False
    while True:
        try:
            packet, _ = sock.recvfrom(4096)
        except BlockingIOError:
            break

        try:
            msg = json.loads(packet.decode("utf-8"))
            if not isinstance(msg, dict):
                continue
            right_target = msg.get("right")
            if not isinstance(right_target, dict):
                continue

            session_id = msg.get("session_id")
            sequence = msg.get("sequence")
            valid = right_target.get("valid")
            command_state = msg.get("command_state")
            if command_state is None:
                command_state = "active" if valid else "idle"
            if command_state not in ("active", "idle", "workspace_exit"):
                continue
            if command_state == "active" and valid is not True:
                continue
            if command_state != "active" and valid is not False:
                continue
            pos = right_target.get("pos", msg.get("pos"))
            rot = right_target.get("rot", msg.get("rot"))
            if valid:
                if (
                    not isinstance(pos, (list, tuple))
                    or len(pos) != 3
                    or not isinstance(rot, (list, tuple))
                    or len(rot) != 4
                ):
                    continue
                parsed_position = np.asarray(pos, dtype=float)
                parsed_rotation = np.asarray(rot, dtype=float)
                if not (
                    np.all(np.isfinite(parsed_position))
                    and np.all(np.isfinite(parsed_rotation))
                ):
                    continue

            arrival_time_ns = time.monotonic_ns()
            acceptance = packet_watchdog.accept(
                session_id,
                sequence,
                valid,
                arrival_time_ns,
            )
            if not acceptance.accepted:
                continue

            if valid:
                latest_position = parsed_position
                latest_rotation = normalize_quaternion_xyzw(parsed_rotation)
                latest_valid = True
            else:
                latest_valid = False
                if command_state == "workspace_exit":
                    accepted_workspace_exit = True
            received += 1
        except (
            AttributeError,
            json.JSONDecodeError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ):
            pass
    return (
        latest_position,
        latest_rotation,
        latest_valid,
        received,
        accepted_workspace_exit,
    )


def write_runtime_status(status_value):
    RUNTIME_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = RUNTIME_STATUS_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(status_value, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(RUNTIME_STATUS_PATH)


def capture_clutch_reference(
    data,
    position_body,
    orientation_body,
    input_position,
    input_rotation,
    shoulder_body,
    elbow_body,
):
    return {
        "input_position": input_position.copy(),
        "input_rotation": operator_rotation_to_robot_matrix(input_rotation),
        "robot_position": data.xpos[position_body].copy(),
        "robot_rotation": data.xmat[orientation_body].reshape(3, 3).copy(),
        "elbow_pole": capture_elbow_pole_reference(
            data,
            shoulder_body,
            elbow_body,
            position_body,
        ),
    }


def calculate_clutched_target(reference, input_position, input_rotation):
    target_position = (
        reference["robot_position"]
        + input_position
        - reference["input_position"]
    )
    current_input_rotation = operator_rotation_to_robot_matrix(input_rotation)
    # UDP rotation is the absolute mapped Unity wrist pose. Applying the world
    # rotation change since engagement preserves the robot pose at engagement
    # and avoids changing coordinate conventions when the clutch activates.
    rotation_delta = (
        current_input_rotation
        @ reference["input_rotation"].T
    )
    target_rotation = rotation_delta @ reference["robot_rotation"]
    return target_position, target_rotation


def initialize_model(scene_name="control"):
    make_demo_xml(scene_name)
    model = mujoco.MjModel.from_xml_path(str(DEMO_XML))
    data = mujoco.MjData(model)
    initial_qpos = data.qpos.copy()

    initial_right = np.radians(RIGHT_ARM_READY_DEGREES)
    for name, value in zip(RIGHT_ARM_JOINTS, initial_right):
        set_joint(model, data, name, value)
    set_left_arm_ready(model, data)
    mujoco.mj_forward(model, data)
    return model, data, initial_qpos, initial_right.copy()


def solve_right_arm_target(
    model,
    data,
    initial_qpos,
    preferred,
    target,
    target_rotation=None,
    iterations=1,
    substeps=4,
    context=None,
    elbow_pole_reference=None,
):
    if context is None:
        context = create_right_arm_ik_context(model)

    right_dof_ids = context["right_dof_ids"]
    right_qpos_ids = context["right_qpos_ids"]
    position_body = context["position_body"]
    orientation_body = context["orientation_body"]
    elbow_body = context["elbow_body"]
    shoulder_body = context["shoulder_body"]
    position_joint_count = context["position_joint_count"]
    position_dof_ids = right_dof_ids[:position_joint_count]
    position_qpos_ids = right_qpos_ids[:position_joint_count]
    jacp = context["jacp"]
    jacr = context["jacr"]
    orientation_jacp = context["orientation_jacp"]
    orientation_jacr = context["orientation_jacr"]
    elbow_jacp = context["elbow_jacp"]
    elbow_jacr = context["elbow_jacr"]

    context["collision_limited"] = False
    context["workspace_limited"] = False
    target_position = np.asarray(target, dtype=float)
    if (
        context["enforce_torso_safety"]
        and not is_right_wrist_target_safe(target_position)
    ):
        context["workspace_limited"] = True
        mujoco.mj_forward(model, data)
        return data.xpos[position_body].copy()

    blocked_by_collision = False
    for _ in range(iterations):
        freeze_non_arm_joints(model, data, initial_qpos)
        set_left_arm_ready(model, data)
        for _ in range(substeps):
            mujoco.mj_forward(model, data)
            position_error = target_position - data.xpos[position_body]
            mujoco.mj_jacBody(model, data, jacp, jacr, position_body)
            position_jacobian = jacp[:, position_dof_ids]
            position_task_error = position_error
            position_task_jacobian = position_jacobian

            # Keep the right elbow outside the torso while retaining the hand
            # target as the primary task. This also chooses a human-like IK
            # branch when the wrist reaches across the front of the robot.
            if context["enforce_torso_safety"]:
                mujoco.mj_jacBody(model, data, elbow_jacp, elbow_jacr, elbow_body)
                elbow_lateral_error = (
                    RIGHT_ELBOW_LATERAL_LIMIT - data.xpos[elbow_body][1]
                )
                if elbow_lateral_error < 0.0:
                    position_task_error = np.concatenate(
                        [
                            position_task_error,
                            [ELBOW_AVOIDANCE_WEIGHT * elbow_lateral_error],
                        ]
                    )
                    position_task_jacobian = np.vstack(
                        [
                            position_task_jacobian,
                            ELBOW_AVOIDANCE_WEIGHT
                            * elbow_jacp[1, position_dof_ids],
                        ]
                    )

            position_pseudoinverse = damped_pseudoinverse(
                position_task_jacobian,
                POSITION_DAMPING,
            )
            position_delta = position_pseudoinverse @ position_task_error
            nullspace_projector = (
                np.eye(position_joint_count)
                - position_pseudoinverse @ position_task_jacobian
            )
            posture_error = (
                preferred[:position_joint_count]
                - data.qpos[position_qpos_ids]
            )
            posture_projector = nullspace_projector
            if elbow_pole_reference is not None:
                elbow_target = calculate_elbow_pole_target(
                    data.xpos[shoulder_body],
                    target_position,
                    elbow_pole_reference,
                )
                elbow_error = elbow_target - data.xpos[elbow_body]
                mujoco.mj_jacBody(model, data, elbow_jacp, elbow_jacr, elbow_body)
                elbow_jacobian = elbow_jacp[:, position_dof_ids]
                elbow_null_jacobian = elbow_jacobian @ nullspace_projector
                elbow_pseudoinverse = damped_pseudoinverse(
                    elbow_null_jacobian,
                    ELBOW_POLE_DAMPING,
                )
                elbow_residual = elbow_error - elbow_jacobian @ position_delta
                position_delta += ELBOW_POLE_GAIN * (
                    nullspace_projector
                    @ elbow_pseudoinverse
                    @ elbow_residual
                )
                posture_projector = nullspace_projector @ (
                    np.eye(position_joint_count)
                    - elbow_pseudoinverse @ elbow_null_jacobian
                )

            position_delta += posture_projector @ (POSTURE_GAIN * posture_error)

            delta_q = np.zeros(len(right_dof_ids))
            delta_q[:position_joint_count] = position_delta

            # Position and orientation are deliberately decoupled. The wrist
            # base position uses shoulder/elbow joints, while hand orientation
            # uses only the three wrist joints. Rotating the operator's wrist
            # therefore cannot be "helped" by moving the robot elbow.
            if target_rotation is not None:
                current_rotation = data.xmat[orientation_body].reshape(3, 3)
                rotation_error = calculate_rotation_error(
                    target_rotation,
                    current_rotation,
                )
                mujoco.mj_jacBody(
                    model,
                    data,
                    orientation_jacp,
                    orientation_jacr,
                    orientation_body,
                )
                rotation_jacobian = orientation_jacr[:, right_dof_ids]
                if position_joint_count < len(right_dof_ids):
                    wrist_start = 4
                    predicted_arm_rotation = (
                        rotation_jacobian[:, :position_joint_count]
                        @ (IK_STEP_GAIN * position_delta)
                    )
                    wrist_rotation_error = (
                        rotation_error - predicted_arm_rotation
                    )
                    wrist_jacobian = rotation_jacobian[:, wrist_start:]
                    wrist_pseudoinverse = damped_pseudoinverse(
                        wrist_jacobian,
                        ORIENTATION_DAMPING,
                    )
                    delta_q[wrist_start:] = (
                        wrist_pseudoinverse @ wrist_rotation_error
                    )
                else:
                    orientation_pseudoinverse = damped_pseudoinverse(
                        rotation_jacobian,
                        ORIENTATION_DAMPING,
                    )
                    delta_q += orientation_pseudoinverse @ rotation_error

            delta_q = np.clip(
                delta_q,
                -IK_MAX_STEP_RADIANS,
                IK_MAX_STEP_RADIANS,
            )
            previous_qpos = data.qpos[right_qpos_ids].copy()
            accepted = False
            for line_search_index in range(5):
                step_gain = IK_STEP_GAIN * (0.5 ** line_search_index)
                data.qpos[right_qpos_ids] = (
                    previous_qpos + step_gain * delta_q
                )
                clamp_joint_angles(model, data, RIGHT_ARM_JOINTS)
                mujoco.mj_forward(model, data)
                if not has_right_arm_core_contact(model, data, context):
                    accepted = True
                    break

            if not accepted:
                data.qpos[right_qpos_ids] = previous_qpos
                mujoco.mj_forward(model, data)
                context["collision_limited"] = True
                blocked_by_collision = True
                break
        if blocked_by_collision:
            break

    mujoco.mj_forward(model, data)
    return data.xpos[position_body].copy()


def configure_viewer_camera(viewer, model, view):
    if view != "head":
        return
    camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, G1_D435I_CAMERA_NAME)
    if camera_id < 0:
        raise RuntimeError(f"MuJoCo camera not found: {G1_D435I_CAMERA_NAME}")
    viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
    viewer.cam.fixedcamid = camera_id


def run_snapshot(model, data, destination):
    camera_profile = load_camera_profile(CAMERA_PROFILE_PATH)
    camera_profile["active_source"] = "simulation"
    source = create_head_camera_source(camera_profile, model=model, data=data)
    try:
        frame = source.read()
        save_bgr_bmp(destination, frame.color_bgr)
        print(f"Saved simulated G1 head-camera frame: {destination.resolve()}")
    finally:
        source.close()


def main():
    args = parse_args()
    if args.camera_fps <= 0.0:
        raise ValueError("--camera-fps must be positive")

    model, data, initial_qpos, preferred = initialize_model(args.scene)
    scene_target = np.asarray(SCENES[args.scene]["target_pos"], dtype=float)
    ik_context = create_right_arm_ik_context(model)
    mujoco.mj_forward(model, data)

    if args.snapshot is not None:
        if args.scene == "camera_validation":
            snapshot_context = create_right_arm_ik_context(
                model,
                position_body_name="inspection_tool_tip_body",
                orientation_body_name="inspection_tool_tip_body",
                position_joint_count=7,
            )
            solve_right_arm_target(
                model,
                data,
                initial_qpos,
                preferred,
                scene_target,
                iterations=NEUTRAL_SOLVE_ITERATIONS,
                context=snapshot_context,
            )
        run_snapshot(model, data, args.snapshot)
        return

    position_body = ik_context["position_body"]
    orientation_body = ik_context["orientation_body"]

    sock = setup_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    camera_source = None
    image_writer = None
    if args.publish_head_camera:
        camera_profile = load_camera_profile(CAMERA_PROFILE_PATH)
        camera_profile["active_source"] = "simulation"
        camera_source = create_head_camera_source(camera_profile, model=model, data=data)
        camera_source.start()
        image_writer = UnitreeSimImageWriter()

    raw_target = scene_target.copy()
    filtered_target = data.xpos[position_body].copy()
    desired_target = filtered_target.copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    filtered_rotation = raw_rotation.copy()
    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
    raw_valid = False
    clutch_active = False
    clutch_reference = None
    packet_watchdog = SessionSequenceWatchdog(
        takeover_after_s=INPUT_TIMEOUT_SECONDS
    )
    workspace_fault = WorkspaceFaultLatch()
    workspace_exit_debounce = WorkspaceExitDebounce(
        WORKSPACE_EXIT_CONFIRM_SECONDS
    )
    received_total = 0
    last_received_time = float("-inf")
    packet_was_fresh = False
    input_was_active = False
    next_camera_time = time.monotonic()
    camera_period = 1.0 / args.camera_fps
    next_state_time = time.monotonic()
    state_period = 1.0 / UNITY_STATE_HZ
    next_status_time = time.monotonic()
    status_period = 1.0 / RUNTIME_STATUS_HZ
    last_control_time = time.monotonic()

    print("G1 right-arm UDP IK demo")
    print("------------------------")
    print(f"Listening for UDP JSON on 127.0.0.1:{UDP_PORT} and local interfaces")
    print(
        'Expected format: {"session_id": "...", "sequence": 0, '
        '"right": {"pos": [0.42, -0.16, 1.05], '
        '"rot": [0, 0, 0, 1], "valid": true}}'
    )
    print("This legacy receiver is retained for camera and regression checks only.")
    print("Initial ready pose: both arms down; clutch motion is relative to this pose.")
    print(
        f"Publishing right-arm joint state to "
        f"{UNITY_STATE_HOST}:{UNITY_STATE_PORT} at {UNITY_STATE_HZ:g} Hz."
    )
    if args.publish_head_camera:
        print(
            "Head camera: 640x480 BGR at "
            f"{args.camera_fps:g} FPS -> isaac_head_image_shm (TeleImager-compatible)"
        )

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            configure_viewer_camera(viewer, model, args.view)
            last_print = 0.0

            while viewer.is_running():
                t = time.monotonic()
                control_delta_time = float(np.clip(
                    t - last_control_time,
                    model.opt.timestep,
                    0.05,
                ))
                last_control_time = t
                freeze_non_arm_joints(model, data, initial_qpos)
                set_left_arm_ready(model, data)

                (
                    raw_target,
                    raw_rotation,
                    raw_valid,
                    received_now,
                    accepted_workspace_exit,
                ) = receive_target(
                    sock,
                    packet_watchdog,
                    raw_target,
                    raw_rotation,
                    raw_valid,
                )
                if received_now:
                    received_total += received_now
                    last_received_time = t
                if accepted_workspace_exit:
                    if not workspace_fault.latched:
                        workspace_fault.trip()
                    workspace_fault.observe_workspace_exit()
                packet_fresh = (t - last_received_time) < INPUT_TIMEOUT_SECONDS
                valid_permitted = False
                if raw_valid and packet_fresh:
                    valid_permitted = workspace_fault.permit_valid()
                requested_active = (
                    raw_valid
                    and packet_fresh
                    and valid_permitted
                )
                workspace_limited = workspace_fault.latched
                input_resumed = requested_active and not input_was_active

                if requested_active and not clutch_active:
                    mujoco.mj_forward(model, data)
                    clutch_reference = capture_clutch_reference(
                        data,
                        position_body,
                        orientation_body,
                        raw_target,
                        raw_rotation,
                        ik_context["shoulder_body"],
                        ik_context["elbow_body"],
                    )
                    preferred[:] = data.qpos[ik_context["right_qpos_ids"]]
                    filtered_target = clutch_reference["robot_position"].copy()
                    filtered_rotation = raw_rotation.copy()
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    clutch_active = True
                    workspace_exit_debounce.reset()
                    print("\nRight-arm clutch engaged without a target jump.")
                elif input_resumed and clutch_active:
                    mujoco.mj_forward(model, data)
                    clutch_reference = capture_clutch_reference(
                        data,
                        position_body,
                        orientation_body,
                        raw_target,
                        raw_rotation,
                        ik_context["shoulder_body"],
                        ik_context["elbow_body"],
                    )
                    preferred[:] = data.qpos[ik_context["right_qpos_ids"]]
                    filtered_target = clutch_reference["robot_position"].copy()
                    filtered_rotation = raw_rotation.copy()
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    workspace_exit_debounce.reset()
                    print("\nInput resumed; clutch reference rebased without a jump.")

                if accepted_workspace_exit and clutch_active:
                    clutch_active = False
                    clutch_reference = None
                    raw_valid = False
                    workspace_limited = True
                    workspace_exit_debounce.reset()
                    mujoco.mj_forward(model, data)
                    filtered_target = data.xpos[position_body].copy()
                    desired_target = filtered_target.copy()
                    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                    data.mocap_pos[0] = filtered_target
                    print(
                        "\nExplicit workspace exit received; clutch released "
                        "and current pose held."
                    )

                if not packet_fresh and packet_was_fresh and clutch_active:
                    print("\nUDP input temporarily stale; holding the current pose.")
                packet_was_fresh = packet_fresh

                if clutch_active:
                    desired_target, desired_rotation = calculate_clutched_target(
                        clutch_reference,
                        raw_target,
                        raw_rotation,
                    )
                    desired_target = clamp_to_clutch_workspace(
                        desired_target,
                        clutch_reference["robot_position"],
                    )
                    requested_delta = (
                        desired_target - clutch_reference["robot_position"]
                    )
                    workspace_safe = (
                        is_clutch_delta_within_workspace(requested_delta)
                        and is_right_wrist_target_safe(desired_target)
                    )
                    workspace_exit_confirmed = workspace_exit_debounce.update(
                        workspace_safe,
                        control_delta_time,
                    )
                    if workspace_exit_confirmed:
                        workspace_fault.trip_and_arm_reset()
                        workspace_limited = True
                        clutch_active = False
                        clutch_reference = None
                        raw_valid = False
                        mujoco.mj_forward(model, data)
                        filtered_target = data.xpos[position_body].copy()
                        desired_target = filtered_target.copy()
                        target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                        data.mocap_pos[0] = filtered_target
                        print(
                            "\nRight-arm workspace exited; clutch released "
                            "and current pose held."
                        )
                    else:
                        filtered_target = update_safe_position_reference(
                            filtered_target,
                            desired_target,
                            control_delta_time,
                        )
                        filtered_rotation = update_safe_rotation_reference(
                            filtered_rotation,
                            raw_rotation,
                            control_delta_time,
                        )
                        _, target_rotation = calculate_clutched_target(
                            clutch_reference,
                            raw_target,
                            filtered_rotation,
                        )
                        data.mocap_pos[0] = filtered_target

                        solve_right_arm_target(
                            model,
                            data,
                            initial_qpos,
                            preferred,
                            filtered_target,
                            target_rotation=target_rotation,
                            context=ik_context,
                            elbow_pole_reference=clutch_reference["elbow_pole"],
                        )
                else:
                    # Tracking loss and pre-engagement are hold states. The next
                    # active edge captures a new zero-delta clutch reference.
                    mujoco.mj_forward(model, data)
                    filtered_target = data.xpos[position_body].copy()
                    desired_target = filtered_target.copy()
                    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                    data.mocap_pos[0] = filtered_target

                input_was_active = requested_active and clutch_active

                monotonic_time = time.monotonic()
                if monotonic_time >= next_state_time:
                    send_robot_state(
                        state_sock,
                        data,
                        ik_context["right_qpos_ids"],
                        clutch_active,
                        position_body,
                        filtered_target,
                        clutch_reference,
                        ik_context,
                        workspace_limited,
                    )
                    next_state_time = monotonic_time + state_period

                if camera_source is not None and monotonic_time >= next_camera_time:
                    frame = camera_source.read()
                    image_writer.write_frame(frame, "head")
                    next_camera_time = monotonic_time + camera_period

                if monotonic_time >= next_status_time:
                    wrist_position = data.xpos[position_body].copy()
                    status_value = {
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "received_packets": received_total,
                        "packets_fresh": bool(packet_fresh),
                        "input_valid": bool(raw_valid),
                        "clutch_active": bool(clutch_active),
                        "raw_target": raw_target.tolist(),
                        "desired_target": desired_target.tolist(),
                        "safe_target": filtered_target.tolist(),
                        "g1_wrist": wrist_position.tolist(),
                        "safe_reference_lag_m": float(
                            np.linalg.norm(desired_target - filtered_target)
                        ),
                        "tracking_error_m": float(
                            np.linalg.norm(filtered_target - wrist_position)
                        ),
                        "workspace_limited": bool(workspace_limited),
                        "workspace_exit_pending_s": float(
                            workspace_exit_debounce.unsafe_duration_s
                        ),
                        "collision_limited": bool(ik_context["collision_limited"]),
                    }
                    write_runtime_status(status_value)
                    next_status_time = monotonic_time + status_period

                if t - last_print > 0.25:
                    last_print = t
                    wrist_pos = data.xpos[position_body].copy()
                    dist = np.linalg.norm(filtered_target - wrist_pos)
                    rotation_dist = np.linalg.norm(
                        calculate_rotation_error(
                            target_rotation,
                            data.xmat[orientation_body].reshape(3, 3),
                        )
                    )
                    if clutch_active:
                        status = "ACTIVE"
                    elif packet_fresh:
                        status = "waiting"
                    else:
                        status = "NO UDP"
                    safety_flags = []
                    if workspace_limited:
                        safety_flags.append("workspace")
                    if ik_context["collision_limited"]:
                        safety_flags.append("collision")
                    safety_text = ",".join(safety_flags) if safety_flags else "clear"
                    print(
                        f"{status} packets={received_total} "
                        f"target=({filtered_target[0]: .2f}, {filtered_target[1]: .2f}, {filtered_target[2]: .2f}) "
                        f"wrist=({wrist_pos[0]: .2f}, {wrist_pos[1]: .2f}, {wrist_pos[2]: .2f}) "
                        f"error={dist: .3f} rot_error={math.degrees(rotation_dist): .1f}deg "
                        f"safety={safety_text}",
                        end="\r",
                    )

                viewer.sync()
                time.sleep(model.opt.timestep)
    finally:
        sock.close()
        state_sock.close()
        if camera_source is not None:
            camera_source.close()
        if image_writer is not None:
            image_writer.close()


if __name__ == "__main__":
    main()
