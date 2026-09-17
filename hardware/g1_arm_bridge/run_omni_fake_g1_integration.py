"""Run the real Omni Gateway against a loopback-only fake G1 receiver.

This is a PC-only integration harness.  It deliberately uses test ports and
binds/sends only on 127.0.0.1, so it cannot discover or command a physical G1.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import secrets
import select
import socket
import subprocess
import sys
import threading
import time


DISCOVERY_SCHEMA = "g1.velocity.discovery.v1"
COMMAND_SCHEMA = "g1.velocity.command.v1"
PROVENANCE = "omni_gateway"
DEFAULT_DISCOVERY_PORT = 55118
DEFAULT_VELOCITY_PORT = 55117


def discovery_loop(stop: threading.Event, token: str, discovery_port: int,
                   velocity_port: int) -> None:
    packet = json.dumps({
        "schema": DISCOVERY_SCHEMA,
        "robot_id": "pc-loopback-fake-g1",
        "velocity_port": velocity_port,
        "sequence": 0,
        "relay_token": token,
    }, separators=(",", ":")).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while not stop.wait(0.10):
            sock.sendto(packet, ("127.0.0.1", discovery_port))
    finally:
        sock.close()


def validate_command(raw: bytes, token: str, previous_sequence: int | None):
    packet = json.loads(raw)
    if packet.get("schema") != COMMAND_SCHEMA:
        raise ValueError("schema")
    if packet.get("command_provenance") != PROVENANCE:
        raise ValueError("provenance")
    if packet.get("simulation_only") is not False:
        raise ValueError("simulation_only")
    if packet.get("relay_token") != token:
        raise ValueError("relay_token")
    sequence = packet.get("sequence")
    timestamp = packet.get("source_monotonic_s")
    velocity = packet.get("velocity")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("sequence")
    if previous_sequence is not None and sequence <= previous_sequence:
        raise ValueError("non-monotonic sequence")
    if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
        raise ValueError("timestamp")
    if not isinstance(velocity, list) or len(velocity) != 3:
        raise ValueError("velocity")
    velocity = tuple(float(value) for value in velocity)
    if not all(math.isfinite(value) for value in velocity):
        raise ValueError("nonfinite velocity")
    return sequence, velocity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=float, default=120.0)
    parser.add_argument("--start-delay-seconds", type=float, default=0.0)
    parser.add_argument("--omni-url", default="ws://127.0.0.1:32123")
    parser.add_argument("--discovery-port", type=int,
                        default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--velocity-port", type=int,
                        default=DEFAULT_VELOCITY_PORT)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    if not 2.0 <= args.duration_seconds <= 3600.0:
        raise ValueError("duration must be in [2, 3600] seconds")

    root = Path(__file__).resolve().parents[2]
    token = secrets.token_hex(16)
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", args.velocity_port))
    receiver.setblocking(False)
    stop = threading.Event()
    discovery = threading.Thread(
        target=discovery_loop,
        args=(stop, token, args.discovery_port, args.velocity_port),
        daemon=True,
    )
    discovery.start()

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-B",
        str(root / "hardware/g1_arm_bridge/g1_omni_velocity_gateway.py"),
        "--relay-token", token,
        "--omni-url", args.omni_url,
        "--discovery-port", str(args.discovery_port),
        "--duration-seconds", str(args.duration_seconds),
        "--start-delay-seconds", str(args.start_delay_seconds),
        "--csv", str(args.csv),
    ]
    print("[PC-ONLY] Real Omni Connect -> Gateway -> fake G1 receiver", flush=True)
    print("[PC-ONLY] All discovery and velocity UDP stays on 127.0.0.1", flush=True)
    print("[PC-ONLY] No Unitree SDK, DDS, LowCmd, SSH, or physical G1 output", flush=True)
    print(f"[CSV] {args.csv}", flush=True)
    process = subprocess.Popen(command, cwd=root)
    packets = 0
    rejected = 0
    previous_sequence = None
    peaks = [0.0, 0.0, 0.0]
    last_printed = -math.inf
    try:
        while process.poll() is None:
            readable, _, _ = select.select([receiver], [], [], 0.10)
            if not readable:
                continue
            raw, peer = receiver.recvfrom(4096)
            if peer[0] != "127.0.0.1":
                rejected += 1
                continue
            try:
                previous_sequence, velocity = validate_command(
                    raw, token, previous_sequence)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                rejected += 1
                continue
            packets += 1
            peaks = [max(peaks[index], abs(velocity[index]))
                     for index in range(3)]
            now = time.monotonic()
            if now - last_printed >= 0.20:
                print(f"[FAKE G1] received vx={velocity[0]:+.3f} "
                      f"vy={velocity[1]:+.3f} wz={velocity[2]:+.3f}",
                      flush=True)
                last_printed = now
        return_code = process.wait()
    except KeyboardInterrupt:
        print("\n[STOP] PC-only test interrupted; terminating Gateway", flush=True)
        process.terminate()
        return_code = process.wait(timeout=5.0)
    finally:
        stop.set()
        receiver.close()
        if process.poll() is None:
            process.terminate()

    summary = {
        "status": "PASS" if return_code == 0 and packets > 0 else "FAIL",
        "gateway_exit_code": return_code,
        "packets_received": packets,
        "packets_rejected": rejected,
        "peak_abs_vx": peaks[0],
        "peak_abs_vy": peaks[1],
        "peak_abs_yaw_rate": peaks[2],
        "csv": str(args.csv),
        "physical_g1_output": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
