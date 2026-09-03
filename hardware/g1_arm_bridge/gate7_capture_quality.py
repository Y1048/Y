#!/usr/bin/env python3
"""Analyze a recorded Quest/Mink stream without G1, DDS, or robot output."""

from __future__ import annotations

import argparse
import base64
import html
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Final, Iterable

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    RIGHT_ARM_INDICES,
    RIGHT_ARM_JOINT_NAMES,
    RIGHT_ARM_LIMITS_RAD,
)
from arm_sdk_teleop_contract import (
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from gate7_live_dry_run import Gate7LiveDryRunSession
from ruckig_gate7_controller import RuckigGate7TeleopController

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
TELEOP_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "teleop.json"
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "quality"


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, int(math.floor(len(ordered) * fraction)))
    return ordered[index]


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _replace_dual(all_q, dual_q):
    result = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        result[index] = float(value)
    return tuple(result)


def _decode_capture(path: Path) -> tuple[dict, list[dict]]:
    manifest = None
    packets: list[dict] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            schema = record.get("schema")
            if schema == "g1.mink.capture.manifest.v1":
                if manifest is not None or packets:
                    raise ValueError("capture manifest must be the first record")
                if record.get("hardware_output_authorized") is not False:
                    raise ValueError("capture manifest must keep hardware output locked")
                manifest = record
                continue
            if schema != "g1.mink.capture.packet.v1" or manifest is None:
                raise ValueError(f"invalid capture record at line {line_number}")
            payload = base64.b64decode(record["payload_base64"], validate=True)
            sample = parse_mink_arm_sample(payload)
            if int(record["index"]) != len(packets):
                raise ValueError(f"capture packet index gap at line {line_number}")
            offset_s = float(record["offset_s"])
            if not math.isfinite(offset_s) or offset_s < 0.0:
                raise ValueError("capture offset must be finite and non-negative")
            if packets and offset_s < packets[-1]["offset_s"]:
                raise ValueError("capture offsets must be monotonic")
            packets.append(
                {
                    "offset_s": offset_s,
                    "sample": sample,
                    "value": json.loads(payload.decode("utf-8")),
                }
            )
    if manifest is None or not packets:
        raise ValueError("capture must contain a manifest and at least one packet")
    return manifest, packets


def _series_metrics(values: list[list[float]]) -> list[dict]:
    metrics = []
    for joint_values in values:
        metrics.append(
            {
                "p95_abs": _round(_percentile((abs(v) for v in joint_values), 0.95)),
                "p95_abs_nonzero": _round(
                    _percentile(
                        (abs(v) for v in joint_values if abs(v) > 1.0e-9),
                        0.95,
                    )
                ),
                "max_abs": _round(max((abs(v) for v in joint_values), default=0.0)),
            }
        )
    return metrics


def _raw_metrics(packets: list[dict], input_timeout_s: float) -> dict:
    offsets = [packet["offset_s"] for packet in packets]
    gaps = [current - previous for previous, current in zip(offsets, offsets[1:])]
    modes = Counter(packet["sample"].input_command_mode for packet in packets)
    positions = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    velocities = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    accelerations = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    jerks = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    position_errors = []
    orientation_errors = []
    clearances = []
    wrist_margins = []
    active_workspace_limited_packets = 0
    active_collision_limited_packets = 0
    active_segments = []
    segment = None
    previous = None
    previous_velocity = None
    previous_acceleration = None
    zero_dt_active_intervals = 0

    for packet in packets:
        sample = packet["sample"]
        value = packet["value"]
        right = value["right_arm"]
        if not (sample.active and sample.input_command_mode == "active"):
            if segment is not None:
                active_segments.append(segment)
                segment = None
            previous = None
            previous_velocity = None
            previous_acceleration = None
            continue

        offset_s = packet["offset_s"]
        active_workspace_limited_packets += int(sample.workspace_limited)
        active_collision_limited_packets += int(sample.collision_limited)
        if (
            previous is None
            or sample.session_id != previous["sample"].session_id
            or offset_s - previous["offset_s"] > input_timeout_s
        ):
            if segment is not None:
                active_segments.append(segment)
            segment = {
                "start_s": offset_s,
                "end_s": offset_s,
                "packets": 0,
            }
            previous = None
            previous_velocity = None
            previous_acceleration = None

        segment["end_s"] = offset_s
        segment["packets"] += 1
        for index, q_rad in enumerate(sample.right_arm_q_rad):
            positions[index].append(math.degrees(q_rad))
        if right.get("position_error") is not None:
            position_errors.append(float(right["position_error"]))
        if right.get("orientation_error_deg") is not None:
            orientation_errors.append(float(right["orientation_error_deg"]))
        if sample.minimum_clearance_m is not None:
            clearances.append(float(sample.minimum_clearance_m))
        if right.get("min_wrist_limit_margin_deg") is not None:
            wrist_margins.append(float(right["min_wrist_limit_margin_deg"]))

        if previous is not None:
            dt_s = offset_s - previous["offset_s"]
            if dt_s <= 0.0:
                # 같은 수신 시각의 패킷은 자세 통계에 유지하되 미분값을 만들지 않는다.
                zero_dt_active_intervals += 1
                previous = packet
                previous_velocity = None
                previous_acceleration = None
                continue
            velocity = [
                math.degrees((current - old) / dt_s)
                for current, old in zip(
                    sample.right_arm_q_rad,
                    previous["sample"].right_arm_q_rad,
                )
            ]
            for index, value_deg_s in enumerate(velocity):
                velocities[index].append(value_deg_s)
            if previous_velocity is not None:
                acceleration = [
                    (current - old) / dt_s
                    for current, old in zip(velocity, previous_velocity)
                ]
                for index, value_deg_s2 in enumerate(acceleration):
                    accelerations[index].append(value_deg_s2)
                if previous_acceleration is not None:
                    jerk = [
                        (current - old) / dt_s
                        for current, old in zip(acceleration, previous_acceleration)
                    ]
                    for index, value_deg_s3 in enumerate(jerk):
                        jerks[index].append(value_deg_s3)
                previous_acceleration = acceleration
            previous_velocity = velocity
        previous = packet

    if segment is not None:
        active_segments.append(segment)
    for item in active_segments:
        item["start_s"] = _round(item["start_s"], 3)
        item["end_s"] = _round(item["end_s"], 3)
        item["duration_s"] = _round(item["end_s"] - item["start_s"], 3)

    velocity_metrics = _series_metrics(velocities)
    acceleration_metrics = _series_metrics(accelerations)
    jerk_metrics = _series_metrics(jerks)
    joints = []
    for index, name in enumerate(RIGHT_ARM_JOINT_NAMES):
        q_values = positions[index]
        lower, upper = RIGHT_ARM_LIMITS_RAD[index]
        minimum = min(q_values) if q_values else None
        maximum = max(q_values) if q_values else None
        margin = None
        if minimum is not None and maximum is not None:
            margin = min(minimum - math.degrees(lower), math.degrees(upper) - maximum)
        joints.append(
            {
                "name": name,
                "min_deg": _round(minimum),
                "max_deg": _round(maximum),
                "range_deg": _round(None if minimum is None else maximum - minimum),
                "minimum_model_limit_margin_deg": _round(margin),
                "raw_velocity_deg_s": velocity_metrics[index],
                "raw_acceleration_deg_s2": acceleration_metrics[index],
                "raw_jerk_deg_s3": jerk_metrics[index],
            }
        )

    duration_s = offsets[-1] - offsets[0]
    return {
        "packet_count": len(packets),
        "zero_dt_active_intervals": zero_dt_active_intervals,
        "duration_s": _round(duration_s, 3),
        "mean_packet_rate_hz": _round((len(packets) - 1) / duration_s, 3),
        "packet_gap_ms": {
            "mean": _round(1000.0 * sum(gaps) / len(gaps), 3),
            "p95": _round(1000.0 * _percentile(gaps, 0.95), 3),
            "max": _round(1000.0 * max(gaps), 3),
        },
        "command_modes": dict(sorted(modes.items())),
        "workspace_limited_packets": sum(
            packet["sample"].workspace_limited for packet in packets
        ),
        "collision_limited_packets": sum(
            packet["sample"].collision_limited for packet in packets
        ),
        "active_workspace_limited_packets": active_workspace_limited_packets,
        "active_collision_limited_packets": active_collision_limited_packets,
        "active_segments": active_segments,
        "active_packet_count": sum(item["packets"] for item in active_segments),
        "active_duration_s": _round(sum(item["duration_s"] for item in active_segments), 3),
        "position_error_m": {
            "p95": _round(_percentile(position_errors, 0.95), 5),
            "max": _round(max(position_errors, default=0.0), 5),
        },
        "orientation_error_deg": {
            "p95": _round(_percentile(orientation_errors, 0.95), 3),
            "max": _round(max(orientation_errors, default=0.0), 3),
        },
        "minimum_clearance_m": _round(min(clearances), 5) if clearances else None,
        "minimum_wrist_limit_margin_deg": _round(min(wrist_margins), 3) if wrist_margins else None,
        "joints": joints,
    }


def _gate7_metrics(
    packets: list[dict],
    config,
    regular,
    *,
    velocity_scale: float = 1.25,
    acceleration_scale: float = 3.0,
    jerk_scale: float = 6.0,
) -> dict:
    samples = [packet["sample"] for packet in packets]
    first_offset = packets[0]["offset_s"]
    offsets = [packet["offset_s"] - first_offset for packet in packets]
    duration_s = offsets[-1] + 13.0
    dt_s = 1.0 / config.command_hz
    tick_count = max(1, math.ceil(duration_s * config.command_hz) + 1)
    session = Gate7LiveDryRunSession(
        regular,
        config,
        measured_source="lowstate",
        return_path_validator=lambda _trajectory, _all_q: (True, "quality_path_ok"),
    )
    measured = _replace_dual(regular.reference_all_joint_q_rad, regular.dual_arm_q_rad)
    experimental_controller = RuckigGate7TeleopController(
        regular,
        config,
        return_path_validator=lambda _trajectory, _all_q: (True, "quality_path_ok"),
        velocity_scale=velocity_scale,
        acceleration_scale=acceleration_scale,
        jerk_scale=jerk_scale,
    )
    experimental_measured = measured
    sample_index = 0
    states = Counter()
    targets = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    velocities = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    accelerations = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    jerks = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    previous_q = None
    previous_velocity = None
    previous_acceleration = None
    limited_targets = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    limited_velocities = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    limited_accelerations = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    limited_jerks = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    limited_tracking_errors = [[] for _ in RIGHT_ARM_JOINT_NAMES]
    previous_limited_q = None
    previous_limited_velocity = None
    previous_limited_acceleration = None
    for tick_index in range(tick_count):
        now_s = tick_index * dt_s
        new_sample = None
        while sample_index < len(samples) and offsets[sample_index] <= now_s + 1.0e-12:
            new_sample = samples[sample_index]
            sample_index += 1
        tick = session.Step(
            new_sample,
            measured,
            dt_s,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        experimental_decision = experimental_controller.step(
            new_sample,
            experimental_measured,
            dt_s,
        )
        states[tick.decision.state] += 1
        right_q = tuple(tick.decision.target_dual_arm_q_rad[7:14])
        limited_right_q = tuple(experimental_decision.target_dual_arm_q_rad[7:14])
        for index, q_rad in enumerate(right_q):
            targets[index].append(math.degrees(q_rad))
        for index, (q_rad, target_q_rad) in enumerate(
            zip(limited_right_q, right_q)
        ):
            limited_targets[index].append(math.degrees(q_rad))
            if experimental_decision.state == "TRACK_MINK_RIGHT":
                limited_tracking_errors[index].append(
                    math.degrees(abs(target_q_rad - q_rad))
                )
        if previous_q is not None:
            velocity = [
                math.degrees((current - old) / dt_s)
                for current, old in zip(right_q, previous_q)
            ]
            for index, value in enumerate(velocity):
                velocities[index].append(value)
            if previous_velocity is not None:
                acceleration = [
                    (current - old) / dt_s
                    for current, old in zip(velocity, previous_velocity)
                ]
                for index, value in enumerate(acceleration):
                    accelerations[index].append(value)
                if previous_acceleration is not None:
                    jerk = [
                        (current - old) / dt_s
                        for current, old in zip(acceleration, previous_acceleration)
                    ]
                    for index, value in enumerate(jerk):
                        jerks[index].append(value)
                previous_acceleration = acceleration
            previous_velocity = velocity
        previous_q = right_q
        if previous_limited_q is not None:
            limited_velocity = [
                math.degrees((current - old) / dt_s)
                for current, old in zip(limited_right_q, previous_limited_q)
            ]
            for index, value in enumerate(limited_velocity):
                limited_velocities[index].append(value)
            if previous_limited_velocity is not None:
                limited_acceleration = [
                    (current - old) / dt_s
                    for current, old in zip(
                        limited_velocity,
                        previous_limited_velocity,
                    )
                ]
                for index, value in enumerate(limited_acceleration):
                    limited_accelerations[index].append(value)
                if previous_limited_acceleration is not None:
                    limited_jerk = [
                        (current - old) / dt_s
                        for current, old in zip(
                            limited_acceleration,
                            previous_limited_acceleration,
                        )
                    ]
                    for index, value in enumerate(limited_jerk):
                        limited_jerks[index].append(value)
                previous_limited_acceleration = limited_acceleration
            previous_limited_velocity = limited_velocity
        previous_limited_q = limited_right_q
        if tick.frame is not None:
            measured = _replace_dual(measured, tick.decision.target_dual_arm_q_rad)
        if experimental_decision.command_candidate_valid:
            experimental_measured = _replace_dual(
                experimental_measured,
                experimental_decision.target_dual_arm_q_rad,
            )

    velocity_metrics = _series_metrics(velocities)
    acceleration_metrics = _series_metrics(accelerations)
    jerk_metrics = _series_metrics(jerks)
    limited_velocity_metrics = _series_metrics(limited_velocities)
    limited_acceleration_metrics = _series_metrics(limited_accelerations)
    limited_jerk_metrics = _series_metrics(limited_jerks)
    limited_tracking_error_metrics = _series_metrics(limited_tracking_errors)
    joints = []
    limited_joints = []
    acceleration_violations = 0
    jerk_violations = 0
    limited_velocity_violations = 0
    limited_acceleration_violations = 0
    limited_jerk_violations = 0
    for index, name in enumerate(RIGHT_ARM_JOINT_NAMES):
        proximal = index < 4
        velocity_limit = math.degrees(
            config.proximal_max_velocity_rad_s
            if proximal
            else config.wrist_max_velocity_rad_s
        )
        acceleration_limit = math.degrees(
            config.proximal_max_acceleration_rad_s2
            if proximal
            else config.wrist_max_acceleration_rad_s2
        )
        jerk_limit = math.degrees(
            config.proximal_max_jerk_rad_s3
            if proximal
            else config.wrist_max_jerk_rad_s3
        )
        acceleration_violations += sum(
            abs(value) > acceleration_limit + 1.0e-6
            for value in accelerations[index]
        )
        jerk_violations += sum(
            abs(value) > jerk_limit + 1.0e-6 for value in jerks[index]
        )
        limited_velocity_violations += sum(
            abs(value)
            > math.degrees(experimental_controller.velocity_limits_rad_s[7 + index])
            + 1.0e-6
            for value in limited_velocities[index]
        )
        limited_acceleration_violations += sum(
            abs(value)
            > math.degrees(
                experimental_controller.acceleration_limits_rad_s2[7 + index]
            )
            + 1.0e-6
            for value in limited_accelerations[index]
        )
        limited_jerk_violations += sum(
            abs(value)
            > math.degrees(experimental_controller.jerk_limits_rad_s3[7 + index])
            + 1.0e-5
            for value in limited_jerks[index]
        )
        joints.append(
            {
                "name": name,
                "target_min_deg": _round(min(targets[index])),
                "target_max_deg": _round(max(targets[index])),
                "velocity_limit_deg_s": _round(velocity_limit),
                "velocity_deg_s": velocity_metrics[index],
                "acceleration_limit_deg_s2": _round(acceleration_limit),
                "acceleration_deg_s2": acceleration_metrics[index],
                "jerk_limit_deg_s3": _round(jerk_limit),
                "jerk_deg_s3": jerk_metrics[index],
            }
        )
        limited_joints.append(
            {
                "name": name,
                "target_min_deg": _round(min(limited_targets[index])),
                "target_max_deg": _round(max(limited_targets[index])),
                "velocity_limit_deg_s": _round(
                    math.degrees(
                        experimental_controller.velocity_limits_rad_s[7 + index]
                    )
                ),
                "velocity_deg_s": limited_velocity_metrics[index],
                "acceleration_limit_deg_s2": _round(
                    math.degrees(
                        experimental_controller.acceleration_limits_rad_s2[7 + index]
                    )
                ),
                "acceleration_deg_s2": limited_acceleration_metrics[index],
                "jerk_limit_deg_s3": _round(
                    math.degrees(
                        experimental_controller.jerk_limits_rad_s3[7 + index]
                    )
                ),
                "jerk_deg_s3": limited_jerk_metrics[index],
                "baseline_tracking_error_deg": limited_tracking_error_metrics[index],
            }
        )
    return {
        "command_hz": config.command_hz,
        "tick_count": tick_count,
        "state_counts": dict(sorted(states.items())),
        "acceleration_limit_exceedance_ticks": acceleration_violations,
        "jerk_limit_exceedance_ticks": jerk_violations,
        "joints": joints,
        "experimental_stateful_limiter": {
            "engine": "ruckig",
            "version": "0.19.4",
            "velocity_scale": experimental_controller.velocity_scale,
            "acceleration_scale": experimental_controller.acceleration_scale,
            "jerk_scale": experimental_controller.jerk_scale,
            "velocity_limit_exceedance_ticks": limited_velocity_violations,
            "acceleration_limit_exceedance_ticks": limited_acceleration_violations,
            "jerk_limit_exceedance_ticks": limited_jerk_violations,
            "joints": limited_joints,
        },
    }


def _issues(raw: dict, gate7: dict, config, teleop_config: dict) -> list[dict]:
    issues = []
    if raw["packet_gap_ms"]["max"] > config.input_timeout_s * 1000.0:
        issues.append(
            {
                "severity": "warning",
                "code": "packet_gap_exceeds_watchdog",
                "message": "At least one recorded packet gap exceeded the Gate 7 input watchdog.",
            }
        )
    if raw["active_workspace_limited_packets"]:
        issues.append(
            {
                "severity": "warning",
                "code": "workspace_limited",
                "message": (
                    "Workspace limiting appeared in "
                    f"{raw['active_workspace_limited_packets']} active packets."
                ),
            }
        )
    if raw["active_collision_limited_packets"]:
        issues.append(
            {
                "severity": "warning",
                "code": "collision_limited",
                "message": (
                    "Collision limiting appeared in "
                    f"{raw['active_collision_limited_packets']} active packets."
                ),
            }
        )
    if (
        raw["minimum_clearance_m"] is not None
        and raw["minimum_clearance_m"] < config.minimum_collision_clearance_m
    ):
        issues.append(
            {
                "severity": "warning",
                "code": "clearance_below_gate7_minimum",
                "message": "Recorded Mink clearance fell below the Gate 7 minimum.",
            }
        )
    position_threshold = float(
        teleop_config["ik"]["fallback"]["position_error_enter_m"]
    )
    rotation_threshold = float(
        teleop_config["ik"]["fallback"]["rotation_error_enter_deg"]
    )
    if (
        raw["position_error_m"]["p95"] is not None
        and raw["position_error_m"]["p95"] > position_threshold
    ):
        issues.append(
            {
                "severity": "review",
                "code": "ik_position_error_high",
                "message": (
                    f"Active IK position-error p95 is {raw['position_error_m']['p95']} m, "
                    f"above the configured fallback threshold {position_threshold} m."
                ),
            }
        )
    if (
        raw["orientation_error_deg"]["p95"] is not None
        and raw["orientation_error_deg"]["p95"] > rotation_threshold
    ):
        issues.append(
            {
                "severity": "review",
                "code": "ik_orientation_error_high",
                "message": (
                    f"Active IK orientation-error p95 is {raw['orientation_error_deg']['p95']} deg, "
                    f"above the configured fallback threshold {rotation_threshold} deg."
                ),
            }
        )
    if (
        raw["minimum_wrist_limit_margin_deg"] is not None
        and raw["minimum_wrist_limit_margin_deg"] <= 0.0
    ):
        issues.append(
            {
                "severity": "review",
                "code": "wrist_limit_margin_exhausted",
                "message": "At least one active packet reached zero wrist joint-limit margin.",
            }
        )
    if gate7["acceleration_limit_exceedance_ticks"]:
        issues.append(
            {
                "severity": "review",
                "code": "active_acceleration_not_limited",
                "message": (
                    "Gate 7 target finite differences exceed the configured acceleration "
                    "limit; the active path currently rate-limits position by velocity only."
                ),
            }
        )
    if gate7["jerk_limit_exceedance_ticks"]:
        issues.append(
            {
                "severity": "review",
                "code": "active_jerk_not_limited",
                "message": (
                    "Gate 7 target finite differences exceed the configured jerk limit; "
                    "review before enabling physical output."
                ),
            }
        )
    experimental = gate7["experimental_stateful_limiter"]
    if any(
        experimental[key]
        for key in (
            "velocity_limit_exceedance_ticks",
            "acceleration_limit_exceedance_ticks",
            "jerk_limit_exceedance_ticks",
        )
    ):
        issues.append(
            {
                "severity": "review",
                "code": "experimental_limiter_violation",
                "message": (
                    "The experimental stateful limiter exceeded at least one configured "
                    "derivative limit and is not acceptable for integration."
                ),
            }
        )
    return issues


def BuildQualityReport(
    capture_path: Path,
    *,
    velocity_scale: float = 1.25,
    acceleration_scale: float = 3.0,
    jerk_scale: float = 6.0,
) -> dict:
    manifest, packets = _decode_capture(capture_path)
    config = load_gate7_config(CONFIG_PATH)
    regular = load_regular_arm_pose(REGULAR_PATH)
    teleop_config = json.loads(TELEOP_CONFIG_PATH.read_text(encoding="utf-8"))
    raw = _raw_metrics(packets, config.input_timeout_s)
    if raw["active_packet_count"] == 0:
        raise ValueError("capture contains no active engaged packet")
    gate7 = _gate7_metrics(
        packets,
        config,
        regular,
        velocity_scale=velocity_scale,
        acceleration_scale=acceleration_scale,
        jerk_scale=jerk_scale,
    )
    issues = _issues(raw, gate7, config, teleop_config)
    return {
        "schema": "g1.gate7.capture_quality.result.v1",
        "capture_id": manifest["capture_id"],
        "capture_path": str(capture_path.resolve()),
        "quality_status": "REVIEW_REQUIRED" if issues else "PASS",
        "issues": issues,
        "raw_mink": raw,
        "gate7_candidate": gate7,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": False,
    }


def _fmt(value, suffix="") -> str:
    return "-" if value is None else f"{value}{suffix}"


def WriteHtmlReport(report: dict, path: Path) -> None:
    raw = report["raw_mink"]
    gate7 = report["gate7_candidate"]
    experimental = gate7["experimental_stateful_limiter"]
    issue_rows = "".join(
        f"<tr><td>{html.escape(item['severity'])}</td><td><code>{html.escape(item['code'])}</code></td>"
        f"<td>{html.escape(item['message'])}</td></tr>"
        for item in report["issues"]
    ) or "<tr><td colspan='3'>No review item detected.</td></tr>"
    joint_rows = "".join(
        "<tr>"
        f"<td>{html.escape(raw_joint['name'])}</td>"
        f"<td>{_fmt(raw_joint['min_deg'])}</td><td>{_fmt(raw_joint['max_deg'])}</td>"
        f"<td>{_fmt(raw_joint['minimum_model_limit_margin_deg'])}</td>"
        f"<td>{_fmt(raw_joint['raw_velocity_deg_s']['p95_abs'])}</td>"
        f"<td>{_fmt(gate_joint['velocity_deg_s']['p95_abs_nonzero'])} / {_fmt(gate_joint['velocity_deg_s']['max_abs'])} / {_fmt(gate_joint['velocity_limit_deg_s'])}</td>"
        f"<td>{_fmt(gate_joint['acceleration_deg_s2']['p95_abs_nonzero'])} / {_fmt(gate_joint['acceleration_deg_s2']['max_abs'])} / {_fmt(gate_joint['acceleration_limit_deg_s2'])}</td>"
        f"<td>{_fmt(gate_joint['jerk_deg_s3']['p95_abs_nonzero'])} / {_fmt(gate_joint['jerk_deg_s3']['max_abs'])} / {_fmt(gate_joint['jerk_limit_deg_s3'])}</td>"
        "</tr>"
        for raw_joint, gate_joint in zip(raw["joints"], gate7["joints"])
    )
    segment_rows = "".join(
        f"<tr><td>{index + 1}</td><td>{item['start_s']}</td><td>{item['end_s']}</td>"
        f"<td>{item['duration_s']}</td><td>{item['packets']}</td></tr>"
        for index, item in enumerate(raw["active_segments"])
    )
    experimental_rows = "".join(
        "<tr>"
        f"<td>{html.escape(item['name'])}</td>"
        f"<td>{_fmt(item['velocity_deg_s']['p95_abs_nonzero'])} / {_fmt(item['velocity_deg_s']['max_abs'])} / {_fmt(item['velocity_limit_deg_s'])}</td>"
        f"<td>{_fmt(item['acceleration_deg_s2']['p95_abs_nonzero'])} / {_fmt(item['acceleration_deg_s2']['max_abs'])} / {_fmt(item['acceleration_limit_deg_s2'])}</td>"
        f"<td>{_fmt(item['jerk_deg_s3']['p95_abs_nonzero'])} / {_fmt(item['jerk_deg_s3']['max_abs'])} / {_fmt(item['jerk_limit_deg_s3'])}</td>"
        f"<td>{_fmt(item['baseline_tracking_error_deg']['p95_abs'])} / {_fmt(item['baseline_tracking_error_deg']['max_abs'])}</td>"
        "</tr>"
        for item in experimental["joints"]
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G1 Gate 7 Quest Capture Quality</title>
<style>
body{{font:14px/1.45 Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#17202a}}
header{{background:#20262d;color:white;padding:22px 30px}}h1{{font-size:22px;margin:0 0 5px}}
main{{max-width:1180px;margin:0 auto;padding:24px}}h2{{font-size:17px;margin:28px 0 10px}}
.status{{display:inline-block;padding:4px 8px;border-radius:4px;background:#ffd166;color:#2b2100;font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
.metric{{background:white;border:1px solid #d9dee3;border-radius:6px;padding:13px}}
.metric b{{display:block;font-size:20px;margin-top:3px}}table{{width:100%;border-collapse:collapse;background:white}}
th,td{{border:1px solid #d9dee3;padding:8px;text-align:left}}th{{background:#e8edf1}}code{{font-size:12px}}
.note{{background:#fff;border-left:4px solid #527a9e;padding:10px 12px}}small{{color:#5b6570}}
</style></head><body><header><h1>G1 Gate 7 Quest Capture Quality</h1>
<div>Capture <code>{html.escape(report['capture_id'])}</code> &nbsp; <span class="status">{report['quality_status']}</span></div></header>
<main><div class="grid">
<div class="metric">Packets<b>{raw['packet_count']}</b></div><div class="metric">Active packets<b>{raw['active_packet_count']}</b></div>
<div class="metric">Mean input rate<b>{raw['mean_packet_rate_hz']} Hz</b></div><div class="metric">Maximum gap<b>{raw['packet_gap_ms']['max']} ms</b></div>
<div class="metric">Minimum clearance<b>{_fmt(raw['minimum_clearance_m'], ' m')}</b></div><div class="metric">Active collision flags<b>{raw['active_collision_limited_packets']}</b></div>
<div class="metric">Position error p95<b>{raw['position_error_m']['p95']} m</b></div><div class="metric">Orientation error p95<b>{raw['orientation_error_deg']['p95']} deg</b></div>
</div><h2>Review items</h2><table><tr><th>Severity</th><th>Code</th><th>Meaning</th></tr>{issue_rows}</table>
 <h2>Right-arm joint metrics</h2><table><tr><th>Joint</th><th>Raw min deg</th><th>Raw max deg</th><th>Limit margin deg</th>
 <th>Raw velocity p95</th><th>Gate7 velocity p95nz / max / limit</th><th>Gate7 accel p95nz / max / limit</th><th>Gate7 jerk p95nz / max / limit</th></tr>{joint_rows}</table>
 <h2>Experimental stateful limiter</h2><div class="note">Offline responsive comparison only. Engine: {experimental['engine']} {experimental['version']}; velocity scale {experimental['velocity_scale']}x; acceleration scale {experimental['acceleration_scale']}x; jerk scale {experimental['jerk_scale']}x. Physical Gate 7 remains unchanged and locked.</div>
 <table><tr><th>Joint</th><th>Velocity p95nz / max / limit</th><th>Acceleration p95nz / max / limit</th><th>Jerk p95nz / max / limit</th><th>Baseline tracking error p95 / max deg</th></tr>{experimental_rows}</table>
 <h2>Engaged segments</h2><table><tr><th>#</th><th>Start s</th><th>End s</th><th>Duration s</th><th>Packets</th></tr>{segment_rows}</table>
<h2>Interpretation boundary</h2><div class="note">This report analyzes recorded Mink targets and an ideal-following Gate 7 candidate. It does not prove physical G1 tracking, balance, actuator torque, DDS timing, or camera behavior. No Unitree publisher or robot command was created.</div>
<p><small>{html.escape(report['capture_path'])}</small></p></main></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")


def _automatic_paths() -> tuple[Path, Path]:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return (
        RESULT_DIRECTORY / f"g1_gate7_capture_quality_{stamp}.json",
        RESULT_DIRECTORY / f"g1_gate7_capture_quality_{stamp}.html",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a Quest/Mink Gate 7 capture")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--result-html", type=Path)
    parser.add_argument("--velocity-scale", type=float, default=1.25)
    parser.add_argument("--acceleration-scale", type=float, default=3.0)
    parser.add_argument("--jerk-scale", type=float, default=6.0)
    parser.add_argument("--require-ruckig-limit-pass", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    automatic_json, automatic_html = _automatic_paths()
    result_json = args.result_json or automatic_json
    result_html = args.result_html or automatic_html
    report = BuildQualityReport(
        args.capture,
        velocity_scale=args.velocity_scale,
        acceleration_scale=args.acceleration_scale,
        jerk_scale=args.jerk_scale,
    )
    result_json.parent.mkdir(parents=True, exist_ok=True)
    result_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    WriteHtmlReport(report, result_html)
    raw = report["raw_mink"]
    print(f"[{report['quality_status']}] Gate 7 Quest capture quality analysis completed.")
    print(f"Packets={raw['packet_count']} active={raw['active_packet_count']} segments={len(raw['active_segments'])}")
    print(f"Input rate={raw['mean_packet_rate_hz']} Hz max gap={raw['packet_gap_ms']['max']} ms")
    print(f"Minimum clearance={raw['minimum_clearance_m']} m")
    for issue in report["issues"]:
        print(f"[{issue['severity'].upper()}] {issue['code']}: {issue['message']}")
    experimental = report["gate7_candidate"]["experimental_stateful_limiter"]
    print(
        "Experimental limiter exceedances: "
        f"velocity={experimental['velocity_limit_exceedance_ticks']} "
        f"acceleration={experimental['acceleration_limit_exceedance_ticks']} "
        f"jerk={experimental['jerk_limit_exceedance_ticks']}"
    )
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")
    print(f"JSON saved to: {result_json.resolve()}")
    print(f"HTML saved to: {result_html.resolve()}")
    if args.require_ruckig_limit_pass and any(
        experimental[key] != 0
        for key in (
            "velocity_limit_exceedance_ticks",
            "acceleration_limit_exceedance_ticks",
            "jerk_limit_exceedance_ticks",
        )
    ):
        print("[FAIL] Ruckig hardware-profile derivative limits were exceeded.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
