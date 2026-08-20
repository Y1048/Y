import csv
import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


xml = """
<mujoco model="two_link_arm_csv_replay">
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

    <body name="target" mocap="true" pos="0.25 0 0.65">
      <geom type="sphere" size="0.04" rgba="0.1 1.0 0.1 1" contype="0" conaffinity="0"/>
    </body>
  </worldbody>

  <actuator>
    <position name="shoulder_ctrl" joint="shoulder_pitch" kp="70" dampratio="1.5"/>
    <position name="elbow_ctrl" joint="elbow_pitch" kp="60" dampratio="1.5"/>
  </actuator>
</mujoco>
"""


def clamp(value, low, high):
    return max(low, min(high, value))


def solve_planar_ik(x, z, l1=0.45, l2=0.35):
    distance = math.sqrt(x * x + z * z)
    distance = clamp(distance, 0.05, l1 + l2 - 0.02)

    cos_elbow = (distance * distance - l1 * l1 - l2 * l2) / (2.0 * l1 * l2)
    cos_elbow = clamp(cos_elbow, -1.0, 1.0)
    elbow = -math.acos(cos_elbow)

    shoulder_to_target = math.atan2(x, z)
    elbow_offset = math.atan2(l2 * math.sin(elbow), l1 + l2 * math.cos(elbow))
    shoulder = shoulder_to_target - elbow_offset

    shoulder = clamp(shoulder, math.radians(-120), math.radians(120))
    elbow = clamp(elbow, math.radians(-140), math.radians(0))
    return shoulder, elbow


def load_hand_csv(path):
    samples = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append({
                "time": float(row["time"]),
                "left": np.array([
                    float(row["left_x"]),
                    float(row["left_y"]),
                    float(row["left_z"]),
                ]),
            })
    if not samples:
        raise RuntimeError(f"No samples in {path}")
    return samples


def sample_left_position(samples, t):
    duration = samples[-1]["time"]
    t = t % duration

    for i in range(len(samples) - 1):
        a = samples[i]
        b = samples[i + 1]
        if a["time"] <= t <= b["time"]:
            span = b["time"] - a["time"]
            alpha = 0.0 if span <= 0 else (t - a["time"]) / span
            return (1.0 - alpha) * a["left"] + alpha * b["left"]

    return samples[-1]["left"]


csv_path = Path(__file__).resolve().parents[1] / "data" / "fake_hand_tracking.csv"
if not csv_path.exists():
    raise FileNotFoundError(f"Missing {csv_path}. Run generate_fake_hand_data.py first.")

samples = load_hand_csv(csv_path)

model = mujoco.MjModel.from_xml_string(xml)
data = mujoco.MjData(model)

shoulder_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "shoulder_ctrl")
elbow_ctrl = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, "elbow_ctrl")
wrist_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "wrist")

base_pos = np.array([0.0, 0.0, 0.25])
q_cmd = np.array([0.0, math.radians(-70.0)])
filtered_target = samples[0]["left"].copy()

with mujoco.viewer.launch_passive(model, data) as viewer:
    start = time.time()
    last_print = 0.0

    while viewer.is_running():
        t = time.time() - start

        raw_target = sample_left_position(samples, t)
        filtered_target = 0.92 * filtered_target + 0.08 * raw_target
        data.mocap_pos[0] = filtered_target

        rel = filtered_target - base_pos
        q_goal = np.array(solve_planar_ik(rel[0], rel[2]))
        q_cmd = 0.96 * q_cmd + 0.04 * q_goal

        data.ctrl[shoulder_ctrl] = q_cmd[0]
        data.ctrl[elbow_ctrl] = q_cmd[1]

        mujoco.mj_step(model, data)

        if t - last_print > 0.25:
            last_print = t
            wrist_pos = data.xpos[wrist_body].copy()
            error = np.linalg.norm(filtered_target - wrist_pos)
            print(
                f"csv target=({filtered_target[0]: .3f}, {filtered_target[2]: .3f}) "
                f"wrist=({wrist_pos[0]: .3f}, {wrist_pos[2]: .3f}) "
                f"error={error: .3f}",
                end="\r",
            )

        viewer.sync()
        time.sleep(model.opt.timestep)
