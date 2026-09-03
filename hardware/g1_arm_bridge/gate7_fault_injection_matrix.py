#!/usr/bin/env python3
"""Gate 7 fault-injection matrix with no Unitree SDK or robot output."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Final

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import (
    Gate7TeleopController,
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from g1_joint_contract import G1_29_JOINT_NAMES
from gate7_live_dry_run import Gate7LiveDryRunSession
from gate7_mink_replay import LoadCapture
from gate7_mink_wsl_relay import MinkOrderGuard

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "test_results"


def _replace_dual(all_q, dual_q):
    result = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        result[index] = float(value)
    return tuple(result)


def _synthetic_active_value(regular) -> dict:
    dual = list(regular.dual_arm_q_rad)
    dual[7] += math.radians(4.0)
    dual[10] += math.radians(6.0)
    dual[11] += math.radians(8.0)
    all_q = _replace_dual(regular.reference_all_joint_q_rad, dual)
    return {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": 0,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": list(all_q),
        "right_arm": {
            "joints": list(all_q[22:29]),
            "active": True,
            "workspace_limited": False,
            "collision_limited": False,
            "minimum_clearance_m": 0.040,
            "command_state": "active",
        },
        "input_command_mode": "active",
        "session_id": "gate7-fault-matrix",
        "input_packet_age_s": 0.0,
        "timestamp": 0.0,
    }


def _load_active_value(capture_path: Path | None, regular) -> tuple[dict, str]:
    if capture_path is None:
        return _synthetic_active_value(regular), "synthetic"
    _manifest, packets = LoadCapture(capture_path)
    for packet in packets:
        sample = parse_mink_arm_sample(packet.payload)
        if sample.active and sample.input_command_mode == "active":
            return json.loads(packet.payload.decode("utf-8")), str(capture_path.resolve())
    raise ValueError(
        "capture has no active Mink packet; record an engaged VR movement first"
    )


def _payload(value: dict, sequence: int, *, mode: str = "active") -> bytes:
    packet = json.loads(json.dumps(value))
    packet["session_id"] = "gate7-fault-matrix"
    packet["sequence"] = sequence
    packet["timestamp"] = sequence / 250.0
    packet["input_packet_age_s"] = 0.0
    right = packet["right_arm"]
    right["workspace_limited"] = mode == "workspace_exit"
    right["collision_limited"] = mode == "collision"
    right["minimum_clearance_m"] = 0.005 if mode == "collision" else 0.040
    if mode in {"tracking_disengaged", "workspace_exit"}:
        packet["input_command_mode"] = mode
        right["active"] = False
        right["command_state"] = "workspace_fault" if mode == "workspace_exit" else "hold"
    else:
        packet["input_command_mode"] = "active"
        right["active"] = True
        right["command_state"] = "active"
    encoded = json.dumps(packet, separators=(",", ":")).encode("utf-8")
    parse_mink_arm_sample(encoded)
    return encoded


def _new_controller(regular, config):
    return Gate7TeleopController(
        regular,
        config,
        return_path_validator=lambda _trajectory, _all_q: (True, "matrix_path_ok"),
    )


def _establish_tracking(controller, base_value, measured, dt_s):
    first = parse_mink_arm_sample(_payload(base_value, 0))
    second = parse_mink_arm_sample(_payload(base_value, 1))
    controller.step(first, measured, dt_s)
    decision = controller.step(second, measured, dt_s)
    if decision.state != "TRACK_MINK_RIGHT":
        raise RuntimeError("could not establish TRACK_MINK_RIGHT")
    measured = _replace_dual(measured, decision.target_dual_arm_q_rad)
    return measured, decision


def BuildFaultMatrix(capture_path: Path | None = None) -> dict:
    regular = load_regular_arm_pose(REGULAR_PATH)
    config = load_gate7_config(CONFIG_PATH)
    base_value, source = _load_active_value(capture_path, regular)
    dt_s = 1.0 / config.command_hz
    initial_measured = _replace_dual(
        regular.reference_all_joint_q_rad, regular.dual_arm_q_rad
    )
    scenarios: dict[str, dict] = {}

    controller = _new_controller(regular, config)
    measured, decision = _establish_tracking(controller, base_value, initial_measured, dt_s)
    short_ticks = max(1, int((config.input_timeout_s - 2.0 * dt_s) / dt_s))
    for _ in range(short_ticks):
        decision = controller.step(None, measured, dt_s)
    resumed = controller.step(
        parse_mink_arm_sample(_payload(base_value, 2)), measured, dt_s
    )
    scenarios["short_packet_gap"] = {
        "passed": decision.state == "TRACK_MINK_RIGHT" and resumed.state == "TRACK_MINK_RIGHT",
        "gap_s": short_ticks * dt_s,
        "state_before_resume": decision.state,
        "state_after_resume": resumed.state,
    }

    controller = _new_controller(regular, config)
    measured, decision = _establish_tracking(controller, base_value, initial_measured, dt_s)
    frozen_target = decision.target_dual_arm_q_rad
    stale = decision
    while stale.state != "SAFETY_HOLD":
        stale = controller.step(None, measured, dt_s)
    recovered = controller.step(
        parse_mink_arm_sample(_payload(base_value, 2)), measured, dt_s
    )
    scenarios["stale_packet_recovery"] = {
        "passed": (
            stale.reason == "input_stale"
            and stale.target_dual_arm_q_rad == frozen_target
            and recovered.state == "TRACK_MINK_RIGHT"
        ),
        "fault_state": stale.state,
        "fault_reason": stale.reason,
        "target_frozen": stale.target_dual_arm_q_rad == frozen_target,
        "recovered_state": recovered.state,
    }

    for name, mode, expected_reason in (
        ("tracking_loss", "tracking_disengaged", "tracking_loss_hold"),
        ("workspace_exit", "workspace_exit", "workspace_hold"),
        ("collision_limit", "collision", "collision_hold"),
    ):
        controller = _new_controller(regular, config)
        measured, decision = _establish_tracking(
            controller, base_value, initial_measured, dt_s
        )
        frozen_target = decision.target_dual_arm_q_rad
        fault = controller.step(
            parse_mink_arm_sample(_payload(base_value, 2, mode=mode)),
            measured,
            dt_s,
        )
        recovered = controller.step(
            parse_mink_arm_sample(_payload(base_value, 3)), measured, dt_s
        )
        scenarios[name] = {
            "passed": (
                fault.state == "SAFETY_HOLD"
                and fault.reason == expected_reason
                and fault.target_dual_arm_q_rad == frozen_target
                and recovered.state == "TRACK_MINK_RIGHT"
            ),
            "fault_state": fault.state,
            "fault_reason": fault.reason,
            "target_frozen": fault.target_dual_arm_q_rad == frozen_target,
            "recovered_state": recovered.state,
        }

    controller = _new_controller(regular, config)
    measured, _decision = _establish_tracking(
        controller, base_value, initial_measured, dt_s
    )
    transitions = []
    previous_state = controller.state
    final = None
    maximum_ticks = int(
        (config.input_timeout_s + config.unintended_hold_before_regular_return_s + 5.0)
        * config.command_hz
    )
    for tick in range(maximum_ticks):
        final = controller.step(None, measured, dt_s)
        if final.state != previous_state:
            transitions.append(
                {"time_s": round((tick + 1) * dt_s, 4), "state": final.state}
            )
            previous_state = final.state
        measured = _replace_dual(measured, final.target_dual_arm_q_rad)
        if final.state == "REGULAR_HOLD":
            break
    scenarios["persistent_packet_loss"] = {
        "passed": final is not None and final.state == "REGULAR_HOLD",
        "final_state": None if final is None else final.state,
        "final_reason": None if final is None else final.reason,
        "transitions": transitions,
    }

    order = MinkOrderGuard()
    order.Accept("gate7-fault-matrix", 10)
    duplicate_rejected = False
    reordered_rejected = False
    try:
        order.Accept("gate7-fault-matrix", 10)
    except ValueError:
        duplicate_rejected = True
    try:
        order.Accept("gate7-fault-matrix", 9)
    except ValueError:
        reordered_rejected = True
    scenarios["packet_order"] = {
        "passed": duplicate_rejected and reordered_rejected,
        "duplicate_rejected": duplicate_rejected,
        "reordered_rejected": reordered_rejected,
    }

    session = Gate7LiveDryRunSession(
        regular,
        config,
        measured_source="lowstate",
        return_path_validator=lambda _trajectory, _all_q: (True, "matrix_path_ok"),
    )
    session.Step(
        parse_mink_arm_sample(_payload(base_value, 0)),
        initial_measured,
        dt_s,
        lowstate_age_s=0.0,
        mode_pr=0,
        mode_machine=5,
    )
    stale_tick = session.Step(
        parse_mink_arm_sample(_payload(base_value, 1)),
        initial_measured,
        dt_s,
        lowstate_age_s=session.hold_config.lowstate_timeout_s + dt_s,
        mode_pr=0,
        mode_machine=5,
    )
    scenarios["stale_lowstate"] = {
        "passed": stale_tick.frame is None and stale_tick.validation_reason == "lowstate_stale",
        "frame_removed": stale_tick.frame is None,
        "validation_reason": stale_tick.validation_reason,
    }

    passed = all(scenario["passed"] for scenario in scenarios.values())
    return {
        "schema": "g1.gate7.fault_injection_matrix.result.v1",
        "passed": passed,
        "input_source": source,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "unitree_sdk_imported": False,
        "dds_entity_created": False,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": False,
    }


def _automatic_result_path() -> Path:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return RESULT_DIRECTORY / (
        "g1_gate7_fault_matrix_" + time.strftime("%Y%m%d_%H%M%S") + ".json"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate 7 offline fault matrix")
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--result-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = BuildFaultMatrix(args.capture)
    result_path = args.result_json or _automatic_result_path()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for name, scenario in result["scenarios"].items():
        label = "PASS" if scenario["passed"] else "FAIL"
        print(f"[{label}] {name}")
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")
    print(f"Result saved to: {result_path.resolve()}")
    if not result["passed"]:
        print("[ACTION] Keep hardware output locked and inspect the failed scenario.")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
