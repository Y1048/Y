"""Replay a recorded Omni Gateway CSV through the official G1 MuJoCo policy."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import mujoco
import numpy as np
import torch

from evaluate_g1_velocity_direction_mujoco import (
    DECIMATION, DEFAULT, DT, EXPECTED_POLICY_SHA256, run_episode, sha256,
    step_policy, yaw_from_quaternion,
)


def roll_pitch(quaternion):
    w, x, y, z = quaternion
    roll = math.atan2(2.0 * (w * x + y * z),
                      1.0 - 2.0 * (x * x + y * y))
    pitch_value = 2.0 * (w * y - z * x)
    pitch = math.asin(max(-1.0, min(1.0, pitch_value)))
    return roll, pitch


def load_commands(path: Path):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    ready = [row for row in rows if int(row["calibrated"])]
    if len(ready) < 2:
        raise ValueError("CSV has insufficient calibrated samples")
    start = float(ready[0]["receive_monotonic_s"])
    samples = []
    previous = -math.inf
    for row in ready:
        timestamp = float(row["receive_monotonic_s"]) - start
        values = [float(row[key]) for key in ("vx", "vy", "yaw_rate")]
        if timestamp < previous or not all(math.isfinite(x) for x in values):
            raise ValueError("non-monotonic or nonfinite CSV sample")
        # This capture predates the corrected Omni right-positive X -> G1
        # left-positive Y conversion. Reversing stored vy reproduces the fixed
        # Gateway output; vx and yaw already had the correct signs.
        samples.append((timestamp, np.array(
            [values[0], -values[1], values[2]], dtype=np.float32)))
        previous = timestamp
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--warmup-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if sha256(args.policy) != EXPECTED_POLICY_SHA256:
        raise RuntimeError("policy SHA256 mismatch")
    commands = load_commands(args.input_csv)
    policy = torch.jit.load(str(args.policy), map_location="cpu")
    policy.eval()
    model = mujoco.MjModel.from_xml_path(str(args.xml))
    data = mujoco.MjData(model)
    model.opt.timestep = DT
    if model.nu != 12 or model.nq != 19 or model.nv != 18:
        raise RuntimeError("expected official 12-DoF G1 model")
    data.qpos[7:] = DEFAULT
    mujoco.mj_forward(model, data)
    state = (np.zeros(12, dtype=np.float32), DEFAULT.copy())
    counter = 0
    zero = np.zeros(3, dtype=np.float32)
    for _ in range(round(args.warmup_seconds / DT)):
        state, counter = step_policy(model, data, policy, zero, state, counter)

    start_xy = data.qpos[:2].copy()
    start_yaw = yaw_from_quaternion(data.qpos[3:7])
    minimum_height = float(data.qpos[2])
    maximum_abs_roll = 0.0
    maximum_abs_pitch = 0.0
    fell_at = None
    sample_index = 0
    trace = []
    replay_duration = commands[-1][0]
    simulation_steps = math.ceil(replay_duration / DT) + 1
    for step in range(simulation_steps):
        elapsed = step * DT
        while (sample_index + 1 < len(commands) and
               commands[sample_index + 1][0] <= elapsed):
            sample_index += 1
        command = commands[sample_index][1]
        state, counter = step_policy(model, data, policy, command, state, counter)
        height = float(data.qpos[2])
        roll, pitch = roll_pitch(data.qpos[3:7])
        minimum_height = min(minimum_height, height)
        maximum_abs_roll = max(maximum_abs_roll, abs(roll))
        maximum_abs_pitch = max(maximum_abs_pitch, abs(pitch))
        if fell_at is None and (height < 0.55 or abs(roll) > 0.8 or abs(pitch) > 0.8):
            fell_at = elapsed
        if step % DECIMATION == 0:
            trace.append({
                "elapsed_s": elapsed,
                "vx": float(command[0]),
                "vy": float(command[1]),
                "yaw_rate": float(command[2]),
                "world_x_m": float(data.qpos[0]),
                "world_y_m": float(data.qpos[1]),
                "height_m": height,
                "roll_rad": roll,
                "pitch_rad": pitch,
                "yaw_rad": yaw_from_quaternion(data.qpos[3:7]),
            })

    delta = data.qpos[:2] - start_xy
    cosine, sine = math.cos(start_yaw), math.sin(start_yaw)
    summary = {
        "status": "PASS" if fell_at is None else "FALL_DETECTED",
        "simulation_only": True,
        "input_csv": str(args.input_csv),
        "replay_duration_s": replay_duration,
        "body_forward_m": float(cosine * delta[0] + sine * delta[1]),
        "body_left_m": float(-sine * delta[0] + cosine * delta[1]),
        "minimum_height_m": minimum_height,
        "maximum_abs_roll_rad": maximum_abs_roll,
        "maximum_abs_pitch_rad": maximum_abs_pitch,
        "fall_detected_at_s": fell_at,
        "lateral_sign_corrected": True,
    }
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=trace[0].keys())
        writer.writeheader()
        writer.writerows(trace)
    args.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
