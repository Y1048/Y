"""Record validated Mink right-arm targets before any G1 relay or controller.

The logger only binds Windows UDP 5008 and writes CSV. It has no Unitree SDK,
DDS, SSH, relay socket, or motor-command path.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import socket
import time
from pathlib import Path

SCHEMA = "g1.mink.right_arm.state.v1"
JOINT_NAMES = (
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
)


def _finite_number(value, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(field)
    return float(value)


def parse_mink_state(raw: bytes) -> dict:
    def reject_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    raw_json_text = raw.decode("utf-8")
    packet = json.loads(raw_json_text, object_pairs_hook=reject_duplicates)
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ValueError("schema")
    if packet.get("state_source") != "mink_simulation":
        raise ValueError("state_source")
    sequence = packet.get("sequence")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("sequence")
    names = packet.get("all_joint_names")
    all_q = packet.get("all_joint_q_rad")
    right = packet.get("right_arm")
    if not isinstance(names, list) or len(names) != 29:
        raise ValueError("all_joint_names")
    if tuple(names[22:29]) != JOINT_NAMES:
        raise ValueError("right-arm joint ordering")
    if not isinstance(all_q, list) or len(all_q) != 29:
        raise ValueError("all_joint_q_rad")
    all_q = [_finite_number(value, "all_joint_q_rad") for value in all_q]
    if not isinstance(right, dict):
        raise ValueError("right_arm")
    right_q = right.get("joints")
    if not isinstance(right_q, list) or len(right_q) != 7:
        raise ValueError("right_arm.joints")
    right_q = [_finite_number(value, "right_arm.joints") for value in right_q]
    if right_q != all_q[22:29]:
        raise ValueError("right-arm duplicate mismatch")
    if type(right.get("active")) is not bool:
        raise ValueError("right_arm.active")
    command_state = right.get("command_state")
    if not isinstance(command_state, str) or not command_state:
        raise ValueError("right_arm.command_state")
    source_timestamp = _finite_number(packet.get("timestamp"), "timestamp")
    return {
        "sequence": sequence,
        "source_timestamp_unix_s": source_timestamp,
        "session_id": packet.get("session_id") or "",
        "active": right["active"],
        "command_state": command_state,
        "input_command_mode": packet.get("input_command_mode") or "",
        "input_packet_age_s": packet.get("input_packet_age_s"),
        "position_error_m": right.get("position_error"),
        "minimum_clearance_m": right.get("minimum_clearance_m"),
        "collision_limited": bool(right.get("collision_limited", False)),
        "trajectory_status": right.get("trajectory_status") or "",
        "q_rad": right_q,
        "raw_json_text": raw_json_text,
    }


def row_for(packet: dict, receive_monotonic_s: float) -> list:
    optional = []
    for key in ("input_packet_age_s", "position_error_m", "minimum_clearance_m"):
        value = packet[key]
        optional.append("" if value is None else _finite_number(value, key))
    return [
        f"{receive_monotonic_s:.9f}",
        f"{packet['source_timestamp_unix_s']:.9f}",
        packet["sequence"],
        packet["session_id"],
        int(packet["active"]),
        packet["command_state"],
        packet["input_command_mode"],
        *optional,
        int(packet["collision_limited"]),
        packet["trajectory_status"],
        *packet["q_rad"],
        packet["raw_json_text"],
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5008)
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise ValueError("port")
    if args.duration_seconds < 0:
        raise ValueError("duration")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.2)
    started = time.monotonic()
    last_sequence = -1
    accepted = 0
    rejected = 0
    header = [
        "receive_monotonic_s", "source_timestamp_unix_s", "sequence",
        "session_id", "active", "command_state", "input_command_mode",
        "input_packet_age_s", "position_error_m", "minimum_clearance_m",
        "collision_limited", "trajectory_status",
        *[f"q{22 + index}_{name}_rad" for index, name in enumerate(JOINT_NAMES)],
        "raw_json_text",
    ]
    print(f"[IK CSV] receive-only udp://{args.host}:{args.port}", flush=True)
    print(f"[IK CSV] {args.output}", flush=True)
    try:
        with args.output.open("x", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(header)
            output.flush()
            while not args.duration_seconds or time.monotonic() - started < args.duration_seconds:
                try:
                    raw, peer = sock.recvfrom(65536)
                except socket.timeout:
                    continue
                if peer[0] != "127.0.0.1":
                    rejected += 1
                    continue
                try:
                    packet = parse_mink_state(raw)
                    if packet["sequence"] <= last_sequence:
                        raise ValueError("non-monotonic sequence")
                    writer.writerow(row_for(packet, time.monotonic()))
                except (ValueError, KeyError, json.JSONDecodeError):
                    rejected += 1
                    continue
                last_sequence = packet["sequence"]
                accepted += 1
                output.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    print(f"[IK CSV COMPLETE] accepted={accepted} rejected={rejected}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
