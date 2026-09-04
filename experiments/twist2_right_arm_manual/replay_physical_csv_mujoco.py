#!/usr/bin/env python3
"""TWIST2 물리 시험 CSV의 실측 29관절을 MuJoCo에서 로컬 재생한다.

Unitree SDK, DDS, 네트워크 소켓 및 로봇 명령을 사용하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
if str(BRIDGE_PATH) not in sys.path:
    sys.path.insert(0, str(BRIDGE_PATH))

from g1_joint_contract import G1_29_JOINT_NAMES
import live_lowstate_mujoco


DEFAULT_CSV = (
    PROJECT_ROOT
    / "logs"
    / "physical_tests"
    / "g1_twist2_right_arm_trial_1787638008.csv"
)


@dataclass(frozen=True)
class PhysicalSample:
    elapsed_s: float
    phase: str
    q_rad: np.ndarray
    dq_rad_s: np.ndarray


def _FiniteValue(row: dict[str, str], name: str, row_number: int) -> float:
    try:
        value = float(row[name])
    except KeyError as exc:
        raise ValueError(f"CSV is missing required column: {name}") from exc
    except ValueError as exc:
        raise ValueError(f"row {row_number} has a non-numeric {name}") from exc
    if not math.isfinite(value):
        raise ValueError(f"row {row_number} has a non-finite {name}")
    return value


def LoadPhysicalCsv(path: Path) -> tuple[PhysicalSample, ...]:
    """CSV를 읽고 29관절과 단조 증가 시간을 검증한다."""
    try:
        stream = path.open(newline="", encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"physical CSV not found: {path}") from exc

    samples: list[PhysicalSample] = []
    with stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("physical CSV has no header")
        required = {"elapsed_s", "phase"}
        required.update(f"q_{index}" for index in range(29))
        required.update(f"dq_{index}" for index in range(29))
        missing = sorted(required.difference(reader.fieldnames))
        if missing:
            raise ValueError("physical CSV is missing columns: " + ", ".join(missing))

        previous_elapsed_s = float("-inf")
        for row_number, row in enumerate(reader, start=2):
            elapsed_s = _FiniteValue(row, "elapsed_s", row_number)
            if elapsed_s < previous_elapsed_s:
                raise ValueError(
                    f"row {row_number} elapsed_s moved backward: "
                    f"{elapsed_s} < {previous_elapsed_s}"
                )
            previous_elapsed_s = elapsed_s
            samples.append(
                PhysicalSample(
                    elapsed_s=elapsed_s,
                    phase=row["phase"].strip(),
                    q_rad=np.asarray(
                        [_FiniteValue(row, f"q_{index}", row_number) for index in range(29)],
                        dtype=float,
                    ),
                    dq_rad_s=np.asarray(
                        [
                            _FiniteValue(row, f"dq_{index}", row_number)
                            for index in range(29)
                        ],
                        dtype=float,
                    ),
                )
            )

    if not samples:
        raise ValueError("physical CSV contains no samples")
    return tuple(samples)


def BuildSummary(samples: tuple[PhysicalSample, ...]) -> dict[str, float | int]:
    """재생 전 확인할 핵심 shoulder-pitch 범위를 계산한다."""
    q22 = np.asarray([sample.q_rad[22] for sample in samples], dtype=float)
    return {
        "sample_count": len(samples),
        "duration_s": samples[-1].elapsed_s - samples[0].elapsed_s,
        "right_shoulder_pitch_start_rad": float(q22[0]),
        "right_shoulder_pitch_end_rad": float(q22[-1]),
        "right_shoulder_pitch_min_rad": float(np.min(q22)),
        "right_shoulder_pitch_max_rad": float(np.max(q22)),
    }


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay measured TWIST2 full-body CSV in MuJoCo without G1"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def Main() -> int:
    args = ParseArguments()
    if not math.isfinite(args.speed) or args.speed <= 0.0:
        raise SystemExit("--speed must be a finite value > 0")

    source = args.source.expanduser().resolve()
    try:
        samples = LoadPhysicalCsv(source)
    except ValueError as exc:
        print(f"[ERROR] Physical CSV replay is unavailable: {exc}")
        print("[ACTION] Copy the complete G1 CSV into logs/physical_tests and retry.")
        return 2

    model, data, _ = live_lowstate_mujoco.LoadModel(show_inspection_scene=False)
    qpos_addresses = live_lowstate_mujoco.ResolveFullBodyQposAddresses(model)
    if tuple(G1_29_JOINT_NAMES) != tuple(
        live_lowstate_mujoco.G1_29_JOINT_NAMES
    ):
        raise RuntimeError("G1 joint contract differs from the MuJoCo viewer")
    live_lowstate_mujoco.ApplyFullBodyPose(
        model,
        data,
        qpos_addresses,
        samples[0].q_rad,
    )

    summary = BuildSummary(samples)
    print("TWIST2 physical CSV - MuJoCo OFFLINE replay")
    print("--------------------------------------------")
    print(f"CSV:              {source}")
    print(f"Samples:          {summary['sample_count']}")
    print(f"Duration:         {summary['duration_s']:.3f} s")
    print(f"Playback speed:   {args.speed:.2f}x")
    print("Joint mapping:    q_0..q_28 -> canonical G1 motor order")
    print("Inspection scene: HIDDEN")
    print("Unitree SDK:      NONE")
    print("DDS/socket:       NONE")
    print("Robot command:    NONE")
    print(
        "Right shoulder:  "
        f"{summary['right_shoulder_pitch_start_rad']:.6f} -> "
        f"{summary['right_shoulder_pitch_end_rad']:.6f} rad "
        f"(range {summary['right_shoulder_pitch_min_rad']:.6f} .. "
        f"{summary['right_shoulder_pitch_max_rad']:.6f})"
    )

    if args.validate_only:
        print("[PASS] CSV schema, values, time order, model, and joint mapping are valid.")
        return 0

    print("Close the MuJoCo window to finish after replay.")
    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        viewer.cam.lookat[:] = np.asarray([0.0, 0.0, 0.9])
        viewer.cam.distance = 3.0
        viewer.cam.azimuth = 135.0
        viewer.cam.elevation = -12.0
        viewer.sync()

        source_start_s = samples[0].elapsed_s
        replay_start_s = time.monotonic()
        sample_index = 0
        while viewer.is_running() and sample_index < len(samples):
            replay_elapsed_s = (time.monotonic() - replay_start_s) * args.speed
            source_elapsed_s = samples[sample_index].elapsed_s - source_start_s
            if replay_elapsed_s < source_elapsed_s:
                time.sleep(min(0.005, max(0.0, source_elapsed_s - replay_elapsed_s)))
                continue
            live_lowstate_mujoco.ApplyFullBodyPose(
                model,
                data,
                qpos_addresses,
                samples[sample_index].q_rad,
            )
            viewer.sync()
            sample_index += 1

        if viewer.is_running():
            print("[COMPLETE] Holding the final measured pose.")
        while viewer.is_running():
            viewer.sync()
            time.sleep(0.01)
    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
