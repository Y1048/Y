import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import mujoco.viewer


ROOT = Path(__file__).resolve().parents[1]
G1_DIR = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1"
G1_XML = G1_DIR / "g1_29dof.xml"

tree = ET.parse(G1_XML)
root = tree.getroot()

worldbody = root.find("worldbody")
if worldbody is None:
    raise RuntimeError("No <worldbody> in G1 XML")

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

robot_body = worldbody.find("body")
if robot_body is None:
    raise RuntimeError("No robot body in <worldbody>")

# Remove floating freejoint so the robot torso stays fixed in space.
for joint in list(robot_body.findall("freejoint")):
    robot_body.remove(joint)

# Put the robot at a comfortable standing height for arm-only tests.
robot_body.set("pos", "0 0 0.8")

option = root.find("option")
if option is None:
    option = ET.SubElement(root, "option")
option.set("gravity", "0 0 0")

tmp_path = G1_DIR / "_generated_g1_29dof_fixed_base.xml"
tree.write(tmp_path, encoding="unicode")

model = mujoco.MjModel.from_xml_path(str(tmp_path))
data = mujoco.MjData(model)

print("Loaded fixed-base G1 model:", G1_XML)
print("nq:", model.nq)
print("nv:", model.nv)
print("nu:", model.nu)
print("njnt:", model.njnt)
print("nbody:", model.nbody)
print("This viewer disables gravity and removes the floating base for arm-control practice.")

try:
    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            mujoco.mj_step(model, data)
            viewer.sync()
            time.sleep(model.opt.timestep)
finally:
    try:
        tmp_path.unlink()
    except OSError:
        pass
