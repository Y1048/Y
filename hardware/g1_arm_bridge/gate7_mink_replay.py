#!/usr/bin/env python3
"""Replay a validated Mink capture with fresh transport metadata."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from arm_sdk_teleop_contract import parse_mink_arm_sample

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CapturedPacket:
    index: int
    offset_s: float
    payload: bytes


def LoadCapture(path: Path) -> tuple[dict, tuple[CapturedPacket, ...]]:
    manifest = None
    packets: list[CapturedPacket] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        schema = value.get("schema")
        if schema == "g1.mink.capture.manifest.v1":
            if manifest is not None or packets:
                raise ValueError("capture manifest must be the first record")
            if value.get("hardware_output_authorized") is not False:
                raise ValueError("capture manifest is not hardware locked")
            manifest = value
        elif schema == "g1.mink.capture.packet.v1":
            if manifest is None:
                raise ValueError("capture packet appeared before manifest")
            payload = base64.b64decode(value["payload_base64"], validate=True)
            parse_mink_arm_sample(payload)
            packet = CapturedPacket(
                index=int(value["index"]),
                offset_s=float(value["offset_s"]),
                payload=payload,
            )
            if packet.index != len(packets):
                raise ValueError(f"capture packet index gap at line {line_number}")
            if not math.isfinite(packet.offset_s) or packet.offset_s < 0.0:
                raise ValueError("capture packet offset must be finite and non-negative")
            if packets and packet.offset_s < packets[-1].offset_s:
                raise ValueError("capture packet offsets must be monotonic")
            packets.append(packet)
        else:
            raise ValueError(f"unknown capture schema at line {line_number}")
    if manifest is None or not packets:
        raise ValueError("capture must contain a manifest and at least one packet")
    return manifest, tuple(packets)


def NormalizePayload(payload: bytes, *, session_id: str, sequence: int) -> bytes:
    value = json.loads(payload.decode("utf-8"))
    value["session_id"] = session_id
    value["sequence"] = sequence
    value["timestamp"] = time.time()
    value["input_packet_age_s"] = 0.0
    normalized = json.dumps(value, separators=(",", ":")).encode("utf-8")
    parse_mink_arm_sample(normalized)
    return normalized


def CaptureSha256(packets: tuple[CapturedPacket, ...]) -> str:
    digest = hashlib.sha256()
    for packet in packets:
        digest.update(packet.payload)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a strict Mink UDP capture")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5008)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--no-timing", action="store_true")
    parser.add_argument("--exact-transport", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.host != "127.0.0.1":
        raise ValueError("replay destination must remain localhost")
    if not 1 <= args.port <= 65535:
        raise ValueError("port must be within 1..65535")
    if not math.isfinite(args.speed) or args.speed <= 0.0:
        raise ValueError("speed must be finite and positive")
    manifest, packets = LoadCapture(args.capture)
    replay_session = "replay-" + uuid.uuid4().hex
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    started = time.monotonic()
    try:
        for index, packet in enumerate(packets):
            if not args.no_timing:
                target = started + packet.offset_s / args.speed
                while True:
                    remaining_s = target - time.monotonic()
                    if remaining_s <= 0.0:
                        break
                    time.sleep(min(0.002, remaining_s))
            payload = (
                packet.payload
                if args.exact_transport
                else NormalizePayload(packet.payload, session_id=replay_session, sequence=index)
            )
            sock.sendto(payload, (args.host, args.port))
    finally:
        sock.close()
    print("[PASS] Mink capture replay completed.")
    print(f"Capture ID: {manifest['capture_id']}")
    print(f"Packets: {len(packets)}")
    print(f"Payload SHA256: {CaptureSha256(packets)}")
    print("Unitree SDK: NONE / DDS publisher: NONE / Robot command: NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
