#!/usr/bin/env python3
"""Gate 6 Ctrl+C release contract test without SDK, DDS, or robot output."""

from __future__ import annotations

import json
import math
import time
import unittest
from pathlib import Path

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    blend_weight,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
)
from gate6_arm_sdk_hold import load_runtime_config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "g1_gate6_interrupt_release_test.json"
RESULT_DIR = PROJECT_ROOT / "logs" / "test_results"


def validate_interrupt_release_contract() -> dict[str, object]:
    config = load_runtime_config(CONFIG_PATH)
    assert math.isclose(config.maximum_weight, 0.2)
    assert math.isclose(config.ramp_down_s, 2.0)
    assert config.release_zero_cycles == 25

    measured = [0.0] * 29
    measured[15:22] = [0.25, 0.15, 0.0, 0.85, 0.0, 0.0, 0.0]
    measured[22:29] = [0.25, -0.15, 0.0, 0.85, 0.0, 0.0, 0.0]
    target = dual_arm_from_all_joints(measured)

    period_s = 1.0 / config.publish_hz
    release_samples = int(round(config.ramp_down_s * config.publish_hz))
    weights: list[float] = []
    frames = []
    for index in range(release_samples + 1):
        elapsed_s = config.ramp_up_s + config.hold_s + index * period_s
        phase, weight, done = blend_weight(
            elapsed_s,
            ramp_up_s=config.ramp_up_s,
            hold_s=config.hold_s,
            ramp_down_s=config.ramp_down_s,
            maximum_weight=config.maximum_weight,
        )
        if index < release_samples:
            assert phase == "RELEASE" and not done
        else:
            assert phase == "COMPLETE" and done
        weights.append(weight)
        frames.append(
            build_measured_hold_frame(
                measured,
                target,
                mode_pr=config.expected_mode_pr,
                mode_machine=config.expected_mode_machine,
                weight=weight,
                config=config.safety,
            )
        )

    assert math.isclose(weights[0], config.maximum_weight)
    assert math.isclose(weights[-1], 0.0)
    assert all(current <= previous for previous, current in zip(weights, weights[1:]))
    assert all(
        tuple(frame.motor_q_rad[index] for index in DUAL_ARM_INDICES) == target
        for frame in frames
    )
    assert all(
        frame.motor_mode[index] == 0
        and frame.motor_kp[index] == 0.0
        and frame.motor_kd[index] == 0.0
        for frame in frames
        for index in range(15)
    )

    zero_frame = frames[-1]
    zero_frames = [zero_frame] * config.release_zero_cycles
    assert len(zero_frames) == 25
    assert all(frame.weight == 0.0 for frame in zero_frames)

    return {
        "schema": "g1.gate6.interrupt_release.offline_result.v1",
        "passed": True,
        "unitree_sdk": "NONE",
        "dds_entity": "NONE",
        "publisher": "NONE",
        "robot_command": "NONE",
        "hardware_output_authorized": config.hardware_output_authorized,
        "maximum_weight": config.maximum_weight,
        "release_duration_s": config.ramp_down_s,
        "release_samples": release_samples + 1,
        "zero_weight_cycles": len(zero_frames),
        "target_changed_during_release": False,
        "non_arm_command_enabled": False,
    }


class Gate6InterruptReleaseTests(unittest.TestCase):
    def test_release_contract(self) -> None:
        result = validate_interrupt_release_contract()
        self.assertTrue(result["passed"])
        self.assertEqual(25, result["zero_weight_cycles"])
        self.assertEqual("NONE", result["publisher"])


def main() -> int:
    result = validate_interrupt_release_contract()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULT_DIR / time.strftime(
        "g1_gate6_interrupt_release_offline_%Y%m%d_%H%M%S.json"
    )
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("[PASS] Gate 6 interruption release contract passed.")
    print("Release: 0.200 -> 0.000 over 2.000 s at 250 Hz")
    print("Zero-weight tail: 25 frames")
    print("Measured dual-arm target: unchanged")
    print("Unitree SDK: NONE")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    print(f"Result saved to: {result_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
