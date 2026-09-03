#!/usr/bin/env python3
"""Deterministic Gate 7 regression trace from a recorded Mink capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Final

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose, parse_mink_arm_sample
from gate7_live_dry_run import Gate7LiveDryRunSession
from gate7_mink_arm_sdk_offline import CollisionPathValidator
from gate7_mink_replay import CaptureSha256, LoadCapture

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "test_results"


def _replace_dual(all_q, dual_q):
    result = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        result[index] = float(value)
    return tuple(result)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def BuildRegressionTrace(capture_path: Path, postroll_s: float) -> dict:
    if not math.isfinite(postroll_s) or postroll_s < 0.0:
        raise ValueError("postroll_s must be finite and non-negative")
    manifest, packets = LoadCapture(capture_path)
    config = load_gate7_config(CONFIG_PATH)
    regular = load_regular_arm_pose(REGULAR_PATH)
    samples = [parse_mink_arm_sample(packet.payload) for packet in packets]
    first_offset = packets[0].offset_s
    offsets = [packet.offset_s - first_offset for packet in packets]
    duration_s = offsets[-1] + postroll_s
    tick_period = 1.0 / config.command_hz
    tick_count = max(1, math.ceil(duration_s * config.command_hz) + 1)
    session = Gate7LiveDryRunSession(
        regular,
        config,
        measured_source="lowstate",
        return_path_validator=CollisionPathValidator(),
    )
    measured = _replace_dual(
        regular.reference_all_joint_q_rad,
        regular.dual_arm_q_rad,
    )
    sample_index = 0
    digest = hashlib.sha256()
    states = Counter()
    transitions: list[dict] = []
    previous_state = None
    candidate_frames = 0
    denied_frames = 0
    final_tick = None

    for tick_index in range(tick_count):
        now_s = tick_index * tick_period
        new_sample = None
        while sample_index < len(samples) and offsets[sample_index] <= now_s + 1.0e-12:
            new_sample = samples[sample_index]
            sample_index += 1
        final_tick = session.Step(
            new_sample,
            measured,
            tick_period,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        state = final_tick.decision.state
        states[state] += 1
        if state != previous_state:
            transitions.append(
                {
                    "tick": tick_index,
                    "time_s": round(now_s, 6),
                    "state": state,
                    "reason": final_tick.decision.reason,
                }
            )
            previous_state = state
        if final_tick.frame is None:
            denied_frames += 1
        else:
            candidate_frames += 1
            measured = _replace_dual(
                measured, final_tick.decision.target_dual_arm_q_rad
            )
        digest_record = {
            "tick": tick_index,
            "state": state,
            "reason": final_tick.decision.reason,
            "frame": final_tick.frame is not None,
            "target": [
                round(value, 9)
                for value in final_tick.decision.target_dual_arm_q_rad
            ],
        }
        digest.update(
            json.dumps(digest_record, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )

    return {
        "schema": "g1.gate7.capture_regression.trace.v1",
        "capture_id": manifest["capture_id"],
        "capture_payload_sha256": CaptureSha256(packets),
        "gate7_config_sha256": _file_sha256(CONFIG_PATH),
        "packet_count": len(packets),
        "tick_count": tick_count,
        "normalized_duration_s": duration_s,
        "postroll_s": postroll_s,
        "trace_sha256": digest.hexdigest(),
        "state_counts": dict(sorted(states.items())),
        "state_transitions": transitions,
        "candidate_frames": candidate_frames,
        "denied_frames": denied_frames,
        "final_state": None if final_tick is None else final_tick.decision.state,
        "final_reason": None if final_tick is None else final_tick.decision.reason,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": False,
    }


def CompareTrace(baseline: dict, current: dict) -> tuple[bool, list[str]]:
    differences = []
    for key in (
        "capture_payload_sha256",
        "gate7_config_sha256",
        "trace_sha256",
        "state_counts",
        "candidate_frames",
        "denied_frames",
        "final_state",
        "final_reason",
    ):
        if baseline.get(key) != current.get(key):
            differences.append(key)
    return not differences, differences


def _automatic_result_path() -> Path:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return RESULT_DIRECTORY / (
        "g1_gate7_capture_regression_"
        + time.strftime("%Y%m%d_%H%M%S")
        + ".json"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate 7 recorded-input regression")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--postroll-s", type=float, default=13.0)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    trace = BuildRegressionTrace(args.capture, args.postroll_s)
    result_path = args.result_json or _automatic_result_path()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    passed = True
    differences: list[str] = []
    mode = "TRACE_ONLY"
    if args.baseline is not None:
        if args.write_baseline:
            args.baseline.parent.mkdir(parents=True, exist_ok=True)
            args.baseline.write_text(json.dumps(trace, indent=2), encoding="utf-8")
            mode = "BASELINE_WRITTEN"
        else:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
            passed, differences = CompareTrace(baseline, trace)
            mode = "BASELINE_COMPARE"
    result = dict(trace)
    result.update(
        schema="g1.gate7.capture_regression.result.v1",
        passed=passed,
        mode=mode,
        baseline=None if args.baseline is None else str(args.baseline.resolve()),
        differences=differences,
    )
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("[PASS] Gate 7 capture regression matched." if passed else "[FAIL] Gate 7 capture regression changed.")
    print(f"Mode: {mode}")
    print(f"Trace SHA256: {trace['trace_sha256']}")
    print(f"States: {trace['state_counts']}")
    if differences:
        print("Changed fields: " + ", ".join(differences))
        print("[ACTION] Review the recorded-input behavior change before hardware use.")
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")
    if args.baseline is not None and args.write_baseline:
        print(f"Baseline saved to: {args.baseline.resolve()}")
    print(f"Result saved to: {result_path.resolve()}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
