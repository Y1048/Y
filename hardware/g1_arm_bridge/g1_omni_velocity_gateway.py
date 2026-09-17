"""Omni Connect WebSocket -> auto-discovered G1 velocity UDP gateway.

This module contains no Unitree SDK or DDS code. It converts observed Omni
samples into a bounded body-relative velocity request and sends only after a
token-bound G1 discovery announcement has been received.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import select
import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

try:
    from .g1_velocity_discovery import DEFAULT_DISCOVERY_PORT, make_listener, parse_discovery
except ImportError:
    from g1_velocity_discovery import DEFAULT_DISCOVERY_PORT, make_listener, parse_discovery


SCHEMA = "g1.velocity.command.v1"
PROVENANCE = "omni_gateway"
OMNI_CSV_SCHEMA = "g1.omni.timeseries.v1"
OMNI_CSV_HEADER = [
    "schema", "receive_monotonic_s", "elapsed_s", "sample_sequence",
    "mx", "my", "arm_yaw_deg", "omni_yaw_rate_deg_s",
    "vx", "vy", "yaw_rate", "yaw_diff_deg", "yaw_step_diff_deg",
    "calibrated", "raw_json_text",
]


def clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def deadzone(value: float, width: float) -> float:
    magnitude = abs(value)
    if magnitude <= width:
        return 0.0
    return math.copysign((magnitude - width) / (1.0 - width), value)


def wrapped_delta_degrees(current: float, previous: float) -> float:
    return (current - previous + 180.0) % 360.0 - 180.0


@dataclass
class OmniVelocityConfig:
    calibration_s: float = 1.0
    movement_deadzone: float = 0.08
    forward_max_m_s: float = 0.8
    lateral_max_m_s: float = 0.8
    yaw_gain: float = 1.0
    yaw_deadzone_deg_s: float = 3.0
    yaw_max_rad_s: float = 1.6
    yaw_output_deadzone_rad_s: float = 0.08
    yaw_filter_alpha: float = 0.25
    maximum_sample_gap_s: float = 0.25


class OmniVelocityMapper:
    def __init__(self, config: OmniVelocityConfig | None = None):
        self.config = config or OmniVelocityConfig()
        self.started_s: float | None = None
        self.zero_x_samples: list[float] = []
        self.zero_y_samples: list[float] = []
        self.zero_x = 0.0
        self.zero_y = 0.0
        self.zero_yaw_deg: float | None = None
        self.calibrated = False
        self.previous_yaw: float | None = None
        self.previous_time_s: float | None = None
        self.filtered_yaw_rate = 0.0
        self.yaw_from_origin_deg = 0.0
        self.yaw_step_diff_deg = 0.0
        self.yaw_rate_raw_deg_s = 0.0
        self.last_velocity = (0.0, 0.0, 0.0)

    def update(self, movement_x: float, movement_y: float, arm_yaw_deg: float,
               now_s: float) -> tuple[float, float, float]:
        values = (movement_x, movement_y, arm_yaw_deg, now_s)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("nonfinite Omni sample")
        if self.previous_time_s is not None and now_s < self.previous_time_s:
            raise ValueError("non-monotonic Omni sample")
        if self.previous_time_s is not None and now_s == self.previous_time_s:
            return self.last_velocity
        if self.started_s is None:
            self.started_s = now_s
        if not self.calibrated:
            self.zero_x_samples.append(movement_x)
            self.zero_y_samples.append(movement_y)
            self.previous_yaw = arm_yaw_deg
            if self.zero_yaw_deg is None:
                self.zero_yaw_deg = arm_yaw_deg
            self.yaw_from_origin_deg = wrapped_delta_degrees(
                arm_yaw_deg, self.zero_yaw_deg)
            self.yaw_step_diff_deg = 0.0
            self.yaw_rate_raw_deg_s = 0.0
            self.previous_time_s = now_s
            if now_s - self.started_s >= self.config.calibration_s:
                self.zero_x = sum(self.zero_x_samples) / len(self.zero_x_samples)
                self.zero_y = sum(self.zero_y_samples) / len(self.zero_y_samples)
                self.calibrated = True
            self.last_velocity = (0.0, 0.0, 0.0)
            return self.last_velocity

        assert self.previous_time_s is not None and self.previous_yaw is not None
        dt = now_s - self.previous_time_s
        if dt > self.config.maximum_sample_gap_s:
            self.previous_yaw = arm_yaw_deg
            self.previous_time_s = now_s
            self.filtered_yaw_rate = 0.0
            origin = arm_yaw_deg if self.zero_yaw_deg is None else self.zero_yaw_deg
            self.yaw_from_origin_deg = wrapped_delta_degrees(arm_yaw_deg, origin)
            self.yaw_step_diff_deg = 0.0
            self.yaw_rate_raw_deg_s = 0.0
            self.last_velocity = (0.0, 0.0, 0.0)
            return self.last_velocity

        yaw_delta = wrapped_delta_degrees(arm_yaw_deg, self.previous_yaw)
        raw_yaw_rate_deg_s = yaw_delta / dt
        origin = arm_yaw_deg if self.zero_yaw_deg is None else self.zero_yaw_deg
        self.yaw_from_origin_deg = wrapped_delta_degrees(arm_yaw_deg, origin)
        self.yaw_step_diff_deg = yaw_delta
        self.yaw_rate_raw_deg_s = raw_yaw_rate_deg_s
        if abs(raw_yaw_rate_deg_s) <= self.config.yaw_deadzone_deg_s:
            raw_yaw_rate_deg_s = 0.0
        raw_yaw_rate = math.radians(raw_yaw_rate_deg_s) * self.config.yaw_gain
        alpha = self.config.yaw_filter_alpha
        self.filtered_yaw_rate += alpha * (raw_yaw_rate - self.filtered_yaw_rate)
        filtered_magnitude = abs(self.filtered_yaw_rate)
        if filtered_magnitude <= self.config.yaw_output_deadzone_rad_s:
            yaw_output = 0.0
        else:
            usable = self.config.yaw_max_rad_s - self.config.yaw_output_deadzone_rad_s
            yaw_output = math.copysign(
                (filtered_magnitude - self.config.yaw_output_deadzone_rad_s)
                * self.config.yaw_max_rad_s / usable,
                self.filtered_yaw_rate)

        forward = deadzone(movement_y - self.zero_y,
                           self.config.movement_deadzone)
        # Omni/Unity movementX is right-positive. The Unitree velocity policy
        # is body +Y/left-positive, so the lateral axis must be inverted.
        lateral = -deadzone(movement_x - self.zero_x,
                            self.config.movement_deadzone)
        velocity = (
            clamp(forward * self.config.forward_max_m_s,
                  self.config.forward_max_m_s),
            clamp(lateral * self.config.lateral_max_m_s,
                  self.config.lateral_max_m_s),
            clamp(yaw_output, self.config.yaw_max_rad_s),
        )
        self.previous_yaw = arm_yaw_deg
        self.previous_time_s = now_s
        self.last_velocity = velocity
        return self.last_velocity


def parse_omni_message(raw: str) -> tuple[float, float, float]:
    packet = json.loads(raw)
    movement = packet.get("movementXY")
    yaw = packet.get("armYaw")
    if not isinstance(movement, list) or len(movement) != 2:
        raise ValueError("movementXY")
    if type(yaw) not in (int, float):
        raise ValueError("armYaw")
    x, y = movement
    if type(x) not in (int, float) or type(y) not in (int, float):
        raise ValueError("movementXY type")
    values = (float(x), float(y), float(yaw))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("nonfinite Omni packet")
    return values


def encode_command(session: str, sequence: int, now_s: float,
                   velocity: tuple[float, float, float], token: str) -> bytes:
    return json.dumps({
        "schema": SCHEMA,
        "command_provenance": PROVENANCE,
        "simulation_only": False,
        "session": session,
        "sequence": sequence,
        "source_monotonic_s": now_s,
        "velocity": velocity,
        "relay_token": token,
    }, allow_nan=False, separators=(",", ":")).encode()


def omni_csv_row(now_s: float, run_started_s: float, sequence: int,
                 movement_x: float, movement_y: float, arm_yaw_deg: float,
                 velocity: tuple[float, float, float],
                 mapper: OmniVelocityMapper, raw_json_text: str) -> list:
    return [
        OMNI_CSV_SCHEMA, f"{now_s:.9f}", f"{now_s - run_started_s:.9f}",
        sequence, movement_x, movement_y, arm_yaw_deg,
        mapper.yaw_rate_raw_deg_s, *velocity, mapper.yaw_from_origin_deg,
        mapper.yaw_step_diff_deg, int(mapper.calibrated), raw_json_text,
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relay-token", default="")
    parser.add_argument("--omni-url", default="ws://127.0.0.1:32123")
    parser.add_argument("--discovery-port", type=int, default=DEFAULT_DISCOVERY_PORT)
    parser.add_argument("--calibration-seconds", type=float, default=1.0)
    parser.add_argument("--start-delay-seconds", type=float, default=0.0,
                        help="receive but ignore Omni samples before calibration")
    parser.add_argument("--dry-run", action="store_true",
                        help="read and map Omni only; no discovery or UDP output")
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--max-samples", type=int, default=0,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.dry_run and (not args.relay_token.isascii() or
            not args.relay_token.isalnum() or
            not 16 <= len(args.relay_token) <= 128):
        raise ValueError("live mode requires a valid relay token")
    if args.duration_seconds < 0.0:
        raise ValueError("duration seconds")
    if not 0.0 <= args.start_delay_seconds <= 300.0:
        raise ValueError("start delay seconds")
    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError("Install websocket-client in the selected Python environment") from exc

    discovery = None if args.dry_run else make_listener(args.discovery_port)
    target: tuple[str, int] | None = None
    outbound = None if args.dry_run else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if not 0.1 <= args.calibration_seconds <= 10.0:
        raise ValueError("calibration seconds")
    if args.max_samples < 0:
        raise ValueError("max samples")
    mapper = OmniVelocityMapper(OmniVelocityConfig(
        calibration_s=args.calibration_seconds))
    session = uuid.uuid4().hex
    sequence = 0
    last_omni_received = -math.inf
    stale_zero_sent = False
    ws = websocket.create_connection(args.omni_url, timeout=0.10)
    sample_count = 0
    last_printed = -math.inf
    run_started = time.monotonic()
    calibration_starts = run_started + args.start_delay_seconds
    csv_file = None
    csv_writer = None
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        csv_file = args.csv.open("w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(OMNI_CSV_HEADER)
    print(f"[OMNI] connected {args.omni_url}; preparation delay "
          f"{args.start_delay_seconds:.1f} s, then calibrating for "
          f"{mapper.config.calibration_s:.1f} s", flush=True)
    while True:
        readable = []
        if discovery is not None:
            readable, _, _ = select.select([discovery], [], [], 0.0)
        if discovery is not None and readable:
            raw, peer = discovery.recvfrom(2049)
            try:
                announcement = parse_discovery(raw, args.relay_token)
            except (ValueError, json.JSONDecodeError):
                announcement = None
            if announcement is not None and target is None:
                target = (peer[0], announcement["velocity_port"])
                print(f"[G1] discovered {announcement['robot_id']} at {target[0]}:{target[1]}", flush=True)
        try:
            raw_message = ws.recv()
        except websocket.WebSocketTimeoutException:
            now = time.monotonic()
            if (outbound is not None and target is not None and not stale_zero_sent and
                    now - last_omni_received > mapper.config.maximum_sample_gap_s):
                outbound.sendto(encode_command(session, sequence, now,
                                               (0.0, 0.0, 0.0),
                                               args.relay_token), target)
                sequence += 1
                stale_zero_sent = True
                print("[OMNI STALE] zero velocity sent", flush=True)
            continue
        now = time.monotonic()
        last_omni_received = now
        stale_zero_sent = False
        movement_x, movement_y, yaw = parse_omni_message(raw_message)
        if now < calibration_starts:
            velocity = (0.0, 0.0, 0.0)
        else:
            velocity = mapper.update(movement_x, movement_y, yaw, now)
        if outbound is not None and target is not None:
            outbound.sendto(encode_command(session, sequence, now, velocity,
                                           args.relay_token), target)
            sequence += 1
        if csv_writer is not None:
            csv_writer.writerow(omni_csv_row(
                now, run_started, sample_count, movement_x, movement_y, yaw,
                velocity, mapper, raw_message))
            csv_file.flush()
        if now < calibration_starts:
            state = f"PREP {calibration_starts - now:.1f}s"
        else:
            state = "READY" if mapper.calibrated else "CALIBRATING"
        if now - last_printed >= 0.2:
            print(f"[OMNI {state}] vx={velocity[0]:+.3f} vy={velocity[1]:+.3f} wz={velocity[2]:+.3f}", flush=True)
            last_printed = now
        sample_count += 1
        if args.max_samples and sample_count >= args.max_samples:
            break
        if args.duration_seconds and now - run_started >= args.duration_seconds:
            break
    if outbound is not None and target is not None:
        now = time.monotonic()
        outbound.sendto(encode_command(session, sequence, now,
                                       (0.0, 0.0, 0.0),
                                       args.relay_token), target)
    ws.close()
    if csv_file is not None:
        csv_file.close()


if __name__ == "__main__":
    main()
