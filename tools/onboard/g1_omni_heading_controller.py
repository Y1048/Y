#!/usr/bin/env python3
"""Omni observation -> GR00T high-level locomotion controller.

This process is the UDP 55070 receiver, so it replaces
G1_INPUT_RECEIVE_AUDIT.py while active.  It never uses Unitree DDS or LowCmd.
It receives the existing observation-only packet, acknowledges the exact
datagram, receives G1 state from the C++ runtime on localhost:15101, and sends
only vx/vy/wz high-level commands to localhost:15100.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import select
import socket
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


OMNI_ADDRESS = ("0.0.0.0", 55070)
COMMAND_ADDRESS = ("127.0.0.1", 15100)
STATE_ADDRESS = ("127.0.0.1", 15101)
QUEST_FORWARD_HOST = "127.0.0.1"
QUEST_FORWARD_PORT = 15102
OBSERVATION_SCHEMA = "g1.observation.audit.v1"
ACK_SCHEMA = "g1.observation.audit.ack.v1"
SEND_PERIOD_S = 0.02
DISPLAY_PERIOD_S = 0.25
LINEAR_COMMAND_LIMIT = 1.0
YAW_COMMAND_LIMIT = 0.70


class AsyncJsonlLog:
    """Bounded non-blocking JSONL writer for control-path diagnostics."""

    def __init__(self, path: Path, capacity: int = 4096) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path.resolve()
        self._stream = path.open("x", encoding="utf-8")
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=capacity)
        self._stop = threading.Event()
        self.dropped = 0
        self.written = 0
        self.error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, row: Dict[str, Any]) -> None:
        if self.error is not None:
            self.dropped += 1
            return
        enriched = dict(row)
        enriched.setdefault("log_monotonic_s", time.monotonic())
        try:
            self._queue.put_nowait(enriched)
        except queue.Full:
            self.dropped += 1

    def _run(self) -> None:
        last_flush = time.monotonic()
        pending_flush = 0
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    row = self._queue.get(timeout=0.05)
                except queue.Empty:
                    row = None
                if row is not None:
                    self._stream.write(
                        json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n"
                    )
                    self.written += 1
                    pending_flush += 1
                now = time.monotonic()
                if pending_flush and (pending_flush >= 64 or now - last_flush >= 0.10):
                    self._stream.flush()
                    pending_flush = 0
                    last_flush = now
            self._stream.write(
                json.dumps(
                    {
                        "kind": "log_summary",
                        "records_written": self.written,
                        "records_dropped": self.dropped,
                        "log_monotonic_s": time.monotonic(),
                    },
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            self._stream.flush()
        except (OSError, TypeError, ValueError) as exc:
            self.error = str(exc)
        finally:
            try:
                self._stream.close()
            except OSError:
                pass

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def angular_delta(current: float, previous: float) -> float:
    """Shortest signed delta, valid across the +/-pi wrap boundary."""
    difference = current - previous
    return math.atan2(math.sin(difference), math.cos(difference))


@dataclass
class RobotState:
    sequence: int
    yaw: float
    received_at: float


@dataclass
class OmniSample:
    session: str
    sequence: int
    source_session: Optional[str]
    omni_live: bool
    vx: float
    vy: float
    arm_yaw_rad: float
    source_age: float
    arms_active: bool
    arm_state: str
    arm_source_age: float
    left_q: Tuple[float, ...]
    right_q: Tuple[float, ...]
    received_at: float


class RawTerminal:
    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.original = None

    def __enter__(self) -> "RawTerminal":
        if not sys.stdin.isatty():
            raise RuntimeError("controller requires an interactive terminal")
        self.original = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.original is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.original)

    def read_available(self) -> str:
        ready, _, _ = select.select([sys.stdin], [], [], 0.0)
        return sys.stdin.read(1) if ready else ""


class HeadingFollower:
    """Tracks Omni relative yaw with G1 relative yaw using proportional wz."""

    def __init__(self, gain: float, max_wz: float, deadband_rad: float, sign: float) -> None:
        self.gain = gain
        self.max_wz = max_wz
        self.deadband_rad = deadband_rad
        self.sign = sign
        self.reset()

    def reset(self) -> None:
        self.omni_previous: Optional[float] = None
        self.robot_previous: Optional[float] = None
        self.omni_relative = 0.0
        self.robot_relative = 0.0
        self.ready = False

    def update(self, omni_yaw: float, robot_yaw: float) -> Tuple[float, float, float]:
        if self.omni_previous is None or self.robot_previous is None:
            self.omni_previous = omni_yaw
            self.robot_previous = robot_yaw
            self.omni_relative = 0.0
            self.robot_relative = 0.0
            self.ready = True
        else:
            self.omni_relative += angular_delta(omni_yaw, self.omni_previous)
            self.robot_relative += angular_delta(robot_yaw, self.robot_previous)
            self.omni_previous = omni_yaw
            self.robot_previous = robot_yaw

        target = self.sign * self.omni_relative
        error = target - self.robot_relative
        wz = 0.0 if abs(error) <= self.deadband_rad else clamp(self.gain * error, self.max_wz)
        return target, error, wz


def parse_robot_state(raw: bytes, now: float) -> Optional[RobotState]:
    try:
        packet = json.loads(raw.decode("utf-8"))
        if not isinstance(packet, dict):
            return None
        if not isinstance(packet.get("seq"), int) or packet["seq"] < 0:
            return None
        if not finite_number(packet.get("yaw")):
            return None
        q = packet.get("q")
        dq = packet.get("dq")
        if not isinstance(q, list) or len(q) != 29 or not all(finite_number(x) for x in q):
            return None
        if not isinstance(dq, list) or len(dq) != 29 or not all(finite_number(x) for x in dq):
            return None
        return RobotState(packet["seq"], float(packet["yaw"]), now)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_omni_observation(raw: bytes, now: float) -> OmniSample:
    if len(raw) > 6000:
        raise ValueError("packet_size")

    def reject_nonfinite(_: str) -> None:
        raise ValueError("nonfinite")

    packet = json.loads(raw.decode("utf-8"), parse_constant=reject_nonfinite)
    if not isinstance(packet, dict):
        raise ValueError("object_required")
    if packet.get("schema") != OBSERVATION_SCHEMA or packet.get("observation_only") is not True:
        raise ValueError("schema")
    session = packet.get("session")
    if (
        not isinstance(session, str)
        or len(session) != 32
        or any(character not in "0123456789abcdef" for character in session)
    ):
        raise ValueError("session")
    sequence = packet.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or not 0 <= sequence < 2**53:
        raise ValueError("sequence")
    payload = packet.get("payload")
    omni = payload.get("omni") if isinstance(payload, dict) else None
    if not isinstance(omni, dict):
        raise ValueError("omni")
    omni_live = omni.get("status") == "FRESH_LIVE"
    if omni.get("status") == "WAIT":
        # This exact shape is LiveSources.snapshot() before its first sample.
        # Do not turn malformed/live/uncalibrated data into a missing device.
        if omni != {"status": "WAIT", "source_age_s": None, "values": None}:
            raise ValueError("omni_wait")
        source_session = None
        source_age = float("inf")
        vx = vy = arm_yaw_rad = 0.0
    else:
        # Preserve all existing validation and values for connected sources.
        for age_name in ("source_age_s", "source_receive_age_s"):
            age = omni.get(age_name)
            if not finite_number(age) or age < 0.0:
                raise ValueError(age_name)
        source_session = omni.get("source_session")
        if not isinstance(source_session, str) or not source_session:
            raise ValueError("source_session")
        values = omni.get("values")
        if not isinstance(values, dict) or values.get("calibrated") is not True:
            raise ValueError("omni_values")
        for name in ("vx", "vy", "arm_yaw_deg"):
            if not finite_number(values.get(name)):
                raise ValueError(name)
        vx = float(values["vx"])
        vy = float(values["vy"])
        arm_yaw_rad = math.radians(float(values["arm_yaw_deg"]))
        source_age = max(float(omni["source_age_s"]), float(omni["source_receive_age_s"]))

    arms_active = False
    arm_state = "unavailable"
    arm_source_age = float("inf")
    left_q: Tuple[float, ...] = ()
    right_q: Tuple[float, ...] = ()
    arm = payload.get("arm")
    if isinstance(arm, dict) and arm.get("status") == "FRESH_LIVE":
        arm_ages = (arm.get("source_age_s"), arm.get("source_receive_age_s"))
        if not all(finite_number(age) and age >= 0.0 for age in arm_ages):
            raise ValueError("arm_source_age")
        arm_values = arm.get("values")
        if not isinstance(arm_values, dict):
            raise ValueError("arm_values")
        arm_state_value = arm_values.get("state")
        if arm_state_value not in ("ready", "tracking", "returning", "blocked"):
            raise ValueError("arm_state")
        arm_state = arm_state_value
        left = arm_values.get("left_q_rad")
        right = arm_values.get("right_q_rad")
        if (
            not isinstance(left, list)
            or len(left) != 7
            or not all(finite_number(value) for value in left)
            or not isinstance(right, list)
            or len(right) != 7
            or not all(finite_number(value) for value in right)
        ):
            raise ValueError("arm_joint_arrays")
        left_q = tuple(float(value) for value in left)
        right_q = tuple(float(value) for value in right)
        arm_source_age = max(float(arm_ages[0]), float(arm_ages[1]))
        # ready/blocked values are observations, not active motor targets.
        # returning remains active so the upstream controller can perform its
        # intentional return trajectory at the same rate limit.
        arms_active = arm_state in ("tracking", "returning")
    return OmniSample(
        session=session,
        sequence=sequence,
        source_session=source_session,
        omni_live=omni_live,
        vx=vx,
        vy=vy,
        arm_yaw_rad=arm_yaw_rad,
        source_age=source_age,
        arms_active=arms_active,
        arm_state=arm_state,
        arm_source_age=arm_source_age,
        left_q=left_q,
        right_q=right_q,
        received_at=now,
    )


def send_ack(sock: socket.socket, peer: Tuple[str, int], raw: bytes, sample: OmniSample,
             receive_count: int, now: float) -> None:
    # The ACK proves transport receipt only; it deliberately does not claim actuation.
    ack: Dict[str, Any] = {
        "schema": ACK_SCHEMA,
        "session": sample.session,
        "sequence": sample.sequence,
        "received_sha256": hashlib.sha256(raw).hexdigest(),
        "receive_count": receive_count,
        "receiver_monotonic_s": now,
        "motor_acceptance": "NOT_CHECKED",
    }
    sock.sendto(json.dumps(ack, separators=(",", ":")).encode("utf-8"), peer)


def send_command(
    sock: socket.socket,
    sequence: int,
    vx: float,
    vy: float,
    wz: float,
    arms_active: bool = False,
    left_q: Tuple[float, ...] = (),
    right_q: Tuple[float, ...] = (),
) -> Dict[str, Any]:
    packet = {
        "seq": sequence,
        "timestamp": time.monotonic(),
        "vx": clamp(vx, LINEAR_COMMAND_LIMIT),
        "vy": clamp(vy, LINEAR_COMMAND_LIMIT),
        "wz": clamp(wz, YAW_COMMAND_LIMIT),
        "arms": {"active": arms_active},
    }
    if arms_active:
        if len(left_q) != 7 or len(right_q) != 7:
            raise ValueError("active arm command requires left_q[7] and right_q[7]")
        packet["arms"]["left_q"] = list(left_q)
        packet["arms"]["right_q"] = list(right_q)
    sock.sendto(json.dumps(packet, separators=(",", ":")).encode("utf-8"), COMMAND_ADDRESS)
    return packet


def send_zero(sock: socket.socket, sequence: int) -> None:
    for offset in range(5):
        send_command(sock, sequence + offset, 0.0, 0.0, 0.0)
        time.sleep(0.01)


def run_self_test() -> int:
    assert clamp(0.98, LINEAR_COMMAND_LIMIT) == 0.98
    assert clamp(-1.0, LINEAR_COMMAND_LIMIT) == -1.0
    assert abs(math.degrees(angular_delta(math.radians(-179), math.radians(179))) - 2.0) < 1e-9
    follower = HeadingFollower(1.5, 0.7, math.radians(0.5), +1.0)
    target, error, wz = follower.update(math.radians(112.5), math.radians(170.0))
    assert (target, error, wz) == (0.0, 0.0, 0.0)
    target, error, wz = follower.update(math.radians(142.5), math.radians(170.0))
    assert abs(math.degrees(target) - 30.0) < 1e-9
    assert abs(math.degrees(error) - 30.0) < 1e-9
    assert abs(wz - 0.7) < 1e-9
    _, error, wz = follower.update(math.radians(142.5), math.radians(-170.0))
    assert abs(math.degrees(error) - 10.0) < 1e-9
    assert abs(wz - 1.5 * math.radians(10.0)) < 1e-9
    inverse = HeadingFollower(1.5, 0.7, 0.0, -1.0)
    inverse.update(0.0, 0.0)
    target, _, wz = inverse.update(math.radians(30.0), 0.0)
    assert target < 0.0 and wz < 0.0

    persistent = HeadingFollower(1.5, 0.7, 0.0, +1.0)
    persistent.update(math.radians(10.0), math.radians(20.0))
    persistent.update(math.radians(40.0), math.radians(30.0))
    # A transport/freshness gap performs no follower update and, critically,
    # no reset.  The first sample after reconnection is measured from the last
    # accepted angles, so the process-start reference remains authoritative.
    target, error, _ = persistent.update(math.radians(70.0), math.radians(40.0))
    assert abs(math.degrees(target) - 60.0) < 1e-9
    assert abs(math.degrees(error) - 40.0) < 1e-9
    persistent.reset()  # Models the explicit keyboard r/s action only.
    target, error, wz = persistent.update(math.radians(70.0), math.radians(40.0))
    assert (target, error, wz) == (0.0, 0.0, 0.0)

    sample_packet = {
        "schema": OBSERVATION_SCHEMA,
        "observation_only": True,
        "session": "0" * 32,
        "sequence": 1,
        "payload": {
            "omni": {
                "status": "FRESH_LIVE",
                "source_age_s": 0.0,
                "source_receive_age_s": 0.0,
                "source_session": "omni-test",
                "values": {
                    "vx": 0.0,
                    "vy": 0.0,
                    "arm_yaw_deg": 112.5,
                    "calibrated": True,
                },
            },
            "arm": {
                "status": "FRESH_LIVE",
                "source_age_s": 0.0,
                "source_receive_age_s": 0.0,
                "values": {
                    "state": "tracking",
                    "left_q_rad": [0.1] * 7,
                    "right_q_rad": [-0.1] * 7,
                },
            },
        },
    }
    sample = parse_omni_observation(
        json.dumps(sample_packet, separators=(",", ":")).encode("utf-8"),
        time.monotonic(),
    )
    assert sample.arms_active and sample.left_q == (0.1,) * 7
    sample_packet["payload"]["arm"]["values"]["state"] = "ready"
    sample = parse_omni_observation(
        json.dumps(sample_packet, separators=(",", ":")).encode("utf-8"),
        time.monotonic(),
    )
    assert not sample.arms_active
    sample_packet["payload"]["omni"]["status"] = "STALE"
    sample_packet["payload"]["omni"]["source_age_s"] = 10.0
    sample_packet["payload"]["arm"]["values"]["state"] = "tracking"
    sample = parse_omni_observation(
        json.dumps(sample_packet, separators=(",", ":")).encode("utf-8"),
        time.monotonic(),
    )
    assert not sample.omni_live and sample.arms_active
    sample_packet["payload"]["omni"] = {
        "status": "WAIT", "source_age_s": None, "values": None,
    }
    sample = parse_omni_observation(
        json.dumps(sample_packet, separators=(",", ":")).encode("utf-8"),
        time.monotonic(),
    )
    assert not sample.omni_live and sample.arms_active
    assert sample.source_session is None and math.isinf(sample.source_age)
    assert (sample.vx, sample.vy, sample.arm_yaw_rad) == (0.0, 0.0, 0.0)
    print("never-connected Omni / fresh bilateral arms decoupling test: PASS")
    print("body-frame vx/vy direct pass-through up to +/-1.0: PASS")
    print("wrap test: +179 deg -> -179 deg = +2 deg: PASS")
    print("relative heading test: Omni +30 deg -> target +30 deg: PASS")
    print("G1 wrap test: +170 deg -> -170 deg advances +20 deg: PASS")
    print("yaw-sign inversion test: PASS")
    print("stale/reconnect heading persistence and manual re-zero test: PASS")
    print("bilateral arm tracking/ready gating test: PASS")
    print("stale Omni / fresh tracking arms decoupling test: PASS")
    print("SELF TEST: PASS")
    return 0


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0", help="Omni observation bind address")
    parser.add_argument("--omni-port", type=int, default=55070)
    parser.add_argument(
        "--quest-forward-port",
        type=int,
        default=QUEST_FORWARD_PORT,
        help="localhost port receiving an exact live copy of each Omni/Quest datagram; 0 disables",
    )
    parser.add_argument("--yaw-kp", type=float, default=1.5, help="heading P gain in 1/s")
    parser.add_argument("--max-wz", type=float, default=0.70, help="absolute yaw-rate limit in rad/s")
    parser.add_argument("--yaw-deadband-deg", type=float, default=0.5)
    parser.add_argument(
        "--yaw-sign", type=float, choices=(-1.0, 1.0), default=1.0,
        help="mapping from increasing Omni armYaw to G1 positive yaw",
    )
    parser.add_argument("--freshness", type=float, default=0.25, help="input/state timeout in seconds")
    parser.add_argument("--duration", type=float, default=0.0, help="0 means until x/Ctrl+C")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="JSONL output path; default is logs/g1_omni_heading_<time>_<pid>.jsonl",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    for name in ("yaw_kp", "max_wz", "yaw_deadband_deg", "freshness", "duration"):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 0.0:
            parser.error(f"--{name.replace('_', '-')} must be finite and >= 0")
    if args.max_wz > YAW_COMMAND_LIMIT:
        parser.error(f"--max-wz must be <= {YAW_COMMAND_LIMIT}")
    if not 1 <= args.omni_port <= 65535:
        parser.error("--omni-port must be 1..65535")
    if not 0 <= args.quest_forward_port <= 65535:
        parser.error("--quest-forward-port must be 0..65535")

    omni_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    quest_forward_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    omni_socket.bind((args.bind, args.omni_port))
    state_socket.bind(STATE_ADDRESS)
    omni_socket.setblocking(False)
    state_socket.setblocking(False)

    log_path = args.log
    if log_path is None:
        log_path = Path("logs") / (
            "g1_omni_heading_"
            + time.strftime("%Y%m%d_%H%M%S")
            + f"_{os.getpid()}.jsonl"
        )
    diagnostic_log = AsyncJsonlLog(log_path)

    follower = HeadingFollower(
        args.yaw_kp, args.max_wz, math.radians(args.yaw_deadband_deg), args.yaw_sign
    )
    latest_omni: Optional[OmniSample] = None
    latest_state: Optional[RobotState] = None
    active_source_session: Optional[str] = None
    last_outer_sequence: Dict[Tuple[str, int, str], int] = {}
    command_sequence = 0
    received = rejected = stale_events = 0
    started = next_send = next_display = time.monotonic()
    base_was_fresh = False
    re_zero_requested = False

    print("G1 Omni relative-heading controller")
    print(f"omni_rx={args.bind}:{args.omni_port} state_rx=127.0.0.1:15101 command_tx=127.0.0.1:15100")
    if args.quest_forward_port:
        print(
            f"quest_live_copy={QUEST_FORWARD_HOST}:{args.quest_forward_port} "
            "(exact in-memory datagram; no log path)"
        )
    print("This replaces G1_INPUT_RECEIVE_AUDIT.py; do not run both receivers together.")
    print("r=re-zero current Omni/G1 heading  s=flip yaw sign and re-zero  x=zero and exit")
    print(f"yaw_kp={args.yaw_kp:.3f} max_wz={args.max_wz:.3f} yaw_sign={args.yaw_sign:+.0f}")
    print(f"log={diagnostic_log.path}")
    diagnostic_log.submit(
        {
            "kind": "controller_start",
            "pid": os.getpid(),
            "yaw_sign": args.yaw_sign,
            "yaw_kp": args.yaw_kp,
            "max_wz": args.max_wz,
            "freshness_s": args.freshness,
            "omni_bind": [args.bind, args.omni_port],
            "command_destination": list(COMMAND_ADDRESS),
            "state_bind": list(STATE_ADDRESS),
            "quest_live_copy": (
                [QUEST_FORWARD_HOST, args.quest_forward_port]
                if args.quest_forward_port
                else None
            ),
        }
    )

    try:
        with RawTerminal() as terminal:
            while True:
                now = time.monotonic()
                if args.duration and now - started >= args.duration:
                    break
                key = terminal.read_available()
                if key in ("x", "X"):
                    break
                if key in ("r", "R"):
                    re_zero_requested = True
                    print("\n[heading] re-zero requested")
                elif key in ("s", "S"):
                    follower.sign *= -1.0
                    re_zero_requested = True
                    print(f"\n[heading] yaw_sign={follower.sign:+.0f}; re-zero requested")

                while True:
                    try:
                        raw, peer = omni_socket.recvfrom(6001)
                    except BlockingIOError:
                        break
                    packet_time = time.monotonic()
                    raw_text = raw.decode("utf-8", errors="backslashreplace")
                    if args.quest_forward_port:
                        # The camera follower consumes the same live packet in
                        # memory.  UDP 55070 remains single-owner and JSONL is
                        # diagnostics only, never a control input.
                        quest_forward_socket.sendto(
                            raw,
                            (QUEST_FORWARD_HOST, args.quest_forward_port),
                        )
                    try:
                        sample = parse_omni_observation(raw, packet_time)
                        identity = (peer[0], peer[1], sample.session)
                        previous_sequence = last_outer_sequence.get(identity, -1)
                        if sample.sequence <= previous_sequence:
                            raise ValueError("reordered")
                        last_outer_sequence[identity] = sample.sequence
                        received += 1
                        send_ack(omni_socket, peer, raw, sample, received, packet_time)
                        if (sample.source_session is not None
                                and active_source_session not in (None, sample.source_session)):
                            # A controller process owns one persistent heading
                            # reference.  Transport/source reconnections must not
                            # silently redefine zero; only an explicit keyboard
                            # re-zero may do that.
                            print(
                                "\n[heading] Omni source session changed; "
                                "preserving the existing heading reference"
                            )
                        if sample.source_session is not None:
                            active_source_session = sample.source_session
                        latest_omni = sample
                        diagnostic_log.submit(
                            {
                                "kind": "observation_rx",
                                "accepted": True,
                                "peer": [peer[0], peer[1]],
                                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                                "raw_json": raw_text,
                                "outer_session": sample.session,
                                "outer_sequence": sample.sequence,
                                "omni_source_session": sample.source_session,
                                "omni_live_from_source": sample.omni_live,
                                "omni_source_age_s": (
                                    sample.source_age if math.isfinite(sample.source_age) else None
                                ),
                                "vx_body": sample.vx,
                                "vy_body": sample.vy,
                                "arm_yaw_rad": sample.arm_yaw_rad,
                                "arms_active_from_source": sample.arms_active,
                                "arm_state": sample.arm_state,
                                "arm_source_age_s": (
                                    sample.arm_source_age
                                    if math.isfinite(sample.arm_source_age)
                                    else None
                                ),
                                "left_q": list(sample.left_q),
                                "right_q": list(sample.right_q),
                            }
                        )
                    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                        rejected += 1
                        diagnostic_log.submit(
                            {
                                "kind": "observation_rx",
                                "accepted": False,
                                "reason": str(exc),
                                "peer": [peer[0], peer[1]],
                                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                                "raw_json": raw_text,
                            }
                        )
                        if rejected == 1 or rejected % 50 == 0:
                            print(f"\n[warning] rejected Omni observation count={rejected} reason={exc}")

                while True:
                    try:
                        raw, _ = state_socket.recvfrom(65535)
                    except BlockingIOError:
                        break
                    parsed_state = parse_robot_state(raw, time.monotonic())
                    if parsed_state is not None:
                        latest_state = parsed_state

                omni_fresh = (
                    latest_omni is not None
                    and latest_omni.omni_live
                    and latest_omni.source_age + (now - latest_omni.received_at) <= args.freshness
                )
                state_fresh = latest_state is not None and now - latest_state.received_at <= args.freshness
                base_fresh = omni_fresh and state_fresh
                arm_fresh = (
                    latest_omni is not None
                    and latest_omni.arms_active
                    and latest_omni.arm_source_age
                    + (now - latest_omni.received_at) <= args.freshness
                )
                if base_was_fresh and not base_fresh:
                    stale_events += 1
                    print(
                        "\n[locomotion] Omni/G1 stale; vx=vy=wz forced to zero, "
                        "heading reference preserved; arm freshness remains independent"
                    )
                base_was_fresh = base_fresh
                if re_zero_requested:
                    follower.reset()
                    re_zero_requested = False

                vx = vy = target = error = wz = 0.0
                arms_active = False
                left_q: Tuple[float, ...] = ()
                right_q: Tuple[float, ...] = ()
                if base_fresh and latest_omni is not None and latest_state is not None:
                    # vx/vy are already robot-body-frame commands from the
                    # Omni gateway.  Do not rotate them using mx/my or G1 yaw.
                    vx = clamp(latest_omni.vx, LINEAR_COMMAND_LIMIT)
                    vy = clamp(latest_omni.vy, LINEAR_COMMAND_LIMIT)
                    target, error, wz = follower.update(latest_omni.arm_yaw_rad, latest_state.yaw)
                # Arm validity is intentionally independent of Omni
                # locomotion freshness. A stale Omni sample zeros the base,
                # but fresh tracking/returning arm targets continue.
                arms_active = arm_fresh
                if arms_active and latest_omni is not None:
                    left_q = latest_omni.left_q
                    right_q = latest_omni.right_q

                if now >= next_send:
                    sent_packet = send_command(
                        command_socket,
                        command_sequence,
                        vx,
                        vy,
                        wz,
                        arms_active,
                        left_q,
                        right_q,
                    )
                    diagnostic_log.submit(
                        {
                            "kind": "command_tx",
                            "packet": sent_packet,
                            "status": (
                                "ACTIVE" if base_fresh and follower.ready else "WAIT_ZERO"
                            ),
                            "g1_state_sequence": (
                                latest_state.sequence if latest_state is not None else None
                            ),
                            "g1_yaw_rad": (
                                latest_state.yaw if latest_state is not None else None
                            ),
                            "heading_target_relative_rad": target,
                            "heading_error_rad": error,
                            "omni_fresh": omni_fresh,
                            "g1_state_fresh": state_fresh,
                            "arm_fresh": arm_fresh,
                            "arm_state": (
                                latest_omni.arm_state if latest_omni is not None else "none"
                            ),
                            "observation_received": received,
                            "observation_rejected": rejected,
                        }
                    )
                    command_sequence += 1
                    next_send += SEND_PERIOD_S
                    if now - next_send > SEND_PERIOD_S:
                        next_send = now + SEND_PERIOD_S

                if now >= next_display:
                    omni_deg = math.degrees(latest_omni.arm_yaw_rad) if latest_omni else float("nan")
                    robot_deg = math.degrees(latest_state.yaw) if latest_state else float("nan")
                    status = "ACTIVE" if base_fresh and follower.ready else "WAIT/ZERO"
                    print(
                        f"\n[{status}] arm_yaw={omni_deg:+.2f}deg g1_yaw={robot_deg:+.2f}deg "
                        f"target_rel={math.degrees(target):+.2f}deg error={math.degrees(error):+.2f}deg "
                        f"cmd=({vx:+.3f},{vy:+.3f},{wz:+.3f}) sign={follower.sign:+.0f} "
                        f"arms={'ACTIVE' if arms_active else 'HOLD'} "
                        f"arm_state={latest_omni.arm_state if latest_omni else 'none'} "
                        f"rx={received} reject={rejected} stale={stale_events}"
                    )
                    next_display = now + DISPLAY_PERIOD_S

                sleep_time = max(0.0, min(next_send, next_display) - time.monotonic())
                time.sleep(min(sleep_time, 0.005))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            send_zero(command_socket, command_sequence)
        finally:
            diagnostic_log.submit(
                {
                    "kind": "controller_exit",
                    "command_sequence": command_sequence,
                    "observation_received": received,
                    "observation_rejected": rejected,
                    "stale_events": stale_events,
                }
            )
            diagnostic_log.close()
            omni_socket.close()
            state_socket.close()
            command_socket.close()
            quest_forward_socket.close()
    print("\n[exit] sent zero command five times")
    print(
        f"[log] {diagnostic_log.path} records={diagnostic_log.written} "
        f"dropped={diagnostic_log.dropped} error={diagnostic_log.error}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
