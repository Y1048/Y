import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer


ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"
FIXED_XML = G1_DIR / "_generated_g1_29dof_fixed_base.xml"


ARM_ACTUATORS = [
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
]


def make_fixed_base_xml():
    tree = ET.parse(G1_XML)
    root = tree.getroot()

    worldbody = root.find("worldbody")
    robot_body = worldbody.find("body")

    ET.SubElement(worldbody, "light", {"pos": "0 -3 4", "dir": "0 1 -1", "diffuse": "0.8 0.8 0.8"})
    ET.SubElement(worldbody, "light", {"pos": "0 3 3", "dir": "0 -1 -1", "diffuse": "0.4 0.4 0.4"})
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "debug_floor",
            "type": "plane",
            "size": "4 4 0.05",
            "rgba": "0.75 0.82 0.88 1",
            "contype": "0",
            "conaffinity": "0",
        },
    )

    for joint in list(robot_body.findall("freejoint")):
        robot_body.remove(joint)

    robot_body.set("pos", "0 0 0.8")

    option = root.find("option")
    if option is None:
        option = ET.SubElement(root, "option")
    option.set("gravity", "0 0 0")

    tree.write(FIXED_XML, encoding="unicode")


def set_ctrl(model, data, actuator_name, value):
    actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
    low, high = model.actuator_ctrlrange[actuator_id]
    data.ctrl[actuator_id] = max(low, min(high, value))


make_fixed_base_xml()
model = mujoco.MjModel.from_xml_path(str(FIXED_XML))
data = mujoco.MjData(model)

print("G1 arm motion test")
print("------------------")
print("This uses the fixed-base, zero-gravity G1 model.")
print("Moving these arm actuators:")
for name in ARM_ACTUATORS:
    actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
    ctrl_range = model.actuator_ctrlrange[actuator_id]
    print(f"- {name}: ctrlrange={ctrl_range}")
print()
print("Close the MuJoCo window to finish.")

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()

    while viewer.is_running():
        t = time.time() - start

        shoulder_wave = 0.45 * math.sin(0.7 * t)
        elbow_wave = 0.75 + 0.35 * math.sin(0.9 * t)
        wrist_wave = 0.35 * math.sin(1.3 * t)

        set_ctrl(model, data, "left_shoulder_pitch", 0.35 + shoulder_wave)
        set_ctrl(model, data, "left_shoulder_roll", 0.25)
        set_ctrl(model, data, "left_shoulder_yaw", 0.15 * math.sin(0.5 * t))
        set_ctrl(model, data, "left_elbow", elbow_wave)
        set_ctrl(model, data, "left_wrist_roll", wrist_wave)
        set_ctrl(model, data, "left_wrist_pitch", 0.20 * math.sin(1.1 * t))
        set_ctrl(model, data, "left_wrist_yaw", 0.20 * math.sin(1.5 * t))

        set_ctrl(model, data, "right_shoulder_pitch", 0.35 + shoulder_wave)
        set_ctrl(model, data, "right_shoulder_roll", -0.25)
        set_ctrl(model, data, "right_shoulder_yaw", -0.15 * math.sin(0.5 * t))
        set_ctrl(model, data, "right_elbow", elbow_wave)
        set_ctrl(model, data, "right_wrist_roll", -wrist_wave)
        set_ctrl(model, data, "right_wrist_pitch", 0.20 * math.sin(1.1 * t))
        set_ctrl(model, data, "right_wrist_yaw", -0.20 * math.sin(1.5 * t))

        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)
