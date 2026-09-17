"""Headless direction audit for Unitree's official G1 12-DoF velocity policy.

The simulation loop intentionally mirrors unitree_rl_gym's deploy_mujoco.py:
2 ms MuJoCo step, 10-step/50 Hz policy update, 47 observations, 12 actions,
the published default angles, PD gains and command/action scales.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import mujoco
import numpy as np
import torch


EXPECTED_POLICY_SHA256 = (
    "cf668f75b90d1abf73d2b87612a6e76bccc61ff7e083b63582d3f6aaa3c1759d")
DT = 0.002
DECIMATION = 10
DEFAULT = np.array([
    -0.1, 0.0, 0.0, 0.3, -0.2, 0.0,
    -0.1, 0.0, 0.0, 0.3, -0.2, 0.0], dtype=np.float32)
KP = np.array([100, 100, 100, 150, 40, 40,
               100, 100, 100, 150, 40, 40], dtype=np.float32)
KD = np.array([2, 2, 2, 4, 2, 2,
               2, 2, 2, 4, 2, 2], dtype=np.float32)
CMD_SCALE = np.array([2.0, 2.0, 0.25], dtype=np.float32)
ACTION_SCALE = 0.25


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gravity_orientation(quaternion):
    qw, qx, qy, qz = quaternion
    return np.array([
        2.0 * (-qz * qx + qw * qy),
        -2.0 * (qz * qy + qw * qx),
        1.0 - 2.0 * (qw * qw + qz * qz),
    ], dtype=np.float32)


def yaw_from_quaternion(quaternion) -> float:
    w, x, y, z = quaternion
    return math.atan2(2.0 * (w * z + x * y),
                      1.0 - 2.0 * (y * y + z * z))


def wrapped(value: float) -> float:
    return (value + math.pi) % (2.0 * math.pi) - math.pi


def step_policy(model, data, policy, command, state, counter):
    action, target = state
    torque = (target - data.qpos[7:]) * KP - data.qvel[6:] * KD
    data.ctrl[:] = torque
    mujoco.mj_step(model, data)
    counter += 1
    if counter % DECIMATION == 0:
        phase = (counter * DT % 0.8) / 0.8
        observation = np.zeros(47, dtype=np.float32)
        observation[:3] = data.qvel[3:6] * 0.25
        observation[3:6] = gravity_orientation(data.qpos[3:7])
        observation[6:9] = command * CMD_SCALE
        observation[9:21] = data.qpos[7:] - DEFAULT
        observation[21:33] = data.qvel[6:] * 0.05
        observation[33:45] = action
        observation[45:47] = (math.sin(2.0 * math.pi * phase),
                              math.cos(2.0 * math.pi * phase))
        with torch.inference_mode():
            result = policy(torch.from_numpy(observation).unsqueeze(0))
        action = result.detach().cpu().numpy().reshape(-1).astype(np.float32)
        if action.shape != (12,) or not np.isfinite(action).all():
            raise RuntimeError("policy must return 12 finite actions")
        target = DEFAULT + ACTION_SCALE * action
    return (action, target), counter


def run_episode(xml: Path, policy, command, warmup_s: float, command_s: float):
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    model.opt.timestep = DT
    if model.nu != 12 or model.nq != 19 or model.nv != 18:
        raise RuntimeError(
            f"expected official 12-DoF model; got nu={model.nu}, nq={model.nq}, nv={model.nv}")
    data.qpos[7:] = DEFAULT
    mujoco.mj_forward(model, data)
    state = (np.zeros(12, dtype=np.float32), DEFAULT.copy())
    counter = 0
    zero = np.zeros(3, dtype=np.float32)
    for _ in range(round(warmup_s / DT)):
        state, counter = step_policy(model, data, policy, zero, state, counter)
    start_xy = data.qpos[:2].copy()
    start_yaw = yaw_from_quaternion(data.qpos[3:7])
    start_height = float(data.qpos[2])
    minimum_height = start_height
    for _ in range(round(command_s / DT)):
        state, counter = step_policy(model, data, policy, command, state, counter)
        minimum_height = min(minimum_height, float(data.qpos[2]))
    world_delta = data.qpos[:2] - start_xy
    cosine, sine = math.cos(start_yaw), math.sin(start_yaw)
    body_forward = cosine * world_delta[0] + sine * world_delta[1]
    body_left = -sine * world_delta[0] + cosine * world_delta[1]
    yaw_delta = wrapped(yaw_from_quaternion(data.qpos[3:7]) - start_yaw)
    return {
        "command_vx": float(command[0]),
        "command_vy": float(command[1]),
        "command_yaw_rate": float(command[2]),
        "body_forward_m": float(body_forward),
        "body_left_m": float(body_left),
        "yaw_delta_rad": float(yaw_delta),
        "start_height_m": start_height,
        "minimum_height_m": minimum_height,
        "end_height_m": float(data.qpos[2]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup-seconds", type=float, default=2.0)
    parser.add_argument("--command-seconds", type=float, default=4.0)
    parser.add_argument("--magnitude", type=float, default=0.2)
    args = parser.parse_args()
    if sha256(args.policy) != EXPECTED_POLICY_SHA256:
        raise RuntimeError("policy SHA256 does not match deployed velocity policy")
    if not 0.05 <= args.magnitude <= 0.3:
        raise ValueError("magnitude must be in [0.05, 0.3]")
    policy = torch.jit.load(str(args.policy), map_location="cpu")
    policy.eval()
    trials = [
        ("vx_positive", (args.magnitude, 0.0, 0.0)),
        ("vx_negative", (-args.magnitude, 0.0, 0.0)),
        ("vy_positive", (0.0, args.magnitude, 0.0)),
        ("vy_negative", (0.0, -args.magnitude, 0.0)),
        ("yaw_positive", (0.0, 0.0, args.magnitude)),
        ("yaw_negative", (0.0, 0.0, -args.magnitude)),
    ]
    results = []
    for name, values in trials:
        result = run_episode(args.xml, policy, np.array(values, dtype=np.float32),
                             args.warmup_seconds, args.command_seconds)
        result["trial"] = name
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["trial", "command_vx", "command_vy", "command_yaw_rate",
              "body_forward_m", "body_left_m", "yaw_delta_rad",
              "start_height_m", "minimum_height_m", "end_height_m"]
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({"status": "PASS", "output": str(args.output),
                      "simulation_only": True, "trials": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
