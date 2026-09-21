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
import os
import select
import socket
import threading
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


def world_movement_to_body(movement_x: float, movement_y: float,
                           arm_yaw_deg: float) -> tuple[float, float]:
    """Express a world XY movement vector in the current body frame.

    Input contract: heading zero faces world +X, positive heading turns toward
    world +Y. Output +X is forward, +Y is left. Use absolute armYaw in this same
    world frame, not the yaw difference from session start. This rotates the
    vector without normalizing its magnitude or integrating a robot position.
    """
    if not all(math.isfinite(value) for value in
               (movement_x, movement_y, arm_yaw_deg)):
        raise ValueError('nonfinite world movement or heading')
    theta = math.radians(arm_yaw_deg % 360.0)
    cosine, sine = math.cos(theta), math.sin(theta)
    return (cosine * movement_x + sine * movement_y,
            -sine * movement_x + cosine * movement_y)


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

        # Bias is measured in world coordinates. Rotate before per-axis
        # deadzones/scales, so forward walking stays forward at every heading.
        body_forward, body_left = world_movement_to_body(
            movement_x - self.zero_x, movement_y - self.zero_y, arm_yaw_deg)
        forward = deadzone(body_forward, self.config.movement_deadzone)
        lateral = deadzone(body_left, self.config.movement_deadzone)
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


@dataclass(frozen=True)
class ReceivedOmniSample:
    sequence: int
    received_monotonic_s: float
    values: tuple[float, float, float]
    raw_json_text: str


class LatestOmniReader:
    """One bounded latest-sample slot; WS waiting never controls processing cadence."""
    CONNECT_TIMEOUT_S = 2.0
    RECEIVE_TIMEOUT_S = .10
    RECONNECT_DELAY_S = .5

    def __init__(self, url, websocket_module):
        self.url, self.websocket = url, websocket_module
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.latest = None
        self.received = 0
        self.error = None
        self.status = 'CONNECTING'
        self.connect_attempts = self.reconnect_count = self.receive_timeouts = 0
        self.last_transport_error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        timeouts = (TimeoutError, self.websocket.WebSocketTimeoutException)
        transport_errors = (OSError, self.websocket.WebSocketTimeoutException,
                            getattr(self.websocket, 'WebSocketConnectionClosedException', ConnectionError))
        failures = successful_connections = 0
        while not self.stop.is_set():
            connection = None
            retry = False
            with self.lock:
                self.status = 'CONNECTING'
                self.connect_attempts += 1
            try:
                # Handshake waiting is independent of the short recv polling period.
                connection = self.websocket.create_connection(self.url, timeout=self.CONNECT_TIMEOUT_S)
                connection.settimeout(self.RECEIVE_TIMEOUT_S)
                if self.stop.is_set():
                    break
                successful_connections += 1
                failures = 0
                with self.lock:
                    self.reconnect_count = successful_connections - 1
                    self.status = 'WAIT_SAMPLE'
                while not self.stop.is_set():
                    try:
                        raw = connection.recv()
                    except timeouts:
                        with self.lock:
                            self.receive_timeouts += 1
                        continue
                    received_at = time.monotonic()
                    if self.stop.is_set():
                        break
                    if not raw:
                        raise ConnectionError('Omni WebSocket disconnected')
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8')
                    values = parse_omni_message(raw)
                    with self.lock:
                        self.latest = ReceivedOmniSample(self.received, received_at, values, raw)
                        self.received += 1
                        self.status = 'RECEIVING'
            except transport_errors as error:
                # Keep the original last-sample timestamp; retrying is not new input.
                failures += 1
                retry = True
                with self.lock:
                    self.last_transport_error = '%s: %s' % (type(error).__name__, error)
                    self.status = 'RETRY_WAIT'
            except Exception as error:
                # Invalid payloads/protocol configuration remain fatal.
                with self.lock:
                    self.error = '%s: %s' % (type(error).__name__, error)
                    self.status = 'ERROR'
                break
            finally:
                if connection is not None:
                    try:
                        connection.close(timeout=0)
                    except (OSError, ValueError):
                        pass
            if retry:
                self.stop.wait(min(2., self.RECONNECT_DELAY_S * failures))
        with self.lock:
            if self.error is None:
                self.status = 'STOPPED'

    def transport_status(self):
        with self.lock:
            status = self.status
            if status == 'RECEIVING' and self.latest is not None and (
                    time.monotonic() - self.latest.received_monotonic_s > .75):
                status = 'WAIT_SAMPLE'
            return dict(status=status, connect_attempts=self.connect_attempts,
                        reconnect_count=self.reconnect_count, receive_timeouts=self.receive_timeouts,
                        last_transport_error=self.last_transport_error)

    def snapshot(self):
        with self.lock:
            return self.latest, self.received, self.error

    def close(self):
        self.stop.set()
        # Retry waits stop immediately. recv polls at 100 ms; connection setup
        # uses its separate 2 s socket timeout and cannot publish input after stop.
        self.thread.join(timeout=.5)


class ClockedOmniProcessor:
    """Map each new raw sample at most once; repeats never acquire a new source time."""
    def __init__(self, mapper, process_hz, calibration_starts):
        self.mapper, self.process_hz = mapper, process_hz
        self.calibration_starts = calibration_starts
        self.last_sequence = -1
        self.processed_samples = self.raw_samples_skipped = 0

    def process(self, sample, tick, processed_at, deadline_misses):
        if sample is None or sample.sequence <= self.last_sequence:
            return None
        self.raw_samples_skipped += sample.sequence - self.last_sequence - 1
        self.last_sequence = sample.sequence
        self.processed_samples += 1
        x, y, yaw = sample.values
        velocity = ((0., 0., 0.) if sample.received_monotonic_s < self.calibration_starts
                    else self.mapper.update(x, y, yaw, sample.received_monotonic_s))
        return dict(source_origin='omni_connect_readonly', sample_sequence=sample.sequence,
            raw_sample_sequence=sample.sequence, mx=x, my=y, arm_yaw_deg=yaw,
            omni_yaw_rate_deg_s=self.mapper.yaw_rate_raw_deg_s,
            vx=velocity[0], vy=velocity[1], yaw_rate=velocity[2],
            yaw_diff_deg=self.mapper.yaw_from_origin_deg,
            yaw_step_diff_deg=self.mapper.yaw_step_diff_deg, calibrated=self.mapper.calibrated,
            processing_hz=self.process_hz, process_tick=tick,
            processed_monotonic_s=processed_at, raw_samples_skipped=self.raw_samples_skipped,
            processing_deadlines_missed=deadline_misses,
            source_clock='python.time.monotonic:PC_WS_receipt',
            processing_clock='python.time.perf_counter:scheduler')


def next_processing_deadline(previous, now, period):
    """Skip elapsed deadlines rather than executing a catch-up burst."""
    following = previous + period
    missed = 0
    if following <= now:
        missed = int((now - following) / period) + 1
        following = now + period
    return following, missed


def run_clocked_observation(args, observation, websocket_module):
    """Opt-in dry-run only; CSV rows are processed new samples, not all WS messages."""
    mapper = OmniVelocityMapper(OmniVelocityConfig(calibration_s=args.calibration_seconds))
    started = time.monotonic()
    process = ClockedOmniProcessor(mapper, args.process_hz, started + args.start_delay_seconds)
    reader = LatestOmniReader(args.omni_url, websocket_module)
    csv_file = None
    writer = None
    extra_fields = ['raw_sample_sequence', 'processing_hz', 'process_tick',
                    'processed_monotonic_s', 'raw_samples_skipped', 'processing_deadlines_missed',
                    'source_clock', 'processing_clock', 'csv_row_kind']
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        csv_file = args.csv.open('x', newline='', encoding='utf-8')
        writer = csv.writer(csv_file)
        writer.writerow(OMNI_CSV_HEADER + extra_fields)
    print('[OMNI CLOCKED OBSERVATION] processing %.3f Hz; raw WS receipt independent; '
          'only new samples published; no command/discovery transport' % args.process_hz, flush=True)
    print('[OMNI FRAME] world mx/my -> body vx/vy using current absolute armYaw; '
          'yaw 0: +mx forward, +my left. Speed scale/limits unchanged.', flush=True)
    print('[CSV] processed-new samples only, original raw JSON/timestamp preserved; '
          'raw_samples_skipped reports samples superseded before processing', flush=True)
    period = 1. / args.process_hz
    started_perf = deadline = time.perf_counter()
    ticks = missed = 0
    reader_error = None
    last_transport_status = None
    last_transport_print = -math.inf
    reader.thread.start()
    try:
        while True:
            now_perf = time.perf_counter()
            remaining = args.duration_seconds - (now_perf - started_perf) if args.duration_seconds else None
            if remaining is not None and remaining <= 0:
                break
            delay = deadline - now_perf
            if delay > 0:
                time.sleep(min(delay, remaining) if remaining is not None else delay)
            if args.duration_seconds and time.perf_counter() - started_perf >= args.duration_seconds:
                break
            sample, received, reader_error = reader.snapshot()
            transport = reader.transport_status()
            if transport['status'] != last_transport_status and (
                    time.perf_counter() - last_transport_print >= .5):
                print('[OMNI CONNECTION] ' + json.dumps(transport, allow_nan=False), flush=True)
                last_transport_status = transport['status']
                last_transport_print = time.perf_counter()
            values = process.process(sample, ticks, time.monotonic(), missed)
            if values is not None:
                # The envelope time is raw receipt time, never the scheduler tick.
                observation.publish(values, sample.received_monotonic_s)
                if writer is not None:
                    velocity = (values['vx'], values['vy'], values['yaw_rate'])
                    row = omni_csv_row(sample.received_monotonic_s, started, sample.sequence,
                        *sample.values, velocity, mapper, sample.raw_json_text)
                    writer.writerow(row + [values.get(key, 'processed_new_raw_sample') for key in extra_fields])
                    csv_file.flush()
            ticks += 1
            if reader_error or (args.max_samples and received >= args.max_samples):
                break
            deadline, skipped = next_processing_deadline(deadline, time.perf_counter(), period)
            missed += skipped
    finally:
        processing_elapsed = time.perf_counter() - started_perf
        reader.close()
        observation.close()
        if csv_file is not None:
            csv_file.close()
    _, received, _ = reader.snapshot()
    summary = dict(processing_hz=args.process_hz, process_ticks=ticks,
                   processed_samples=process.processed_samples, raw_samples_received=received,
                   raw_samples_skipped=process.raw_samples_skipped,
                   processing_deadlines_missed=missed, elapsed_perf_s=processing_elapsed,
                   reader_thread_stopped=not reader.thread.is_alive(), reader_error=reader_error,
                   connection=reader.transport_status())
    print('[OMNI CLOCKED SUMMARY] ' + json.dumps(summary, allow_nan=False), flush=True)
    if reader_error:
        raise RuntimeError(reader_error)
    return summary


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
    parser.add_argument('--process-hz', type=float, default=0.,
                        help='0 keeps event-driven mapping; 10..120 enables clocked observation only')
    args = parser.parse_args()
    if (not math.isfinite(args.process_hz) or
            (args.process_hz != 0 and not 10 <= args.process_hz <= 120)):
        raise ValueError('process-hz must be zero or finite 10..120')
    if args.process_hz and (not args.dry_run or os.environ.get('G1_OBSERVATION_TAP') != '1'):
        raise ValueError('process-hz requires --dry-run and G1_OBSERVATION_TAP=1')
    observation = None
    if os.environ.get('G1_OBSERVATION_TAP') == '1':
        if not args.dry_run:
            raise ValueError('Observation tap requires --dry-run; motor command transport stays disabled')
        import importlib.util
        tap_path = Path(__file__).resolve().parents[2]/'tools/g1_observation_tap.py'
        spec = importlib.util.spec_from_file_location('omni_observation_tap', tap_path)
        tap_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tap_module)
        observation = tap_module.ObservationTap('omni')
    if not args.dry_run and (not args.relay_token.isascii() or
            not args.relay_token.isalnum() or
            not 16 <= len(args.relay_token) <= 128):
        raise ValueError("live mode requires a valid relay token")
    if not math.isfinite(args.duration_seconds) or args.duration_seconds < 0.0:
        raise ValueError("duration seconds")
    if not 0.0 <= args.start_delay_seconds <= 300.0:
        raise ValueError("start delay seconds")
    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError("Install websocket-client in the selected Python environment") from exc

    if args.process_hz:
        if not 0.1 <= args.calibration_seconds <= 10.0:
            raise ValueError('calibration seconds')
        if args.max_samples < 0:
            raise ValueError('max samples')
        run_clocked_observation(args, observation, websocket)
        return

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
    print('[OMNI FRAME] world mx/my -> body vx/vy using current absolute armYaw; '
          'yaw 0: +mx forward, +my left. Speed scale/limits unchanged.', flush=True)
    if observation:
        print('[OBSERVATION] sample copy -> localhost:55071; no G1 command transport', flush=True)
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
        if observation:
            observation.publish(dict(source_origin='omni_connect_readonly',
                sample_sequence=sample_count, mx=movement_x, my=movement_y,
                arm_yaw_deg=yaw, omni_yaw_rate_deg_s=mapper.yaw_rate_raw_deg_s,
                vx=velocity[0], vy=velocity[1], yaw_rate=velocity[2],
                yaw_diff_deg=mapper.yaw_from_origin_deg,
                yaw_step_diff_deg=mapper.yaw_step_diff_deg, calibrated=mapper.calibrated), now)
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
    if observation:
        observation.close()
    if csv_file is not None:
        csv_file.close()


if __name__ == "__main__":
    main()
