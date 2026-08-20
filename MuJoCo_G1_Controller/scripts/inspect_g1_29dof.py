from pathlib import Path

import mujoco


ROOT = Path(__file__).resolve().parents[1]
G1_SCENE = ROOT / "external" / "unitree_mujoco" / "unitree_robots" / "g1" / "scene_29dof.xml"

model = mujoco.MjModel.from_xml_path(str(G1_SCENE))

print("G1 29DoF model")
print("--------------")
print("scene:", G1_SCENE)
print("nq:", model.nq)
print("nv:", model.nv)
print("nu:", model.nu)
print("njnt:", model.njnt)
print("nbody:", model.nbody)
print()

print("Joints")
print("------")
for i in range(model.njnt):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, i)
    joint_type = model.jnt_type[i]
    qpos_adr = model.jnt_qposadr[i]
    dof_adr = model.jnt_dofadr[i]
    print(f"{i:02d} name={name}, type={joint_type}, qpos_adr={qpos_adr}, dof_adr={dof_adr}")

print()
print("Actuators")
print("---------")
for i in range(model.nu):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
    trnid = model.actuator_trnid[i]
    joint_id = trnid[0]
    joint_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
    ctrl_range = model.actuator_ctrlrange[i]
    print(f"{i:02d} name={name}, joint={joint_name}, ctrlrange={ctrl_range}")

print()
print("Bodies containing arm / wrist / hand")
print("------------------------------------")
for i in range(model.nbody):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
    if name and any(key in name.lower() for key in ["shoulder", "elbow", "wrist", "hand", "left", "right"]):
        print(f"{i:02d} {name}")
