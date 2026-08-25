#!/usr/bin/env python3
"""Validate live Mink right-arm targets through the hardware safety gate.

This process listens only on localhost UDP 5008. It has no Unitree SDK import,
no DDS publisher, and cannot command the robot. The measured state is simulated
as the previously accepted safe command so we can exercise rate limiting and
all gate checks against the real live Mink target stream.
"""

from __future__ import annotations

import json
import math
import socket
import time

from safety_gate import SafetyConfig, evaluate_target

HOST = "127.0.0.1"
PORT = 5008
STALE_TIMEOUT_S = 0.35
REPORT_PERIOD_S = 1.0


def _fmt_deg(values: tuple[float, ...]) -> str:
    return ", ".join(f"{math.degrees(v):.1f}" for v in values)


def main() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    sock.settimeout(0.10)

    print("Mink -> G1 Safety Gate LIVE DRY RUN")
    print("-----------------------------------")
    print(f"Listening: udp://{HOST}:{PORT}")
    print("Unitree SDK: NONE")
    print("DDS publisher: NONE")
    print("Robot command: IMPOSSIBLE from this process")

    config = SafetyConfig()
    measured: tuple[float, ...] | None = None
    previous_command: tuple[float, ...] | None = None
    last_packet = float("-inf")
    last_cycle = time.monotonic()
    next_report = time.monotonic() + REPORT_PERIOD_S
    accepted = 0
    denied = 0
    rate_limited = 0
    packets = 0
    last_reason = "waiting"

    try:
        while True:
            now = time.monotonic()
            try:
                payload, _ = sock.recvfrom(4096)
            except socket.timeout:
                if packets and now - last_packet > STALE_TIMEOUT_S:
                    print(f"[PASS] Mink stream stale after {now-last_packet:.3f}s; no command candidate produced.")
                    print(f"[SUMMARY] packets={packets} accepted={accepted} denied={denied} rate_limited={rate_limited}")
                    return 0
                continue

            try:
                message = json.loads(payload.decode("utf-8"))
                joints = message.get("right_arm", {}).get("joints")
                if not isinstance(joints, list) or len(joints) != 7:
                    continue
                requested = tuple(float(v) for v in joints)
                if not all(math.isfinite(v) for v in requested):
                    continue
            except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                continue

            packets += 1
            last_packet = now
            if measured is None:
                measured = requested
                previous_command = requested
                last_cycle = now
                print("[SYNC] Initial simulated measured pose captured from Mink.")
                print("[SYNC] q[deg]: " + _fmt_deg(requested))
                continue

            dt = max(1e-4, now - last_cycle)
            last_cycle = now
            decision = evaluate_target(
                measured_q_rad=measured,
                requested_q_rad=requested,
                previous_command_q_rad=previous_command,
                lowstate_age_s=0.0,
                dt_s=dt,
                config=config,
            )
            last_reason = decision.reason

            if not decision.allowed or decision.command_q_rad is None:
                denied += 1
            else:
                accepted += 1
                if decision.rate_limited:
                    rate_limited += 1
                previous_command = decision.command_q_rad
                # Ideal-following plant for dry-run only. Real hardware phase will
                # replace this with actual rt/lowstate measured q every cycle.
                measured = decision.command_q_rad

            if now >= next_report:
                state = "ALLOW" if decision.allowed else "DENY"
                print(
                    f"[{state}] packets={packets} accepted={accepted} denied={denied} "
                    f"rate_limited={rate_limited} reason={last_reason}"
                )
                if decision.command_q_rad is not None:
                    print("       safe q[deg]: " + _fmt_deg(decision.command_q_rad))
                next_report = now + REPORT_PERIOD_S
    except KeyboardInterrupt:
        print("\n[PASS] Dry-run stopped by operator; no robot command was sent.")
        print(f"[SUMMARY] packets={packets} accepted={accepted} denied={denied} rate_limited={rate_limited}")
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
