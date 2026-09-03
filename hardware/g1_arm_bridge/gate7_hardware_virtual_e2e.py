#!/usr/bin/env python3
"""Virtual end-to-end test of the locked Gate 7 hardware data path.

Synthetic Mink packets traverse the real localhost relay before the Gate 7
controller consumes them with an ideal virtual LowState plant. No Unitree SDK,
DDS entity, publisher or physical command is created.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import (
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from g1_joint_contract import G1_29_JOINT_NAMES
from gate7_live_arm_sdk import (
    AcquireWeight,
    CreateHardwareTrajectoryController,
    LoadLiveHardwareConfig,
    ReleaseWeight,
    ValidateStartPoseExcursion,
)
from gate7_live_dry_run import Gate7LiveDryRunSession
from gate7_mink_arm_sdk_offline import CollisionPathValidator

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BRIDGE_ROOT: Final[Path] = Path(__file__).resolve().parent
CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
HARDWARE_CONFIG_PATH: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_gate7_live_hardware_output.json"
)
REGULAR_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "test_results"


def _replace_dual(all_q, dual_q):
    result = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        result[index] = float(value)
    return tuple(result)


def _packet(
    regular,
    sequence: int,
    *,
    collision: bool = False,
    motion_scale: float = 1.0,
) -> bytes:
    dual = list(regular.dual_arm_q_rad)
    phase = sequence * 0.25
    dual[7] += math.radians(4.0 * motion_scale * math.sin(phase))
    dual[10] += math.radians(6.0 * motion_scale * math.sin(phase + 0.8))
    dual[11] += math.radians(8.0 * motion_scale * math.sin(phase + 1.6))
    all_q = _replace_dual(regular.reference_all_joint_q_rad, dual)
    value = {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": sequence,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": list(all_q),
        "right_arm": {
            "joints": list(all_q[22:29]),
            "active": True,
            "workspace_limited": False,
            "collision_limited": collision,
            "minimum_clearance_m": 0.005 if collision else 0.040,
            "command_state": "active",
        },
        "input_command_mode": "active",
        "session_id": "gate7-virtual-hardware-e2e",
        "input_packet_age_s": 0.0,
        "timestamp": time.time(),
    }
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _automatic_result_path() -> Path:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return RESULT_DIRECTORY / (
        "g1_gate7_hardware_virtual_e2e_"
        + time.strftime("%Y%m%d_%H%M%S")
        + ".json"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Virtual Gate 7 hardware E2E")
    parser.add_argument("--relay-port", type=int, default=5008)
    parser.add_argument("--adapter-port", type=int, default=5013)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--gate7-config", type=Path, default=CONFIG_PATH)
    parser.add_argument(
        "--hardware-config", type=Path, default=HARDWARE_CONFIG_PATH
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not 1 <= args.relay_port <= 65535 or not 1 <= args.adapter_port <= 65535:
        raise ValueError("UDP ports must be within 1..65535")
    result_path = args.result_json or _automatic_result_path()
    result_path.parent.mkdir(parents=True, exist_ok=True)

    gate7_config = load_gate7_config(args.gate7_config)
    hardware_config = LoadLiveHardwareConfig(args.hardware_config)
    regular = load_regular_arm_pose(REGULAR_PATH)
    if gate7_config.hardware_output_authorized:
        raise RuntimeError("Gate 7 algorithm config is not locked")
    if hardware_config.hardware_output_authorized:
        raise RuntimeError("Gate 7 hardware config is not locked")
    motion_scale = min(
        1.0,
        math.degrees(hardware_config.maximum_start_pose_excursion_rad) / 10.0,
    )

    adapter_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    adapter_socket.bind(("127.0.0.1", args.adapter_port))
    adapter_socket.settimeout(2.0)
    relay_result = Path(tempfile.gettempdir()) / (
        f"g1_gate7_virtual_relay_{time.time_ns()}.json"
    )
    relay_command = [
        sys.executable,
        str(BRIDGE_ROOT / "gate7_mink_wsl_relay.py"),
        "--listen-port",
        str(args.relay_port),
        "--target-host",
        "127.0.0.1",
        "--target-port",
        str(args.adapter_port),
        "--duration-s",
        "1.5",
        "--result-json",
        str(relay_result),
    ]
    relay = subprocess.Popen(
        relay_command,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    forwarded_payloads: list[bytes] = []
    try:
        time.sleep(0.25)
        for sequence in range(8):
            payload = _packet(regular, sequence, motion_scale=motion_scale)
            sender.sendto(payload, ("127.0.0.1", args.relay_port))
            if sequence == 2:
                sender.sendto(payload, ("127.0.0.1", args.relay_port))
                sender.sendto(b"not-json", ("127.0.0.1", args.relay_port))
            time.sleep(0.02)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(forwarded_payloads) < 8:
            try:
                payload, _source = adapter_socket.recvfrom(65535)
                forwarded_payloads.append(payload)
            except socket.timeout:
                break
        relay_output, _ = relay.communicate(timeout=3.0)
    finally:
        sender.close()
        adapter_socket.close()
        if relay.poll() is None:
            relay.terminate()
            relay.wait(timeout=2.0)

    if relay.returncode != 0:
        raise RuntimeError("relay process failed:\n" + relay_output)
    relay_summary = json.loads(relay_result.read_text(encoding="utf-8"))
    relay_result.unlink(missing_ok=True)
    samples = [parse_mink_arm_sample(payload) for payload in forwarded_payloads]
    if len(samples) != 8:
        raise RuntimeError(f"forwarded packet count {len(samples)} != 8")
    if relay_summary["rejected_packets"] != 2:
        raise RuntimeError("relay did not reject duplicate and malformed packets")

    collision_validator = CollisionPathValidator()
    trajectory_controller = CreateHardwareTrajectoryController(
        regular,
        gate7_config,
        hardware_config,
        return_path_validator=collision_validator,
    )
    session = Gate7LiveDryRunSession(
        regular,
        gate7_config,
        measured_source="lowstate",
        return_path_validator=collision_validator,
        controller=trajectory_controller,
    )
    session.hold_config = type(session.hold_config)(
        lowstate_timeout_s=hardware_config.lowstate_timeout_s,
        maximum_target_error_rad=gate7_config.maximum_target_error_rad,
    )
    measured = _replace_dual(
        regular.reference_all_joint_q_rad,
        regular.dual_arm_q_rad,
    )

    acquire_weights = [
        AcquireWeight(t, hardware_config.acquire_ramp_s, gate7_config.command_weight)
        for t in (0.0, hardware_config.acquire_ramp_s / 2.0, hardware_config.acquire_ramp_s)
    ]
    active_frames = 0
    maximum_start_pose_excursion_rad = 0.0
    states: list[str] = []
    last_tick = None
    for sample in samples:
        last_tick = session.Step(
            sample,
            measured,
            1.0 / 60.0,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        states.append(last_tick.decision.state)
        if last_tick.frame is not None:
            excursion = ValidateStartPoseExcursion(
                last_tick.frame,
                regular.dual_arm_q_rad,
                hardware_config.maximum_start_pose_excursion_rad,
            )
            maximum_start_pose_excursion_rad = max(
                maximum_start_pose_excursion_rad,
                excursion,
            )
            active_frames += 1
            measured = _replace_dual(measured, last_tick.decision.target_dual_arm_q_rad)

    collision_sample = parse_mink_arm_sample(
        _packet(regular, 8, collision=True, motion_scale=motion_scale)
    )
    collision_tick = session.Step(
        collision_sample,
        measured,
        1.0 / 60.0,
        lowstate_age_s=0.0,
        mode_pr=0,
        mode_machine=5,
    )
    if collision_tick.decision.state != "SAFETY_HOLD":
        raise RuntimeError("collision sample did not enter SAFETY_HOLD")

    timeout_tick = collision_tick
    for _ in range(41):
        timeout_tick = session.Step(
            None,
            measured,
            0.25,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
    if timeout_tick.decision.state != "REGULAR_RETURN":
        raise RuntimeError("10-second unintended hold did not start Regular return")

    stale_session = Gate7LiveDryRunSession(
        regular,
        gate7_config,
        measured_source="lowstate",
        return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
    )
    stale_session.hold_config = session.hold_config
    stale_session.Step(
        samples[0], measured, 0.01, lowstate_age_s=0.0, mode_pr=0, mode_machine=5
    )
    stale_tick = stale_session.Step(
        samples[1],
        measured,
        0.01,
        lowstate_age_s=hardware_config.lowstate_timeout_s + 0.01,
        mode_pr=0,
        mode_machine=5,
    )
    if stale_tick.frame is not None or stale_tick.validation_reason != "lowstate_stale":
        raise RuntimeError("stale LowState did not remove the command frame")

    release_weights = [
        ReleaseWeight(t, hardware_config.release_ramp_s, gate7_config.command_weight)
        for t in (0.0, hardware_config.release_ramp_s / 2.0, hardware_config.release_ramp_s)
    ]
    passed = bool(
        states[0] == "HOLD_CURRENT"
        and "TRACK_MINK_RIGHT" in states
        and active_frames >= 7
        and acquire_weights == [0.0, gate7_config.command_weight / 2.0, gate7_config.command_weight]
        and release_weights == [gate7_config.command_weight, gate7_config.command_weight / 2.0, 0.0]
    )
    result = {
        "schema": "g1.gate7.hardware_virtual_e2e.result.v1",
        "passed": passed,
        "mode": "VIRTUAL_LOWSTATE_ONLY",
        "ports": {"mink_input": args.relay_port, "wsl_adapter_simulated": args.adapter_port},
        "relay": relay_summary,
        "gate7_states": states,
        "active_candidate_frames": active_frames,
        "collision_state": collision_tick.decision.state,
        "collision_reason": collision_tick.decision.reason,
        "timeout_state": timeout_tick.decision.state,
        "timeout_reason": timeout_tick.decision.reason,
        "stale_lowstate_frame_removed": stale_tick.frame is None,
        "stale_lowstate_reason": stale_tick.validation_reason,
        "acquire_weights": acquire_weights,
        "release_weights": release_weights,
        "release_zero_cycles": hardware_config.release_zero_cycles,
        "maximum_start_pose_excursion_deg": math.degrees(
            hardware_config.maximum_start_pose_excursion_rad
        ),
        "maximum_observed_start_pose_excursion_deg": math.degrees(
            maximum_start_pose_excursion_rad
        ),
        "unitree_sdk_imported": False,
        "dds_entity_created": False,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": False,
        "trajectory_generator": hardware_config.trajectory_generator,
        "ruckig_version": hardware_config.ruckig_version,
        "trajectory_scales": {
            "velocity": hardware_config.trajectory_velocity_scale,
            "acceleration": hardware_config.trajectory_acceleration_scale,
            "jerk": hardware_config.trajectory_jerk_scale,
        },
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if passed:
        print("[PASS] Gate 7 virtual hardware E2E completed.")
    else:
        print("[FAIL] Gate 7 virtual hardware E2E acceptance criteria failed.")
    print(f"Relay accepted={relay_summary['accepted_packets']} rejected={relay_summary['rejected_packets']}")
    print(f"Active candidate frames={active_frames}")
    print(f"Collision={collision_tick.decision.state}:{collision_tick.decision.reason}")
    print(f"LowState stale frame removed={stale_tick.frame is None}")
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")
    print(f"Result saved to: {result_path.resolve()}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
