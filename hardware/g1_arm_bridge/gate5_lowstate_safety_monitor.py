#!/usr/bin/env python3
"""실제 G1 LowState를 Safety Gate에 넣는 Gate 5 읽기 전용 모니터.

이 프로세스는 Windows에서 UDP telemetry만 받는다. Unitree SDK를 import하지
않고 DDS publisher나 모터 명령 경로도 만들지 않는다. 각 프레임에서 실제 측정
자세를 측정값과 HOLD 요청값 양쪽에 동일하게 넣어 Safety Gate의 신선도, 유한값,
관절 안전범위 검사를 수행한다. 거부된 판정은 항상 후보 관절 벡터를 제거한다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Mapping

from hardware_state import (
    FaultCode,
    HardwarePhase,
    build_status,
    write_status,
)
from safety_gate import SafetyConfig, SafetyDecision, evaluate_target

LOWSTATE_TELEMETRY_SCHEMA: Final[str] = "g1.lowstate.right_arm.v1"
LOWSTATE_MODE: Final[str] = "READ_ONLY_LOWSTATE"
LOWSTATE_TOPIC: Final[str] = "rt/lowstate"
DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 5007
DEFAULT_STARTUP_TIMEOUT_S: Final[float] = 8.0
DEFAULT_REPORT_HZ: Final[float] = 2.0
DEFAULT_EXPECTED_HZ: Final[float] = 30.0
MAX_PACKET_BYTES: Final[int] = 8192


class LowStatePacketError(ValueError):
    """수신한 telemetry가 Gate 5 계약을 만족하지 않을 때 발생한다."""


@dataclass(frozen=True)
class LowStateTelemetry:
    bridge_session_id: str
    sequence: int
    sent_at_unix_ns: int
    measured_q_rad: tuple[float, ...]
    measured_dq_rad_s: tuple[float, ...]


class PacketOrderTracker:
    """한 bridge 세션에서 LowState 순번이 계속 증가하는지 확인한다."""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.sequence: int | None = None

    def accept(self, packet: LowStateTelemetry) -> None:
        if self.session_id is None:
            self.session_id = packet.bridge_session_id
        elif packet.bridge_session_id != self.session_id:
            raise LowStatePacketError(
                "bridge_session_changed; restart Gate 5 explicitly"
            )

        if self.sequence is not None and packet.sequence <= self.sequence:
            raise LowStatePacketError(
                f"non_increasing_sequence:{packet.sequence}<={self.sequence}"
            )
        self.sequence = packet.sequence


def _finite_joint_vector(value: object, name: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != 7:
        raise LowStatePacketError(f"{name} must contain exactly 7 joints")
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise LowStatePacketError(f"{name} contains a non-numeric value") from exc
    if not all(math.isfinite(item) for item in vector):
        raise LowStatePacketError(f"{name} contains a non-finite value")
    return vector


def parse_lowstate_telemetry(payload: bytes) -> LowStateTelemetry:
    """UDP datagram 하나를 엄격한 Gate 5 LowState 문서로 변환한다."""

    try:
        message = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LowStatePacketError("invalid_json") from exc
    if not isinstance(message, dict):
        raise LowStatePacketError("packet_root_must_be_object")
    if message.get("schema") != LOWSTATE_TELEMETRY_SCHEMA:
        raise LowStatePacketError("unexpected_schema")
    if message.get("mode") != LOWSTATE_MODE:
        raise LowStatePacketError("unexpected_mode")
    if message.get("topic") != LOWSTATE_TOPIC:
        raise LowStatePacketError("unexpected_topic")
    if message.get("publisher_present") is not False:
        raise LowStatePacketError("source_reports_publisher_present")
    if message.get("command_output_enabled") is not False:
        raise LowStatePacketError("source_reports_command_output_enabled")

    session_id = message.get("bridge_session_id")
    if not isinstance(session_id, str) or not 8 <= len(session_id) <= 128:
        raise LowStatePacketError("invalid_bridge_session_id")

    sequence = message.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise LowStatePacketError("invalid_sequence")

    sent_at_unix_ns = message.get("sent_at_unix_ns")
    if (
        isinstance(sent_at_unix_ns, bool)
        or not isinstance(sent_at_unix_ns, int)
        or sent_at_unix_ns <= 0
    ):
        raise LowStatePacketError("invalid_sent_at_unix_ns")

    return LowStateTelemetry(
        bridge_session_id=session_id,
        sequence=sequence,
        sent_at_unix_ns=sent_at_unix_ns,
        measured_q_rad=_finite_joint_vector(
            message.get("right_arm_q_rad"), "right_arm_q_rad"
        ),
        measured_dq_rad_s=_finite_joint_vector(
            message.get("right_arm_dq_rad_s"), "right_arm_dq_rad_s"
        ),
    )


def packet_age_s(
    packet: LowStateTelemetry,
    *,
    received_monotonic: float,
    now_monotonic: float,
    now_unix_ns: int,
) -> float:
    """수신 후 경과시간과 송신 시각 기반 지연 중 더 보수적인 값을 사용한다."""

    receive_age = max(0.0, now_monotonic - received_monotonic)
    transport_age = max(0.0, (now_unix_ns - packet.sent_at_unix_ns) / 1e9)
    return max(receive_age, transport_age)


def evaluate_measured_hold(
    packet: LowStateTelemetry,
    *,
    age_s: float,
    dt_s: float,
    config: SafetyConfig,
) -> SafetyDecision:
    """실측 자세 자체를 HOLD 요청으로 사용해 Gate를 우회 없이 평가한다."""

    return evaluate_target(
        measured_q_rad=packet.measured_q_rad,
        requested_q_rad=packet.measured_q_rad,
        previous_command_q_rad=None,
        lowstate_age_s=age_s,
        dt_s=dt_s,
        config=config,
    )


def _fault_for_reason(reason: str) -> FaultCode:
    if reason == "lowstate_stale":
        return FaultCode.LOWSTATE_TIMEOUT
    if "joint_limit:" in reason:
        return FaultCode.JOINT_LIMIT
    if reason.startswith("target_error:"):
        return FaultCode.TARGET_ERROR
    return FaultCode.LOWSTATE_INVALID


def _degrees(values: tuple[float, ...] | None) -> list[float] | None:
    if values is None:
        return None
    return [math.degrees(value) for value in values]


def _details(
    *,
    host: str,
    port: int,
    config: SafetyConfig,
    source: str | None,
    packet: LowStateTelemetry | None,
    packet_age: float | None,
    decision: SafetyDecision | None,
    valid_packets: int,
    invalid_packets: int,
) -> dict[str, object]:
    measured = packet.measured_q_rad if packet is not None else None
    velocity = packet.measured_dq_rad_s if packet is not None else None
    candidate = decision.command_q_rad if decision is not None else None
    return {
        "gate": 5,
        "mode": "REAL_LOWSTATE_SAFETY_DRY_RUN",
        "command_authority": "NONE",
        "input_topic": LOWSTATE_TOPIC,
        "udp_listener": f"{host}:{port}",
        "source": source,
        "bridge_session_id": packet.bridge_session_id if packet else None,
        "packet_sequence": packet.sequence if packet else None,
        "packet_age_s": packet_age,
        "valid_packets": valid_packets,
        "invalid_packets": invalid_packets,
        "measured_q_rad": list(measured) if measured is not None else None,
        "measured_q_deg": _degrees(measured),
        "measured_dq_rad_s": list(velocity) if velocity is not None else None,
        "requested_q_rad": list(measured) if measured is not None else None,
        "candidate_q_rad": list(candidate) if candidate is not None else None,
        "candidate_q_deg": _degrees(candidate),
        "candidate_forwarded": False,
        "gate_decision": {
            "allowed": decision.allowed if decision is not None else False,
            "reason": decision.reason if decision is not None else "waiting",
            "rate_limited": decision.rate_limited if decision is not None else False,
        },
        "safety_config": {
            "lowstate_timeout_s": config.lowstate_timeout_s,
            "joint_limit_margin_deg": math.degrees(config.joint_limit_margin_rad),
            "max_target_error_deg": math.degrees(config.max_target_error_rad),
            "max_command_velocity_deg_s": math.degrees(
                config.max_command_velocity_rad_s
            ),
        },
        "dds_publisher_count": 0,
        "unitree_command_topic": None,
    }


def _record_status(
    status_path: Path,
    event_path: Path,
    *,
    phase: HardwarePhase,
    details: Mapping[str, object],
    fault_code: FaultCode = FaultCode.NONE,
    fault_message: str = "",
) -> dict[str, object]:
    payload = build_status(
        phase=phase,
        component="gate5_lowstate_safety_monitor",
        command_output_enabled=False,
        publisher_present=False,
        fault_code=fault_code,
        fault_message=fault_message,
        details=details,
    )
    write_status(status_path, payload)
    event_path.parent.mkdir(parents=True, exist_ok=True)
    with event_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def _print_decision(
    phase: HardwarePhase,
    packet: LowStateTelemetry | None,
    age_s: float | None,
    decision: SafetyDecision | None,
) -> None:
    sequence = packet.sequence if packet is not None else "-"
    age_ms = age_s * 1000.0 if age_s is not None else float("nan")
    reason = decision.reason if decision is not None else "waiting"
    print(
        f"[{phase.value}] sequence={sequence} age={age_ms:.1f}ms "
        f"reason={reason} candidate_forwarded=false"
    )
    if packet is not None:
        print(
            "  measured q[deg]: "
            + ", ".join(f"{value:.2f}" for value in _degrees(packet.measured_q_rad))
        )
    if decision is not None and decision.command_q_rad is not None:
        print(
            "  candidate q[deg]: "
            + ", ".join(f"{value:.2f}" for value in _degrees(decision.command_q_rad))
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate 5 real LowState -> Safety Gate monitor; sends no robot command"
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--startup-timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT_S
    )
    parser.add_argument("--report-hz", type=float, default=DEFAULT_REPORT_HZ)
    parser.add_argument(
        "--lowstate-timeout",
        type=float,
        default=SafetyConfig().lowstate_timeout_s,
    )
    parser.add_argument(
        "--status-json",
        type=Path,
        default=Path("logs/runtime/g1_gate5_lowstate_safety.json"),
    )
    parser.add_argument(
        "--event-log",
        type=Path,
        default=Path("logs/runtime/g1_gate5_lowstate_safety.jsonl"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if args.startup_timeout <= 0.0:
        raise SystemExit("--startup-timeout must be > 0")
    if args.report_hz <= 0.0:
        raise SystemExit("--report-hz must be > 0")
    if args.lowstate_timeout <= 0.0:
        raise SystemExit("--lowstate-timeout must be > 0")

    config = SafetyConfig(lowstate_timeout_s=args.lowstate_timeout)
    report_period = 1.0 / args.report_hz
    expected_period = 1.0 / DEFAULT_EXPECTED_HZ
    tracker = PacketOrderTracker()
    valid_packets = 0
    invalid_packets = 0
    last_packet: LowStateTelemetry | None = None
    last_source: str | None = None
    last_received_monotonic: float | None = None
    last_cycle_monotonic: float | None = None
    last_decision: SafetyDecision | None = None
    start_monotonic = time.monotonic()
    next_report = start_monotonic

    print("G1 Gate 5 - REAL LowState through Safety Gate")
    print("-------------------------------------------------")
    print(f"UDP listener:  {args.host}:{args.port}")
    print(f"LowState gate: {config.lowstate_timeout_s * 1000.0:.0f} ms")
    print("Unitree SDK:   NONE in this process")
    print("DDS publisher: NONE")
    print("Robot command: IMPOSSIBLE from this process")
    print(f"Status JSON:   {args.status_json.resolve()}")
    print(f"Event log:     {args.event_log.resolve()}")

    waiting_details = _details(
        host=args.host,
        port=args.port,
        config=config,
        source=None,
        packet=None,
        packet_age=None,
        decision=None,
        valid_packets=0,
        invalid_packets=0,
    )
    _record_status(
        args.status_json,
        args.event_log,
        phase=HardwarePhase.READ_ONLY_WAIT,
        details=waiting_details,
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.host, args.port))
    except OSError as exc:
        details = dict(waiting_details)
        details["socket_error"] = str(exc)
        _record_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.FAULT,
            details=details,
            fault_code=FaultCode.INTERNAL_ERROR,
            fault_message=f"UDP bind failed: {exc}",
        )
        print(f"[FAULT] UDP bind failed: {exc}")
        return 2

    sock.settimeout(min(0.05, config.lowstate_timeout_s / 4.0))
    try:
        while True:
            now_monotonic = time.monotonic()
            try:
                payload, source = sock.recvfrom(MAX_PACKET_BYTES)
            except socket.timeout:
                if last_packet is None:
                    if now_monotonic - start_monotonic >= args.startup_timeout:
                        message = (
                            "No valid LowState telemetry within "
                            f"{args.startup_timeout:.2f}s"
                        )
                        details = _details(
                            host=args.host,
                            port=args.port,
                            config=config,
                            source=None,
                            packet=None,
                            packet_age=None,
                            decision=None,
                            valid_packets=valid_packets,
                            invalid_packets=invalid_packets,
                        )
                        _record_status(
                            args.status_json,
                            args.event_log,
                            phase=HardwarePhase.FAULT,
                            details=details,
                            fault_code=FaultCode.LOWSTATE_TIMEOUT,
                            fault_message=message,
                        )
                        print(f"[FAULT] {message}; no command candidate exists.")
                        return 3
                    continue

                age = packet_age_s(
                    last_packet,
                    received_monotonic=last_received_monotonic,
                    now_monotonic=now_monotonic,
                    now_unix_ns=time.time_ns(),
                )
                dt = max(expected_period, now_monotonic - last_cycle_monotonic)
                decision = evaluate_measured_hold(
                    last_packet,
                    age_s=age,
                    dt_s=dt,
                    config=config,
                )
                if not decision.allowed:
                    last_decision = decision
                    details = _details(
                        host=args.host,
                        port=args.port,
                        config=config,
                        source=last_source,
                        packet=last_packet,
                        packet_age=age,
                        decision=decision,
                        valid_packets=valid_packets,
                        invalid_packets=invalid_packets,
                    )
                    _record_status(
                        args.status_json,
                        args.event_log,
                        phase=HardwarePhase.FAULT,
                        details=details,
                        fault_code=_fault_for_reason(decision.reason),
                        fault_message=decision.reason,
                    )
                    _print_decision(
                        HardwarePhase.FAULT, last_packet, age, decision
                    )
                    print("[FAULT] No command candidate was produced.")
                    return 4

                if now_monotonic >= next_report:
                    details = _details(
                        host=args.host,
                        port=args.port,
                        config=config,
                        source=last_source,
                        packet=last_packet,
                        packet_age=age,
                        decision=last_decision,
                        valid_packets=valid_packets,
                        invalid_packets=invalid_packets,
                    )
                    _record_status(
                        args.status_json,
                        args.event_log,
                        phase=HardwarePhase.HOLD_READY,
                        details=details,
                    )
                    _print_decision(
                        HardwarePhase.HOLD_READY,
                        last_packet,
                        age,
                        last_decision,
                    )
                    next_report = now_monotonic + report_period
                continue

            received_monotonic = time.monotonic()
            try:
                packet = parse_lowstate_telemetry(payload)
                tracker.accept(packet)
            except LowStatePacketError as exc:
                invalid_packets += 1
                message = str(exc)
                details = _details(
                    host=args.host,
                    port=args.port,
                    config=config,
                    source=f"{source[0]}:{source[1]}",
                    packet=last_packet,
                    packet_age=None,
                    decision=SafetyDecision(False, message, None),
                    valid_packets=valid_packets,
                    invalid_packets=invalid_packets,
                )
                _record_status(
                    args.status_json,
                    args.event_log,
                    phase=HardwarePhase.FAULT,
                    details=details,
                    fault_code=FaultCode.LOWSTATE_INVALID,
                    fault_message=message,
                )
                print(f"[FAULT] Invalid LowState telemetry: {message}")
                print("[FAULT] No command candidate was produced.")
                return 5

            dt = (
                expected_period
                if last_cycle_monotonic is None
                else max(1e-4, received_monotonic - last_cycle_monotonic)
            )
            age = packet_age_s(
                packet,
                received_monotonic=received_monotonic,
                now_monotonic=received_monotonic,
                now_unix_ns=time.time_ns(),
            )
            decision = evaluate_measured_hold(
                packet,
                age_s=age,
                dt_s=dt,
                config=config,
            )
            valid_packets += 1
            last_packet = packet
            last_source = f"{source[0]}:{source[1]}"
            last_received_monotonic = received_monotonic
            last_cycle_monotonic = received_monotonic
            last_decision = decision

            details = _details(
                host=args.host,
                port=args.port,
                config=config,
                source=last_source,
                packet=packet,
                packet_age=age,
                decision=decision,
                valid_packets=valid_packets,
                invalid_packets=invalid_packets,
            )
            if not decision.allowed or decision.command_q_rad is None:
                _record_status(
                    args.status_json,
                    args.event_log,
                    phase=HardwarePhase.FAULT,
                    details=details,
                    fault_code=_fault_for_reason(decision.reason),
                    fault_message=decision.reason,
                )
                _print_decision(HardwarePhase.FAULT, packet, age, decision)
                print("[FAULT] No command candidate was produced.")
                return 6

            if valid_packets == 1 or received_monotonic >= next_report:
                _record_status(
                    args.status_json,
                    args.event_log,
                    phase=HardwarePhase.HOLD_READY,
                    details=details,
                )
                _print_decision(HardwarePhase.HOLD_READY, packet, age, decision)
                next_report = received_monotonic + report_period
    except KeyboardInterrupt:
        now_monotonic = time.monotonic()
        age = (
            packet_age_s(
                last_packet,
                received_monotonic=last_received_monotonic,
                now_monotonic=now_monotonic,
                now_unix_ns=time.time_ns(),
            )
            if last_packet is not None
            else None
        )
        details = _details(
            host=args.host,
            port=args.port,
            config=config,
            source=last_source,
            packet=last_packet,
            packet_age=age,
            decision=last_decision,
            valid_packets=valid_packets,
            invalid_packets=invalid_packets,
        )
        _record_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.OFFLINE,
            details=details,
        )
        print("\n[STOP] Gate 5 stopped; no robot command was sent.")
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
