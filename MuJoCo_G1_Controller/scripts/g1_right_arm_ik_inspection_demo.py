import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"
DEMO_XML = G1_DIR / "_generated_g1_right_arm_ik_inspection.xml"

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


def find_body(element, name):
    if element.tag == "body" and element.get("name") == name:
        return element
    for child in element:
        found = find_body(child, name)
        if found is not None:
            return found
    return None


def make_demo_xml():
    tree = ET.parse(G1_XML)
    root = tree.getroot()

    worldbody = root.find("worldbody")
    robot_body = worldbody.find("body")

    for joint in list(robot_body.findall("freejoint")):
        robot_body.remove(joint)
    robot_body.set("pos", "0 0 0.78")

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
            "pos": "0.46 0 1.08",
            "size": "0.025 0.48 0.34",
            "rgba": "0.16 0.18 0.20 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )
    ET.SubElement(
        worldbody,
        "body",
        {
            "name": "inspection_target",
            "mocap": "true",
            "pos": "0.42 -0.16 1.05",
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
            {"name": "inspection_tool_tip_body", "pos": "0.16 0 0"},
        ).append(
            ET.Element(
                "geom",
                {
                    "name": "inspection_tool_tip",
                    "type": "sphere",
                    "size": "0.035",
                    "rgba": "0.9 0.18 0.08 1",
                    "contype": "0",
                    "conaffinity": "0",
                },
            )
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_handle",
                "type": "cylinder",
                "pos": "0.08 0 0",
                "euler": "0 1.5708 0",
                "size": "0.018 0.16",
                "rgba": "0.05 0.05 0.05 1",
                "contype": "0",
                "conaffinity": "0",
            },
        )

    tree.write(DEMO_XML, encoding="unicode")


def joint_qpos_addr(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise RuntimeError(f"Missing joint: {joint_name}")
    return model.jnt_qposadr[joint_id]


def joint_dof_addr(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise RuntimeError(f"Missing joint: {joint_name}")
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


def set_left_arm_idle(model, data):
    values = [
        math.radians(10),
        math.radians(22),
        math.radians(0),
        math.radians(55),
        math.radians(0),
        math.radians(0),
        math.radians(0),
    ]
    for name, value in zip(LEFT_ARM_JOINTS, values):
        set_joint(model, data, name, value)


def clamp_joint_angles(model, data, joint_names):
    for name in joint_names:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if model.jnt_limited[joint_id]:
            low, high = model.jnt_range[joint_id]
            adr = model.jnt_qposadr[joint_id]
            data.qpos[adr] = np.clip(data.qpos[adr], low, high)


make_demo_xml()
model = mujoco.MjModel.from_xml_path(str(DEMO_XML))
data = mujoco.MjData(model)
initial_qpos = data.qpos.copy()

right_dof_ids = np.array([joint_dof_addr(model, name) for name in RIGHT_ARM_JOINTS])
right_qpos_ids = np.array([joint_qpos_addr(model, name) for name in RIGHT_ARM_JOINTS])
tip_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "inspection_tool_tip_body")
target_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "inspection_target")

jacp = np.zeros((3, model.nv))
jacr = np.zeros((3, model.nv))

# Start from a reasonable reaching posture.
initial_right = [
    math.radians(24),
    math.radians(-34),
    math.radians(-18),
    math.radians(95),
    math.radians(0),
    math.radians(-10),
    math.radians(0),
]
for name, value in zip(RIGHT_ARM_JOINTS, initial_right):
    set_joint(model, data, name, value)
set_left_arm_idle(model, data)
mujoco.mj_forward(model, data)

print("G1 right-arm IK inspection demo")
print("-------------------------------")
print("Lower body and torso fixed. Right tool tip follows the green target on the panel.")
print("Close the MuJoCo window to finish.")

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()
    last_print = 0.0

    while viewer.is_running():
        t = time.time() - start
        freeze_non_arm_joints(model, data, initial_qpos)
        set_left_arm_idle(model, data)

        target_pos = np.array([
            0.42,
            -0.16 + 0.13 * math.sin(0.55 * t),
            1.05 + 0.10 * math.sin(0.85 * t),
        ])
        data.mocap_pos[0] = target_pos

        for _ in range(4):
            mujoco.mj_forward(model, data)
            tip_pos = data.xpos[tip_body].copy()
            error = target_pos - tip_pos

            mujoco.mj_jacBody(model, data, jacp, jacr, tip_body)
            j = jacp[:, right_dof_ids]
            damping = 0.06
            dq = j.T @ np.linalg.solve(j @ j.T + damping * np.eye(3), error)
            preferred = np.array([
                math.radians(24),
                math.radians(-34),
                math.radians(-18),
                math.radians(95),
                math.radians(0),
                math.radians(-10),
                math.radians(0),
            ])
            posture_error = preferred - data.qpos[right_qpos_ids]
            dq += 0.015 * posture_error
            dq = np.clip(dq, math.radians(-1.5), math.radians(1.5))
            data.qpos[right_qpos_ids] += 0.35 * dq
            clamp_joint_angles(model, data, RIGHT_ARM_JOINTS)

        mujoco.mj_forward(model, data)

        if t - last_print > 0.25:
            last_print = t
            tip_pos = data.xpos[tip_body].copy()
            dist = np.linalg.norm(target_pos - tip_pos)
            print(
                f"target=({target_pos[0]: .2f}, {target_pos[1]: .2f}, {target_pos[2]: .2f}) "
                f"tool=({tip_pos[0]: .2f}, {tip_pos[1]: .2f}, {tip_pos[2]: .2f}) "
                f"error={dist: .3f}",
                end="\r",
            )

        viewer.sync()
        time.sleep(model.opt.timestep)
