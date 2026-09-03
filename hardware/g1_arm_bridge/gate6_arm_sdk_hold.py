#!/usr/bin/env python3
"""Gate 6 measured-pose HOLD for G1 Regular Mode.

기본 실행은 ``rt/lowstate``만 구독하는 준비 검사다. 실제
``rt/arm_sdk`` publisher는 다음 조건을 모두 만족할 때만 생성한다.

1. config가 hardware output을 명시적으로 허용한다.
2. 실행 인자에 hardware output 플래그와 정확한 확인 문구가 있다.
3. G1이 평평한 지면에서 Regular Mode로 자립 중임을 별도로 확인한다.
4. 같은 세션 직전에 생성된 startup precheck가 DIRECT_TELEOP_READY다.
5. 현재 MotionSwitcher mode와 LowState가 설정값과 일치한다.

이 파일은 ``rt/lowcmd``를 사용하지 않으며 허리/하체 관절을 target update
set에 포함하지 않는다. Arm SDK의 전역 weight 특성 때문에 양팔 14축은 모두
실측 자세로 시드한 뒤 함께 검증한다.
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
from typing import Any, Final

from arm_sdk_hold_contract import (
    ARM_SDK_TOPIC,
    BODY_JOINT_COUNT,
    DUAL_ARM_INDICES,
    LOWSTATE_TOPIC,
    ArmSdkCommandFrame,
    ArmSdkHoldConfig,
    blend_weight,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
    validate_measured_hold,
)
from hardware_state import FaultCode, HardwarePhase, build_status, write_status

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_gate6_hold.json"
DEFAULT_PRECHECK_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_startup_precheck.json"
)
DEFAULT_STATUS_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_gate6_arm_sdk_hold.json"
)
DEFAULT_EVENT_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_gate6_arm_sdk_hold.jsonl"
)


@dataclass(frozen=True)
class RuntimeConfig:
    expected_form: str
    expected_name: str
    expected_mode_pr: int
    expected_mode_machine: int
    settle_duration_s: float
    minimum_settle_samples: int
    maximum_initial_arm_velocity_rad_s: float
    publish_hz: float
    ramp_up_s: float
    hold_s: float
    ramp_down_s: float
    maximum_weight: float
    release_zero_cycles: int
    precheck_max_age_s: float
    hardware_output_authorized: bool
    hardware_confirmation_phrase: str
    grounded_regular_confirmation_phrase: str
    safety: ArmSdkHoldConfig


@dataclass(frozen=True)
class LowStateSnapshot:
    received_monotonic_s: float
    received_unix_ns: int
    sequence: int
    mode_pr: int
    mode_machine: int
    all_q_rad: tuple[float, ...]
    all_dq_rad_s: tuple[float, ...]


class LowStateBuffer:
    """DDS callback에서 최신 29축 상태를 원자적으로 보관한다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: LowStateSnapshot | None = None
        self._sequence = 0

    def callback(self, message: Any) -> None:
        try:
            all_q = tuple(
                float(message.motor_state[index].q)
                for index in range(BODY_JOINT_COUNT)
            )
            all_dq = tuple(
                float(message.motor_state[index].dq)
                for index in range(BODY_JOINT_COUNT)
            )
            mode_pr = int(message.mode_pr)
            mode_machine = int(message.mode_machine)
            if not all(math.isfinite(value) for value in all_q + all_dq):
                return
        except (AttributeError, IndexError, TypeError, ValueError):
            return

        now_monotonic = time.monotonic()
        with self._lock:
            self._sequence += 1
            self._snapshot = LowStateSnapshot(
                received_monotonic_s=now_monotonic,
                received_unix_ns=time.time_ns(),
                sequence=self._sequence,
                mode_pr=mode_pr,
                mode_machine=mode_machine,
                all_q_rad=all_q,
                all_dq_rad_s=all_dq,
            )

    def snapshot(self) -> LowStateSnapshot | None:
        with self._lock:
            return self._snapshot


def _finite_number(message: dict[str, Any], name: str) -> float:
    value = float(message[name])
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def load_runtime_config(path: Path) -> RuntimeConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.gate6.arm_sdk_hold.config.v1":
        raise ValueError("unsupported Gate 6 config schema")
    if payload.get("arm_sdk_topic") != ARM_SDK_TOPIC:
        raise ValueError(f"arm_sdk_topic must be {ARM_SDK_TOPIC}")
    if payload.get("lowstate_topic") != LOWSTATE_TOPIC:
        raise ValueError(f"lowstate_topic must be {LOWSTATE_TOPIC}")

    expected_mode = payload["expected_motion_mode"]
    safety = ArmSdkHoldConfig(
        lowstate_timeout_s=_finite_number(payload, "lowstate_timeout_s"),
        joint_limit_margin_rad=math.radians(
            _finite_number(payload, "joint_limit_margin_deg")
        ),
        maximum_target_error_rad=math.radians(
            _finite_number(payload, "maximum_target_error_deg")
        ),
        proximal_kp=_finite_number(payload, "proximal_kp"),
        proximal_kd=_finite_number(payload, "proximal_kd"),
        wrist_kp=_finite_number(payload, "wrist_kp"),
        wrist_kd=_finite_number(payload, "wrist_kd"),
    )
    config = RuntimeConfig(
        expected_form=str(expected_mode["form"]),
        expected_name=str(expected_mode["name"]),
        expected_mode_pr=int(payload["expected_mode_pr"]),
        expected_mode_machine=int(payload["expected_mode_machine"]),
        settle_duration_s=_finite_number(payload, "settle_duration_s"),
        minimum_settle_samples=int(payload["minimum_settle_samples"]),
        maximum_initial_arm_velocity_rad_s=math.radians(
            _finite_number(payload, "maximum_initial_arm_velocity_deg_s")
        ),
        publish_hz=_finite_number(payload, "publish_hz"),
        ramp_up_s=_finite_number(payload, "ramp_up_s"),
        hold_s=_finite_number(payload, "hold_s"),
        ramp_down_s=_finite_number(payload, "ramp_down_s"),
        maximum_weight=_finite_number(payload, "maximum_weight"),
        release_zero_cycles=int(payload["release_zero_cycles"]),
        precheck_max_age_s=_finite_number(payload, "precheck_max_age_s"),
        hardware_output_authorized=bool(payload["hardware_output_authorized"]),
        hardware_confirmation_phrase=str(payload["hardware_confirmation_phrase"]),
        grounded_regular_confirmation_phrase=str(
            payload["grounded_regular_confirmation_phrase"]
        ),
        safety=safety,
    )
    validate_runtime_config(config)
    return config


def validate_runtime_config(config: RuntimeConfig) -> None:
    if config.settle_duration_s <= 0.0:
        raise ValueError("settle_duration_s must be > 0")
    if config.minimum_settle_samples < 1:
        raise ValueError("minimum_settle_samples must be >= 1")
    if config.maximum_initial_arm_velocity_rad_s <= 0.0:
        raise ValueError("maximum_initial_arm_velocity_deg_s must be > 0")
    if config.publish_hz <= 0.0:
        raise ValueError("publish_hz must be > 0")
    if config.ramp_up_s <= 0.0 or config.hold_s < 0.0 or config.ramp_down_s <= 0.0:
        raise ValueError("invalid acquire/hold/release duration")
    if config.maximum_weight <= 0.0 or config.maximum_weight > 1.0:
        raise ValueError("maximum_weight must be in (0, 1]")
    if config.release_zero_cycles < 1:
        raise ValueError("release_zero_cycles must be >= 1")
    if config.precheck_max_age_s <= 0.0:
        raise ValueError("precheck_max_age_s must be > 0")
    if not config.hardware_confirmation_phrase:
        raise ValueError("hardware_confirmation_phrase must not be empty")
    if not config.grounded_regular_confirmation_phrase:
        raise ValueError(
            "grounded_regular_confirmation_phrase must not be empty"
        )


def validate_precheck(path: Path, maximum_age_s: float) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.startup_precheck.result.v1":
        raise ValueError("startup precheck schema mismatch")
    if payload.get("decision") != "DIRECT_TELEOP_READY":
        raise ValueError(f"startup precheck decision is {payload.get('decision')}")
    if payload.get("recovery_bypass_allowed") is not True:
        raise ValueError("startup precheck did not allow recovery bypass")
    if payload.get("command_output_enabled") is not False:
        raise ValueError("startup precheck unexpectedly enabled command output")
    if payload.get("publisher_present") is not False:
        raise ValueError("startup precheck unexpectedly reports a publisher")
    checked_ns = int(payload["checked_at_unix_ns"])
    age_s = (time.time_ns() - checked_ns) / 1_000_000_000.0
    if age_s < 0.0 or age_s > maximum_age_s:
        raise ValueError(
            f"startup precheck is stale: {age_s:.1f}s > {maximum_age_s:.1f}s"
        )
    return payload


def validate_output_authorization(
    config: RuntimeConfig,
    *,
    enable_hardware_output: bool,
    confirmation: str,
    grounded_regular_confirmation: str,
) -> None:
    if not enable_hardware_output:
        return
    if not config.hardware_output_authorized:
        raise PermissionError("hardware_output_authorized is false in Gate 6 config")
    if confirmation != config.hardware_confirmation_phrase:
        raise PermissionError("hardware confirmation phrase does not match")
    if (
        grounded_regular_confirmation
        != config.grounded_regular_confirmation_phrase
    ):
        raise PermissionError(
            "grounded Regular confirmation phrase does not match"
        )


def _append_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, separators=(",", ":")) + "\n")


def _status_details(
    *,
    network_interface: str,
    snapshot: LowStateSnapshot | None,
    target_dual_arm_q_rad: tuple[float, ...] | None,
    mode_form: str | None,
    mode_name: str | None,
    weight: float,
    schedule_phase: str,
    published_frames: int,
    reason: str,
) -> dict[str, Any]:
    age_s = None
    if snapshot is not None:
        age_s = max(0.0, time.monotonic() - snapshot.received_monotonic_s)
    return {
        "network_interface": network_interface,
        "dds_lowstate_topic": LOWSTATE_TOPIC,
        "dds_command_topic": ARM_SDK_TOPIC,
        "motion_mode": {"form": mode_form, "name": mode_name},
        "lowstate_sequence": snapshot.sequence if snapshot else None,
        "lowstate_age_s": age_s,
        "mode_pr": snapshot.mode_pr if snapshot else None,
        "mode_machine": snapshot.mode_machine if snapshot else None,
        "target_dual_arm_q_rad": (
            list(target_dual_arm_q_rad) if target_dual_arm_q_rad else None
        ),
        "weight": float(weight),
        "schedule_phase": schedule_phase,
        "published_frames": int(published_frames),
        "dynamic_joint_indices": list(DUAL_ARM_INDICES),
        "waist_target_updated": False,
        "reason": reason,
    }


def _write_runtime_status(
    path: Path,
    event_path: Path,
    *,
    phase: HardwarePhase,
    command_output_enabled: bool,
    publisher_present: bool,
    details: dict[str, Any],
    fault_code: FaultCode = FaultCode.NONE,
    fault_message: str = "",
) -> None:
    payload = build_status(
        phase=phase,
        component="gate6_arm_sdk_hold",
        command_output_enabled=command_output_enabled,
        publisher_present=publisher_present,
        fault_code=fault_code,
        fault_message=fault_message,
        details=details,
    )
    write_status(path, payload)
    _append_event(event_path, payload)


def _wait_for_first_snapshot(
    buffer: LowStateBuffer,
    timeout_s: float,
) -> LowStateSnapshot:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        snapshot = buffer.snapshot()
        if snapshot is not None:
            return snapshot
        time.sleep(0.01)
    raise TimeoutError(f"no {LOWSTATE_TOPIC} received within {timeout_s:.1f}s")


def _collect_settled_snapshot(
    buffer: LowStateBuffer,
    config: RuntimeConfig,
) -> tuple[LowStateSnapshot, int, float]:
    deadline = time.monotonic() + config.settle_duration_s
    last_sequence = -1
    sample_count = 0
    maximum_velocity = 0.0
    latest: LowStateSnapshot | None = None
    while time.monotonic() < deadline:
        snapshot = buffer.snapshot()
        if snapshot is None or snapshot.sequence == last_sequence:
            time.sleep(0.001)
            continue
        last_sequence = snapshot.sequence
        latest = snapshot
        sample_count += 1
        maximum_velocity = max(
            maximum_velocity,
            max(abs(snapshot.all_dq_rad_s[index]) for index in DUAL_ARM_INDICES),
        )
        time.sleep(0.001)
    if latest is None:
        raise RuntimeError("no LowState sample collected during settle window")
    if sample_count < config.minimum_settle_samples:
        raise RuntimeError(
            f"only {sample_count} settle samples; need {config.minimum_settle_samples}"
        )
    age_s = time.monotonic() - latest.received_monotonic_s
    if age_s > config.safety.lowstate_timeout_s:
        raise RuntimeError(f"LowState stale after settle window: {age_s:.3f}s")
    if maximum_velocity > config.maximum_initial_arm_velocity_rad_s:
        raise RuntimeError(
            "initial arm velocity too high: "
            f"{math.degrees(maximum_velocity):.2f}deg/s > "
            f"{math.degrees(config.maximum_initial_arm_velocity_rad_s):.2f}deg/s"
        )
    return latest, sample_count, maximum_velocity


def _apply_frame(message: Any, frame: ArmSdkCommandFrame) -> None:
    message.mode_pr = frame.mode_pr
    message.mode_machine = frame.mode_machine
    for index in range(len(frame.motor_q_rad)):
        command = message.motor_cmd[index]
        command.mode = frame.motor_mode[index]
        command.q = frame.motor_q_rad[index]
        command.dq = frame.motor_dq_rad_s[index]
        command.tau = frame.motor_tau_nm[index]
        command.kp = frame.motor_kp[index]
        command.kd = frame.motor_kd[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="G1 Gate 6 measured-pose Arm SDK HOLD"
    )
    parser.add_argument("network_interface")
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--precheck-json", type=Path, default=DEFAULT_PRECHECK_PATH)
    parser.add_argument("--status-json", type=Path, default=DEFAULT_STATUS_PATH)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_PATH)
    parser.add_argument("--startup-timeout", type=float, default=5.0)
    parser.add_argument("--enable-hardware-output", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--confirm-grounded-regular", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_runtime_config(args.config)
        validate_output_authorization(
            config,
            enable_hardware_output=args.enable_hardware_output,
            confirmation=args.confirm,
            grounded_regular_confirmation=args.confirm_grounded_regular,
        )
        if args.enable_hardware_output:
            validate_precheck(args.precheck_json, config.precheck_max_age_s)
    except PermissionError as exc:
        details = _status_details(
            network_interface=args.network_interface,
            snapshot=None,
            target_dual_arm_q_rad=None,
            mode_form=None,
            mode_name=None,
            weight=0.0,
            schedule_phase="BLOCKED",
            published_frames=0,
            reason=str(exc),
        )
        _write_runtime_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.FAULT,
            command_output_enabled=False,
            publisher_present=False,
            details=details,
            fault_code=FaultCode.OUTPUT_NOT_AUTHORIZED,
            fault_message=str(exc),
        )
        print(f"[BLOCKED] {exc}")
        print("[ACTION] Keep hardware output disabled and review Gate 6 config.")
        print(f"Result saved to: {args.status_json.resolve()}")
        return 10
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        details = _status_details(
            network_interface=args.network_interface,
            snapshot=None,
            target_dual_arm_q_rad=None,
            mode_form=None,
            mode_name=None,
            weight=0.0,
            schedule_phase="BLOCKED",
            published_frames=0,
            reason=str(exc),
        )
        _write_runtime_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.FAULT,
            command_output_enabled=False,
            publisher_present=False,
            details=details,
            fault_code=(
                FaultCode.PRECHECK_REQUIRED
                if args.enable_hardware_output
                else FaultCode.INTERNAL_ERROR
            ),
            fault_message=str(exc),
        )
        print(f"[ERROR] Invalid Gate 6 input: {exc}")
        print("[ACTION] Keep hardware output disabled and repair the config/precheck.")
        print(f"Result saved to: {args.status_json.resolve()}")
        return 2

    # Linux-only imports remain inside main so offline Windows tests can import
    # and exercise the complete contract without Unitree SDK2 installed.
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
        MotionSwitcherClient,
    )
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
    from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

    buffer = LowStateBuffer()
    publisher = None
    mode_form: str | None = None
    mode_name: str | None = None
    target_dual_arm: tuple[float, ...] | None = None
    published_frames = 0

    try:
        ChannelFactoryInitialize(args.domain_id, args.network_interface)
        motion_client = MotionSwitcherClient()
        motion_client.SetTimeout(args.startup_timeout)
        motion_client.Init()
        result_code, result = motion_client.CheckMode()
        if result_code != 0 or not isinstance(result, dict):
            raise RuntimeError(f"MotionSwitcher CheckMode failed: code={result_code}")
        mode_form = str(result.get("form"))
        mode_name = str(result.get("name"))
        if (mode_form, mode_name) != (config.expected_form, config.expected_name):
            raise RuntimeError(
                "motion mode mismatch: "
                f"actual=({mode_form},{mode_name}) "
                f"expected=({config.expected_form},{config.expected_name})"
            )

        subscriber = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        subscriber.Init(buffer.callback, 10)
        _wait_for_first_snapshot(buffer, args.startup_timeout)
        snapshot, settle_samples, maximum_velocity = _collect_settled_snapshot(
            buffer, config
        )
        if snapshot.mode_pr != config.expected_mode_pr:
            raise RuntimeError(
                f"mode_pr mismatch: {snapshot.mode_pr} != {config.expected_mode_pr}"
            )
        if snapshot.mode_machine != config.expected_mode_machine:
            raise RuntimeError(
                "mode_machine mismatch: "
                f"{snapshot.mode_machine} != {config.expected_mode_machine}"
            )

        target_dual_arm = dual_arm_from_all_joints(snapshot.all_q_rad)
        validation = validate_measured_hold(
            snapshot.all_q_rad,
            target_dual_arm,
            time.monotonic() - snapshot.received_monotonic_s,
            config.safety,
        )
        if not validation.allowed:
            raise RuntimeError(f"measured HOLD rejected: {validation.reason}")
        build_measured_hold_frame(
            snapshot.all_q_rad,
            target_dual_arm,
            mode_pr=snapshot.mode_pr,
            mode_machine=snapshot.mode_machine,
            weight=config.maximum_weight,
            config=config.safety,
        )

        details = _status_details(
            network_interface=args.network_interface,
            snapshot=snapshot,
            target_dual_arm_q_rad=target_dual_arm,
            mode_form=mode_form,
            mode_name=mode_name,
            weight=0.0,
            schedule_phase="READY",
            published_frames=0,
            reason="measured dual-arm HOLD contract accepted",
        )
        details["settle_samples"] = settle_samples
        details["maximum_initial_arm_velocity_deg_s"] = math.degrees(
            maximum_velocity
        )
        details["configured_maximum_weight"] = config.maximum_weight
        _write_runtime_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.HOLD_READY,
            command_output_enabled=False,
            publisher_present=False,
            details=details,
        )

        if not args.enable_hardware_output:
            print("G1 Gate 6 preparation -- READ ONLY")
            print(f"Motion mode: form={mode_form} name={mode_name}")
            print(f"LowState settle samples: {settle_samples}")
            print(
                "Maximum arm velocity: "
                f"{math.degrees(maximum_velocity):.2f} deg/s"
            )
            print("Dual-arm measured-pose HOLD candidate: ACCEPTED")
            print("DDS publisher: NONE")
            print("Robot command: NONE")
            print(f"Result saved to: {args.status_json.resolve()}")
            return 0

        # 이 분기 전까지는 ChannelPublisher가 import되거나 생성되지 않는다.
        from unitree_sdk2py.core.channel import ChannelPublisher
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
        from unitree_sdk2py.utils.crc import CRC

        publisher = ChannelPublisher(ARM_SDK_TOPIC, LowCmd_)
        publisher.Init()
        message = unitree_hg_msg_dds__LowCmd_()
        crc = CRC()
        stop_requested = threading.Event()

        def request_stop(_signum: int, _frame: Any) -> None:
            stop_requested.set()

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)

        period_s = 1.0 / config.publish_hz
        started_s = time.monotonic()
        next_tick_s = started_s
        zero_cycles_remaining = config.release_zero_cycles
        last_report_s = started_s
        print("[ACTIVE] rt/arm_sdk measured-pose HOLD started.")

        while True:
            now_s = time.monotonic()
            if now_s < next_tick_s:
                time.sleep(min(next_tick_s - now_s, period_s))
                continue
            next_tick_s += period_s

            current = buffer.snapshot()
            if current is None:
                raise RuntimeError("LowState disappeared after publisher start")
            age_s = now_s - current.received_monotonic_s
            validation = validate_measured_hold(
                current.all_q_rad,
                target_dual_arm,
                age_s,
                config.safety,
            )
            if not validation.allowed:
                raise RuntimeError(f"active HOLD rejected: {validation.reason}")
            if current.mode_pr != config.expected_mode_pr:
                raise RuntimeError(f"active mode_pr changed to {current.mode_pr}")
            if current.mode_machine != config.expected_mode_machine:
                raise RuntimeError(
                    f"active mode_machine changed to {current.mode_machine}"
                )

            elapsed_s = now_s - started_s
            schedule_phase, weight, done = blend_weight(
                elapsed_s,
                ramp_up_s=config.ramp_up_s,
                hold_s=config.hold_s,
                ramp_down_s=config.ramp_down_s,
                maximum_weight=config.maximum_weight,
            )
            if stop_requested.is_set() and schedule_phase not in ("RELEASE", "COMPLETE"):
                started_s = now_s - config.ramp_up_s - config.hold_s
                schedule_phase = "RELEASE"
                weight = config.maximum_weight

            if done:
                if zero_cycles_remaining <= 0:
                    break
                zero_cycles_remaining -= 1

            frame = build_measured_hold_frame(
                current.all_q_rad,
                target_dual_arm,
                mode_pr=current.mode_pr,
                mode_machine=current.mode_machine,
                weight=weight,
                config=config.safety,
            )
            _apply_frame(message, frame)
            message.crc = crc.Crc(message)
            publisher.Write(message)
            published_frames += 1

            if now_s - last_report_s >= 0.25:
                details = _status_details(
                    network_interface=args.network_interface,
                    snapshot=current,
                    target_dual_arm_q_rad=target_dual_arm,
                    mode_form=mode_form,
                    mode_name=mode_name,
                    weight=weight,
                    schedule_phase=schedule_phase,
                    published_frames=published_frames,
                    reason="active measured-pose HOLD",
                )
                _write_runtime_status(
                    args.status_json,
                    args.event_log,
                    phase=HardwarePhase.HOLD_ACTIVE,
                    command_output_enabled=True,
                    publisher_present=True,
                    details=details,
                )
                print(
                    f"[{schedule_phase}] weight={weight:.3f} "
                    f"frames={published_frames} age={age_s * 1000.0:.1f}ms"
                )
                last_report_s = now_s

        final_snapshot = buffer.snapshot()
        details = _status_details(
            network_interface=args.network_interface,
            snapshot=final_snapshot,
            target_dual_arm_q_rad=target_dual_arm,
            mode_form=mode_form,
            mode_name=mode_name,
            weight=0.0,
            schedule_phase="COMPLETE",
            published_frames=published_frames,
            reason="normal release completed at zero Arm SDK weight",
        )
        _write_runtime_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.HOLD_READY,
            command_output_enabled=False,
            publisher_present=False,
            details=details,
        )
        print("[PASS] Gate 6 HOLD completed and weight returned to zero.")
        print(f"Result saved to: {args.status_json.resolve()}")
        return 0
    except Exception as exc:
        snapshot = buffer.snapshot()
        message = f"{type(exc).__name__}: {exc}"
        fault_code = FaultCode.INTERNAL_ERROR
        if "motion mode mismatch" in str(exc):
            fault_code = FaultCode.MOTION_MODE_MISMATCH
        elif "LowState" in str(exc) or "lowstate" in str(exc):
            fault_code = FaultCode.LOWSTATE_TIMEOUT
        elif "HOLD rejected" in str(exc):
            fault_code = FaultCode.TARGET_ERROR
        details = _status_details(
            network_interface=args.network_interface,
            snapshot=snapshot,
            target_dual_arm_q_rad=target_dual_arm,
            mode_form=mode_form,
            mode_name=mode_name,
            weight=0.0,
            schedule_phase="FAULT",
            published_frames=published_frames,
            reason=message,
        )
        _write_runtime_status(
            args.status_json,
            args.event_log,
            phase=HardwarePhase.FAULT,
            command_output_enabled=False,
            publisher_present=publisher is not None,
            details=details,
            fault_code=fault_code,
            fault_message=message,
        )
        print(f"[FAULT] {message}")
        if publisher is not None:
            print("[ACTION] Command stream stopped fail-closed; use the robot stop control.")
        else:
            print("[ACTION] No publisher was created. Fix the reported precondition.")
        print(f"Result saved to: {args.status_json.resolve()}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
