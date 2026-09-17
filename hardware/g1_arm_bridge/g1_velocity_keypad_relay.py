"""Validated loopback Unity keypad -> G1 UDP relay. Contains no Unitree SDK or DDS."""
import argparse
import json
import math
from pathlib import Path
import socket
import select
import time

from g1_velocity_discovery import DEFAULT_DISCOVERY_PORT, make_listener, parse_discovery

SCHEMA = "g1.velocity.keypad.v1"
LIMITS = (0.80, 0.80, 0.80)


class StalePacket(ValueError):
    """A duplicate or reordered UDP sample that must not be forwarded."""


def strict_load(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("packet object")
    return value


def validate(packet: dict) -> dict:
    if packet.get("schema") != SCHEMA or packet.get("command_provenance") != "unity_keypad":
        raise ValueError("provenance")
    if packet.get("simulation_only") is not False:
        raise ValueError("simulation_only")
    session = packet.get("session")
    if not isinstance(session, str) or not session or len(session) > 128:
        raise ValueError("session")
    if type(packet.get("sequence")) is not int or not 0 <= packet["sequence"] < 2**63:
        raise ValueError("sequence")
    stamp = packet.get("source_monotonic_s")
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0:
        raise ValueError("timestamp")
    velocity = packet.get("velocity")
    if not isinstance(velocity, list) or len(velocity) != 3:
        raise ValueError("velocity")
    for value, limit in zip(velocity, LIMITS):
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > limit + 1e-6:
            raise ValueError("velocity range")
    return packet


def validate_order(previous_session: str | None, previous_sequence: int,
                   packet: dict) -> bool:
    """Validate ordering and report a legitimate Unity Play restart."""
    if previous_session is None:
        return False
    if packet["session"] == previous_session:
        if packet["sequence"] <= previous_sequence:
            raise StalePacket("sequence")
        return False
    if packet["sequence"] != 0:
        raise ValueError("session restart sequence")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-host", default="auto",
                        help="G1 IPv4 or 'auto' for UDP discovery")
    parser.add_argument("--target-port", type=int, default=5017)
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--relay-token", required=True)
    parser.add_argument("--status-file", type=Path)
    args = parser.parse_args()
    if not args.relay_token.isascii() or not args.relay_token.isalnum() or not 16 <= len(args.relay_token) <= 128:
        raise ValueError("invalid relay token")
    inbound = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    inbound.bind(("127.0.0.1", 5016))
    outbound = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    outbound.bind(("0.0.0.0", 0))
    discovery = None
    target = None
    if args.target_host == "auto":
        discovery = make_listener(args.discovery_port)
    else:
        target = (args.target_host, args.target_port)
    session = None
    sequence = -1
    last_received = -math.inf
    last_velocity = None
    target_text = "auto-discovered G1" if target is None else f"{target[0]}:{target[1]}"
    print(f"Unity keypad localhost:5016 -> {target_text}; no SDK/DDS", flush=True)
    while True:
        readable, _, _ = select.select(
            [inbound] + ([] if discovery is None else [discovery]), [], [], 1.0)
        if discovery is not None and discovery in readable:
            raw, peer = discovery.recvfrom(2049)
            try:
                announcement = parse_discovery(raw, args.relay_token)
            except (ValueError, json.JSONDecodeError):
                continue
            candidate = (peer[0], announcement["velocity_port"])
            if target is None:
                target = candidate
                print(f"[DISCOVERY] robot_id={announcement['robot_id']} target={target[0]}:{target[1]}", flush=True)
            elif target != candidate:
                print(f"[DISCOVERY] ignored additional robot_id={announcement['robot_id']} target={candidate[0]}:{candidate[1]}", flush=True)
            readable.remove(discovery)
        if inbound not in readable:
            continue
        try:
            raw, peer = inbound.recvfrom(2049)
        except ConnectionResetError as exc:
            # Windows reports an ICMP port-unreachable on a later recvfrom when
            # G1 has not bound 5017 yet. Keep the relay alive for Robot startup.
            if getattr(exc, "winerror", None) != 10054:
                raise
            continue
        if peer[0] != "127.0.0.1" or len(raw) > 2048:
            raise ValueError("source/size")
        now = time.monotonic()
        packet = validate(strict_load(raw))
        try:
            restarted = validate_order(session, sequence, packet)
        except StalePacket:
            print(f"[KEYPAD] dropped stale sequence={packet['sequence']} after {sequence}",
                  flush=True)
            continue
        if restarted:
            print(f"[KEYPAD] Unity Play session restarted: {packet['session']}",
                  flush=True)
            last_velocity = None
        session = packet["session"]
        sequence = packet["sequence"]
        last_received = now
        forwarded = dict(packet)
        forwarded["relay_token"] = args.relay_token
        data = json.dumps(forwarded, allow_nan=False, separators=(",", ":")).encode()
        if target is not None:
            outbound.sendto(data, target)
        current_velocity = tuple(float(value) for value in packet["velocity"])
        if current_velocity != last_velocity:
            print(f"[KEYPAD] velocity={current_velocity}", flush=True)
            if args.status_file:
                args.status_file.parent.mkdir(parents=True, exist_ok=True)
                args.status_file.write_text(json.dumps({
                    "received_monotonic_s": now,
                    "session": packet["session"],
                    "sequence": packet["sequence"],
                    "velocity": current_velocity,
                }, allow_nan=False, indent=2) + "\n", encoding="utf-8")
            last_velocity = current_velocity


if __name__ == "__main__":
    main()
