import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer


ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"
DEMO_XML = G1_DIR / "_generated_g1_inspection_arm_demo.xml"


LEFT_ARM_JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
]

RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
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

    # Fixed-base, kinematic-looking demo. The real robot will need balance/whole-body control.
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
            "pos": "0.42 -0.58 1.08",
            "size": "0.03 0.34 0.34",
            "rgba": "0.18 0.22 0.26 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )

    right_wrist = find_body(robot_body, "right_wrist_yaw_link")
    if right_wrist is not None:
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_handle",
                "type": "cylinder",
                "pos": "0.05 0 0",
                "euler": "0 1.5708 0",
                "size": "0.025 0.12",
                "rgba": "0.05 0.05 0.05 1",
                "contype": "0",
                "conaffinity": "0",
            },
        )
        ET.SubElement(
            right_wrist,
            "geom",
            {
                "name": "inspection_tool_tip",
                "type": "sphere",
                "pos": "0.18 0 0",
                "size": "0.035",
                "rgba": "0.9 0.18 0.08 1",
                "contype": "0",
                "conaffinity": "0",
            },
        )

    tree.write(DEMO_XML, encoding="unicode")


def qpos_addr(model, joint_name):
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise RuntimeError(f"Missing joint: {joint_name}")
    return model.jnt_qposadr[joint_id]


def set_joint(model, data, joint_name, value):
    data.qpos[qpos_addr(model, joint_name)] = value


def set_arm_pose(model, data, side, pose):
    names = LEFT_ARM_JOINTS if side == "left" else RIGHT_ARM_JOINTS
    for joint_name, value in zip(names, pose):
        set_joint(model, data, joint_name, value)


def freeze_non_arm_joints(model, data, initial_qpos):
    arm_joint_set = set(LEFT_ARM_JOINTS + RIGHT_ARM_JOINTS)
    for i in range(model.njnt):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
        if name not in arm_joint_set:
            adr = model.jnt_qposadr[i]
            # All remaining joints in this fixed-base model are hinge joints.
            data.qpos[adr] = initial_qpos[adr]
    data.qvel[:] = 0.0


make_demo_xml()
model = mujoco.MjModel.from_xml_path(str(DEMO_XML))
data = mujoco.MjData(model)
initial_qpos = data.qpos.copy()

print("G1 inspection arm demo")
print("----------------------")
print("Purpose: lower body/torso fixed, arms perform a facility-inspection motion.")
print("This is a kinematic demo for presentation planning, not a balance controller.")
print("Close the MuJoCo window to finish.")

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()

    while viewer.is_running():
        t = time.time() - start
        sweep = math.sin(0.8 * t)
        small = math.sin(1.7 * t)

        freeze_non_arm_joints(model, data, initial_qpos)

        # Left arm stays as a balancing/support pose.
        left_pose = [
            math.radians(15),
            math.radians(18),
            math.radians(0),
            math.radians(55),
            math.radians(0),
            math.radians(5),
            math.radians(0),
        ]

        # Right arm points the attached inspection tool toward the panel and sweeps slightly.
        right_pose = [
            math.radians(58 + 4 * sweep),
            math.radians(-18),
            math.radians(-36 + 10 * sweep),
            math.radians(78 + 5 * small),
            math.radians(0),
            math.radians(-18 + 5 * sweep),
            math.radians(12 * small),
        ]

        set_arm_pose(model, data, "left", left_pose)
        set_arm_pose(model, data, "right", right_pose)

        mujoco.mj_forward(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)
