#!/usr/bin/env python3
"""Validate localhost Gate 7 Mink packets and relay them to WSL.

입력: Windows localhost UDP 5008의 Mink 관절 후보/상태 JSON.
출력: 형식과 순서를 검증하고 필요한 필드만 WSL UDP 5013으로 전달한다.
이 파일은 SDK publisher를 만들지 않지만 출력은 실제 로봇 제어 경로의 입력이다.
최종 명령 허용 여부는 gate7_live_arm_sdk.py에서 실측 상태와 함께 판단한다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from arm_sdk_teleop_contract import Gate7ContractError, parse_mink_arm_sample
from g1_joint_contract import G1_29_JOINT_NAMES

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_RESULT_DIR: Final[Path] = PROJECT_ROOT / "logs" / "test_results"
MAX_PACKET_BYTES: Final[int] = 65535
MAX_RELAY_PACKET_BYTES: Final[int] = 1400


@dataclass
class MinkOrderGuard:
    session_id: str | None = None
    sequence: int | None = None

    def Accept(self, session_id: str | None, sequence: int) -> None:
        if session_id != self.session_id:
            self.session_id = session_id
            self.sequence = sequence
            return
        if self.sequence is not None and sequence <= self.sequence:
            raise Gate7ContractError(
                f"non-increasing Mink sequence:{sequence}<={self.sequence}"
            )
        self.sequence = sequence


def ValidateRelayEndpoint(listen_host: str, target_host: str, target_port: int) -> None:
    if listen_host != "127.0.0.1":
        raise ValueError("relay listen host must remain 127.0.0.1")
    if not target_host.strip():
        raise ValueError("target host must not be empty")
    if not 1 <= int(target_port) <= 65535:
        raise ValueError("target port must be within 1..65535")


def ValidateAndForward(
    payload: bytes,
    order_guard: MinkOrderGuard,
    output_socket: socket.socket,
    target: tuple[str, int],
) -> None:
    """후보 패킷을 검증·축약해 송신한다. 관절각은 rad이며 IK를 재계산하지 않는다."""
    sample = parse_mink_arm_sample(payload)
    order_guard.Accept(sample.session_id, sample.sequence)
    # The full Unity/Mink diagnostic packet can exceed the Ethernet MTU and
    # fragmented Windows-to-WSL UDP is not reliable on mirrored networking.
    # Re-serialize only contract fields after strict validation.
    all_q = [round(value, 10) for value in sample.all_joint_q_rad]
    canonical = {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": sample.sequence,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": all_q,
        "right_arm": {
            "joints": all_q[22:29],
            "active": sample.active,
            "workspace_limited": sample.workspace_limited,
            "collision_limited": sample.collision_limited,
            "minimum_clearance_m": sample.minimum_clearance_m,
            "command_state": sample.controller_state,
        },
        "input_command_mode": sample.input_command_mode,
        "session_id": sample.session_id,
        "input_packet_age_s": sample.input_packet_age_s,
        "timestamp": sample.timestamp_s,
    }
    forwarded = json.dumps(canonical, separators=(",", ":")).encode("utf-8")
    if len(forwarded) > MAX_RELAY_PACKET_BYTES:
        raise Gate7ContractError(
            f"canonical relay packet exceeds {MAX_RELAY_PACKET_BYTES} bytes"
        )
    parse_mink_arm_sample(forwarded)
    output_socket.sendto(forwarded, target)


def _automatic_result_path() -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return DEFAULT_RESULT_DIR / f"g1_gate7_mink_wsl_relay_{timestamp}.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate 7 localhost-to-WSL relay")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=5008)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-port", type=int, default=5013)
    parser.add_argument("--duration-s", type=float, default=0.0)
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ValidateRelayEndpoint(args.listen_host, args.target_host, args.target_port)
    if not 1 <= args.listen_port <= 65535:
        raise ValueError("listen port must be within 1..65535")
    if not math.isfinite(args.duration_s) or args.duration_s < 0.0:
        raise ValueError("duration-s must be finite and non-negative")

    print("G1 Gate 7 Mink relay")
    print(f"Input:  udp://{args.listen_host}:{args.listen_port}")
    print(f"Output: udp://{args.target_host}:{args.target_port}")
    print("Unitree SDK: NONE")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    if args.validate_only:
        print("[PASS] Relay configuration and packet contract are valid.")
        return 0

    result_path = args.result_json or _automatic_result_path()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    input_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    output_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    order_guard = MinkOrderGuard()
    accepted = 0
    rejected = 0
    started = time.monotonic()
    try:
        input_socket.bind((args.listen_host, args.listen_port))
        input_socket.settimeout(0.1)
        while args.duration_s == 0.0 or time.monotonic() - started < args.duration_s:
            try:
                payload, source = input_socket.recvfrom(MAX_PACKET_BYTES)
            except socket.timeout:
                continue
            if source[0] != "127.0.0.1":
                rejected += 1
                continue
            try:
                ValidateAndForward(
                    payload,
                    order_guard,
                    output_socket,
                    (args.target_host, args.target_port),
                )
                accepted += 1
                if accepted == 1:
                    print(
                        "[RELAY] First valid Mink packet forwarded to "
                        f"udp://{args.target_host}:{args.target_port}",
                        flush=True,
                    )
                elif accepted % 250 == 0:
                    print(
                        f"[RELAY] Forwarded {accepted} valid Mink packets; "
                        f"rejected={rejected}",
                        flush=True,
                    )
            except (Gate7ContractError, ValueError, UnicodeDecodeError):
                rejected += 1
    except KeyboardInterrupt:
        print("\n[STOP] Relay stopped by operator.")
    finally:
        input_socket.close()
        output_socket.close()

    result = {
        "schema": "g1.gate7.mink_wsl_relay.result.v1",
        "passed": accepted > 0,
        "accepted_packets": accepted,
        "rejected_packets": rejected,
        "publisher_present": False,
        "command_output_enabled": False,
        "unitree_sdk_imported": False,
        "target": f"udp://{args.target_host}:{args.target_port}",
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Accepted={accepted} rejected={rejected}")
    print(f"Result saved to: {result_path.resolve()}")
    if accepted == 0:
        print("[ACTION] Start Unity/Mink output on UDP 5008, then retry.")
    return 0 if accepted > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
