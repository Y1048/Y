#!/usr/bin/env python3
"""Decide whether the measured G1 pose can bypass Startup Recovery.

This Windows-side process receives the existing read-only LowState UDP stream,
checks the separately queried MotionSwitcher mode, evaluates a one-second
settling window through Gate 5, and runs the active MuJoCo/Mink collision model.
It creates no DDS endpoint and cannot send a robot command.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import mujoco
import numpy as np

from gate5_lowstate_safety_monitor import (
    MAX_PACKET_BYTES,
    LowStatePacketError,
    LowStateTelemetry,
    PacketOrderTracker,
    evaluate_measured_hold,
    packet_age_s,
    parse_lowstate_telemetry,
)
from g1_joint_contract import G1_29_JOINT_NAMES
from safety_gate import SafetyConfig


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_startup_precheck.json"
DEFAULT_MODE_PATH: Final[Path] = PROJECT_ROOT / "logs" / "runtime" / "g1_motion_mode_query.json"
DEFAULT_RESULT_PATH: Final[Path] = PROJECT_ROOT / "logs" / "runtime" / "g1_startup_precheck.json"
RESULT_SCHEMA: Final[str] = "g1.startup_precheck.result.v1"
MOTION_MODE_SCHEMA: Final[str] = "g1.motion_mode.query.v1"
DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 5007
DEFAULT_STARTUP_TIMEOUT_S: Final[float] = 8.0
EXPECTED_G1_29_JOINT_NAMES: Final[tuple[str, ...]] = G1_29_JOINT_NAMES


@dataclass(frozen=True)
class PrecheckConfig:
    expected_form: str
    expected_name: str
    expected_mode_machine: int
    expected_mode_pr: int
    observation_window_s: float
    minimum_packet_count: int
    maximum_packet_age_s: float
    maximum_pose_span_deg: float
    maximum_velocity_p95_deg_s: float
    minimum_collision_distance_m: float
    maximum_motion_mode_query_age_s: float


@dataclass(frozen=True)
class TimedPacket:
    telemetry: LowStateTelemetry
    age_s: float


@dataclass(frozen=True)
class Blocker:
    code: str
    message: str
    action: str


def _positive_float(value: object, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a positive finite number")
    return number


def load_config(path: Path) -> PrecheckConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.startup_precheck.config.v1":
        raise ValueError("unexpected startup precheck config schema")
    expected = payload.get("expected_motion_mode")
    if not isinstance(expected, dict):
        raise ValueError("expected_motion_mode must be an object")
    form = expected.get("form")
    name = expected.get("name")
    if not isinstance(form, str) or not isinstance(name, str) or not name:
        raise ValueError("expected motion form/name are invalid")
    packet_count = int(payload["minimum_packet_count"])
    if packet_count <= 0:
        raise ValueError("minimum_packet_count must be > 0")
    mode_machine = int(payload["expected_mode_machine"])
    mode_pr = int(payload["expected_mode_pr"])
    if not 0 <= mode_machine <= 255 or not 0 <= mode_pr <= 255:
        raise ValueError("expected mode values must be uint8")
    return PrecheckConfig(
        expected_form=form,
        expected_name=name,
        expected_mode_machine=mode_machine,
        expected_mode_pr=mode_pr,
        observation_window_s=_positive_float(
            payload["observation_window_s"], "observation_window_s"
        ),
        minimum_packet_count=packet_count,
        maximum_packet_age_s=_positive_float(
            payload["maximum_packet_age_s"], "maximum_packet_age_s"
        ),
        maximum_pose_span_deg=_positive_float(
            payload["maximum_pose_span_deg"], "maximum_pose_span_deg"
        ),
        maximum_velocity_p95_deg_s=_positive_float(
            payload["maximum_velocity_p95_deg_s"],
            "maximum_velocity_p95_deg_s",
        ),
        minimum_collision_distance_m=_positive_float(
            payload["minimum_collision_distance_m"],
            "minimum_collision_distance_m",
        ),
        maximum_motion_mode_query_age_s=_positive_float(
            payload["maximum_motion_mode_query_age_s"],
            "maximum_motion_mode_query_age_s",
        ),
    )


def _load_motion_mode(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != MOTION_MODE_SCHEMA:
        raise ValueError("unexpected motion mode query schema")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError("percentile must be between 0 and 1")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def summarize_settling(packets: list[TimedPacket]) -> dict[str, object]:
    q_deg = np.degrees(
        np.asarray([item.telemetry.measured_q_rad for item in packets], dtype=float)
    )
    dq_deg_s = np.abs(
        np.degrees(
            np.asarray(
                [item.telemetry.measured_dq_rad_s for item in packets],
                dtype=float,
            )
        )
    )
    spans = np.max(q_deg, axis=0) - np.min(q_deg, axis=0)
    velocity_p95 = [
        percentile_nearest_rank(dq_deg_s[:, index].tolist(), 0.95)
        for index in range(dq_deg_s.shape[1])
    ]
    return {
        "right_arm_pose_span_deg": spans.tolist(),
        "maximum_right_arm_pose_span_deg": float(np.max(spans)),
        "right_arm_velocity_p95_deg_s": velocity_p95,
        "maximum_right_arm_velocity_p95_deg_s": max(velocity_p95),
    }


def latest_full_body_snapshot(packet: TimedPacket) -> dict[str, object]:
    """Build the persisted 29-joint snapshot from a validated timed packet."""

    telemetry = packet.telemetry
    if (
        telemetry.all_joint_names is None
        or telemetry.all_joint_q_rad is None
        or telemetry.all_joint_dq_rad_s is None
    ):
        raise ValueError("latest LowState packet is missing full 29-joint fields")
    return {
        "latest_all_joint_names": list(telemetry.all_joint_names),
        "latest_all_joint_q_rad": list(telemetry.all_joint_q_rad),
        "latest_all_joint_dq_rad_s": list(telemetry.all_joint_dq_rad_s),
    }


def _collect_packets(
    host: str,
    port: int,
    config: PrecheckConfig,
    startup_timeout_s: float,
) -> tuple[list[TimedPacket], list[str]]:
    tracker = PacketOrderTracker()
    packets: list[TimedPacket] = []
    invalid: list[str] = []
    started = time.monotonic()
    window_deadline: float | None = None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((host, port))
        sock.settimeout(0.10)
        while True:
            now = time.monotonic()
            if window_deadline is not None and now >= window_deadline:
                break
            if window_deadline is None and now - started >= startup_timeout_s:
                raise TimeoutError(
                    f"no valid LowState packet within {startup_timeout_s:.1f}s"
                )
            try:
                payload, _source = sock.recvfrom(MAX_PACKET_BYTES)
            except socket.timeout:
                continue
            received = time.monotonic()
            try:
                packet = parse_lowstate_telemetry(payload)
                tracker.accept(packet)
            except LowStatePacketError as exc:
                invalid.append(str(exc))
                continue
            age = packet_age_s(
                packet,
                received_monotonic=received,
                now_monotonic=received,
                now_unix_ns=time.time_ns(),
            )
            packets.append(TimedPacket(packet, age))
            if window_deadline is None:
                window_deadline = received + config.observation_window_s
    finally:
        sock.close()
    return packets, invalid


def _set_full_body_pose(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    names: tuple[str, ...],
    values: tuple[float, ...],
) -> None:
    data.qpos[:] = model.qpos0.copy()
    for name, value in zip(names, values):
        joint_name = name + "_joint"
        joint_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_JOINT, joint_name
        )
        if joint_id < 0:
            raise RuntimeError(f"MuJoCo joint missing: {joint_name}")
        qpos_id = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_id] = float(value)
    mujoco.mj_forward(model, data)


def evaluate_collision_window(packets: list[TimedPacket]) -> dict[str, object]:
    os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller
    from diagnose_initial_pose_collision import _nearby_pairs

    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    data = mujoco.MjData(model)
    dual_arm_body_names = (
        controller.g1.RIGHT_ARM_BODY_NAMES | controller.g1.LEFT_ARM_BODY_NAMES
    )
    _, geom_pairs = controller._build_collision_pairs(
        model,
        controlled_body_names=dual_arm_body_names,
    )

    worst_distance = float("inf")
    worst_pair: dict[str, object] | None = None
    sample_count = 0
    for timed in packets:
        packet = timed.telemetry
        if (
            packet.all_joint_names is None
            or packet.all_joint_q_rad is None
            or packet.all_joint_dq_rad_s is None
        ):
            raise ValueError("full 29-joint LowState fields are missing")
        if packet.all_joint_names != EXPECTED_G1_29_JOINT_NAMES:
            raise ValueError("full 29-joint name order does not match G1 contract")
        _set_full_body_pose(
            model,
            data,
            packet.all_joint_names,
            packet.all_joint_q_rad,
        )
        nearby = _nearby_pairs(model, data, controller, geom_pairs)
        distance = (
            controller.COLLISION_DETECTION_DISTANCE_M
            if not nearby
            else float(nearby[0]["distance_m"])
        )
        if distance < worst_distance:
            worst_distance = distance
            worst_pair = None if not nearby else dict(nearby[0])
        sample_count += 1

    return {
        "sample_count": sample_count,
        "collision_pair_count": len(geom_pairs),
        "minimum_distance_m": worst_distance,
        "minimum_distance_mm": worst_distance * 1000.0,
        "nearest_pair": worst_pair,
        "distance_is_detection_floor": worst_pair is None,
        "detection_distance_m": controller.COLLISION_DETECTION_DISTANCE_M,
    }


def _append_blocker(
    blockers: list[Blocker], code: str, message: str, action: str
) -> None:
    blockers.append(Blocker(code=code, message=message, action=action))


def evaluate_readiness(
    packets: list[TimedPacket],
    invalid_packets: list[str],
    mode_query: dict[str, object],
    config: PrecheckConfig,
    collision: dict[str, object],
    now_unix_ns: int,
) -> tuple[str, list[Blocker], dict[str, object]]:
    blockers: list[Blocker] = []
    metrics = summarize_settling(packets)

    if invalid_packets:
        _append_blocker(
            blockers,
            "invalid_lowstate_packet",
            f"{len(invalid_packets)} invalid LowState packet(s) were observed",
            "Keep commands disabled; inspect the first packet-contract error.",
        )
    if len(packets) < config.minimum_packet_count:
        _append_blocker(
            blockers,
            "insufficient_lowstate_packets",
            f"received {len(packets)}, require {config.minimum_packet_count}",
            "Verify the 30 Hz UDP forwarder and rerun the precheck.",
        )

    maximum_age = max(item.age_s for item in packets)
    if maximum_age > config.maximum_packet_age_s:
        _append_blocker(
            blockers,
            "stale_lowstate",
            f"maximum packet age {maximum_age:.3f}s exceeds {config.maximum_packet_age_s:.3f}s",
            "Verify Ethernet/DDS latency and rerun; do not use stale state.",
        )

    gate_config = SafetyConfig(lowstate_timeout_s=config.maximum_packet_age_s)
    gate_failures = []
    for item in packets:
        decision = evaluate_measured_hold(
            item.telemetry,
            age_s=item.age_s,
            dt_s=1.0 / 30.0,
            config=gate_config,
        )
        if not decision.allowed:
            gate_failures.append(decision.reason)
    if gate_failures:
        _append_blocker(
            blockers,
            "gate5_rejected_measured_pose",
            gate_failures[0],
            "Use the validated recovery path only after reviewing the rejected joint or state.",
        )

    mode_machine_values = sorted(
        {item.telemetry.mode_machine for item in packets},
        key=lambda value: -1 if value is None else value,
    )
    mode_pr_values = sorted(
        {item.telemetry.mode_pr for item in packets},
        key=lambda value: -1 if value is None else value,
    )
    metrics["mode_machine_values"] = mode_machine_values
    metrics["mode_pr_values"] = mode_pr_values
    if mode_machine_values != [config.expected_mode_machine]:
        _append_blocker(
            blockers,
            "mode_machine_mismatch",
            f"observed {mode_machine_values}, expected {[config.expected_mode_machine]}",
            "Confirm the connected robot model/firmware before continuing.",
        )
    if mode_pr_values != [config.expected_mode_pr]:
        _append_blocker(
            blockers,
            "mode_pr_mismatch",
            f"observed {mode_pr_values}, expected {[config.expected_mode_pr]}",
            "Confirm the G1 joint-layout mode before continuing.",
        )

    query_time = mode_query.get("queried_at_unix_ns")
    query_age_s = float("inf")
    if isinstance(query_time, int) and not isinstance(query_time, bool):
        query_age_s = max(0.0, (now_unix_ns - query_time) / 1e9)
    metrics["motion_mode_query_age_s"] = query_age_s
    actual_mode = (mode_query.get("form"), mode_query.get("name"))
    expected_mode = (config.expected_form, config.expected_name)
    if (
        mode_query.get("operation") != "MotionSwitcherClient.CheckMode"
        or mode_query.get("state_mutation_requested") is not False
        or mode_query.get("motor_command_publisher_present") is not False
        or mode_query.get("command_output_enabled") is not False
    ):
        _append_blocker(
            blockers,
            "unsafe_motion_mode_query_contract",
            "motion mode query does not prove the read-only CheckMode contract",
            "Use query_motion_mode.py; do not substitute a mode-changing RPC.",
        )
    if mode_query.get("result_code") != 0 or actual_mode != expected_mode:
        _append_blocker(
            blockers,
            "regular_mode_required",
            f"MotionSwitcher reported {actual_mode}, expected {expected_mode}",
            "Put G1 in the operator-confirmed Regular Mode and rerun the precheck.",
        )
    if query_age_s > config.maximum_motion_mode_query_age_s:
        _append_blocker(
            blockers,
            "stale_motion_mode_query",
            f"mode query age {query_age_s:.2f}s exceeds {config.maximum_motion_mode_query_age_s:.2f}s",
            "Run CheckMode again immediately before the LowState precheck.",
        )

    if metrics["maximum_right_arm_pose_span_deg"] > config.maximum_pose_span_deg:
        _append_blocker(
            blockers,
            "right_arm_not_settled",
            f"pose span {metrics['maximum_right_arm_pose_span_deg']:.3f} deg exceeds {config.maximum_pose_span_deg:.3f} deg",
            "Keep clear, wait until the arm settles, then rerun the precheck.",
        )
    if (
        metrics["maximum_right_arm_velocity_p95_deg_s"]
        > config.maximum_velocity_p95_deg_s
    ):
        _append_blocker(
            blockers,
            "right_arm_velocity_high",
            f"velocity p95 {metrics['maximum_right_arm_velocity_p95_deg_s']:.3f} deg/s exceeds {config.maximum_velocity_p95_deg_s:.3f} deg/s",
            "Keep clear, wait until the arm settles, then rerun the precheck.",
        )

    minimum_distance = float(collision["minimum_distance_m"])
    if minimum_distance < config.minimum_collision_distance_m:
        _append_blocker(
            blockers,
            "collision_clearance_below_minimum",
            f"clearance {minimum_distance * 1000.0:.2f} mm is below {config.minimum_collision_distance_m * 1000.0:.2f} mm",
            "Do not start teleoperation; use the reviewed Startup Recovery fallback.",
        )

    codes = {item.code for item in blockers}
    if not blockers:
        decision = "DIRECT_TELEOP_READY"
    elif "regular_mode_required" in codes:
        decision = "REGULAR_MODE_REQUIRED"
    elif codes.intersection({"right_arm_not_settled", "right_arm_velocity_high"}):
        decision = "WAIT_AND_RETRY"
    elif codes.intersection(
        {"gate5_rejected_measured_pose", "collision_clearance_below_minimum"}
    ):
        decision = "RECOVERY_REQUIRED"
    else:
        decision = "STARTUP_BLOCKED"
    return decision, blockers, metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 Regular-pose startup precheck"
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--startup-timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT_S)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--motion-mode-json", type=Path, default=DEFAULT_MODE_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("G1 startup readiness precheck -- READ ONLY")
    print("------------------------------------------")
    print("DDS publisher: NONE in this process")
    print("Robot command: IMPOSSIBLE from this process")
    print(f"Result JSON:  {args.output.resolve()}")

    try:
        config = load_config(args.config)
        mode_query = _load_motion_mode(args.motion_mode_json)
        packets, invalid = _collect_packets(
            args.host,
            args.port,
            config,
            args.startup_timeout,
        )
        if not packets:
            raise RuntimeError("no valid LowState packet was collected")
        collision = evaluate_collision_window(packets)
        decision, blockers, metrics = evaluate_readiness(
            packets,
            invalid,
            mode_query,
            config,
            collision,
            time.time_ns(),
        )
    except Exception as exc:
        result = {
            "schema": RESULT_SCHEMA,
            "checked_at_unix_ns": time.time_ns(),
            "decision": "CHECK_FAILED",
            "command_output_enabled": False,
            "publisher_present": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        _write_json(args.output, result)
        print(f"[ERROR] Startup precheck failed: {exc}")
        print("[ACTION] Keep robot commands disabled and inspect the saved error.")
        print(f"Result saved to: {args.output.resolve()}")
        return 2

    result = {
        "schema": RESULT_SCHEMA,
        "checked_at_unix_ns": time.time_ns(),
        "decision": decision,
        "recovery_bypass_allowed": decision == "DIRECT_TELEOP_READY",
        "command_output_enabled": False,
        "publisher_present": False,
        "lowstate_packet_count": len(packets),
        "invalid_packet_count": len(invalid),
        "latest_right_arm_q_rad": list(packets[-1].telemetry.measured_q_rad),
        "latest_right_arm_q_deg": [
            math.degrees(value) for value in packets[-1].telemetry.measured_q_rad
        ],
        **latest_full_body_snapshot(packets[-1]),
        "motion_mode_query": mode_query,
        "metrics": metrics,
        "collision": collision,
        "thresholds": {
            "minimum_packet_count": config.minimum_packet_count,
            "maximum_packet_age_s": config.maximum_packet_age_s,
            "maximum_pose_span_deg": config.maximum_pose_span_deg,
            "maximum_velocity_p95_deg_s": config.maximum_velocity_p95_deg_s,
            "minimum_collision_distance_m": config.minimum_collision_distance_m,
        },
        "blockers": [item.__dict__ for item in blockers],
    }
    _write_json(args.output, result)

    print(f"[{decision}]")
    print(f"LowState packets: {len(packets)}")
    print(
        "Right-arm settled: "
        f"span={metrics['maximum_right_arm_pose_span_deg']:.4f} deg, "
        f"velocity_p95={metrics['maximum_right_arm_velocity_p95_deg_s']:.3f} deg/s"
    )
    print(
        "Collision clearance: "
        f"{collision['minimum_distance_mm']:.2f} mm "
        f"(required {config.minimum_collision_distance_m * 1000.0:.2f} mm)"
    )
    if blockers:
        for blocker in blockers:
            print(f"[BLOCKED] {blocker.code}: {blocker.message}")
            print(f"[ACTION] {blocker.action}")
    else:
        print("Recovery bypass: ALLOWED for the measured startup pose")
        print("Command authorization: NOT GRANTED by this check")
    print(f"Result saved to: {args.output.resolve()}")
    return 0 if decision == "DIRECT_TELEOP_READY" else 10


if __name__ == "__main__":
    sys.exit(main())
