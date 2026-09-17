"""Send one bounded velocity-axis trial to an already-running G1 owner.

This process contains no Unitree SDK, DDS, or LowCmd publisher. It discovers
the existing single command owner and sends token-bound UDP velocity requests.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time
import uuid

try:
    from .g1_omni_velocity_gateway import encode_command
    from .g1_velocity_discovery import DEFAULT_DISCOVERY_PORT, make_listener, parse_discovery
except ImportError:
    from g1_omni_velocity_gateway import encode_command
    from g1_velocity_discovery import DEFAULT_DISCOVERY_PORT, make_listener, parse_discovery


def velocity_for(axis: str, magnitude: float):
    result = [0.0, 0.0, 0.0]
    result[{"vx": 0, "vy": 1, "yaw": 2}[axis]] = magnitude
    return tuple(result)


def discover(listener, token: str, timeout_s: float):
    listener.settimeout(0.2)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            raw, peer = listener.recvfrom(2049)
        except socket.timeout:
            continue
        try:
            packet = parse_discovery(raw, token)
        except (ValueError, json.JSONDecodeError):
            continue
        return peer[0], packet["velocity_port"], packet["robot_id"]
    raise RuntimeError("no token-matched G1 velocity owner discovered")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis", choices=("vx", "vy", "yaw"), required=True)
    parser.add_argument("--sign", choices=("positive", "negative"), required=True)
    parser.add_argument("--relay-token", required=True)
    parser.add_argument("--magnitude", type=float, default=0.05)
    parser.add_argument("--prezero-seconds", type=float, default=6.0)
    parser.add_argument("--command-seconds", type=float, default=8.0)
    parser.add_argument("--zero-seconds", type=float, default=12.0)
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--rate-hz", type=float, default=50.0)
    args = parser.parse_args()
    if not args.relay_token.isascii() or not args.relay_token.isalnum() or not 16 <= len(args.relay_token) <= 128:
        raise ValueError("invalid relay token")
    if not 0.01 <= args.magnitude <= 0.10:
        raise ValueError("trial magnitude must be in [0.01, 0.10]")
    if not 4.5 <= args.command_seconds <= 15.0:
        raise ValueError("command duration must allow the 4 s policy blend")
    if not 5.0 <= args.prezero_seconds <= 30.0:
        raise ValueError("prezero duration must cover initial takeover blend")
    if not 8.0 <= args.zero_seconds <= 30.0:
        raise ValueError("zero duration must allow settle and static-policy blend")
    if not 20.0 <= args.rate_hz <= 100.0:
        raise ValueError("rate")

    listener = make_listener(args.discovery_port)
    host, port, robot_id = discover(listener, args.relay_token, 10.0)
    listener.close()
    output = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    session = uuid.uuid4().hex
    sequence = 0
    sign = 1.0 if args.sign == "positive" else -1.0
    trial_velocity = velocity_for(args.axis, sign * args.magnitude)
    interval = 1.0 / args.rate_hz
    print(f"[DISCOVERED] {robot_id} at {host}:{port}", flush=True)
    print(f"[TRIAL] {args.axis} {args.sign} {sign * args.magnitude:+.3f}; "
          f"zero {args.prezero_seconds:.1f}s, command {args.command_seconds:.1f}s, "
          f"then zero {args.zero_seconds:.1f}s", flush=True)

    def send_for(velocity, duration):
        nonlocal sequence
        deadline = time.monotonic() + duration
        next_send = time.monotonic()
        while next_send < deadline:
            now = time.monotonic()
            if now < next_send:
                time.sleep(next_send - now)
            now = time.monotonic()
            output.sendto(encode_command(session, sequence, now, velocity,
                                         args.relay_token), (host, port))
            sequence += 1
            next_send += interval

    try:
        send_for((0.0, 0.0, 0.0), args.prezero_seconds)
        send_for(trial_velocity, args.command_seconds)
    finally:
        send_for((0.0, 0.0, 0.0), args.zero_seconds)
        output.close()
    print("[COMPLETE] zero velocity tail sent", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
