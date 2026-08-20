import time
from pathlib import Path

import mujoco
import mujoco.viewer


ROOT = Path(__file__).resolve().parents[1]
G1_SCENE = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1" / "scene_29dof.xml"

if not G1_SCENE.exists():
    raise FileNotFoundError(f"Missing G1 scene file: {G1_SCENE}")

model = mujoco.MjModel.from_xml_path(str(G1_SCENE))
data = mujoco.MjData(model)

print("Loaded:", G1_SCENE)
print("nq:", model.nq)
print("nv:", model.nv)
print("nu:", model.nu)
print("njnt:", model.njnt)
print("nbody:", model.nbody)
print("Press Ctrl+C in this console or close the MuJoCo window to stop.")

with mujoco.viewer.launch_passive(model, data) as viewer:
    while viewer.is_running():
        mujoco.mj_step(model, data)
        viewer.sync()
        time.sleep(model.opt.timestep)
