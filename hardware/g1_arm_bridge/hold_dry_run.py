#!/usr/bin/env python3
"""Offline/dry-run validator for the future G1 right-arm HOLD phase.

This script sends NO DDS command. It repeatedly feeds a measured right-arm pose
back to the hardware safety gate as the requested HOLD target and verifies that
normal samples are allowed while stale samples are denied.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from safety_gate import SafetyConfig, evaluate_target

DEFAULT_STATE_PATH = Path("logs/runtime/g1_hardware_initial_state.json")
DEFAULT_HZ = 50.0
DEFAULT_DURATION_S = 3.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="G1 HOLD dry-run; sends no robot command")
    parser.add_argument("--state-json", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="use a safe synthetic posture instead of a captured hardware snapshot",
    )
    return parser.parse_args()


def load_pose(args: argparse.Namespace) -> tuple[float, ...]:
    if args.synthetic:
        return tuple(math.radians(value) for value in (10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0))

    payload = json.loads(args.state_json.read_text(encoding="utf-8"))
    values = payload.get("right_arm_q_rad")
    if not isinstance(values, list) or len(values) != 7:
        raise RuntimeError(f"invalid hardware snapshot: {args.state_json}")
    pose = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in pose):
        raise RuntimeError("hardware snapshot contains non-finite joint values")
    return pose


def main() -> int:
    args = parse_args()
    if args.hz <= 0.0 or args.duration <= 0.0:
        raise SystemExit("--hz and --duration must be > 0")

    try:
        measured = load_pose(args)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[ERROR] {exc}")
        print("[INFO] For an offline test without G1, use --synthetic.")
        return 2

    print("G1 right-arm HOLD dry-run")
    print("-------------------------")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    print("Hold target: measured startup q")
    print("q[deg]: " + ", ".join(f"{math.degrees(value):.2f}" for value in measured))

    config = SafetyConfig()
    dt = 1.0 / args.hz
    previous = None
    cycles = max(1, int(round(args.duration * args.hz)))

    for index in range(cycles):
        decision = evaluate_target(
            measured_q_rad=measured,
            requested_q_rad=measured,
            previous_command_q_rad=previous,
            lowstate_age_s=0.0,
            dt_s=dt,
            config=config,
        )
        if not decision.allowed or decision.command_q_rad is None:
            print(f"[FAIL] HOLD denied at cycle {index}: {decision.reason}")
            return 3
        previous = decision.command_q_rad

    stale = evaluate_target(
        measured_q_rad=measured,
        requested_q_rad=measured,
        previous_command_q_rad=previous,
        lowstate_age_s=config.lowstate_timeout_s + 0.001,
        dt_s=dt,
        config=config,
    )
    if stale.allowed or stale.command_q_rad is not None or stale.reason != "lowstate_stale":
        print("[FAIL] stale LowState was not hard-blocked")
        return 4

    print(f"[PASS] {cycles} HOLD cycles accepted at {args.hz:.1f} Hz.")
    print("[PASS] Stale LowState correctly produced no command candidate.")
    print("[PASS] Dry-run complete; no robot command was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
