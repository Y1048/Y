#!/usr/bin/env python3
"""Generate synthetic right-arm targets for the localhost Mink safety dry-run.

This utility sends only ordinary UDP packets to 127.0.0.1:5008. It has no
Unitree SDK dependency, creates no DDS publisher, and cannot command hardware.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time

HOST = "127.0.0.1"
PORT = 5008
DEFAULT_HZ = 60.0
DEFAULT_DURATION_S = 4.0

BASE_Q_DEG = (10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0)
AMPLITUDE_DEG = (7.0, 3.0, 4.0, 4.0, 5.0, 4.0, 4.0)
PHASE = (0.0, 0.8, 1.6, 2.4, 3.2, 4.0, 4.8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetic Mink right-arm UDP target generator")
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_S)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.hz <= 0.0 or args.duration <= 0.0:
        raise SystemExit("--hz and --duration must be > 0")

    period = 1.0 / args.hz
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start = time.monotonic()
    next_send = start
    packets = 0

    print("Synthetic Mink target generator")
    print("-------------------------------")
    print(f"Destination: udp://{HOST}:{PORT}")
    print(f"Rate:        {args.hz:.1f} Hz")
    print(f"Duration:    {args.duration:.1f} s")
    print("Robot command: NONE")

    try:
        while True:
            now = time.monotonic()
            elapsed = now - start
            if elapsed >= args.duration:
                break
            if now < next_send:
                time.sleep(min(0.002, next_send - now))
                continue

            phase = elapsed * 2.0 * math.pi * 0.55
            q_deg = [
                base + amp * math.sin(phase + offset)
                for base, amp, offset in zip(BASE_Q_DEG, AMPLITUDE_DEG, PHASE)
            ]
            q_rad = [math.radians(value) for value in q_deg]
            payload = {
                "right_arm": {
                    "joints": q_rad,
                    "active": True,
                },
                "timestamp": time.time(),
                "source": "synthetic_mink_target",
            }
            sock.sendto(json.dumps(payload, separators=(",", ":")).encode("utf-8"), (HOST, PORT))
            packets += 1
            next_send += period
    finally:
        sock.close()

    print(f"[PASS] Sent {packets} synthetic target packets.")
    print("[INFO] Stream stopped intentionally; receiver should enter stale-stop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
