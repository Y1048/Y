#!/usr/bin/env python3
"""Read-only Unitree G1 right-arm LowState monitor.

SAFETY CONTRACT
---------------
This module intentionally creates NO DDS publisher and sends NO robot command.
It only subscribes to ``rt/lowstate`` and reports the seven right-arm joints.
Use this as the first hardware connectivity test before any arm_sdk integration.

Expected environment: Linux with Unitree ``unitree_sdk2_python`` installed.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

try:
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
except ImportError as exc:
    raise SystemExit(
        "unitree_sdk2py is not installed. Install Unitree's official "
        "unitree_sdk2_python package on the Linux machine connected to G1."
    ) from exc


TOPIC_LOWSTATE: Final[str] = "rt/lowstate"

# Official G1 29-DoF joint order used by Unitree SDK2 examples.
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


@dataclass(frozen=True)
class JointSample:
    name: str
    index: int
    q_rad: float
    dq_rad_s: float
    tau_est_nm: float


class ReadOnlyG1LowState:
    """Thread-safe, read-only snapshot of G1 LowState."""

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
    # SDK2 Python IDL fields are normally exposed as attributes. Keep support
    # for generated accessor callables as a defensive compatibility fallback.
    if callable(value):
        value = value()
    return float(value)


def _read_right_arm(state: LowState_) -> list[JointSample]:
    samples: list[JointSample] = []
    for name, index in RIGHT_ARM_JOINTS:
        samples.append(
            JointSample(
                name=name,
                index=index,
                q_rad=_motor_value(state, index, "q"),
                dq_rad_s=_motor_value(state, index, "dq"),
                tau_est_nm=_motor_value(state, index, "tau_est"),
            )
        )
    return samples


def _write_status(path: Path, received: int, age_s: float, samples: list[JointSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "READ_ONLY",
        "topic": TOPIC_LOWSTATE,
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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 right-arm rt/lowstate monitor; sends no commands"
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_hz <= 0.0:
        raise SystemExit("--print-hz must be > 0")
    if args.timeout <= 0.0:
        raise SystemExit("--timeout must be > 0")

    print("G1 right-arm hardware bridge -- READ ONLY")
    print("-----------------------------------------")
    print(f"DDS interface: {args.network_interface}")
    print(f"DDS topic:     {TOPIC_LOWSTATE}")
    print("Publishers:    NONE")
    print("Motor command: IMPOSSIBLE from this process")

    ChannelFactoryInitialize(args.domain_id, args.network_interface)

    monitor = ReadOnlyG1LowState()
    subscriber = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
    subscriber.Init(monitor.callback, 10)

    stop = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    period = 1.0 / args.print_hz
    next_report = time.monotonic()
    ever_received = False

    while not stop.is_set():
        now = time.monotonic()
        state, received, last_rx = monitor.snapshot()
        age_s = now - last_rx

        if state is not None:
            ever_received = True
            if now >= next_report:
                samples = _read_right_arm(state)
                _print_samples(received, age_s, samples)
                _write_status(args.status_json, received, age_s, samples)
                next_report = now + period
        elif now >= next_report:
            print("[WAIT] No rt/lowstate packet received yet.")
            next_report = now + period

        if ever_received and age_s > args.timeout:
            print(
                f"[FAULT] LowState heartbeat stale: {age_s:.3f}s > "
                f"{args.timeout:.3f}s. Still READ ONLY; no command was sent."
            )
            return 2

        time.sleep(min(0.02, period))

    print("\nStopped. No robot command was sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
