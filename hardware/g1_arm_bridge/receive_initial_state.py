#!/usr/bin/env python3
"""Receive one fresh, provenance-checked G1 LowState snapshot over UDP.

This Windows process persists a read-only hardware seed for Mink startup. It
accepts only the canonical LowState telemetry contract and never sends a robot
command.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time
from pathlib import Path

from gate5_lowstate_safety_monitor import (
    LowStatePacketError,
    packet_age_s,
    parse_lowstate_telemetry,
)

DEFAULT_PORT = 5007
DEFAULT_TIMEOUT_S = 8.0
DEFAULT_MAX_PACKET_AGE_S = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive one G1 hardware initial-state snapshot"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--max-packet-age",
        type=float,
        default=DEFAULT_MAX_PACKET_AGE_S,
    )
    parser.add_argument("--expected-source-ip")
    parser.add_argument("--expected-forward-token")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/runtime/g1_hardware_initial_state.json"),
    )
    return parser.parse_args()


def _raw_object(payload: bytes) -> dict[str, object]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("LowState telemetry root must be an object")
    return value


def _validate_provenance(
    raw: dict[str, object],
    source: tuple[str, int],
    *,
    expected_source_ip: str | None,
    expected_forward_token: str | None,
) -> None:
    if expected_source_ip is not None and source[0] != expected_source_ip:
        raise ValueError(
            f"unexpected LowState sender {source[0]}; expected {expected_source_ip}"
        )
    if expected_forward_token is not None:
        if raw.get("forward_token") != expected_forward_token:
            raise ValueError("LowState forward token mismatch")
    received_packets = raw.get("received_packets")
    sequence = raw.get("sequence")
    if (
        isinstance(received_packets, bool)
        or not isinstance(received_packets, int)
        or received_packets < 1
        or received_packets != sequence
    ):
        raise ValueError("LowState received_packets/sequence provenance is invalid")


def _validate_full_body_consistency(packet) -> None:
    if (
        packet.all_joint_names is None
        or packet.all_joint_q_rad is None
        or packet.all_joint_dq_rad_s is None
    ):
        raise ValueError("initial LowState snapshot requires canonical 29-joint fields")
    right_q = packet.all_joint_q_rad[22:29]
    right_dq = packet.all_joint_dq_rad_s[22:29]
    if any(
        abs(a - b) > 1.0e-9
        for a, b in zip(packet.measured_q_rad, right_q)
    ):
        raise ValueError("right-arm q conflicts with canonical 29-joint q")
    if any(
        abs(a - b) > 1.0e-9
        for a, b in zip(packet.measured_dq_rad_s, right_dq)
    ):
        raise ValueError("right-arm dq conflicts with canonical 29-joint dq")


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not math.isfinite(args.timeout) or args.timeout <= 0.0:
        raise SystemExit("--timeout must be finite and positive")
    if not math.isfinite(args.max_packet_age) or args.max_packet_age <= 0.0:
        raise SystemExit("--max-packet-age must be finite and positive")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(min(args.timeout, 0.25))
    print(f"[SYNC] Waiting for canonical G1 LowState snapshot on UDP {args.port}...")

    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline:
            try:
                payload, source = sock.recvfrom(8192)
            except socket.timeout:
                continue
            received_monotonic = time.monotonic()
            try:
                raw = _raw_object(payload)
                packet = parse_lowstate_telemetry(payload)
                _validate_provenance(
                    raw,
                    source,
                    expected_source_ip=args.expected_source_ip,
                    expected_forward_token=args.expected_forward_token,
                )
                _validate_full_body_consistency(packet)
                age_s = packet_age_s(
                    packet,
                    received_monotonic=received_monotonic,
                    now_monotonic=time.monotonic(),
                    now_unix_ns=time.time_ns(),
                )
                if age_s > args.max_packet_age:
                    raise ValueError(
                        f"LowState snapshot stale: {age_s:.3f}s > "
                        f"{args.max_packet_age:.3f}s"
                    )
            except (
                UnicodeDecodeError,
                ValueError,
                TypeError,
                json.JSONDecodeError,
                LowStatePacketError,
            ):
                continue

            output = {
                "schema": "g1.hardware_initial_state.v2",
                "received_at_unix_ns": time.time_ns(),
                "udp_source": f"{source[0]}:{source[1]}",
                "mode": "READ_ONLY_LOWSTATE_SNAPSHOT",
                "bridge_session_id": packet.bridge_session_id,
                "sequence": packet.sequence,
                "sent_at_unix_ns": packet.sent_at_unix_ns,
                "packet_age_s": age_s,
                "mode_pr": packet.mode_pr,
                "mode_machine": packet.mode_machine,
                "right_arm_q_rad": list(packet.measured_q_rad),
                "right_arm_dq_rad_s": list(packet.measured_dq_rad_s),
                "all_joint_names": list(packet.all_joint_names),
                "all_joint_q_rad": list(packet.all_joint_q_rad),
                "all_joint_dq_rad_s": list(packet.all_joint_dq_rad_s),
                "forward_token_verified": args.expected_forward_token is not None,
                "publisher_present": False,
                "command_output_enabled": False,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            temporary.write_text(json.dumps(output, indent=2), encoding="utf-8")
            temporary.replace(args.output)
            print("[SYNC] Fresh canonical G1 pose captured.")
            print(
                "[SYNC] q[deg]: "
                + ", ".join(
                    f"{value * 57.295779513:.2f}"
                    for value in packet.measured_q_rad
                )
            )
            return 0
    finally:
        sock.close()

    print(
        f"[ERROR] No fresh canonical G1 LowState snapshot received within "
        f"{args.timeout:.1f}s."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
