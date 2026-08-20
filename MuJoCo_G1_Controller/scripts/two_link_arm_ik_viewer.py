import math
import time

import mujoco
import mujoco.viewer
import numpy as np


xml = """
<mujoco model="two_link_arm_ik">
  <option timestep="0.002" gravity="0 0 0" integrator="implicitfast"/>

  <default>
    <joint damping="5.0" armature="0.08"/>
    <geom density="300" rgba="0.35 0.55 0.9 1"/>
  </default>

  <worldbody>
    <light pos="0 0 3"/>
    <geom type="plane" size="2 2 0.02" rgba="0.8 0.9 0.8 1"/>

    <body name="base" pos="0 0 0.25">
      <geom type="sphere" size="0.06" rgba="0.15 0.15 0.15 1"/>

      <body name="upper_arm" pos="0 0 0">
        <joint name="shoulder_pitch" type="hinge" axis="0 1 0" range="-120 120"/>
        <geom type="capsule" fromto="0 0 0 0 0 0.45" size="0.035"/>

        <body name="forearm" pos="0 0 0.45">
          <joint name="elbow_pitch" type="hinge" axis="0 1 0" range="-140 0"/>
          <geom type="capsule" fromto="0 0 0 0 0 0.35" size="0.03" rgba="0.9 0.45 0.25 1"/>

          <body name="wrist" pos="0 0 0.35">
            <geom type="sphere" size="0.045" rgba="0.2 0.8 0.35 1"/>
          </body>
        </body>
      </body>
    </body>

    <body name="target" mocap="true" pos="0.35 0 0.75">
      <geom type="sphere" size="0.04" rgba="0.1 1.0 0.1 1" contype="0" conaffinity="0"/>
    </body>
  </worldbody>

  <actuator>
    <position name="shoulder_ctrl" joint="shoulder_pitch" kp="60" dampratio="1.4"/>
    <position name="elbow_ctrl" joint="elbow_pitch" kp="50" dampratio="1.4"/>
  </actuator>
</mujoco>
"""


def clamp(value, low, high):
    return max(low, min(high, value))


model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

shoulder_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder_pitch")
elbow_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "elbow_pitch")
shoulder_qpos = model.jnt_qposadr[shoulder_joint]
elbow_qpos = model.jnt_qposadr[elbow_joint]

shoulder_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "shoulder_ctrl")
elbow_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "elbow_ctrl")

wrist_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "wrist")
target_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "target")

arm_dof_ids = np.array([
    model.jnt_dofadr[shoulder_joint],
    model.jnt_dofadr[elbow_joint],
])

jacp = np.zeros((3, model.nv))
jacr = np.zeros((3, model.nv))
q_target = np.array([0.0, math.radians(-70.0)])

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()
    last_print = 0.0

    while viewer.is_running():
        t = time.time() - start

        target_pos = np.array([
            0.28 + 0.10 * math.sin(0.35 * t),
            0.0,
            0.62 + 0.08 * math.sin(0.55 * t),
        ])
        data.mocap_pos[0] = target_pos

        mujoco.mj_forward(model, data)
        wrist_pos = data.xpos[wrist_body].copy()
        error = target_pos - wrist_pos

        mujoco.mj_jacBody(model, data, jacp, jacr, wrist_body)
        j = jacp[:, arm_dof_ids]

        damping = 0.25
        dq = j.T @ np.linalg.solve(j @ j.T + damping * np.eye(3), error)
        dq = np.clip(dq, math.radians(-1.0), math.radians(1.0))
        q_target += 0.15 * dq

        q_target[0] = clamp(q_target[0], math.radians(-120), math.radians(120))
        q_target[1] = clamp(q_target[1], math.radians(-140), math.radians(0))

        data.ctrl[shoulder_ctrl] = q_target[0]
        data.ctrl[elbow_ctrl] = q_target[1]

        mujoco.mj_step(model, data)

        if t - last_print > 0.25:
            last_print = t
            dist = np.linalg.norm(error)
            print(
                f"target=({target_pos[0]: .3f}, {target_pos[1]: .3f}, {target_pos[2]: .3f}) "
                f"wrist=({wrist_pos[0]: .3f}, {wrist_pos[1]: .3f}, {wrist_pos[2]: .3f}) "
                f"error={dist: .3f}",
                end="\r",
            )

        viewer.sync()
        time.sleep(model.opt.timestep)
