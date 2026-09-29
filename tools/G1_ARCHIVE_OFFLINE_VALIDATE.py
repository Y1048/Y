"""Offline-only validation of a captured G1 session archive.

Reads G1.zip directly, replays the recorded bilateral simulation, and cross-checks
Quest/Unity, Omni, LowState, robot-side observation, and GROOT telemetry.  This
module never opens a network connection and never creates robot command output.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import zipfile

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for path in (ROOT / "MuJoCo_G1_Controller" / "scripts",
             ROOT / "hardware" / "g1_arm_bridge", TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import g1_bimanual_session_report as bimanual_report  # noqa: E402
from g1_lowstate_view import validate as validate_lowstate  # noqa: E402
from g1_omni_velocity_gateway import (  # noqa: E402
    OmniVelocityConfig,
    OmniVelocityMapper,
    parse_omni_message,
)

SCHEMA = "g1.archive.offline.validation.v1"
BIMANUAL_PREFIX = "PC/logs/test_results/bimanual/unity_"
OMNI_PREFIX = "PC/logs/test_results/omni_gateway_readonly/omni_observation_"
LOWSTATE_PREFIX = "PC/logs/test_results/lowstate_view/"
CAMERA_PREFIX = "PC/logs/test_results/camera_ssh/"
UNITY_LIVE = "PC/Unity_G1_VR/Logs/live_quest_trace.csv"
ROTATION_PREFIX = "PC/Unity_G1_VR/Logs/rotation_trace_"
G1_HEADING_PREFIX = "G1/logs/g1_omni_heading_"
GROOT_PREFIX = "G1/logs/groot_actuation_"


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    return values[int(fraction * (len(values) - 1))]


def unique_entry(archive, prefix, suffix):
    matches = [
        name for name in archive.namelist()
        if name.startswith(prefix) and name.endswith(suffix)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one archive entry for {prefix}*{suffix}; found {len(matches)}"
        )
    return matches[0]
def open_text(archive, name):
    return io.TextIOWrapper(
        archive.open(name), encoding="utf-8-sig", errors="replace", newline=""
    )


def sha256_entry(archive, name):
    digest = hashlib.sha256()
    with archive.open(name) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(archive):
    manifest = json.loads(archive.read("manifest.json"))
    failures = []
    verified = 0
    for item in manifest.get("files", []):
        name = str(item["path"]).replace("\\", "/")
        try:
            info = archive.getinfo(name)
        except KeyError:
            failures.append("manifest_missing:" + name)
            continue
        if info.file_size != int(item["size"]):
            failures.append("manifest_size:" + name)
            continue
        if sha256_entry(archive, name) != str(item["sha256"]).lower():
            failures.append("manifest_sha256:" + name)
            continue
        verified += 1
    return {
        "listed_files": len(manifest.get("files", [])),
        "verified_files": verified,
        "failures": failures,
    }
def extract_entry(archive, name, directory):
    output = Path(directory) / Path(name).name
    with archive.open(name) as source, output.open("wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    return output


def load_bimanual_maps(path):
    states = {}
    inputs = []
    first_state = last_state = None
    with Path(path).open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "state":
                states[int(row["feedback_sequence"])] = row
                first_state = row if first_state is None else first_state
                last_state = row
            elif row.get("kind") == "input":
                try:
                    packet = json.loads(row["raw_json_text"])
                except (KeyError, TypeError, json.JSONDecodeError):
                    packet = None
                inputs.append((row, packet))
    return {
        "states": states,
        "inputs": inputs,
        "first_state": first_state,
        "last_state": last_state,
    }


def analyze_bimanual(archive, name, directory):
    path = extract_entry(archive, name, directory)
    static = bimanual_report.analyze_session(path)
    replay = bimanual_report.replay_session(path)
    maps = load_bimanual_maps(path)
    failures = list(static.get("failures", []))
    if replay.get("comparison") != "same_motion_limits":
        failures.append("bimanual_motion_limits_not_comparable")
    if replay.get("exact_replay_passed") is not True:
        failures.append("bimanual_exact_replay_failed")
    if not replay.get("current_validation", {}).get("passed"):
        failures.append("bimanual_current_validation_failed")
    return {
        "source": name,
        "state_rows": replay["state_rows"],
        "input_rows": replay["input_rows"],
        "accepted_inputs": static["accepted_inputs"],
        "state_mismatches": replay["state_mismatches"],
        "reason_mismatches": replay["reason_mismatches"],
        "accepted_mismatches": replay["accepted_mismatches"],
        "max_q_difference_rad": replay["maximum_logged_q_difference_rad"],
        "minimum_clearance_mm": replay["minimum_sampled_clearance_mm"],
        "comparison": replay["comparison"],
        "exact_replay_passed": replay["exact_replay_passed"],
        "current_validation_passed": replay["current_validation"]["passed"],
        "final_state": replay["final_state"],
        "final_reason": replay["final_reason"],
        "failures": failures,
    }, maps


def linear_clock_fit(source_times, pc_times):
    count = len(source_times)
    sx, sy = sum(source_times), sum(pc_times)
    sxx = sum(value * value for value in source_times)
    sxy = sum(x * y for x, y in zip(source_times, pc_times))
    denominator = count * sxx - sx * sx
    slope = (count * sxy - sx * sy) / denominator
    intercept = (sy - slope * sx) / count
    residuals = [
        abs(y - (slope * x + intercept))
        for x, y in zip(source_times, pc_times)
    ]
    return {
        "slope": slope,
        "intercept_s": intercept,
        "residual_p95_s": percentile(residuals, 0.95),
        "residual_max_s": max(residuals),
    }


def analyze_lowstate(archive, name):
    source_times = []
    pc_times = []
    sessions = set()
    invalid_rows = 0
    ordering_failures = 0
    gap_total = 0
    max_age = 0.0
    metadata = None
    previous_sequence = previous_source = previous_pc = None
    with open_text(archive, name) as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("event") == "metadata":
                metadata = row
                continue
            try:
                validate_lowstate(row)
            except (TypeError, ValueError):
                invalid_rows += 1
                continue
            sequence = int(row["sequence"])
            source_time = float(row["source_monotonic_s"])
            pc_time = float(row["pc_received_monotonic_s"])
            if (previous_sequence is not None and
                    (sequence <= previous_sequence or
                     source_time <= previous_source or pc_time < previous_pc)):
                ordering_failures += 1
            gap_total += int(row.get("source_gap", 0))
            sessions.add(row["session"])
            source_times.append(source_time)
            pc_times.append(pc_time)
            max_age = max(max_age, float(row["age_s"]))
            previous_sequence, previous_source, previous_pc = sequence, source_time, pc_time
    failures = []
    if metadata is None or metadata.get("publisher_created") is not False:
        failures.append("lowstate_metadata_invalid")
    if invalid_rows:
        failures.append("lowstate_invalid_rows")
    if ordering_failures:
        failures.append("lowstate_ordering")
    if len(sessions) != 1:
        failures.append("lowstate_session_count")
    if not source_times:
        failures.append("lowstate_empty")
        clock = None
        observed_hz = None
    else:
        clock = linear_clock_fit(source_times, pc_times)
        observed_hz = ((len(pc_times) - 1) / (pc_times[-1] - pc_times[0])
                       if len(pc_times) > 1 else None)
        if clock["residual_p95_s"] > 0.020:
            failures.append("lowstate_pc_clock_alignment")
    return {
        "source": name,
        "rows": len(source_times),
        "sessions": len(sessions),
        "invalid_rows": invalid_rows,
        "ordering_failures": ordering_failures,
        "source_gap_total": gap_total,
        "max_transport_age_s": max_age,
        "observed_hz": observed_hz,
        "source_start_s": source_times[0] if source_times else None,
        "source_end_s": source_times[-1] if source_times else None,
        "pc_start_s": pc_times[0] if pc_times else None,
        "pc_end_s": pc_times[-1] if pc_times else None,
        "clock_fit": clock,
        "failures": failures,
    }


def analyze_camera_log(archive, name):
    streaming_updates = 0
    last_frame = 0
    min_bytes = None
    max_bytes = 0
    wait_lines = 0
    error_lines = []
    with open_text(archive, name) as stream:
        for line in stream:
            text = line.strip()
            upper = text.upper()
            if "[WAIT]" in text:
                wait_lines += 1
            if "[ERROR]" in upper or "FAILED" in upper:
                error_lines.append(text)
            if not text.startswith("[STREAMING] frames="):
                continue
            streaming_updates += 1
            fields = dict(
                item.split("=", 1)
                for item in text[len("[STREAMING] "):].split()
                if "=" in item
            )
            frame = int(fields["frames"])
            size = int(fields["latest_bytes"])
            last_frame = max(last_frame, frame)
            min_bytes = size if min_bytes is None else min(min_bytes, size)
            max_bytes = max(max_bytes, size)
    failures = []
    if not streaming_updates or last_frame <= 0:
        failures.append("camera_no_streaming_evidence")
    if min_bytes is not None and min_bytes <= 0:
        failures.append("camera_invalid_frame_size")
    if error_lines:
        failures.append("camera_log_error")
    return {
        "source": name,
        "streaming_updates": streaming_updates,
        "last_frame_counter": last_frame,
        "min_latest_bytes": min_bytes,
        "max_latest_bytes": max_bytes,
        "wait_for_unity_lines": wait_lines,
        "error_lines": error_lines,
        "jpeg_payload_archived": False,
        "failures": failures,
    }


def analyze_omni(archive, name):
    mapper = OmniVelocityMapper(OmniVelocityConfig())
    rows_by_sequence = {}
    count = 0
    previous_sequence = -1
    previous_time = -math.inf
    previous_processed = -math.inf
    ordering_failures = raw_mismatches = calibration_mismatches = 0
    row_kind_mismatches = skipped_mismatches = 0
    max_velocity_error = max_raw_error = 0.0
    receive_start = receive_end = None
    with open_text(archive, name) as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            count += 1
            sequence = int(row["sample_sequence"])
            receive_time = float(row["receive_monotonic_s"])
            processed_time = float(row["processed_monotonic_s"])
            if (sequence <= previous_sequence or receive_time < previous_time
                    or processed_time < previous_processed):
                ordering_failures += 1
            x, y, yaw = parse_omni_message(row["raw_json_text"])
            raw_error = max(
                abs(x - float(row["mx"])),
                abs(y - float(row["my"])),
                abs(yaw - float(row["arm_yaw_deg"])),
            )
            max_raw_error = max(max_raw_error, raw_error)
            raw_mismatches += raw_error > 1e-12
            velocity = mapper.update(x, y, yaw, receive_time)
            logged_velocity = tuple(
                float(row[key]) for key in ("vx", "vy", "yaw_rate")
            )
            velocity_error = max(
                abs(actual - expected)
                for actual, expected in zip(velocity, logged_velocity)
            )
            max_velocity_error = max(max_velocity_error, velocity_error)
            calibration_mismatches += (
                bool(int(row["calibrated"])) != mapper.calibrated
            )
            row_kind_mismatches += row.get("csv_row_kind") != "processed_new_raw_sample"
            expected_skipped = sequence - count + 1
            skipped_mismatches += int(row["raw_samples_skipped"]) != expected_skipped
            rows_by_sequence[sequence] = {
                "receive_monotonic_s": receive_time,
                "mx": x, "my": y, "arm_yaw_deg": yaw,
                "velocity": logged_velocity,
            }
            receive_start = receive_time if receive_start is None else receive_start
            receive_end = receive_time
            previous_sequence, previous_time = sequence, receive_time
            previous_processed = processed_time
    failures = []
    if ordering_failures:
        failures.append("omni_ordering")
    if raw_mismatches or max_raw_error > 1e-12:
        failures.append("omni_raw_json_mismatch")
    if max_velocity_error > 1e-12:
        failures.append("omni_mapper_replay_mismatch")
    if calibration_mismatches:
        failures.append("omni_calibration_mismatch")
    if row_kind_mismatches:
        failures.append("omni_row_kind_mismatch")
    if skipped_mismatches:
        failures.append("omni_skipped_count_mismatch")
    return {
        "source": name,
        "rows": count,
        "sequence_start": min(rows_by_sequence) if rows_by_sequence else None,
        "sequence_end": max(rows_by_sequence) if rows_by_sequence else None,
        "receive_start_s": receive_start,
        "receive_end_s": receive_end,
        "ordering_failures": ordering_failures,
        "raw_mismatches": raw_mismatches,
        "calibration_mismatches": calibration_mismatches,
        "row_kind_mismatches": row_kind_mismatches,
        "skipped_count_mismatches": skipped_mismatches,
        "max_raw_value_error": max_raw_error,
        "max_velocity_replay_error": max_velocity_error,
        "failures": failures,
    }, rows_by_sequence


def analyze_unity_trace_pair(archive, live_name, rotation_name):
    live_rows = list(csv.DictReader(open_text(archive, live_name)))
    rotation_rows = [
        json.loads(line) for line in open_text(archive, rotation_name)
        if line.strip()
    ]
    time_errors = []
    tracked_mismatches = 0
    wrist_quaternion_errors = []
    head_quaternion_errors = []
    state_counts = {}
    for live, rotation in zip(live_rows, rotation_rows):
        time_errors.append(abs(float(live["time_s"]) - float(rotation["time_s"])))
        tracked_mismatches += (
            bool(int(live["tracked"])) != bool(rotation.get("tracked"))
        )
        state = str(rotation.get("engagement_state"))
        state_counts[state] = state_counts.get(state, 0) + 1
        wrist = rotation.get("semantic_wrist") or {}
        if wrist:
            wrist_quaternion_errors.append(max(
                abs(float(live[column]) - float(wrist[key]))
                for column, key in (
                    ("raw_rot_x", "x"), ("raw_rot_y", "y"),
                    ("raw_rot_z", "z"), ("raw_rot_w", "w"),
                )
            ))
        head = rotation.get("head") or {}
        if head:
            head_quaternion_errors.append(max(
                abs(float(live[column]) - float(head[key]))
                for column, key in (
                    ("head_rot_x", "x"), ("head_rot_y", "y"),
                    ("head_rot_z", "z"), ("head_rot_w", "w"),
                )
            ))
    failures = []
    if len(live_rows) != len(rotation_rows):
        failures.append("unity_trace_row_count")
    if time_errors and max(time_errors) > 0.100:
        failures.append("unity_trace_time_alignment")
    if tracked_mismatches:
        failures.append("unity_trace_tracking_mismatch")
    if wrist_quaternion_errors and max(wrist_quaternion_errors) > 2e-6:
        failures.append("unity_trace_wrist_quaternion")
    if head_quaternion_errors and max(head_quaternion_errors) > 2e-6:
        failures.append("unity_trace_head_quaternion")
    return {
        "live_rows": len(live_rows),
        "rotation_rows": len(rotation_rows),
        "time_error_p95_s": percentile(time_errors, 0.95),
        "time_error_max_s": max(time_errors) if time_errors else None,
        "tracked_mismatches": tracked_mismatches,
        "wrist_quaternion_error_max": (
            max(wrist_quaternion_errors) if wrist_quaternion_errors else None
        ),
        "head_quaternion_error_max": (
            max(head_quaternion_errors) if head_quaternion_errors else None
        ),
        "engagement_states": state_counts,
        "failures": failures,
    }, live_rows


def quaternion_l2_sign_invariant(first, second):
    direct = math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))
    negated = math.sqrt(sum((a + b) ** 2 for a, b in zip(first, second)))
    return min(direct, negated)


def analyze_quest_bimanual_link(live_rows, inputs):
    prefix = []
    previous_sender_time = -math.inf
    for _, packet in inputs:
        if not isinstance(packet, dict):
            continue
        sender_time = float(packet["sender_time_s"])
        if sender_time + 1.0 < previous_sender_time:
            break
        prefix.append((sender_time, packet))
        previous_sender_time = max(previous_sender_time, sender_time)
    times = [item[0] for item in prefix]
    matched = tracking_mismatches = both_tracked = 0
    time_errors, wrist_position_errors = [], []
    wrist_quaternion_errors, head_position_errors = [], []
    head_quaternion_errors = []
    for live in live_rows:
        time_s = float(live["time_s"])
        index = bisect.bisect_left(times, time_s)
        candidates = [i for i in (index - 1, index) if 0 <= i < len(times)]
        if not candidates:
            continue
        selected = min(candidates, key=lambda i: abs(times[i] - time_s))
        time_error = abs(times[selected] - time_s)
        if time_error > 0.050:
            continue
        matched += 1
        packet = prefix[selected][1]
        live_tracked = bool(int(live["tracked"]))
        packet_tracked = bool(packet["right"]["tracked"])
        tracking_mismatches += live_tracked != packet_tracked
        if not (live_tracked and packet_tracked):
            continue
        both_tracked += 1
        time_errors.append(time_error)
        right_position = packet["right"]["raw_position_m"]
        wrist_position_errors.append(math.sqrt(sum(
            (float(live[column]) - right_position[i]) ** 2
            for i, column in enumerate(
                ("raw_wrist_x", "raw_wrist_y", "raw_wrist_z")
            )
        )))
        right_quaternion = packet["right"]["quaternion_wxyz"]
        live_quaternion = [
            float(live[column]) for column in
            ("raw_rot_w", "raw_rot_x", "raw_rot_y", "raw_rot_z")
        ]
        wrist_quaternion_errors.append(
            quaternion_l2_sign_invariant(live_quaternion, right_quaternion)
        )
        head_position = packet["hmd_world_m"]
        head_position_errors.append(math.sqrt(sum(
            (float(live[column]) - head_position[i]) ** 2
            for i, column in enumerate(("head_x", "head_y", "head_z"))
        )))
        head_quaternion = packet["hmd_world_wxyz"]
        live_head_quaternion = [
            float(live[column]) for column in
            ("head_rot_w", "head_rot_x", "head_rot_y", "head_rot_z")
        ]
        head_quaternion_errors.append(
            quaternion_l2_sign_invariant(live_head_quaternion, head_quaternion)
        )
    failures = []
    match_ratio = matched / len(live_rows) if live_rows else 0.0
    tracking_mismatch_ratio = tracking_mismatches / matched if matched else 1.0
    if match_ratio < 0.99:
        failures.append("quest_bimanual_time_match")
    if tracking_mismatch_ratio > 0.001:
        failures.append("quest_bimanual_tracking_match")
    if not both_tracked:
        failures.append("quest_bimanual_no_tracked_overlap")
    else:
        if percentile(wrist_position_errors, 0.95) > 0.012:
            failures.append("quest_bimanual_wrist_position")
        if percentile(wrist_quaternion_errors, 0.95) > 0.025:
            failures.append("quest_bimanual_wrist_rotation")
        if percentile(head_position_errors, 0.95) > 0.008:
            failures.append("quest_bimanual_head_position")
        if percentile(head_quaternion_errors, 0.95) > 0.012:
            failures.append("quest_bimanual_head_rotation")
    return {
        "bimanual_sender_prefix_rows": len(prefix),
        "live_rows": len(live_rows),
        "matched_rows": matched,
        "match_ratio": match_ratio,
        "tracking_mismatches": tracking_mismatches,
        "tracking_mismatch_ratio": tracking_mismatch_ratio,
        "both_tracked_rows": both_tracked,
        "time_error_p95_s": percentile(time_errors, 0.95),
        "time_error_max_s": max(time_errors) if time_errors else None,
        "wrist_position_error_p95_m": percentile(wrist_position_errors, 0.95),
        "wrist_position_error_max_m": max(wrist_position_errors),
        "wrist_quaternion_l2_p95": percentile(wrist_quaternion_errors, 0.95),
        "head_position_error_p95_m": percentile(head_position_errors, 0.95),
        "head_quaternion_l2_p95": percentile(head_quaternion_errors, 0.95),
        "failures": failures,
    }


def analyze_g1_heading(archive, name):
    observations = []
    commands = []
    summaries = []
    raw_hash_mismatches = rejected = 0
    first_log_time = last_log_time = None
    status_counts = {}
    with open_text(archive, name) as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            log_time = row.get("log_monotonic_s")
            if isinstance(log_time, (int, float)):
                first_log_time = log_time if first_log_time is None else first_log_time
                last_log_time = log_time
            kind = row.get("kind")
            if kind == "observation_rx":
                observations.append(row)
                raw_text = row.get("raw_json", "")
                raw_hash_mismatches += (
                    hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                    != row.get("raw_sha256")
                )
                rejected += row.get("accepted") is not True
            elif kind == "command_tx":
                commands.append(row)
                status = str(row.get("status"))
                status_counts[status] = status_counts.get(status, 0) + 1
            elif kind in ("controller_exit", "log_summary"):
                summaries.append(row)
    failures = []
    if raw_hash_mismatches:
        failures.append("g1_observation_raw_sha256")
    if rejected:
        failures.append("g1_observation_rejected")
    for row in summaries:
        if row.get("kind") == "log_summary" and row.get("records_dropped"):
            failures.append("g1_heading_log_dropped")
    return {
        "source": name,
        "observations": len(observations),
        "commands": len(commands),
        "status_counts": status_counts,
        "raw_hash_mismatches": raw_hash_mismatches,
        "rejected_observations": rejected,
        "g1_start_s": first_log_time,
        "g1_end_s": last_log_time,
        "failures": failures,
    }, observations, commands


def analyze_groot(archive, name):
    rows = list(csv.DictReader(open_text(archive, name)))
    ordering_failures = nonfinite_rows = 0
    previous_time = -math.inf
    for row in rows:
        time_s = float(row["t_s"])
        if time_s <= previous_time:
            ordering_failures += 1
        previous_time = time_s
        try:
            values = [
                float(row[key]) for key in
                ("state_age_ms", "vx", "vy", "wz",
                 "inference_ms", "max_tracking_error")
            ]
            if not all(math.isfinite(value) for value in values):
                nonfinite_rows += 1
        except (KeyError, TypeError, ValueError):
            nonfinite_rows += 1
    duration = float(rows[-1]["t_s"]) if rows else None
    observed_hz = (
        (len(rows) - 1) / duration if rows and duration and len(rows) > 1
        else None
    )
    failures = []
    if not rows:
        failures.append("groot_empty")
    if ordering_failures:
        failures.append("groot_time_ordering")
    if nonfinite_rows:
        failures.append("groot_nonfinite")
    return {
        "source": name,
        "rows": len(rows),
        "duration_s": duration,
        "observed_hz": observed_hz,
        "ordering_failures": ordering_failures,
        "nonfinite_rows": nonfinite_rows,
        "failures": failures,
    }, rows


def crosscheck_g1_observations(observations, bimanual_states, omni_rows, clock_fit):
    arm_matched = arm_missing = arm_state_mismatches = 0
    omni_matched = omni_missing = 0
    arm_q_errors = []
    arm_time_errors = []
    omni_velocity_errors = []
    omni_time_errors = []
    mapped_pc_ages = []
    slope = clock_fit["slope"]
    intercept = clock_fit["intercept_s"]
    for row in observations:
        raw = json.loads(row["raw_json"])
        payload = raw.get("payload") or {}
        arm = (payload.get("arm") or {}).get("values") or {}
        feedback_sequence = arm.get("feedback_sequence")
        state = bimanual_states.get(feedback_sequence)
        if state is None:
            arm_missing += 1
        else:
            arm_matched += 1
            arm_q = list(arm["left_q_rad"]) + list(arm["right_q_rad"])
            arm_q_errors.append(max(
                abs(float(a) - float(b))
                for a, b in zip(arm_q, state["q_rad"])
            ))
            arm_time_errors.append(abs(
                float(arm["source_monotonic_s"]) - float(state["monotonic_s"])
            ))
            arm_state_mismatches += (
                arm.get("state") != state.get("state")
                or arm.get("reason", "") != state.get("reason", "")
            )
        omni = (payload.get("omni") or {}).get("values") or {}
        sample_sequence = omni.get("sample_sequence")
        source = omni_rows.get(sample_sequence)
        if source is None:
            omni_missing += 1
        else:
            omni_matched += 1
            omni_velocity_errors.append(max(
                abs(float(omni[key]) - source["velocity"][i])
                for i, key in enumerate(("vx", "vy", "yaw_rate"))
            ))
            omni_time_errors.append(abs(
                float(omni["source_monotonic_s"])
                - source["receive_monotonic_s"]
            ))
        source_times = [
            float(item) for item in (
                arm.get("source_monotonic_s"),
                omni.get("source_monotonic_s"),
            ) if item is not None
        ]
        if source_times:
            mapped_pc = slope * float(row["log_monotonic_s"]) + intercept
            mapped_pc_ages.append(mapped_pc - max(source_times))

    arm_ratio = arm_matched / len(observations) if observations else 0.0
    omni_ratio = omni_matched / len(observations) if observations else 0.0
    failures = []
    if arm_ratio < 0.995:
        failures.append("g1_arm_observation_coverage")
    if arm_state_mismatches:
        failures.append("g1_arm_state_mismatch")
    if arm_q_errors and max(arm_q_errors) > 1e-12:
        failures.append("g1_arm_q_mismatch")
    if omni_ratio < 0.999:
        failures.append("g1_omni_observation_coverage")
    if omni_velocity_errors and max(omni_velocity_errors) > 1e-12:
        failures.append("g1_omni_velocity_mismatch")
    if omni_time_errors and max(omni_time_errors) > 1e-12:
        failures.append("g1_omni_time_mismatch")
    return {
        "observations": len(observations),
        "arm_matched": arm_matched,
        "arm_missing": arm_missing,
        "arm_match_ratio": arm_ratio,
        "arm_state_mismatches": arm_state_mismatches,
        "arm_q_error_max_rad": max(arm_q_errors) if arm_q_errors else None,
        "arm_source_time_error_max_s": (
            max(arm_time_errors) if arm_time_errors else None
        ),
        "omni_matched": omni_matched,
        "omni_missing": omni_missing,
        "omni_match_ratio": omni_ratio,
        "omni_velocity_error_max": (
            max(omni_velocity_errors) if omni_velocity_errors else None
        ),
        "omni_source_time_error_max_s": (
            max(omni_time_errors) if omni_time_errors else None
        ),
        "mapped_pc_age_p95_s": percentile(mapped_pc_ages, 0.95),
        "mapped_pc_age_max_s": max(mapped_pc_ages) if mapped_pc_ages else None,
        "failures": failures,
    }


def crosscheck_groot(commands, groot_rows):
    active = [
        row for row in commands
        if row.get("status") == "ACTIVE"
        and isinstance(row.get("g1_state_sequence"), int)
    ]
    valid = [
        row for row in active
        if 0 <= row["g1_state_sequence"] < len(groot_rows)
    ]
    sequences = [row["g1_state_sequence"] for row in active]
    offsets = [
        float(row["log_monotonic_s"])
        - float(groot_rows[row["g1_state_sequence"]]["t_s"])
        for row in valid
    ]
    offset = statistics.median(offsets) if offsets else None
    time_residuals = [
        abs(
            (float(row["log_monotonic_s"]) - offset)
            - float(groot_rows[row["g1_state_sequence"]]["t_s"])
        )
        for row in valid
    ] if offset is not None else []
    lag_metrics = {}
    for lag in range(-3, 4):
        errors = []
        for row in valid:
            index = row["g1_state_sequence"] + lag
            if not 0 <= index < len(groot_rows):
                continue
            packet = row["packet"]
            groot = groot_rows[index]
            errors.append(max(
                abs(float(packet[source]) - float(groot[target]))
                for source, target in (("vx", "vx"), ("vy", "vy"), ("wz", "wz"))
            ))
        if errors:
            lag_metrics[lag] = {
                "p50": statistics.median(errors),
                "p95": percentile(errors, 0.95),
                "max": max(errors),
            }
    best_lag = min(
        lag_metrics, key=lambda lag: lag_metrics[lag]["p95"]
    ) if lag_metrics else None
    failures = []
    if not sequences or min(sequences) != 0 or max(sequences) != len(groot_rows) - 1:
        failures.append("groot_sequence_coverage")
    if time_residuals and percentile(time_residuals, 0.95) > 0.005:
        failures.append("groot_time_alignment")
    if best_lag is None or lag_metrics[best_lag]["p95"] > 1e-5:
        failures.append("groot_velocity_link")
    return {
        "active_commands": len(active),
        "valid_state_links": len(valid),
        "state_sequence_start": min(sequences) if sequences else None,
        "state_sequence_end": max(sequences) if sequences else None,
        "clock_offset_s": offset,
        "time_alignment_p95_s": percentile(time_residuals, 0.95),
        "time_alignment_max_s": max(time_residuals) if time_residuals else None,
        "velocity_lag_metrics": lag_metrics,
        "best_velocity_lag_rows": best_lag,
        "best_velocity_p95_error": (
            lag_metrics[best_lag]["p95"] if best_lag is not None else None
        ),
        "failures": failures,
    }


def analyze_timeline(bimanual_maps, lowstate, omni, heading, commands):
    first_state = bimanual_maps["first_state"]
    last_state = bimanual_maps["last_state"]
    b_start = float(first_state["monotonic_s"])
    b_end = float(last_state["monotonic_s"])
    low_start = float(lowstate["pc_start_s"])
    low_end = float(lowstate["pc_end_s"])
    omni_start = float(omni["receive_start_s"])
    omni_end = float(omni["receive_end_s"])
    clock = lowstate["clock_fit"]
    slope, intercept = clock["slope"], clock["intercept_s"]
    g1_start = slope * float(heading["g1_start_s"]) + intercept
    g1_end = slope * float(heading["g1_end_s"]) + intercept
    first_engage = None
    for row, packet in bimanual_maps["inputs"]:
        if isinstance(packet, dict) and packet.get("engage"):
            first_engage = float(row["receive_monotonic_s"])
            break
    active_times = [
        slope * float(row["log_monotonic_s"]) + intercept
        for row in commands if row.get("status") == "ACTIVE"
    ]
    failures = []
    if abs(low_start - b_start) > 0.100 or abs(low_end - b_end) > 0.100:
        failures.append("pc_lowstate_bimanual_span")
    if abs(omni_end - b_end) > 0.500:
        failures.append("pc_omni_bimanual_end")
    return {
        "bimanual_pc_start_s": b_start,
        "bimanual_pc_end_s": b_end,
        "lowstate_pc_start_s": low_start,
        "lowstate_pc_end_s": low_end,
        "lowstate_start_delta_s": low_start - b_start,
        "lowstate_end_delta_s": low_end - b_end,
        "omni_pc_start_s": omni_start,
        "omni_pc_end_s": omni_end,
        "omni_start_delta_s": omni_start - b_start,
        "omni_end_delta_s": omni_end - b_end,
        "g1_heading_pc_start_s": g1_start,
        "g1_heading_pc_end_s": g1_end,
        "first_bimanual_engage_pc_s": first_engage,
        "g1_active_pc_start_s": min(active_times) if active_times else None,
        "g1_active_pc_end_s": max(active_times) if active_times else None,
        "g1_active_to_first_engage_delta_s": (
            min(active_times) - first_engage
            if active_times and first_engage is not None else None
        ),
        "failures": failures,
    }


def markdown_report(result):
    lines = [
        "# G1 archive offline validation", "",
        f"- Archive: `{result['archive']}`",
        f"- Passed: **{result['passed']}**",
        f"- Failures: {', '.join(result['failures']) or 'none'}", "",
        "## Replay",
        f"- Bimanual exact replay: {result['bimanual']['exact_replay_passed']}",
        f"- State/reason mismatches: {result['bimanual']['state_mismatches']} / "
        f"{result['bimanual']['reason_mismatches']}",
        f"- Max q difference: {result['bimanual']['max_q_difference_rad']:.12g} rad",
        f"- Omni mapper max velocity error: "
        f"{result['omni']['max_velocity_replay_error']:.12g}",
        f"- Camera log streaming: {result['camera']['streaming_updates']} updates; "
        f"last frame {result['camera']['last_frame_counter']}; "
        f"JPEG payload archived: {result['camera']['jpeg_payload_archived']}",
        "", "## Cross-links",
    ]
    lines.extend([
        f"- Quest->bimanual matched rows: {result['quest_bimanual']['matched_rows']} / "
        f"{result['quest_bimanual']['live_rows']}",
        f"- Quest->bimanual wrist position p95: "
        f"{result['quest_bimanual']['wrist_position_error_p95_m'] * 1000.0:.3f} mm",
        f"- PC->G1 arm observation match: "
        f"{result['g1_observation_link']['arm_matched']} / "
        f"{result['g1_observation_link']['observations']}",
        f"- PC->G1 Omni observation match: "
        f"{result['g1_observation_link']['omni_matched']} / "
        f"{result['g1_observation_link']['observations']}",
        f"- G1->GROOT best command lag: "
        f"{result['groot_link']['best_velocity_lag_rows']} row(s); p95 error "
        f"{result['groot_link']['best_velocity_p95_error']:.12g}",
        "", "## Timeline",
        f"- LowState start/end delta vs bimanual: "
        f"{result['timeline']['lowstate_start_delta_s']:.6f} / "
        f"{result['timeline']['lowstate_end_delta_s']:.6f} s",
        f"- Omni start/end delta vs bimanual: "
        f"{result['timeline']['omni_start_delta_s']:.6f} / "
        f"{result['timeline']['omni_end_delta_s']:.6f} s",
        f"- G1 ACTIVE to first bimanual engage: "
        f"{result['timeline']['g1_active_to_first_engage_delta_s']:.6f} s",
    ])
    return "\n".join(lines) + "\n"


def collect_failures(result):
    failures = []
    for key in (
        "manifest", "bimanual", "lowstate", "camera", "omni", "unity_trace",
        "quest_bimanual", "g1_heading", "g1_observation_link",
        "groot", "groot_link", "timeline",
    ):
        failures.extend(result[key].get("failures", []))
    return list(dict.fromkeys(failures))


def validate_archive(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise RuntimeError(f"Archive does not exist: {path}")
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory() as directory:
        bimanual_name = unique_entry(archive, BIMANUAL_PREFIX, ".jsonl")
        omni_name = unique_entry(archive, OMNI_PREFIX, ".csv")
        lowstate_name = unique_entry(archive, LOWSTATE_PREFIX, ".jsonl")
        camera_name = unique_entry(archive, CAMERA_PREFIX, ".log")
        rotation_name = unique_entry(archive, ROTATION_PREFIX, ".jsonl")
        heading_name = unique_entry(archive, G1_HEADING_PREFIX, ".jsonl")
        groot_name = unique_entry(archive, GROOT_PREFIX, ".csv")
        archive.getinfo(UNITY_LIVE)

        manifest = verify_manifest(archive)
        bimanual, bimanual_maps = analyze_bimanual(
            archive, bimanual_name, directory
        )
        lowstate = analyze_lowstate(archive, lowstate_name)
        camera = analyze_camera_log(archive, camera_name)
        omni, omni_rows = analyze_omni(archive, omni_name)
        unity_trace, live_rows = analyze_unity_trace_pair(
            archive, UNITY_LIVE, rotation_name
        )
        quest_bimanual = analyze_quest_bimanual_link(
            live_rows, bimanual_maps["inputs"]
        )
        heading, observations, commands = analyze_g1_heading(
            archive, heading_name
        )
        groot, groot_rows = analyze_groot(archive, groot_name)
        g1_observation_link = crosscheck_g1_observations(
            observations, bimanual_maps["states"], omni_rows,
            lowstate["clock_fit"],
        )
        groot_link = crosscheck_groot(commands, groot_rows)
        timeline = analyze_timeline(
            bimanual_maps, lowstate, omni, heading, commands
        )
        result = {
            "schema": SCHEMA,
            "offline_only": True,
            "network_accessed": False,
            "robot_commands_created": False,
            "archive": str(path),
            "archive_bytes": path.stat().st_size,
            "captured_git_commit": archive.read(
                "settings/git_commit.txt"
            ).decode("utf-8", errors="replace").strip(),
            "manifest": manifest,
            "bimanual": bimanual,
            "lowstate": lowstate,
            "camera": camera,
            "omni": omni,
            "unity_trace": unity_trace,
            "quest_bimanual": quest_bimanual,
            "g1_heading": heading,
            "g1_observation_link": g1_observation_link,
            "groot": groot,
            "groot_link": groot_link,
            "timeline": timeline,
        }
    result["failures"] = collect_failures(result)
    result["passed"] = not result["failures"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args(argv)
    result = validate_archive(args.archive)
    payload = json.dumps(
        result, ensure_ascii=False, indent=2, allow_nan=False
    ) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown_report(result), encoding="utf-8")
    print(payload, end="")
    return 1 if args.strict and not result["passed"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as error:
        print(
            "[G1 ARCHIVE OFFLINE VALIDATION FAILED] " + str(error),
            file=sys.stderr,
        )
        raise SystemExit(1)
