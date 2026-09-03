#!/usr/bin/env python3
"""Replay the engaged window of a Quest/Mink capture directly in MuJoCo."""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from gate7_capture_quality import _decode_capture
from gate7_capture_quality import CONFIG_PATH, REGULAR_PATH
from arm_sdk_hold_contract import DUAL_ARM_INDICES, RIGHT_ARM_INDICES
from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose
from experimental_stateful_gate7_controller import (
    ExperimentalStatefulGate7TeleopController,
)
from live_lowstate_mujoco import (
    ApplyFullBodyPose,
    LoadModel,
    ResolveFullBodyQposAddresses,
)


def SleepUntilStep(
    target_time: float,
    maximum_sleep_s: float,
    *,
    monotonic=time.monotonic,
    sleeper=time.sleep,
) -> bool:
    """Sleep for one bounded positive step; return false once target is due."""
    remaining_s = target_time - monotonic()
    if remaining_s <= 0.0:
        return False
    sleeper(min(maximum_sleep_s, remaining_s))
    return True


def SelectReplayWindow(packets: list[dict], padding_s: float) -> list[dict]:
    active_indices = [
        index
        for index, packet in enumerate(packets)
        if packet["sample"].input_command_mode in {"active", "tracking_disengaged"}
    ]
    if not active_indices:
        raise ValueError("capture has no active or tracking-disengaged packet")
    start_offset = max(0.0, packets[active_indices[0]]["offset_s"] - padding_s)
    end_offset = packets[active_indices[-1]]["offset_s"] + padding_s
    return [
        packet
        for packet in packets
        if start_offset <= packet["offset_s"] <= end_offset
    ]


def _replace_dual(all_q_rad, dual_q_rad) -> tuple[float, ...]:
    result = list(all_q_rad)
    for index, value in zip(DUAL_ARM_INDICES, dual_q_rad):
        result[index] = float(value)
    return tuple(result)


def BuildExperimentalLimitedFrames(
    packets: list[dict],
    padding_s: float,
) -> list[dict]:
    replay_packets = SelectReplayWindow(packets, padding_s)
    window_start_s = replay_packets[0]["offset_s"]
    window_end_s = replay_packets[-1]["offset_s"]
    context_start_s = max(packets[0]["offset_s"], window_start_s - 2.0)
    context_packets = [
        packet
        for packet in packets
        if context_start_s <= packet["offset_s"] <= window_end_s
    ]
    if not context_packets:
        raise ValueError("capture replay context is empty")

    config = load_gate7_config(CONFIG_PATH)
    regular = load_regular_arm_pose(REGULAR_PATH)
    dt_s = 1.0 / config.command_hz
    controller = ExperimentalStatefulGate7TeleopController(
        regular,
        config,
        return_path_validator=lambda _trajectory, _all_q: (True, "replay_path_ok"),
    )
    measured = _replace_dual(
        regular.reference_all_joint_q_rad,
        regular.dual_arm_q_rad,
    )
    sample_index = 0
    frames = []
    duration_s = window_end_s - context_start_s
    tick_count = max(1, math.ceil(duration_s * config.command_hz) + 1)

    for tick_index in range(tick_count):
        absolute_time_s = context_start_s + tick_index * dt_s
        new_sample = None
        while (
            sample_index < len(context_packets)
            and context_packets[sample_index]["offset_s"] <= absolute_time_s + 1.0e-12
        ):
            new_sample = context_packets[sample_index]["sample"]
            sample_index += 1
        decision = controller.step(
            new_sample,
            measured,
            dt_s,
        )
        limited_right_q = decision.target_dual_arm_q_rad[7:14]
        if decision.command_candidate_valid:
            measured = _replace_dual(measured, decision.target_dual_arm_q_rad)
        if absolute_time_s + 1.0e-12 < window_start_s:
            continue
        pose = list(measured)
        for index, value in zip(RIGHT_ARM_INDICES, limited_right_q):
            pose[index] = float(value)
        frames.append(
            {
                "offset_s": absolute_time_s - window_start_s,
                "pose": tuple(pose),
                "state": decision.state,
            }
        )
    if not frames:
        raise ValueError("experimental limited replay produced no frame")
    return frames


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Quest capture in MuJoCo")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--padding-s", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--show-inspection-scene", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--experimental-limiter", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not math.isfinite(args.speed) or args.speed <= 0.0:
        raise ValueError("speed must be finite and positive")
    if not math.isfinite(args.padding_s) or args.padding_s < 0.0:
        raise ValueError("padding-s must be finite and non-negative")
    manifest, packets = _decode_capture(args.capture)
    replay_packets = SelectReplayWindow(packets, args.padding_s)
    if args.experimental_limiter:
        replay_frames = BuildExperimentalLimitedFrames(packets, args.padding_s)
    else:
        first_offset_s = replay_packets[0]["offset_s"]
        replay_frames = [
            {
                "offset_s": packet["offset_s"] - first_offset_s,
                "pose": packet["sample"].all_joint_q_rad,
                "state": packet["sample"].input_command_mode,
            }
            for packet in replay_packets
        ]
    model, data, _controller = LoadModel(args.show_inspection_scene)
    qpos_addresses = ResolveFullBodyQposAddresses(model)
    for frame in replay_frames:
        pose = np.asarray(frame["pose"], dtype=float)
        ApplyFullBodyPose(model, data, qpos_addresses, pose)

    duration_s = replay_frames[-1]["offset_s"] - replay_frames[0]["offset_s"]
    print("G1 Gate 7 Quest capture - MuJoCo OFFLINE replay")
    print("--------------------------------------------------")
    print(f"Capture ID:       {manifest['capture_id']}")
    print(f"Replay frames:    {len(replay_frames)}")
    print(f"Engaged window:   {duration_s:.3f} s")
    print(f"Playback speed:   {args.speed:.2f}x")
    print("Inspection scene: " + ("VISIBLE" if args.show_inspection_scene else "HIDDEN"))
    print(
        "Motion profile:   "
        + ("EXPERIMENTAL STATEFUL LIMITER" if args.experimental_limiter else "RAW MINK")
    )
    print("Unitree SDK:      NONE")
    print("DDS publisher:    NONE")
    print("Robot command:    NONE")
    if args.validate_only:
        print("[PASS] Capture replay model and active window are valid.")
        return 0

    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        viewer.cam.lookat[:] = np.asarray([0.0, 0.0, 0.95])
        viewer.cam.distance = 2.7
        viewer.cam.azimuth = 135.0
        viewer.cam.elevation = -10.0
        print("Close the MuJoCo window to finish.")
        while viewer.is_running():
            started = time.monotonic()
            first_offset = replay_frames[0]["offset_s"]
            for frame in replay_frames:
                if not viewer.is_running():
                    break
                target_time = started + (
                    frame["offset_s"] - first_offset
                ) / args.speed
                while viewer.is_running():
                    viewer.sync()
                    if not SleepUntilStep(target_time, 0.005):
                        break
                ApplyFullBodyPose(
                    model,
                    data,
                    qpos_addresses,
                    np.asarray(frame["pose"], dtype=float),
                )
                viewer.sync()
            if args.once:
                while viewer.is_running():
                    viewer.sync()
                    time.sleep(0.02)
                break
            if viewer.is_running():
                print("[LOOP] Replaying the engaged window again.")
                time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
