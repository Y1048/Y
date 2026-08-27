#!/usr/bin/env python3
"""저장된 Startup Recovery 결과를 MuJoCo Viewer에서 읽기 전용 재생한다.

이 스크립트는 결과 JSON의 관절 경로만 MuJoCo 모델에 적용한다. Unitree SDK,
DDS, UDP 및 로봇 명령 경로를 만들지 않는다.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_RESULT_PATH = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_startup_mink_recovery.json"
)
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "startup_recovery.json"


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay an offline G1 Startup Recovery in MuJoCo only"
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--speed", type=float)
    parser.add_argument("--initial-hold", type=float)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def LoadViewerSettings(config_path: Path) -> tuple[float, float]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    viewer = payload.get("viewer")
    if not isinstance(viewer, dict):
        raise RuntimeError("viewer must be a JSON object")
    speed = float(viewer.get("playback_speed", 1.0))
    initial_hold = float(viewer.get("initial_hold_s", 2.0))
    if not np.isfinite(speed) or speed <= 0.0:
        raise RuntimeError("viewer.playback_speed must be > 0")
    if not np.isfinite(initial_hold) or initial_hold < 0.0:
        raise RuntimeError("viewer.initial_hold_s must be >= 0")
    return speed, initial_hold


def LoadRecovery(result_path: Path) -> tuple[dict, np.ndarray, np.ndarray, list[str]]:
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if payload.get("passed") is not True:
        raise RuntimeError("Startup Recovery result did not pass validation")

    trace = payload.get("trace")
    initial_q = np.asarray(payload.get("initial_q_rad"), dtype=float)
    if initial_q.shape != (7,) or not np.all(np.isfinite(initial_q)):
        raise RuntimeError("Recovery result has no valid 7-joint initial pose")
    if not isinstance(trace, list) or not trace:
        raise RuntimeError("Recovery result has no replay trace")

    times = np.asarray([0.0] + [float(item["time_s"]) for item in trace])
    poses = np.asarray(
        [initial_q.tolist()] + [item["q_rad"] for item in trace],
        dtype=float,
    )
    phases = ["rest_hold"] + [str(item["phase"]) for item in trace]
    if poses.shape != (len(times), 7) or not np.all(np.isfinite(poses)):
        raise RuntimeError("Recovery replay trace must contain finite 7-joint poses")
    if np.any(np.diff(times) <= 0.0):
        raise RuntimeError("Recovery replay timestamps must increase")
    return payload, times, poses, phases


def InterpolatePose(times: np.ndarray, poses: np.ndarray, replay_time: float) -> np.ndarray:
    if replay_time <= float(times[0]):
        return poses[0].copy()
    if replay_time >= float(times[-1]):
        return poses[-1].copy()

    upper = bisect.bisect_right(times, replay_time)
    lower = upper - 1
    duration = float(times[upper] - times[lower])
    alpha = 0.0 if duration <= 0.0 else (replay_time - times[lower]) / duration
    return poses[lower] * (1.0 - alpha) + poses[upper] * alpha


def ApplyRightArmPose(model, data, controller, pose: np.ndarray) -> None:
    for joint_name, joint_value in zip(controller.g1.RIGHT_ARM_JOINTS, pose):
        controller.g1.set_joint(
            model,
            data,
            joint_name,
            float(joint_value),
        )
    mujoco.mj_forward(model, data)


def Main() -> int:
    args = ParseArguments()
    configured_speed, configured_initial_hold = LoadViewerSettings(args.config)
    playback_speed = configured_speed if args.speed is None else args.speed
    initial_hold = (
        configured_initial_hold
        if args.initial_hold is None
        else args.initial_hold
    )
    if playback_speed <= 0.0:
        raise SystemExit("--speed must be > 0")
    if initial_hold < 0.0:
        raise SystemExit("--initial-hold must be >= 0")

    payload, times, poses, phases = LoadRecovery(args.result)
    duration = float(times[-1])
    print("G1 Startup Recovery - MuJoCo replay")
    print("------------------------------------")
    print(f"Result:      {args.result.resolve()}")
    print(f"Validated:   {payload['passed']}")
    print(f"Path:        {duration:.3f} s, {len(poses)} visual samples")
    print(f"Playback:    {playback_speed:.2f}x")
    print("Robot/DDS:   NOT CONNECTED")
    print("Motor command: NONE")

    if args.validate_only:
        print("[PASS] Recovery replay data is valid.")
        return 0

    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller

    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    data = mujoco.MjData(model)
    data.qpos[:] = controller._initial_configuration(model)
    ApplyRightArmPose(model, data, controller, poses[0])

    print(f"[REST_HOLD] Showing measured startup pose for {initial_hold:.1f} s.")
    print("Close the MuJoCo window to finish.")
    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        viewer.cam.lookat[:] = np.asarray([0.0, 0.0, 0.9])
        viewer.cam.distance = 3.0
        viewer.cam.azimuth = 135.0
        viewer.cam.elevation = -12.0
        viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = True
        viewer.sync()

        wall_start = time.monotonic()
        last_phase = "rest_hold"
        finished = False
        while viewer.is_running():
            now = time.monotonic()
            wall_elapsed = now - wall_start
            replay_time = max(0.0, wall_elapsed - initial_hold) * playback_speed
            if replay_time >= duration:
                replay_time = duration
                if not finished:
                    print("[TELEOP_READY] Recovery replay complete; holding final pose.")
                    finished = True

            pose = InterpolatePose(times, poses, replay_time)
            ApplyRightArmPose(model, data, controller, pose)
            phase_index = max(0, bisect.bisect_right(times, replay_time) - 1)
            phase = phases[min(phase_index, len(phases) - 1)]
            if phase != last_phase:
                print(f"[{phase.upper()}] t={replay_time:.2f} s")
                last_phase = phase

            viewer.sync()
            time.sleep(1.0 / 60.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
