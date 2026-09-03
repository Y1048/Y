#!/usr/bin/env python3
"""실시간 Mink UDP를 Gate 7에 넣는 무출력 Arm SDK 후보 모니터.

기본 ``mink`` 모드는 Mink 자세를 이상적 추종 plant로 사용한다. ``lowstate``
모드는 별도 UDP 포트의 실제 G1 LowState를 측정 자세로 사용한다. 어느 모드도
Unitree SDK를 import하거나 DDS entity/publisher를 만들거나 명령을 송신하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BACKEND_ROOT: Final[Path] = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.gate7_simulation_feedback import build_packet as build_feedback_packet

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    ArmSdkCommandFrame,
    ArmSdkHoldConfig,
    build_measured_hold_frame,
    validate_measured_hold,
)
from arm_sdk_teleop_contract import (
    Gate7Config,
    Gate7Decision,
    Gate7TeleopController,
    MinkArmSample,
    RegularArmPose,
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from gate5_lowstate_safety_monitor import (
    LowStatePacketError,
    LowStateTelemetry,
    PacketOrderTracker,
    parse_lowstate_telemetry,
)
from gate7_mink_arm_sdk_offline import CollisionPathValidator

DEFAULT_CONFIG_PATH: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
)
DEFAULT_REGULAR_POSE_PATH: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
)
DEFAULT_MINK_HOST: Final[str] = "127.0.0.1"
DEFAULT_MINK_PORT: Final[int] = 5008
DEFAULT_LOWSTATE_HOST: Final[str] = "127.0.0.1"
DEFAULT_LOWSTATE_PORT: Final[int] = 5007
DEFAULT_LOWSTATE_TIMEOUT_S: Final[float] = 0.25
DEFAULT_SIMULATION_FEEDBACK_HOST: Final[str] = "127.0.0.1"
DEFAULT_SIMULATION_FEEDBACK_PORT: Final[int] = 5012
MAX_PACKET_BYTES: Final[int] = 65535
RESULT_SCHEMA: Final[str] = "g1.gate7.live_dry_run.result.v1"


@dataclass(frozen=True)
class DryRunTick:
    decision: Gate7Decision
    validation_allowed: bool
    validation_reason: str
    frame: ArmSdkCommandFrame | None
    measured_all_q_rad: tuple[float, ...]
    lowstate_age_s: float


def _finite_all_joints(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != 29:
        raise ValueError("measured_all_q_rad must contain exactly 29 values")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError("measured_all_q_rad contains a non-finite value")
    return result


def _replace_dual_arm(
    all_q_rad: Sequence[float], dual_arm_q_rad: Sequence[float]
) -> tuple[float, ...]:
    result = list(_finite_all_joints(all_q_rad))
    if len(dual_arm_q_rad) != len(DUAL_ARM_INDICES):
        raise ValueError("dual_arm_q_rad must contain exactly 14 values")
    for joint_index, value in zip(DUAL_ARM_INDICES, dual_arm_q_rad):
        result[joint_index] = float(value)
    return tuple(result)


def _automatic_path(directory: Path, stem: str, suffix: str) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return directory / f"{stem}_{timestamp}{suffix}"


def _resolve_output_path(
    value: str | None,
    *,
    directory: Path,
    stem: str,
    suffix: str,
) -> Path | None:
    if value is None:
        return None
    if value.lower() == "auto":
        return _automatic_path(directory, stem, suffix)
    return Path(value)


def _frame_summary(frame: ArmSdkCommandFrame | None) -> dict[str, object] | None:
    if frame is None:
        return None
    return {
        "mode_pr": frame.mode_pr,
        "mode_machine": frame.mode_machine,
        "weight": frame.weight,
        "dynamic_joint_indices": list(DUAL_ARM_INDICES),
        "dual_arm_q_rad": [frame.motor_q_rad[index] for index in DUAL_ARM_INDICES],
        "non_arm_command_enabled": any(
            frame.motor_mode[index] != 0
            for index in range(29)
            if index not in DUAL_ARM_INDICES
        ),
    }


class Gate7LiveDryRunSession:
    """Gate 7 결정과 SDK-neutral frame 생성을 네트워크와 분리한다."""

    def __init__(
        self,
        regular_pose: RegularArmPose,
        config: Gate7Config,
        *,
        measured_source: str,
        return_path_validator,
        controller=None,
        simulate_command_following: bool = False,
    ) -> None:
        if measured_source not in {"mink", "lowstate"}:
            raise ValueError("measured_source must be mink or lowstate")
        if config.hardware_output_authorized:
            raise ValueError("Gate 7 live dry-run requires hardware output locked")
        self.config = config
        self.measured_source = measured_source
        self.simulate_command_following = bool(simulate_command_following)
        if self.simulate_command_following and measured_source != "lowstate":
            raise ValueError(
                "simulate_command_following requires measured_source=lowstate"
            )
        self.controller = controller or Gate7TeleopController(
            regular_pose,
            config,
            return_path_validator=return_path_validator,
        )
        self.hold_config = ArmSdkHoldConfig(
            lowstate_timeout_s=DEFAULT_LOWSTATE_TIMEOUT_S,
            maximum_target_error_rad=config.maximum_target_error_rad,
        )
        self._shadow_measured_all_q_rad: tuple[float, ...] | None = None

    def ResolveMeasuredState(
        self,
        sample: MinkArmSample | None,
        lowstate_all_q_rad: Sequence[float] | None,
    ) -> tuple[float, ...] | None:
        if self.measured_source == "lowstate":
            if lowstate_all_q_rad is None:
                return None
            measured = _finite_all_joints(lowstate_all_q_rad)
            if not self.simulate_command_following:
                return measured
            if self._shadow_measured_all_q_rad is None:
                self._shadow_measured_all_q_rad = measured
            return self._shadow_measured_all_q_rad
        # During normal active tracking the dry-run shadow must keep following
        # the rate-limited Gate 7 candidate; replacing it with every 60 Hz
        # MuJoCo sample makes the 250 Hz target-error gate compare two different
        # timelines. Re-synchronize only at initialization or when control is
        # leaving the active path, so HOLD/return starts at the visible pose.
        unsafe_collision = bool(
            sample is not None
            and (
                (
                    sample.minimum_clearance_m is not None
                    and sample.minimum_clearance_m
                    < self.config.minimum_collision_clearance_m
                )
                or (
                    sample.minimum_clearance_m is None
                    and sample.collision_limited
                )
            )
        )
        rearming_from_regular_hold = bool(
            sample is not None
            and self.controller.state == "REGULAR_HOLD"
            and sample.input_command_mode == "active"
            and sample.active
        )
        resynchronize_visible_pose = bool(
            sample is not None
            and (
                self._shadow_measured_all_q_rad is None
                or sample.input_command_mode != "active"
                or not sample.active
                or sample.workspace_limited
                or unsafe_collision
                or rearming_from_regular_hold
            )
        )
        if resynchronize_visible_pose and sample is not None:
            self._shadow_measured_all_q_rad = sample.all_joint_q_rad
        return self._shadow_measured_all_q_rad

    def Step(
        self,
        sample: MinkArmSample | None,
        measured_all_q_rad: Sequence[float],
        dt_s: float,
        *,
        lowstate_age_s: float,
        mode_pr: int,
        mode_machine: int,
    ) -> DryRunTick:
        measured = _finite_all_joints(measured_all_q_rad)
        decision = self.controller.step(sample, measured, dt_s)
        validation = validate_measured_hold(
            measured,
            decision.target_dual_arm_q_rad,
            lowstate_age_s,
            self.hold_config,
        )
        frame = None
        if decision.command_candidate_valid and validation.allowed:
            frame = build_measured_hold_frame(
                measured,
                decision.target_dual_arm_q_rad,
                mode_pr=mode_pr,
                mode_machine=mode_machine,
                weight=self.config.command_weight,
                config=self.hold_config,
            )
            if self.measured_source == "mink" or self.simulate_command_following:
                self._shadow_measured_all_q_rad = _replace_dual_arm(
                    measured,
                    decision.target_dual_arm_q_rad,
                )
        return DryRunTick(
            decision=decision,
            validation_allowed=validation.allowed,
            validation_reason=validation.reason,
            frame=frame,
            measured_all_q_rad=measured,
            lowstate_age_s=float(lowstate_age_s),
        )


def _drain_mink(sock: socket.socket) -> tuple[MinkArmSample | None, int, int]:
    latest = None
    accepted = 0
    rejected = 0
    while True:
        try:
            payload, _source = sock.recvfrom(MAX_PACKET_BYTES)
        except BlockingIOError:
            break
        try:
            latest = parse_mink_arm_sample(payload)
            accepted += 1
        except (ValueError, UnicodeDecodeError):
            rejected += 1
    return latest, accepted, rejected


def _drain_lowstate(
    sock: socket.socket,
    order: PacketOrderTracker,
) -> tuple[LowStateTelemetry | None, int, int]:
    latest = None
    accepted = 0
    rejected = 0
    while True:
        try:
            payload, _source = sock.recvfrom(MAX_PACKET_BYTES)
        except BlockingIOError:
            break
        try:
            packet = parse_lowstate_telemetry(payload)
            if packet.all_joint_q_rad is None:
                raise LowStatePacketError("full 29-joint LowState is required")
            order.accept(packet)
            latest = packet
            accepted += 1
        except (LowStatePacketError, UnicodeDecodeError):
            rejected += 1
    return latest, accepted, rejected


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gate 7 live Mink-to-Arm-SDK candidate dry-run; sends no command"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--regular-pose", type=Path, default=DEFAULT_REGULAR_POSE_PATH
    )
    parser.add_argument("--mink-host", default=DEFAULT_MINK_HOST)
    parser.add_argument("--mink-port", type=int, default=DEFAULT_MINK_PORT)
    parser.add_argument(
        "--measured-source",
        choices=("mink", "lowstate"),
        default="mink",
    )
    parser.add_argument(
        "--trajectory-generator",
        choices=("baseline", "ruckig"),
        default="baseline",
    )
    parser.add_argument("--simulate-command-following", action="store_true")
    parser.add_argument("--lowstate-host", default=DEFAULT_LOWSTATE_HOST)
    parser.add_argument("--lowstate-port", type=int, default=DEFAULT_LOWSTATE_PORT)
    parser.add_argument(
        "--simulation-feedback-host",
        default=DEFAULT_SIMULATION_FEEDBACK_HOST,
    )
    parser.add_argument(
        "--simulation-feedback-port",
        type=int,
        default=DEFAULT_SIMULATION_FEEDBACK_PORT,
    )
    parser.add_argument("--disable-simulation-feedback", action="store_true")
    parser.add_argument(
        "--lowstate-timeout-s",
        type=float,
        default=DEFAULT_LOWSTATE_TIMEOUT_S,
    )
    parser.add_argument("--mode-pr", type=int, default=0)
    parser.add_argument("--mode-machine", type=int, default=5)
    parser.add_argument("--duration-s", type=float, default=0.0)
    parser.add_argument("--event-log", default="auto")
    parser.add_argument("--result-json", default="auto")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.lowstate_timeout_s <= 0.0 or not math.isfinite(args.lowstate_timeout_s):
        raise ValueError("lowstate-timeout-s must be finite and positive")
    if args.duration_s < 0.0 or not math.isfinite(args.duration_s):
        raise ValueError("duration-s must be finite and non-negative")
    if args.simulation_feedback_host != "127.0.0.1":
        raise ValueError("simulation feedback host must remain 127.0.0.1")
    if not 1 <= args.simulation_feedback_port <= 65535:
        raise ValueError("simulation feedback port must be within 1..65535")
    if args.simulate_command_following and args.measured_source != "lowstate":
        raise ValueError(
            "--simulate-command-following requires --measured-source lowstate"
        )

    config = load_gate7_config(args.config)
    regular_pose = load_regular_arm_pose(args.regular_pose)
    collision_validator = CollisionPathValidator()
    trajectory_controller = None
    if args.trajectory_generator == "ruckig":
        from ruckig_gate7_controller import RuckigGate7TeleopController

        trajectory_controller = RuckigGate7TeleopController(
            regular_pose,
            config,
            return_path_validator=collision_validator,
        )
    session = Gate7LiveDryRunSession(
        regular_pose,
        config,
        measured_source=args.measured_source,
        return_path_validator=collision_validator,
        controller=trajectory_controller,
        simulate_command_following=args.simulate_command_following,
    )
    session.hold_config = ArmSdkHoldConfig(
        lowstate_timeout_s=args.lowstate_timeout_s,
        maximum_target_error_rad=config.maximum_target_error_rad,
    )

    print("G1 Gate 7 LIVE DRY RUN")
    print("----------------------")
    print(f"Mink input:       udp://{args.mink_host}:{args.mink_port}")
    print(f"Measured source:  {args.measured_source}")
    print(f"Trajectory:       {args.trajectory_generator}")
    print(f"Command following:{' simulated' if args.simulate_command_following else ' measured'}")
    if args.measured_source == "lowstate":
        print(f"LowState input:   udp://{args.lowstate_host}:{args.lowstate_port}")
    if not args.disable_simulation_feedback:
        print(
            "MuJoCo feedback:  udp://"
            f"{args.simulation_feedback_host}:{args.simulation_feedback_port} "
            "(SIMULATION ONLY)"
        )
    print("Unitree SDK:      NONE")
    print("DDS entity:       NONE")
    print("Publisher:        NONE")
    print("Robot command:    NONE")
    if args.validate_only:
        print("[PASS] Gate 7 live dry-run dependencies and locked config are valid.")
        return 0

    output_dir = PROJECT_ROOT / "logs" / "test_results"
    event_log_path = _resolve_output_path(
        args.event_log,
        directory=output_dir,
        stem="g1_gate7_live_dry_run_events",
        suffix=".jsonl",
    )
    result_path = _resolve_output_path(
        args.result_json,
        directory=output_dir,
        stem="g1_gate7_live_dry_run",
        suffix=".json",
    )
    if event_log_path is not None:
        event_log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Event log:        {event_log_path.resolve()}")
    if result_path is not None:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Result JSON:      {result_path.resolve()}")

    mink_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    lowstate_sock = None
    simulation_feedback_sock = (
        None
        if args.disable_simulation_feedback
        else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    )
    try:
        mink_sock.bind((args.mink_host, args.mink_port))
        mink_sock.setblocking(False)
        if args.measured_source == "lowstate":
            lowstate_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            lowstate_sock.bind((args.lowstate_host, args.lowstate_port))
            lowstate_sock.setblocking(False)
    except OSError as exc:
        mink_sock.close()
        if lowstate_sock is not None:
            lowstate_sock.close()
        if simulation_feedback_sock is not None:
            simulation_feedback_sock.close()
        print(f"[ERROR] UDP bind failed: {exc}")
        print("[ACTION] Close the process already using port 5008 or 5007 and retry.")
        return 3

    event_stream = (
        event_log_path.open("w", encoding="utf-8")
        if event_log_path is not None
        else None
    )
    lowstate_order = PacketOrderTracker()
    latest_lowstate = None
    latest_mink_sample = None
    pending_mink_sample = None
    last_mink_received_at = float("-inf")
    lowstate_received_at = float("-inf")
    start = time.monotonic()
    previous_tick = start
    next_tick = start
    next_report = start + 1.0
    last_logged_state = None
    mink_packets = 0
    mink_rejected = 0
    lowstate_packets = 0
    lowstate_rejected = 0
    candidate_frames = 0
    denied_frames = 0
    simulation_feedback_frames = 0
    simulation_feedback_sequence = 0
    simulation_feedback_stream_id = uuid.uuid4().hex
    last_tick = None
    stopped_by_operator = False

    try:
        while True:
            now = time.monotonic()
            if args.duration_s > 0.0 and now - start >= args.duration_s:
                break

            received_sample, accepted, rejected = _drain_mink(mink_sock)
            if received_sample is not None:
                latest_mink_sample = received_sample
                pending_mink_sample = received_sample
                last_mink_received_at = now
            mink_packets += accepted
            mink_rejected += rejected
            if lowstate_sock is not None:
                packet, accepted, rejected = _drain_lowstate(
                    lowstate_sock,
                    lowstate_order,
                )
                lowstate_packets += accepted
                lowstate_rejected += rejected
                if packet is not None:
                    latest_lowstate = packet
                    lowstate_received_at = now

            if now < next_tick:
                time.sleep(min(0.001, next_tick - now))
                continue
            dt_s = max(1e-6, now - previous_tick)
            previous_tick = now
            next_tick += 1.0 / config.command_hz
            if next_tick <= now:
                next_tick = now + 1.0 / config.command_hz

            new_sample = pending_mink_sample
            pending_mink_sample = None

            lowstate_all_q = (
                None
                if latest_lowstate is None
                else latest_lowstate.all_joint_q_rad
            )
            measured = session.ResolveMeasuredState(new_sample, lowstate_all_q)
            if measured is None:
                if now >= next_report:
                    source = "Mink" if args.measured_source == "mink" else "LowState"
                    print(f"[WAIT] Waiting for first valid {source} measured pose...")
                    next_report = now + 1.0
                continue

            if args.measured_source == "lowstate":
                lowstate_age_s = max(0.0, now - lowstate_received_at)
                mode_pr = (
                    args.mode_pr
                    if latest_lowstate is None or latest_lowstate.mode_pr is None
                    else latest_lowstate.mode_pr
                )
                mode_machine = (
                    args.mode_machine
                    if latest_lowstate is None or latest_lowstate.mode_machine is None
                    else latest_lowstate.mode_machine
                )
            else:
                lowstate_age_s = 0.0
                mode_pr = args.mode_pr
                mode_machine = args.mode_machine

            tick = session.Step(
                new_sample,
                measured,
                dt_s,
                lowstate_age_s=lowstate_age_s,
                mode_pr=mode_pr,
                mode_machine=mode_machine,
            )
            last_tick = tick
            if tick.frame is None:
                denied_frames += 1
            else:
                candidate_frames += 1
                if simulation_feedback_sock is not None:
                    feedback_payload = build_feedback_packet(
                        stream_id=simulation_feedback_stream_id,
                        sequence=simulation_feedback_sequence,
                        source_time_s=now,
                        state=tick.decision.state,
                        reason=tick.decision.reason,
                        return_progress=tick.decision.return_progress,
                        dual_arm_q_rad=tick.decision.target_dual_arm_q_rad,
                    )
                    simulation_feedback_sock.sendto(
                        feedback_payload,
                        (
                            args.simulation_feedback_host,
                            args.simulation_feedback_port,
                        ),
                    )
                    simulation_feedback_sequence += 1
                    simulation_feedback_frames += 1

            should_log = (
                new_sample is not None
                or tick.decision.state != last_logged_state
                or not tick.validation_allowed
            )
            if should_log and event_stream is not None:
                measured_dual_arm_q_rad = [
                    tick.measured_all_q_rad[index]
                    for index in DUAL_ARM_INDICES
                ]
                record = {
                    "schema": "g1.gate7.live_dry_run.event.v1",
                    "time_s": now - start,
                    "measured_source": args.measured_source,
                    "state": tick.decision.state,
                    "reason": tick.decision.reason,
                    "return_progress": tick.decision.return_progress,
                    "validation_allowed": tick.validation_allowed,
                    "validation_reason": tick.validation_reason,
                    "lowstate_age_s": tick.lowstate_age_s,
                    "mink_input_packet_age_s": (
                        None
                        if latest_mink_sample is None
                        else latest_mink_sample.input_packet_age_s
                    ),
                    "mink_transport_age_s": (
                        None
                        if not math.isfinite(last_mink_received_at)
                        else max(0.0, now - last_mink_received_at)
                    ),
                    "mink_sample_received_this_tick": new_sample is not None,
                    "mink_input_command_mode": (
                        None
                        if latest_mink_sample is None
                        else latest_mink_sample.input_command_mode
                    ),
                    "mink_active": (
                        None
                        if latest_mink_sample is None
                        else latest_mink_sample.active
                    ),
                    "mink_minimum_clearance_m": (
                        None
                        if latest_mink_sample is None
                        else latest_mink_sample.minimum_clearance_m
                    ),
                    "mink_nearest_collision_geoms": (
                        []
                        if latest_mink_sample is None
                        else list(latest_mink_sample.nearest_collision_geoms)
                    ),
                    "mink_nearest_collision_bodies": (
                        []
                        if latest_mink_sample is None
                        else list(latest_mink_sample.nearest_collision_bodies)
                    ),
                    "target_dual_arm_q_rad": list(
                        tick.decision.target_dual_arm_q_rad
                    ),
                    "measured_dual_arm_q_rad": measured_dual_arm_q_rad,
                    "actual_lowstate_dual_arm_q_rad": (
                        None
                        if latest_lowstate is None
                        else [
                            latest_lowstate.all_joint_q_rad[index]
                            for index in DUAL_ARM_INDICES
                        ]
                    ),
                    "target_measured_max_error_deg": math.degrees(
                        max(
                            abs(target - measured)
                            for target, measured in zip(
                                tick.decision.target_dual_arm_q_rad,
                                measured_dual_arm_q_rad,
                            )
                        )
                    ),
                    "frame": _frame_summary(tick.frame),
                }
                event_stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                event_stream.flush()
            last_logged_state = tick.decision.state

            if now >= next_report:
                print(
                    f"[{tick.decision.state}] mink={mink_packets} "
                    f"candidate={candidate_frames} denied={denied_frames} "
                    f"reason={tick.decision.reason}"
                )
                if not tick.validation_allowed:
                    print(f"  [DENY] {tick.validation_reason}")
                next_report = now + 1.0
    except KeyboardInterrupt:
        stopped_by_operator = True
        print("\n[STOP] Dry-run stopped by operator.")
    finally:
        mink_sock.close()
        if lowstate_sock is not None:
            lowstate_sock.close()
        if simulation_feedback_sock is not None:
            simulation_feedback_sock.close()
        if event_stream is not None:
            event_stream.close()

    sdk_imported = any(name.startswith("unitree_sdk2py") for name in sys.modules)
    passed = candidate_frames > 0 and not sdk_imported
    result = {
        "schema": RESULT_SCHEMA,
        "passed": passed,
        "mode": "LIVE_DRY_RUN_ONLY",
        "measured_source": args.measured_source,
        "trajectory_generator": args.trajectory_generator,
        "simulate_command_following": args.simulate_command_following,
        "duration_s": time.monotonic() - start,
        "stopped_by_operator": stopped_by_operator,
        "mink_packets": mink_packets,
        "mink_rejected": mink_rejected,
        "lowstate_packets": lowstate_packets,
        "lowstate_rejected": lowstate_rejected,
        "candidate_frames": candidate_frames,
        "denied_frames": denied_frames,
        "simulation_feedback_enabled": not args.disable_simulation_feedback,
        "simulation_feedback_port": args.simulation_feedback_port,
        "simulation_feedback_frames": simulation_feedback_frames,
        "final_state": None if last_tick is None else last_tick.decision.state,
        "final_reason": None if last_tick is None else last_tick.decision.reason,
        "unitree_sdk_imported": sdk_imported,
        "dds_entity_created": False,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": config.hardware_output_authorized,
        "event_log": None if event_log_path is None else str(event_log_path.resolve()),
    }
    if result_path is not None:
        result_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if passed:
        print("[PASS] Live Gate 7 candidates were generated without robot output.")
    else:
        print("[FAIL] No valid Gate 7 candidate was generated.")
        print("[ACTION] Start the Mink controller and verify UDP 5008 is not blocked.")
        if args.measured_source == "lowstate":
            print("[ACTION] Also verify the read-only LowState forwarder on UDP 5007.")
    if event_log_path is not None:
        print(f"Event log saved to: {event_log_path.resolve()}")
    if result_path is not None:
        print(f"Result saved to: {result_path.resolve()}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
