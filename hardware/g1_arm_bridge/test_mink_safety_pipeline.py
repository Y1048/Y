#!/usr/bin/env python3
"""End-to-end offline test for the Mink-target safety dry-run pipeline.

This test launches the real localhost UDP 5008 dry-run consumer, injects a
smooth 60 Hz synthetic seven-joint target stream, then stops transmission and
requires the consumer to exit only after detecting a stale stream. No Unitree
SDK, DDS publisher, Unity, MuJoCo, or robot is involved.
"""

from __future__ import annotations

import json
import math
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONSUMER = HERE / "mink_target_dry_run.py"
HOST = "127.0.0.1"
PORT = 5008
HZ = 60.0
DURATION_S = 4.0

READY_RAD = tuple(
    math.radians(value)
    for value in (10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0)
)


def _target_at(t: float) -> tuple[float, ...]:
    """Generate a safe but fast-enough trajectory to exercise rate limiting."""
    phase = 2.0 * math.pi * 0.50 * t
    q = list(READY_RAD)
    q[0] += math.radians(8.0) * math.sin(phase)
    q[1] += math.radians(5.0) * math.sin(phase + 0.35)
    q[2] += math.radians(6.0) * math.sin(phase + 0.70)
    q[3] += math.radians(4.0) * math.sin(phase + 1.05)
    q[4] += math.radians(5.0) * math.sin(phase + 1.40)
    q[5] += math.radians(4.0) * math.sin(phase + 1.75)
    q[6] += math.radians(4.0) * math.sin(phase + 2.10)
    return tuple(q)


def main() -> int:
    print("G1 Mink -> Safety Gate end-to-end OFFLINE test")
    print("------------------------------------------------")
    print("Unity:       NONE")
    print("MuJoCo:      NONE")
    print("Unitree SDK: NONE")
    print("DDS:         NONE")
    print("Robot cmd:   NONE")

    process = subprocess.Popen(
        [sys.executable, str(CONSUMER)],
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        time.sleep(0.35)
        start = time.monotonic()
        period = 1.0 / HZ
        sequence = 0
        next_send = start

        while True:
            now = time.monotonic()
            elapsed = now - start
            if elapsed >= DURATION_S:
                break
            if now < next_send:
                time.sleep(min(0.002, next_send - now))
                continue

            joints = _target_at(elapsed)
            packet = {
                "right_arm": {"joints": list(joints)},
                "active": True,
                "sequence": sequence,
                "timestamp": time.time(),
            }
            sock.sendto(
                json.dumps(packet, separators=(",", ":")).encode("utf-8"),
                (HOST, PORT),
            )
            sequence += 1
            next_send += period

        print(f"[TEST] Sent {sequence} synthetic target packets at ~{HZ:.0f} Hz.")
        print("[TEST] Transmission stopped; waiting for stale-stream shutdown...")

        try:
            output, _ = process.communicate(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
            print(output)
            print("[FAIL] Dry-run consumer did not stop after target stream became stale.")
            return 2

        print(output, end="")
        if process.returncode != 0:
            print(f"[FAIL] Dry-run consumer exited with code {process.returncode}.")
            return 3
        if "Mink stream stale" not in output:
            print("[FAIL] Stale-stream fail-safe was not observed.")
            return 4
        if "accepted=" not in output:
            print("[FAIL] No accepted safety-gate cycles were reported.")
            return 5

        print("[PASS] UDP target -> Safety Gate -> stale-stop pipeline passed.")
        print("[PASS] No robot command path existed during this test.")
        return 0
    finally:
        sock.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
