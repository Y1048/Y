#!/usr/bin/env python3
"""Receive one fresh G1 right-arm LowState snapshot over UDP and persist it.

This process runs on the Windows teleoperation PC. It receives a read-only
snapshot forwarded by the Linux G1 bridge and writes the seven right-arm joint
angles to logs/runtime/g1_hardware_initial_state.json for Mink startup.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

DEFAULT_PORT = 5007
DEFAULT_TIMEOUT_S = 8.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Receive one G1 hardware initial-state snapshot")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/runtime/g1_hardware_initial_state.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(args.timeout)
    print(f"[SYNC] Waiting for G1 LowState snapshot on UDP {args.port}...")

    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline:
            try:
                payload, source = sock.recvfrom(4096)
            except socket.timeout:
                break
            try:
                message = json.loads(payload.decode("utf-8"))
                joints = message.get("right_arm_q_rad")
                if not isinstance(joints, list) or len(joints) != 7:
                    continue
                joints = [float(value) for value in joints]
                if not all(abs(value) < 10.0 for value in joints):
                    continue
            except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                continue

            output = {
                "received_at_unix": time.time(),
                "source": f"{source[0]}:{source[1]}",
                "mode": "READ_ONLY_LOWSTATE_SNAPSHOT",
                "right_arm_q_rad": joints,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            temporary.write_text(json.dumps(output, indent=2), encoding="utf-8")
            temporary.replace(args.output)
            print("[SYNC] Fresh G1 right-arm pose captured.")
            print("[SYNC] q[deg]: " + ", ".join(f"{value * 57.295779513:.2f}" for value in joints))
            return 0
    finally:
        sock.close()

    print(f"[ERROR] No valid G1 LowState snapshot received within {args.timeout:.1f}s.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
