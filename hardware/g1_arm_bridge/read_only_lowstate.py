#!/usr/bin/env python3
"""Read-only Unitree G1 right-arm LowState monitor and optional UDP forwarder.

SAFETY CONTRACT
---------------
This module intentionally creates NO DDS publisher and sends NO robot command.
It only subscribes to ``rt/lowstate``, reports the seven right-arm joints, and
optionally forwards those measured joint angles as ordinary UDP telemetry to
the teleoperation PC for startup synchronization.

Expected environment: Linux/WSL2 with Unitree ``unitree_sdk2_python`` installed.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from hardware_state import (
    FaultCode,
    HardwarePhase,
    build_status,
    write_status as write_runtime_status,
)

try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
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
        now = time.monotonic()
        with self._lock:
            self._latest = msg
            self._received += 1
            self._last_rx_monotonic = now

    def snapshot(self) -> tuple[LowState_ | None, int, float]:
        with self._lock:
            return self._latest, self._received, self._last_rx_monotonic


def _motor_value(state: LowState_, index: int, field: str) -> float:
    motor = state.motor_state[index]
    value = getattr(motor, field)
    if callable(value):
        value = value()
    return float(value)


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


def _write_status(
    path: Path,
    *,
    phase: HardwarePhase,
    network_interface: str,
    received: int,
    age_s: float | None,
    samples: list[JointSample],
    fault_code: FaultCode = FaultCode.NONE,
    fault_message: str = "",
) -> None:
    details = {
        "mode": "READ_ONLY",
        "topic": TOPIC_LOWSTATE,
        "network_interface": network_interface,
        "received_packets": received,
        "last_packet_age_s": age_s,
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
    received: int,
    samples: list[JointSample],
) -> None:
    payload = {
        "mode": "READ_ONLY_LOWSTATE",
        "received_packets": received,
        "sent_at_unix": time.time(),
        "right_arm_q_rad": [item.q_rad for item in samples],
        "right_arm_dq_rad_s": [item.dq_rad_s for item in samples],
    }
    sock.sendto(
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        (host, port),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 right-arm rt/lowstate monitor; sends no robot commands"
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_hz <= 0.0 or args.forward_hz <= 0.0:
        raise SystemExit("--print-hz and --forward-hz must be > 0")
    if args.timeout <= 0.0:
        raise SystemExit("--timeout must be > 0")

    print("G1 right-arm hardware bridge -- READ ONLY")
    print("-----------------------------------------")
    print(f"DDS interface: {args.network_interface}")
    print(f"DDS topic:     {TOPIC_LOWSTATE}")
    print("DDS publishers: NONE")
    print("Motor command:  IMPOSSIBLE from this process")
    if args.forward_host:
        print(
            f"UDP telemetry:  {args.forward_host}:{args.forward_port} "
            f"@ {args.forward_hz:.1f} Hz"
        )

    ChannelFactoryInitialize(args.domain_id, args.network_interface)
    monitor = ReadOnlyG1LowState()
    subscriber = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
    subscriber.Init(monitor.callback, 10)

    telemetry_sock = (
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if args.forward_host
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
    ever_received = False
    last_samples: list[JointSample] = []
    last_age_s: float | None = None

    try:
        while not stop.is_set():
            now = time.monotonic()
            state, received, last_rx = monitor.snapshot()
            age_s = now - last_rx

            if state is not None:
                ever_received = True
                samples = _read_right_arm(state)
                last_samples = samples
                last_age_s = age_s
                if now >= next_report:
                    _print_samples(received, age_s, samples)
                    _write_status(
                        args.status_json,
                        phase=HardwarePhase.READ_ONLY_ACTIVE,
                        network_interface=args.network_interface,
                        received=received,
                        age_s=age_s,
                        samples=samples,
                    )
                    next_report = now + print_period
                if telemetry_sock is not None and now >= next_forward:
                    _forward_snapshot(
                        telemetry_sock,
                        args.forward_host,
                        args.forward_port,
                        received,
                        samples,
                    )
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
                    fault_code=FaultCode.LOWSTATE_TIMEOUT,
                    fault_message=message,
                )
                print(
                    f"[FAULT] {message}. Still READ ONLY; no command was sent."
                )
                return 2

            time.sleep(min(0.02, print_period, forward_period))
    finally:
        if telemetry_sock is not None:
            telemetry_sock.close()

    _write_status(
        args.status_json,
        phase=HardwarePhase.OFFLINE,
        network_interface=args.network_interface,
        received=monitor.snapshot()[1],
        age_s=last_age_s,
        samples=last_samples,
    )
    print("\nStopped. No robot command was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
