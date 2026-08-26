#!/usr/bin/env python3
"""Measure one manually moved G1 right-arm joint from read-only LowState."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from statistics import fmean
from typing import Final

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

from read_only_lowstate import (
    RIGHT_ARM_JOINTS,
    TOPIC_LOWSTATE,
    ReadOnlyG1LowState,
    _read_right_arm,
)


DEFAULT_BASELINE_S: Final[float] = 1.0
DEFAULT_DURATION_S: Final[float] = 8.0
DEFAULT_MIN_EXCURSION_DEG: Final[float] = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY manual joint-motion probe; sends no robot command"
    )
    parser.add_argument("network_interface")
    parser.add_argument("--expected-index", type=int)
    parser.add_argument("--baseline", type=float, default=DEFAULT_BASELINE_S)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/runtime/g1_joint_mapping_probe.json"),
    )
    return parser.parse_args()


def current_positions(monitor: ReadOnlyG1LowState) -> list[float] | None:
    state, _, _ = monitor.snapshot()
    if state is None:
        return None
    return [sample.q_rad for sample in _read_right_arm(state)]


def collect_positions(
    monitor: ReadOnlyG1LowState,
    duration_s: float,
) -> list[list[float]]:
    samples: list[list[float]] = []
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        positions = current_positions(monitor)
        if positions is not None:
            samples.append(positions)
        time.sleep(0.01)
    return samples


def summarize(
    baseline_samples: list[list[float]],
    motion_samples: list[list[float]],
) -> dict[str, object]:
    if not baseline_samples or not motion_samples:
        raise RuntimeError("No LowState samples were received.")

    joint_count = len(RIGHT_ARM_JOINTS)
    baseline = [
        fmean(row[index] for row in baseline_samples)
        for index in range(joint_count)
    ]
    results: list[dict[str, object]] = []
    for list_index, (name, hardware_index) in enumerate(RIGHT_ARM_JOINTS):
        values = [row[list_index] for row in motion_samples]
        min_value = min(values)
        max_value = max(values)
        results.append(
            {
                "name": name,
                "hardware_index": hardware_index,
                "baseline_deg": math.degrees(baseline[list_index]),
                "minimum_deg": math.degrees(min_value),
                "maximum_deg": math.degrees(max_value),
                "excursion_deg": math.degrees(max_value - min_value),
                "final_delta_deg": math.degrees(values[-1] - baseline[list_index]),
            }
        )

    ranked = sorted(results, key=lambda item: float(item["excursion_deg"]), reverse=True)
    return {
        "mode": "READ_ONLY_MANUAL_PROBE",
        "publisher_present": False,
        "command_output_enabled": False,
        "dominant_joint": ranked[0],
        "joints": results,
    }


def main() -> int:
    args = parse_args()
    if args.baseline <= 0.0 or args.duration <= 0.0:
        raise SystemExit("--baseline and --duration must be positive")

    print("G1 right-arm manual joint probe -- READ ONLY", flush=True)
    print(f"DDS interface: {args.network_interface}", flush=True)
    print("DDS publishers: NONE", flush=True)
    print("Motor command: IMPOSSIBLE from this process", flush=True)

    ChannelFactoryInitialize(0, args.network_interface)
    monitor = ReadOnlyG1LowState()
    subscriber = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
    subscriber.Init(monitor.callback, 10)

    wait_deadline = time.monotonic() + 5.0
    while current_positions(monitor) is None and time.monotonic() < wait_deadline:
        time.sleep(0.02)
    if current_positions(monitor) is None:
        raise SystemExit("No rt/lowstate packet received within 5 seconds.")

    print(f"Hold still: collecting {args.baseline:.1f}s baseline...", flush=True)
    baseline_samples = collect_positions(monitor, args.baseline)
    print(
        f"MOVE ONE JOINT NOW for {args.duration:.1f}s, then return it near the start pose.",
        flush=True,
    )
    motion_samples = collect_positions(monitor, args.duration)
    result = summarize(baseline_samples, motion_samples)
    result["network_interface"] = args.network_interface
    result["expected_index"] = args.expected_index

    dominant = result["dominant_joint"]
    excursion = float(dominant["excursion_deg"])
    dominant_index = int(dominant["hardware_index"])
    result["enough_motion"] = excursion >= DEFAULT_MIN_EXCURSION_DEG
    result["expected_index_match"] = (
        args.expected_index is None or dominant_index == args.expected_index
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\nMovement ranking:")
    ranked = sorted(
        result["joints"],
        key=lambda item: float(item["excursion_deg"]),
        reverse=True,
    )
    for item in ranked:
        print(
            f"  {item['hardware_index']:>2} {item['name']:<23} "
            f"range={item['excursion_deg']:>7.2f} deg "
            f"final_delta={item['final_delta_deg']:>7.2f} deg"
        )
    print("No robot command was sent.")

    if not result["enough_motion"]:
        print("[FAIL] Dominant motion was below 5 degrees.")
        return 2
    if not result["expected_index_match"]:
        print(
            f"[FAIL] Expected index {args.expected_index}, "
            f"but index {dominant_index} moved most."
        )
        return 3
    print(f"[PASS] Dominant joint index: {dominant_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
