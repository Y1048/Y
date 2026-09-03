#!/usr/bin/env python3
"""Record strict Mink UDP packets while forwarding them to Gate 7 dry-run."""

from __future__ import annotations

import argparse
import base64
import json
import math
import socket
import time
import uuid
from pathlib import Path
from typing import Final

from arm_sdk_teleop_contract import Gate7ContractError, parse_mink_arm_sample
from gate7_mink_wsl_relay import MinkOrderGuard

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
CAPTURE_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "captures"
MAX_PACKET_BYTES: Final[int] = 65535


def _automatic_path() -> Path:
    CAPTURE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return CAPTURE_DIRECTORY / (
        "g1_mink_capture_" + time.strftime("%Y%m%d_%H%M%S") + ".jsonl"
    )


def _write_line(stream, value: dict) -> None:
    stream.write(json.dumps(value, separators=(",", ":")) + "\n")
    stream.flush()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record and forward strict Mink UDP")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=5008)
    parser.add_argument("--forward-host", default="127.0.0.1")
    parser.add_argument("--forward-port", type=int, default=5014)
    parser.add_argument("--duration-s", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.listen_host != "127.0.0.1" or args.forward_host != "127.0.0.1":
        raise ValueError("capture endpoints must remain localhost")
    if not 1 <= args.listen_port <= 65535 or not 1 <= args.forward_port <= 65535:
        raise ValueError("UDP ports must be within 1..65535")
    if not math.isfinite(args.duration_s) or args.duration_s < 0.0:
        raise ValueError("duration-s must be finite and non-negative")

    output_path = args.output or _automatic_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_path = output_path.with_suffix(".result.json")
    capture_id = uuid.uuid4().hex
    input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    order = MinkOrderGuard()
    accepted = 0
    rejected = 0
    started_monotonic = time.monotonic()
    started_unix_ns = time.time_ns()

    print("G1 Mink UDP capture -- NO ROBOT OUTPUT")
    print(f"Input:   udp://{args.listen_host}:{args.listen_port}")
    print(f"Forward: udp://{args.forward_host}:{args.forward_port}")
    print(f"Capture: {output_path.resolve()}")
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")

    try:
        input_socket.bind((args.listen_host, args.listen_port))
        input_socket.settimeout(0.1)
        with output_path.open("w", encoding="utf-8") as stream:
            _write_line(
                stream,
                {
                    "schema": "g1.mink.capture.manifest.v1",
                    "capture_id": capture_id,
                    "created_unix_ns": started_unix_ns,
                    "source": f"udp://{args.listen_host}:{args.listen_port}",
                    "forward": f"udp://{args.forward_host}:{args.forward_port}",
                    "payload_encoding": "base64_exact_udp_datagram",
                    "hardware_output_authorized": False,
                },
            )
            while args.duration_s == 0.0 or time.monotonic() - started_monotonic < args.duration_s:
                try:
                    payload, source = input_socket.recvfrom(MAX_PACKET_BYTES)
                except socket.timeout:
                    continue
                received = time.monotonic()
                try:
                    sample = parse_mink_arm_sample(payload)
                    order.Accept(sample.session_id, sample.sequence)
                except (Gate7ContractError, ValueError, UnicodeDecodeError):
                    rejected += 1
                    continue
                output_socket.sendto(payload, (args.forward_host, args.forward_port))
                _write_line(
                    stream,
                    {
                        "schema": "g1.mink.capture.packet.v1",
                        "capture_id": capture_id,
                        "index": accepted,
                        "offset_s": received - started_monotonic,
                        "source_host": source[0],
                        "source_port": source[1],
                        "session_id": sample.session_id,
                        "sequence": sample.sequence,
                        "input_command_mode": sample.input_command_mode,
                        "payload_base64": base64.b64encode(payload).decode("ascii"),
                    },
                )
                accepted += 1
    except KeyboardInterrupt:
        print("\n[STOP] Capture stopped by operator.")
    finally:
        input_socket.close()
        output_socket.close()

    result = {
        "schema": "g1.mink.capture.result.v1",
        "passed": accepted > 0,
        "capture_id": capture_id,
        "accepted_packets": accepted,
        "rejected_packets": rejected,
        "duration_s": time.monotonic() - started_monotonic,
        "capture_path": str(output_path.resolve()),
        "publisher_present": False,
        "command_output_enabled": False,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Accepted={accepted} rejected={rejected}")
    print(f"Capture saved to: {output_path.resolve()}")
    print(f"Result saved to: {result_path.resolve()}")
    if accepted == 0:
        print("[ACTION] Start Unity/Mink UDP 5008 output and record again.")
    return 0 if accepted > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
