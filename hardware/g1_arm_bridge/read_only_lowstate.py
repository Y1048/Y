#!/usr/bin/env python3
"""Unitree G1 29관절 LowState 읽기 전용 모니터와 선택적 UDP 전달기.

안전 계약:
- DDS publisher를 만들지 않는다.
- 로봇 명령을 보내지 않는다.
- rt/lowstate를 구독해 G1 29개 관절의 위치와 속도를 읽는다.
- 오른팔 7개 값은 기존 Safety Gate 호환 필드로 함께 유지한다.
- 측정 관절값은 일반 UDP telemetry로 PC에 전달하며 명령에는 사용하지 않는다.

실행 환경은 unitree_sdk2_python이 설치되고 G1과 연결된 Linux/WSL2이다.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import socket
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from hardware_state import (
    FaultCode,
    HardwarePhase,
    build_status,
    write_status as write_runtime_status,
)
from g1_base_state import (
    BASE_STATE_TOPIC,
    BasePoseNormalizer,
    InvalidBaseStateError,
    NormalizedBaseState,
)
from g1_joint_contract import G1_29_JOINT_NAMES

try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
except ImportError as exc:
    raise SystemExit(
        "unitree_sdk2py is not installed. Install Unitree's official "
        "unitree_sdk2_python package in the Linux/WSL2 environment connected to G1."
    ) from exc


TOPIC_LOWSTATE: Final[str] = "rt/lowstate"
RIGHT_ARM_JOINTS: Final[tuple[tuple[str, int], ...]] = (
    ("right_shoulder_pitch", 22),
    ("right_shoulder_roll", 23),
    ("right_shoulder_yaw", 24),
    ("right_elbow", 25),
    ("right_wrist_roll", 26),
    ("right_wrist_pitch", 27),
    ("right_wrist_yaw", 28),
)
DEFAULT_PRINT_HZ: Final[float] = 5.0
DEFAULT_TIMEOUT_S: Final[float] = 1.0
DEFAULT_FORWARD_HZ: Final[float] = 30.0
DEFAULT_FORWARD_PORT: Final[int] = 5007
DEFAULT_BASE_TIMEOUT_S: Final[float] = 0.25
# The legacy schema name is retained for Gate 5 compatibility; the payload now
# includes all 29 joint positions and velocities in addition to the arm fields.
LOWSTATE_TELEMETRY_SCHEMA: Final[str] = "g1.lowstate.right_arm.v1"


@dataclass(frozen=True)
class JointSample:
    name: str
    index: int
    q_rad: float
    dq_rad_s: float
    tau_est_nm: float


class ReadOnlyG1LowState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: LowState_ | None = None
        self._received = 0
        self._last_rx_monotonic = float("-inf")

    def callback(self, msg: LowState_) -> None:
        # DDS callback에서는 최신 메시지만 짧게 저장한다. 출력/파일/UDP 작업은
        # 별도 루프가 snapshot을 가져간 뒤 수행해 수신 스레드를 막지 않는다.
        now = time.monotonic()
        with self._lock:
            self._latest = msg
            self._received += 1
            self._last_rx_monotonic = now

    def snapshot(self) -> tuple[LowState_ | None, int, float]:
        with self._lock:
            return self._latest, self._received, self._last_rx_monotonic


class ReadOnlyG1BaseState:
    """명령 기능 없이 odometry 최신값을 상대 base pose로 보관한다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._normalizer = BasePoseNormalizer()
        self._latest: NormalizedBaseState | None = None
        self._received = 0
        self._invalid = 0
        self._last_rx_monotonic = float("-inf")

    def callback(self, msg: SportModeState_) -> None:
        now = time.monotonic()
        try:
            with self._lock:
                self._latest = self._normalizer.Normalize(
                    msg.position,
                    msg.imu_state.quaternion,
                    msg.velocity,
                    msg.yaw_speed,
                )
                self._received += 1
                self._last_rx_monotonic = now
        except InvalidBaseStateError:
            with self._lock:
                self._invalid += 1

    def snapshot(
        self,
    ) -> tuple[NormalizedBaseState | None, int, int, float]:
        with self._lock:
            return (
                self._latest,
                self._received,
                self._invalid,
                self._last_rx_monotonic,
            )


def _motor_value(state: LowState_, index: int, field: str) -> float:
    motor = state.motor_state[index]
    value = getattr(motor, field)
    if callable(value):
        value = value()
    return float(value)


def _state_uint8(state: LowState_, field: str) -> int:
    value = getattr(state, field)
    if callable(value):
        value = value()
    result = int(value)
    if not 0 <= result <= 255:
        raise ValueError(f"{field} is outside uint8 range: {result}")
    return result


def _read_right_arm(state: LowState_) -> list[JointSample]:
    return [
        JointSample(
            name=name,
            index=index,
            q_rad=_motor_value(state, index, "q"),
            dq_rad_s=_motor_value(state, index, "dq"),
            tau_est_nm=_motor_value(state, index, "tau_est"),
        )
        for name, index in RIGHT_ARM_JOINTS
    ]


def _read_g1_29_vector(state: LowState_, field: str) -> list[float]:
    return [_motor_value(state, index, field) for index in range(29)]


def _write_status(
    path: Path,
    *,
    phase: HardwarePhase,
    network_interface: str,
    received: int,
    age_s: float | None,
    samples: list[JointSample],
    all_joint_q_rad: list[float] | None = None,
    all_joint_dq_rad_s: list[float] | None = None,
    mode_pr: int | None = None,
    mode_machine: int | None = None,
    base_state: dict[str, object] | None = None,
    fault_code: FaultCode = FaultCode.NONE,
    fault_message: str = "",
) -> None:
    details = {
        "mode": "READ_ONLY",
        "topic": TOPIC_LOWSTATE,
        "network_interface": network_interface,
        "received_packets": received,
        "last_packet_age_s": age_s,
        "mode_pr": mode_pr,
        "mode_machine": mode_machine,
        "right_arm": [
            {
                "name": item.name,
                "index": item.index,
                "q_rad": item.q_rad,
                "q_deg": math.degrees(item.q_rad),
                "dq_rad_s": item.dq_rad_s,
                "tau_est_nm": item.tau_est_nm,
            }
            for item in samples
        ],
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": all_joint_q_rad,
        "all_joint_dq_rad_s": all_joint_dq_rad_s,
        "base_state": base_state,
    }
    payload = build_status(
        phase=phase,
        component="read_only_lowstate",
        command_output_enabled=False,
        publisher_present=False,
        fault_code=fault_code,
        fault_message=fault_message,
        details=details,
    )
    write_runtime_status(path, payload)


def _print_samples(received: int, age_s: float, samples: list[JointSample]) -> None:
    print(f"\nLowState packets: {received} | age: {age_s * 1000.0:.1f} ms")
    print(" idx  joint                         q[deg]    dq[deg/s]   tau_est[Nm]")
    print(" ---  ----------------------------  --------  ----------  -----------")
    for item in samples:
        print(
            f" {item.index:>3}  {item.name:<28} "
            f"{math.degrees(item.q_rad):>8.2f}  "
            f"{math.degrees(item.dq_rad_s):>10.2f}  "
            f"{item.tau_est_nm:>11.3f}"
        )


def _forward_snapshot(
    sock: socket.socket,
    host: str,
    port: int,
    bridge_session_id: str,
    received: int,
    samples: list[JointSample],
    mode_pr: int,
    mode_machine: int,
    all_joint_q_rad: list[float],
    all_joint_dq_rad_s: list[float],
    base_state: dict[str, object],
) -> dict[str, object]:
    payload = {
        "schema": LOWSTATE_TELEMETRY_SCHEMA,
        "mode": "READ_ONLY_LOWSTATE",
        "topic": TOPIC_LOWSTATE,
        "bridge_session_id": bridge_session_id,
        "sequence": received,
        "received_packets": received,
        "mode_pr": mode_pr,
        "mode_machine": mode_machine,
        "sent_at_unix": time.time(),
        "sent_at_unix_ns": time.time_ns(),
        "right_arm_q_rad": [item.q_rad for item in samples],
        "right_arm_dq_rad_s": [item.dq_rad_s for item in samples],
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": all_joint_q_rad,
        "all_joint_dq_rad_s": all_joint_dq_rad_s,
        "base_state": base_state,
        "publisher_present": False,
        "command_output_enabled": False,
    }
    sock.sendto(
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        (host, port),
    )
    return payload


def _base_state_payload(
    monitor: ReadOnlyG1BaseState,
    now_monotonic: float,
    timeout_s: float,
) -> dict[str, object]:
    state, received, invalid, last_rx = monitor.snapshot()
    age_s = None if state is None else max(0.0, now_monotonic - last_rx)
    valid = state is not None and age_s is not None and age_s <= timeout_s
    values = (
        state.ToPacket()
        if state is not None
        else {
            "position_m": [0.0, 0.0, 0.0],
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
            "velocity_mps": [0.0, 0.0, 0.0],
            "yaw_speed_rad_s": 0.0,
        }
    )
    return {
        "valid": valid,
        "topic": BASE_STATE_TOPIC,
        "received_packets": received,
        "invalid_packets": invalid,
        "last_packet_age_s": age_s,
        **values,
    }


def _resolve_record_path(value: str | None) -> Path | None:
    if value is None:
        return None
    if value.lower() == "auto":
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return Path("logs/runtime") / f"g1_live_state_{timestamp}.jsonl"
    return Path(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 29-joint rt/lowstate monitor; sends no robot commands"
    )
    parser.add_argument(
        "network_interface",
        help="Linux network interface connected to G1, e.g. eth0 or enp3s0",
    )
    parser.add_argument("--domain-id", type=int, default=0, help="DDS domain ID")
    parser.add_argument("--print-hz", type=float, default=DEFAULT_PRINT_HZ)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--status-json",
        type=Path,
        default=Path("logs/runtime/g1_hardware_lowstate.json"),
    )
    parser.add_argument(
        "--forward-host",
        help="Optional teleoperation-PC IPv4 address for READ-ONLY startup telemetry",
    )
    parser.add_argument("--forward-port", type=int, default=DEFAULT_FORWARD_PORT)
    parser.add_argument("--forward-hz", type=float, default=DEFAULT_FORWARD_HZ)
    parser.add_argument(
        "--base-timeout",
        type=float,
        default=DEFAULT_BASE_TIMEOUT_S,
        help="Maximum rt/odommodestate age before base pose becomes invalid",
    )
    parser.add_argument(
        "--record-jsonl",
        help="Write each forwarded UDP 5009 source packet; use 'auto' for a timestamped path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_hz <= 0.0 or args.forward_hz <= 0.0:
        raise SystemExit("--print-hz and --forward-hz must be > 0")
    if args.timeout <= 0.0 or args.base_timeout <= 0.0:
        raise SystemExit("--timeout and --base-timeout must be > 0")
    record_path = _resolve_record_path(args.record_jsonl)
    if record_path is not None and not args.forward_host:
        raise SystemExit("--record-jsonl requires --forward-host")

    print("G1 29-joint hardware bridge -- READ ONLY")
    print("----------------------------------------")
    print(f"DDS interface: {args.network_interface}")
    print(f"DDS topic:     {TOPIC_LOWSTATE}")
    print(f"Base topic:    {BASE_STATE_TOPIC} (read-only odometry)")
    print("DDS publishers: NONE")
    print("Motor command:  IMPOSSIBLE from this process")
    if args.forward_host:
        print(
            f"UDP telemetry:  {args.forward_host}:{args.forward_port} "
            f"@ {args.forward_hz:.1f} Hz"
        )
    if record_path is not None:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Telemetry log: {record_path.resolve()}")

    ChannelFactoryInitialize(args.domain_id, args.network_interface)
    monitor = ReadOnlyG1LowState()
    subscriber = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
    subscriber.Init(monitor.callback, 10)
    base_monitor = ReadOnlyG1BaseState()
    base_subscriber = ChannelSubscriber(BASE_STATE_TOPIC, SportModeState_)
    base_subscriber.Init(base_monitor.callback, 10)

    telemetry_sock = (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if args.forward_host
        else None
    )
    record_stream = (
        record_path.open("w", encoding="utf-8")
        if record_path is not None
        else None
    )
    stop = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    print_period = 1.0 / args.print_hz
    forward_period = 1.0 / args.forward_hz
    next_report = time.monotonic()
    next_forward = time.monotonic()
    bridge_session_id = uuid.uuid4().hex
    last_forwarded_received = -1
    ever_received = False
    last_samples: list[JointSample] = []
    last_age_s: float | None = None
    last_mode_pr: int | None = None
    last_mode_machine: int | None = None
    last_all_joint_q_rad: list[float] | None = None
    last_all_joint_dq_rad_s: list[float] | None = None

    try:
        while not stop.is_set():
            now = time.monotonic()
            state, received, last_rx = monitor.snapshot()
            age_s = now - last_rx
            base_state = _base_state_payload(
                base_monitor,
                now,
                args.base_timeout,
            )

            if state is not None:
                ever_received = True
                samples = _read_right_arm(state)
                mode_pr = _state_uint8(state, "mode_pr")
                mode_machine = _state_uint8(state, "mode_machine")
                all_joint_q_rad = _read_g1_29_vector(state, "q")
                all_joint_dq_rad_s = _read_g1_29_vector(state, "dq")
                last_samples = samples
                last_age_s = age_s
                last_mode_pr = mode_pr
                last_mode_machine = mode_machine
                last_all_joint_q_rad = all_joint_q_rad
                last_all_joint_dq_rad_s = all_joint_dq_rad_s
                if now >= next_report:
                    _print_samples(received, age_s, samples)
                    _write_status(
                        args.status_json,
                        phase=HardwarePhase.READ_ONLY_ACTIVE,
                        network_interface=args.network_interface,
                        received=received,
                        age_s=age_s,
                        samples=samples,
                        all_joint_q_rad=all_joint_q_rad,
                        all_joint_dq_rad_s=all_joint_dq_rad_s,
                        mode_pr=mode_pr,
                        mode_machine=mode_machine,
                        base_state=base_state,
                    )
                    next_report = now + print_period
                if (
                    telemetry_sock is not None
                    and now >= next_forward
                    and received != last_forwarded_received
                ):
                    forwarded_payload = _forward_snapshot(
                        telemetry_sock,
                        args.forward_host,
                        args.forward_port,
                        bridge_session_id,
                        received,
                        samples,
                        mode_pr,
                        mode_machine,
                        all_joint_q_rad,
                        all_joint_dq_rad_s,
                        base_state,
                    )
                    if record_stream is not None:
                        record_stream.write(
                            json.dumps(forwarded_payload, separators=(",", ":"))
                            + "\n"
                        )
                        record_stream.flush()
                    last_forwarded_received = received
                    next_forward += forward_period
                    if next_forward <= now:
                        next_forward = now + forward_period
            elif now >= next_report:
                print("[WAIT] No rt/lowstate packet received yet.")
                _write_status(
                    args.status_json,
                    phase=HardwarePhase.READ_ONLY_WAIT,
                    network_interface=args.network_interface,
                    received=received,
                    age_s=None,
                    samples=[],
                    base_state=base_state,
                )
                next_report = now + print_period

            if ever_received and age_s > args.timeout:
                message = (
                    f"LowState heartbeat stale: {age_s:.3f}s > {args.timeout:.3f}s"
                )
                _write_status(
                    args.status_json,
                    phase=HardwarePhase.FAULT,
                    network_interface=args.network_interface,
                    received=received,
                    age_s=age_s,
                    samples=last_samples,
                    all_joint_q_rad=last_all_joint_q_rad,
                    all_joint_dq_rad_s=last_all_joint_dq_rad_s,
                    mode_pr=last_mode_pr,
                    mode_machine=last_mode_machine,
                    base_state=base_state,
                    fault_code=FaultCode.LOWSTATE_TIMEOUT,
                    fault_message=message,
                )
                print(
                    f"[FAULT] {message}. Still READ ONLY; no command was sent."
                )
                return 2

            next_deadline = next_report
            if telemetry_sock is not None:
                next_deadline = min(next_deadline, next_forward)
            sleep_s = max(
                0.001,
                min(0.01, next_deadline - time.monotonic()),
            )
            time.sleep(sleep_s)
    finally:
        if telemetry_sock is not None:
            telemetry_sock.close()
        if record_stream is not None:
            record_stream.close()
            print(f"Telemetry log saved: {record_path.resolve()}")

    _write_status(
        args.status_json,
        phase=HardwarePhase.OFFLINE,
        network_interface=args.network_interface,
        received=monitor.snapshot()[1],
        age_s=last_age_s,
        samples=last_samples,
        all_joint_q_rad=last_all_joint_q_rad,
        all_joint_dq_rad_s=last_all_joint_dq_rad_s,
        mode_pr=last_mode_pr,
        mode_machine=last_mode_machine,
        base_state=_base_state_payload(
            base_monitor,
            time.monotonic(),
            args.base_timeout,
        ),
    )
    print("\nStopped. No robot command was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
