import math
import time

import mujoco
import mujoco.viewer


xml = """
<mujoco model="two_link_arm">
  <option timestep="0.002" gravity="0 0 -9.81"/>

  <default>
    <joint damping="2.0" armature="0.05"/>
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
  </worldbody>

  <actuator>
    <position name="shoulder_ctrl" joint="shoulder_pitch" kp="180" dampratio="1.0"/>
    <position name="elbow_ctrl" joint="elbow_pitch" kp="140" dampratio="1.0"/>
  </actuator>
</mujoco>
"""


model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

shoulder_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "shoulder_ctrl")
elbow_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "elbow_ctrl")
wrist_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "wrist")

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()

    while viewer.is_running():
        t = time.time() - start

        data.ctrl[shoulder_ctrl] = math.radians(35.0) * math.sin(t)
        data.ctrl[elbow_ctrl] = math.radians(-70.0 + 25.0 * math.sin(1.5 * t))

        mujoco.mj_step(model, data)

        if int(t * 10) % 10 == 0:
            wrist_pos = data.xpos[wrist_body]
            print(f"wrist pos: x={wrist_pos[0]: .3f}, y={wrist_pos[1]: .3f}, z={wrist_pos[2]: .3f}", end="\r")

        viewer.sync()
        time.sleep(model.opt.timestep)
