#!/usr/bin/env python3
"""Locked Gate 7 Mink-to-``rt/arm_sdk`` hardware adapter.

The default repository configuration cannot create a publisher. Hardware mode
requires an explicit flag, two exact confirmations, a separately unlocked
configuration, a fresh startup precheck, the expected MotionSwitcher mode and
fresh settled LowState. Unitree publisher imports occur only after these checks.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from arm_sdk_hold_contract import (
    ARM_SDK_TOPIC,
    DUAL_ARM_INDICES,
    LOWSTATE_TOPIC,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
)
from arm_sdk_teleop_contract import (
    Gate7ContractError,
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from g1_right_arm_jog import (
    collect_settled_snapshot,
    validate_snapshot_matches_precheck,
)
from gate6_arm_sdk_hold import (
    LowStateBuffer,
    _apply_frame,
    _wait_for_first_snapshot,
    validate_precheck,
)
from gate7_live_dry_run import Gate7LiveDryRunSession
from gate7_mink_arm_sdk_offline import CollisionPathValidator
from g1_joint_contract import G1_29_JOINT_NAMES
from g1_unity_state_bridge import SendUnityHardwareState
from gate5_lowstate_safety_monitor import LowStateTelemetry

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_GATE7_CONFIG: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
)
DEFAULT_HARDWARE_CONFIG: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_gate7_live_hardware_output.json"
)
DEFAULT_REGULAR_POSE: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
)
DEFAULT_PRECHECK: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_startup_precheck.json"
)
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "test_results"
MAX_PACKET_BYTES: Final[int] = 65535
UNITY_STATE_HOST: Final[str] = "127.0.0.1"
UNITY_STATE_PORT: Final[int] = 5010
UNITY_STATE_HZ: Final[float] = 30.0


@dataclass(frozen=True)
class LiveHardwareConfig:
    mink_udp_host: str
    mink_udp_port: int
    expected_form: str
    expected_name: str
    expected_mode_pr: int
    expected_mode_machine: int
    lowstate_timeout_s: float
    settle_duration_s: float
    minimum_settle_samples: int
    maximum_initial_arm_velocity_rad_s: float
    precheck_max_age_s: float
    maximum_precheck_pose_delta_rad: float
    mink_startup_timeout_s: float
    acquire_ramp_s: float
    release_ramp_s: float
    release_zero_cycles: int
    maximum_active_duration_s: float
    maximum_start_pose_excursion_rad: float
    trajectory_generator: str
    ruckig_version: str
    trajectory_velocity_scale: float
    trajectory_acceleration_scale: float
    trajectory_jerk_scale: float
    hardware_output_authorized: bool
    hardware_confirmation_phrase: str
    grounded_regular_confirmation_phrase: str


def _finite(payload: dict[str, Any], key: str) -> float:
    value = float(payload[key])
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def LoadLiveHardwareConfig(path: Path) -> LiveHardwareConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.gate7.live_hardware_output.config.v1":
        raise ValueError("unsupported Gate 7 live hardware config schema")
    if payload.get("lowstate_topic") != LOWSTATE_TOPIC:
        raise ValueError(f"lowstate_topic must be {LOWSTATE_TOPIC}")
    if payload.get("arm_sdk_topic") != ARM_SDK_TOPIC:
        raise ValueError(f"arm_sdk_topic must be {ARM_SDK_TOPIC}")
    mode = payload["expected_motion_mode"]
    config = LiveHardwareConfig(
        mink_udp_host=str(payload["mink_udp_host"]),
        mink_udp_port=int(payload["mink_udp_port"]),
        expected_form=str(mode["form"]),
        expected_name=str(mode["name"]),
        expected_mode_pr=int(payload["expected_mode_pr"]),
        expected_mode_machine=int(payload["expected_mode_machine"]),
        lowstate_timeout_s=_finite(payload, "lowstate_timeout_s"),
        settle_duration_s=_finite(payload, "settle_duration_s"),
        minimum_settle_samples=int(payload["minimum_settle_samples"]),
        maximum_initial_arm_velocity_rad_s=math.radians(
            _finite(payload, "maximum_initial_arm_velocity_deg_s")
        ),
        precheck_max_age_s=_finite(payload, "precheck_max_age_s"),
        maximum_precheck_pose_delta_rad=math.radians(
            _finite(payload, "maximum_precheck_pose_delta_deg")
        ),
        mink_startup_timeout_s=_finite(payload, "mink_startup_timeout_s"),
        acquire_ramp_s=_finite(payload, "acquire_ramp_s"),
        release_ramp_s=_finite(payload, "release_ramp_s"),
        release_zero_cycles=int(payload["release_zero_cycles"]),
        maximum_active_duration_s=_finite(payload, "maximum_active_duration_s"),
        maximum_start_pose_excursion_rad=math.radians(
            _finite(payload, "maximum_start_pose_excursion_deg")
        ),
        trajectory_generator=str(payload["trajectory_generator"]),
        ruckig_version=str(payload["ruckig_version"]),
        trajectory_velocity_scale=_finite(payload, "trajectory_velocity_scale"),
        trajectory_acceleration_scale=_finite(
            payload, "trajectory_acceleration_scale"
        ),
        trajectory_jerk_scale=_finite(payload, "trajectory_jerk_scale"),
        hardware_output_authorized=bool(payload["hardware_output_authorized"]),
        hardware_confirmation_phrase=str(payload["hardware_confirmation_phrase"]),
        grounded_regular_confirmation_phrase=str(
            payload["grounded_regular_confirmation_phrase"]
        ),
    )
    ValidateLiveHardwareConfig(config)
    return config


def ValidateLiveHardwareConfig(config: LiveHardwareConfig) -> None:
    if config.mink_udp_host != "0.0.0.0":
        raise ValueError("WSL Mink listener must remain 0.0.0.0")
    if not 1 <= config.mink_udp_port <= 65535:
        raise ValueError("mink_udp_port must be within 1..65535")
    if config.minimum_settle_samples < 1:
        raise ValueError("minimum_settle_samples must be positive")
    positive = (
        config.lowstate_timeout_s,
        config.settle_duration_s,
        config.maximum_initial_arm_velocity_rad_s,
        config.precheck_max_age_s,
        config.maximum_precheck_pose_delta_rad,
        config.mink_startup_timeout_s,
        config.acquire_ramp_s,
        config.release_ramp_s,
        config.maximum_active_duration_s,
        config.maximum_start_pose_excursion_rad,
    )
    if any(value <= 0.0 for value in positive):
        raise ValueError("Gate 7 live timing and limits must be positive")
    if config.maximum_start_pose_excursion_rad > math.pi:
        raise ValueError("maximum_start_pose_excursion_deg must not exceed 180")
    if config.release_zero_cycles < 1:
        raise ValueError("release_zero_cycles must be positive")
    if config.trajectory_generator != "ruckig":
        raise ValueError("trajectory_generator must be ruckig")
    if config.ruckig_version != "0.19.4":
        raise ValueError("ruckig_version must remain pinned to 0.19.4")
    trajectory_scales = (
        config.trajectory_velocity_scale,
        config.trajectory_acceleration_scale,
        config.trajectory_jerk_scale,
    )
    if trajectory_scales != (1.0, 1.0, 1.0):
        raise ValueError("physical Ruckig trajectory scales must remain 1.0")


def ValidateRuckigRuntime(config: LiveHardwareConfig) -> str:
    installed_version = importlib.metadata.version("ruckig")
    if installed_version != config.ruckig_version:
        raise RuntimeError(
            "Ruckig version mismatch: "
            f"installed={installed_version} expected={config.ruckig_version}"
        )
    return installed_version


def CreateHardwareTrajectoryController(
    regular_pose,
    gate7_config,
    hardware_config: LiveHardwareConfig,
    *,
    return_path_validator,
):
    ValidateRuckigRuntime(hardware_config)
    from ruckig_gate7_controller import RuckigGate7TeleopController

    return RuckigGate7TeleopController(
        regular_pose,
        gate7_config,
        return_path_validator=return_path_validator,
        velocity_scale=hardware_config.trajectory_velocity_scale,
        acceleration_scale=hardware_config.trajectory_acceleration_scale,
        jerk_scale=hardware_config.trajectory_jerk_scale,
    )


def ValidateHardwareAuthorization(
    config: LiveHardwareConfig,
    *,
    enable_hardware_output: bool,
    confirmation: str,
    grounded_confirmation: str,
) -> None:
    if not enable_hardware_output:
        raise PermissionError("--enable-hardware-output was not provided")
    if not config.hardware_output_authorized:
        raise PermissionError("hardware_output_authorized is false")
    if confirmation != config.hardware_confirmation_phrase:
        raise PermissionError("hardware confirmation phrase does not match")
    if grounded_confirmation != config.grounded_regular_confirmation_phrase:
        raise PermissionError("grounded Regular confirmation phrase does not match")


def AcquireWeight(elapsed_s: float, ramp_s: float, maximum_weight: float) -> float:
    if elapsed_s <= 0.0:
        return 0.0
    return maximum_weight * min(1.0, elapsed_s / ramp_s)


def ReleaseWeight(elapsed_s: float, ramp_s: float, start_weight: float) -> float:
    if elapsed_s <= 0.0:
        return start_weight
    return start_weight * max(0.0, 1.0 - elapsed_s / ramp_s)


def CalculateStartPoseExcursion(frame, acquisition_target) -> float:
    """Return the largest commanded dual-arm offset from publisher start."""

    if len(acquisition_target) != len(DUAL_ARM_INDICES):
        raise ValueError("acquisition_target must contain 14 arm joints")
    offsets = [
        abs(float(frame.motor_q_rad[index]) - float(initial))
        for index, initial in zip(DUAL_ARM_INDICES, acquisition_target)
    ]
    if not all(math.isfinite(value) for value in offsets):
        raise ValueError("start-pose excursion contains a non-finite value")
    return max(offsets, default=0.0)


def ValidateStartPoseExcursion(
    frame,
    acquisition_target,
    maximum_excursion_rad: float,
) -> float:
    """Reject a candidate before publish when it leaves the first-live envelope."""

    if not math.isfinite(maximum_excursion_rad) or maximum_excursion_rad <= 0.0:
        raise ValueError("maximum start-pose excursion must be positive and finite")
    excursion = CalculateStartPoseExcursion(frame, acquisition_target)
    if excursion > maximum_excursion_rad + 1.0e-12:
        raise RuntimeError(
            "start_pose_excursion_limit: "
            f"{math.degrees(excursion):.2f}deg > "
            f"{math.degrees(maximum_excursion_rad):.2f}deg"
        )
    return excursion


def _ReceiveLatestMink(sock: socket.socket):
    latest = None
    while True:
        try:
            payload, _source = sock.recvfrom(MAX_PACKET_BYTES)
        except BlockingIOError:
            return latest
        latest = parse_mink_arm_sample(payload)


def WaitForFirstActiveMink(sock: socket.socket, timeout_s: float):
    """Wait for an engaged command before permitting publisher construction."""

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        sample = _ReceiveLatestMink(sock)
        if (
            sample is not None
            and sample.input_command_mode == "active"
            and sample.controller_state == "active"
        ):
            return sample
        time.sleep(0.01)
    raise TimeoutError(
        f"no active Mink command received within {timeout_s:.1f}s; "
        "engage the tracked hand in Unity"
    )


def BuildUnityLowStateTelemetry(snapshot, session_id: str) -> LowStateTelemetry:
    """Convert the exact Gate 7 LowState snapshot to Unity's read-only contract."""

    return LowStateTelemetry(
        bridge_session_id=session_id,
        sequence=snapshot.sequence,
        sent_at_unix_ns=snapshot.received_unix_ns,
        mode_pr=snapshot.mode_pr,
        mode_machine=snapshot.mode_machine,
        measured_q_rad=tuple(snapshot.all_q_rad[22:29]),
        measured_dq_rad_s=tuple(snapshot.all_dq_rad_s[22:29]),
        all_joint_names=G1_29_JOINT_NAMES,
        all_joint_q_rad=tuple(snapshot.all_q_rad),
        all_joint_dq_rad_s=tuple(snapshot.all_dq_rad_s),
        base_state=None,
    )


def _result_path() -> Path:
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return RESULT_DIRECTORY / (
        "g1_gate7_live_hardware_" + time.strftime("%Y%m%d_%H%M%S") + ".json"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Locked Gate 7 live Arm SDK adapter")
    parser.add_argument("network_interface", nargs="?", default="")
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--gate7-config", type=Path, default=DEFAULT_GATE7_CONFIG)
    parser.add_argument(
        "--hardware-config", type=Path, default=DEFAULT_HARDWARE_CONFIG
    )
    parser.add_argument("--regular-pose", type=Path, default=DEFAULT_REGULAR_POSE)
    parser.add_argument("--precheck-json", type=Path, default=DEFAULT_PRECHECK)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--startup-timeout", type=float, default=5.0)
    parser.add_argument("--enable-hardware-output", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--confirm-grounded-regular", default="")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--pre-publisher-check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result_path = _result_path()
    result: dict[str, Any] = {
        "schema": "g1.gate7.live_hardware.result.v1",
        "passed": False,
        "publisher_created": False,
        "command_output_enabled": False,
        "published_frames": 0,
        "release_zero_frames": 0,
        "right_arm_command_indices": list(range(22, 29)),
        "left_arm_policy": "measured_hold",
        "waist_and_legs_command_enabled": False,
        "trajectory_generator": None,
        "ruckig_version": None,
        "maximum_start_pose_excursion_deg": None,
        "maximum_observed_start_pose_excursion_deg": 0.0,
        "maximum_command_weight": 0.0,
        "maximum_command_delta_by_arm_joint_deg": [0.0] * len(DUAL_ARM_INDICES),
        "maximum_measured_delta_by_arm_joint_deg": [0.0] * len(DUAL_ARM_INDICES),
        "maximum_tracking_error_by_arm_joint_deg": [0.0] * len(DUAL_ARM_INDICES),
        "received_mink_mode_counts": {},
        "unity_state_host": UNITY_STATE_HOST,
        "unity_state_port": UNITY_STATE_PORT,
        "unity_state_packets": 0,
    }
    publisher = None
    command_message = None
    command_crc = None
    buffer = LowStateBuffer()
    mink_socket = None
    unity_socket = None
    last_target = None
    last_weight = 0.0
    try:
        gate7_config = load_gate7_config(args.gate7_config)
        hardware_config = LoadLiveHardwareConfig(args.hardware_config)
        result["trajectory_generator"] = hardware_config.trajectory_generator
        result["ruckig_version"] = ValidateRuckigRuntime(hardware_config)
        result["maximum_start_pose_excursion_deg"] = math.degrees(
            hardware_config.maximum_start_pose_excursion_rad
        )
        regular_pose = load_regular_arm_pose(args.regular_pose)
        print("[PHASE] Configuration and Ruckig validation passed.", flush=True)
        if gate7_config.hardware_output_authorized:
            raise ValueError("Gate 7 algorithm config must remain hardware locked")
        if args.validate_only:
            result.update(
                passed=True,
                mode="VALIDATE_ONLY",
                hardware_output_authorized=hardware_config.hardware_output_authorized,
            )
            result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print("G1 Gate 7 live hardware adapter -- VALIDATE ONLY")
            print("Unitree SDK: NONE")
            print("DDS publisher: NONE")
            print("Robot command: NONE")
            print("[PASS] Contracts load; physical output remains locked.")
            return 0

        if args.pre_publisher_check_only:
            if args.enable_hardware_output:
                raise ValueError(
                    "pre-publisher check must not enable hardware output"
                )
        else:
            ValidateHardwareAuthorization(
                hardware_config,
                enable_hardware_output=args.enable_hardware_output,
                confirmation=args.confirm,
                grounded_confirmation=args.confirm_grounded_regular,
            )
        precheck = validate_precheck(
            args.precheck_json, hardware_config.precheck_max_age_s
        )
        print("[PHASE] Fresh startup precheck loaded.", flush=True)
        if not args.network_interface:
            raise ValueError("network_interface is required for hardware mode")

        # Hardware-only imports stay below all static authorization checks.
        from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
            MotionSwitcherClient,
        )
        from unitree_sdk2py.core.channel import (
            ChannelFactoryInitialize,
            ChannelPublisher,
            ChannelSubscriber,
        )
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
        from unitree_sdk2py.utils.crc import CRC

        print("[PHASE] Unitree SDK imports passed.", flush=True)
        ChannelFactoryInitialize(args.domain_id, args.network_interface)
        print("[PHASE] DDS channel factory initialized.", flush=True)
        motion_client = MotionSwitcherClient()
        motion_client.SetTimeout(args.startup_timeout)
        motion_client.Init()
        code, mode = motion_client.CheckMode()
        if code != 0 or not isinstance(mode, dict):
            raise RuntimeError(f"MotionSwitcher CheckMode failed: code={code}")
        if (str(mode.get("form")), str(mode.get("name"))) != (
            hardware_config.expected_form,
            hardware_config.expected_name,
        ):
            raise RuntimeError(f"motion mode mismatch: {mode}")
        print("[PHASE] MotionSwitcher read-only mode check passed.", flush=True)

        subscriber = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        subscriber.Init(buffer.callback, 10)
        _wait_for_first_snapshot(buffer, args.startup_timeout)
        print("[PHASE] First LowState packet received.", flush=True)
        snapshot, samples, maximum_velocity = collect_settled_snapshot(
            buffer,
            type(
                "SettleConfig",
                (),
                {
                    "settle_duration_s": hardware_config.settle_duration_s,
                    "minimum_settle_samples": hardware_config.minimum_settle_samples,
                    "maximum_initial_arm_velocity_rad_s": (
                        hardware_config.maximum_initial_arm_velocity_rad_s
                    ),
                },
            )(),
        )
        validate_snapshot_matches_precheck(
            snapshot, precheck, hardware_config.maximum_precheck_pose_delta_rad
        )
        if snapshot.mode_pr != hardware_config.expected_mode_pr:
            raise RuntimeError(f"mode_pr mismatch: {snapshot.mode_pr}")
        if snapshot.mode_machine != hardware_config.expected_mode_machine:
            raise RuntimeError(f"mode_machine mismatch: {snapshot.mode_machine}")
        print(
            f"[PHASE] LowState settled with {samples} samples; "
            f"maximum arm dq={math.degrees(maximum_velocity):.2f} deg/s.",
            flush=True,
        )

        mink_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mink_socket.bind(
            (hardware_config.mink_udp_host, hardware_config.mink_udp_port)
        )
        mink_socket.setblocking(False)
        if args.ready_file is not None:
            args.ready_file.parent.mkdir(parents=True, exist_ok=True)
            args.ready_file.write_text(
                json.dumps(
                    {
                        "schema": "g1.gate7.adapter_ready.v1",
                        "port": hardware_config.mink_udp_port,
                        "ready_unix_ns": time.time_ns(),
                        "publisher_created": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        print(
            f"[PHASE] UDP {hardware_config.mink_udp_port} bound.",
            flush=True,
        )
        collision_validator = CollisionPathValidator()
        trajectory_controller = CreateHardwareTrajectoryController(
            regular_pose,
            gate7_config,
            hardware_config,
            return_path_validator=collision_validator,
        )
        session = Gate7LiveDryRunSession(
            regular_pose,
            gate7_config,
            measured_source="lowstate",
            return_path_validator=collision_validator,
            controller=trajectory_controller,
        )
        session.hold_config = type(session.hold_config)(
            lowstate_timeout_s=hardware_config.lowstate_timeout_s,
            maximum_target_error_rad=gate7_config.maximum_target_error_rad,
        )

        if args.pre_publisher_check_only:
            result.update(
                passed=True,
                mode="PRE_PUBLISHER_CHECK_ONLY",
                settle_samples=samples,
                maximum_initial_arm_velocity_deg_s=math.degrees(maximum_velocity),
                hardware_output_authorized=False,
            )
            print("[PASS] Pre-publisher check completed.", flush=True)
            print("DDS subscriber: rt/lowstate", flush=True)
            print("DDS publisher: NONE", flush=True)
            print("Robot command: NONE", flush=True)
            return 0

        print(
            "[WAIT] UDP 5013 is ready; waiting for an ACTIVE relayed Mink "
            "command before publisher creation."
        )
        WaitForFirstActiveMink(
            mink_socket, hardware_config.mink_startup_timeout_s
        )

        # Recheck time-sensitive evidence at the exact publisher boundary.
        precheck = validate_precheck(
            args.precheck_json, hardware_config.precheck_max_age_s
        )
        snapshot = buffer.snapshot()
        if snapshot is None:
            raise RuntimeError("LowState disappeared before publisher creation")
        lowstate_age = time.monotonic() - snapshot.received_monotonic_s
        if lowstate_age > hardware_config.lowstate_timeout_s:
            raise RuntimeError(
                f"LowState stale before publisher creation: {lowstate_age:.3f}s"
            )
        validate_snapshot_matches_precheck(
            snapshot, precheck, hardware_config.maximum_precheck_pose_delta_rad
        )
        if snapshot.mode_pr != hardware_config.expected_mode_pr:
            raise RuntimeError(f"mode_pr changed before publish: {snapshot.mode_pr}")
        if snapshot.mode_machine != hardware_config.expected_mode_machine:
            raise RuntimeError(
                f"mode_machine changed before publish: {snapshot.mode_machine}"
            )

        # Publisher construction remains the final step after every prerequisite.
        publisher = ChannelPublisher(ARM_SDK_TOPIC, LowCmd_)
        publisher.Init()
        command_message = unitree_hg_msg_dds__LowCmd_()
        command_crc = CRC()
        result["publisher_created"] = True
        stop_requested = threading.Event()

        def RequestStop(_signum: int, _frame: Any) -> None:
            stop_requested.set()

        signal.signal(signal.SIGINT, RequestStop)
        signal.signal(signal.SIGTERM, RequestStop)
        period_s = 1.0 / gate7_config.command_hz
        next_tick = time.monotonic()
        started = next_tick
        last_tick = next_tick
        acquisition_target = dual_arm_from_all_joints(snapshot.all_q_rad)
        last_target = acquisition_target
        maximum_command_delta = [0.0] * len(DUAL_ARM_INDICES)
        maximum_measured_delta = [0.0] * len(DUAL_ARM_INDICES)
        maximum_tracking_error = [0.0] * len(DUAL_ARM_INDICES)
        next_report = started
        unity_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        unity_session_id = f"gate7-live-{time.time_ns()}"
        next_unity_state = started
        print("[ACTIVE] Gate 7 publisher created; acquiring measured arm pose.")
        print(
            f"[MIRROR] Actual 29-joint LowState -> Unity UDP {UNITY_STATE_PORT} "
            f"at {UNITY_STATE_HZ:.0f} Hz.",
            flush=True,
        )

        while not stop_requested.is_set():
            now = time.monotonic()
            if now < next_tick:
                time.sleep(min(0.001, next_tick - now))
                continue
            next_tick += period_s
            if now - started > hardware_config.maximum_active_duration_s:
                print("[STOP] Maximum active duration reached.")
                break
            current = buffer.snapshot()
            if current is None:
                raise RuntimeError("LowState disappeared")
            lowstate_age = now - current.received_monotonic_s
            if lowstate_age > hardware_config.lowstate_timeout_s:
                raise RuntimeError(f"LowState stale: {lowstate_age:.3f}s")
            if current.mode_pr != hardware_config.expected_mode_pr:
                raise RuntimeError(f"mode_pr changed: {current.mode_pr}")
            if current.mode_machine != hardware_config.expected_mode_machine:
                raise RuntimeError(f"mode_machine changed: {current.mode_machine}")

            elapsed = now - started
            if elapsed < hardware_config.acquire_ramp_s:
                last_weight = AcquireWeight(
                    elapsed,
                    hardware_config.acquire_ramp_s,
                    gate7_config.command_weight,
                )
                frame = build_measured_hold_frame(
                    current.all_q_rad,
                    acquisition_target,
                    mode_pr=current.mode_pr,
                    mode_machine=current.mode_machine,
                    weight=last_weight,
                    config=session.hold_config,
                )
            else:
                sample = _ReceiveLatestMink(mink_socket)
                if sample is not None:
                    mode_counts = result["received_mink_mode_counts"]
                    mode_counts[sample.input_command_mode] = (
                        mode_counts.get(sample.input_command_mode, 0) + 1
                    )
                dt_s = max(1.0e-6, now - last_tick)
                tick = session.Step(
                    sample,
                    current.all_q_rad,
                    dt_s,
                    lowstate_age_s=lowstate_age,
                    mode_pr=current.mode_pr,
                    mode_machine=current.mode_machine,
                )
                if tick.frame is None:
                    raise RuntimeError(
                        "Gate 7 command candidate rejected: "
                        f"{tick.validation_reason}"
                    )
                frame = tick.frame
                last_weight = frame.weight

            if now >= next_unity_state:
                SendUnityHardwareState(
                    unity_socket,
                    BuildUnityLowStateTelemetry(current, unity_session_id),
                    UNITY_STATE_HOST,
                    UNITY_STATE_PORT,
                )
                result["unity_state_packets"] += 1
                next_unity_state = now + (1.0 / UNITY_STATE_HZ)
            excursion = ValidateStartPoseExcursion(
                frame,
                acquisition_target,
                hardware_config.maximum_start_pose_excursion_rad,
            )
            result["maximum_observed_start_pose_excursion_deg"] = max(
                result["maximum_observed_start_pose_excursion_deg"],
                math.degrees(excursion),
            )
            last_target = tuple(
                frame.motor_q_rad[index] for index in DUAL_ARM_INDICES
            )
            measured_arm = dual_arm_from_all_joints(current.all_q_rad)
            for offset, (commanded, measured, initial) in enumerate(
                zip(last_target, measured_arm, acquisition_target)
            ):
                maximum_command_delta[offset] = max(
                    maximum_command_delta[offset], abs(commanded - initial)
                )
                maximum_measured_delta[offset] = max(
                    maximum_measured_delta[offset], abs(measured - initial)
                )
                maximum_tracking_error[offset] = max(
                    maximum_tracking_error[offset], abs(commanded - measured)
                )
            result["maximum_command_weight"] = max(
                result["maximum_command_weight"], last_weight
            )
            result["maximum_command_delta_by_arm_joint_deg"] = [
                math.degrees(value) for value in maximum_command_delta
            ]
            result["maximum_measured_delta_by_arm_joint_deg"] = [
                math.degrees(value) for value in maximum_measured_delta
            ]
            result["maximum_tracking_error_by_arm_joint_deg"] = [
                math.degrees(value) for value in maximum_tracking_error
            ]
            if now >= next_report:
                phase = "ACQUIRE" if elapsed < hardware_config.acquire_ramp_s else "CONTROL"
                print(
                    f"[{phase}] weight={last_weight:.3f} "
                    f"command_delta={math.degrees(max(maximum_command_delta)):.2f}deg "
                    f"measured_delta={math.degrees(max(maximum_measured_delta)):.2f}deg "
                    f"tracking_error={math.degrees(max(maximum_tracking_error)):.2f}deg",
                    flush=True,
                )
                next_report = now + 0.5
            last_tick = now
            _apply_frame(command_message, frame)
            command_message.crc = command_crc.Crc(command_message)
            publisher.Write(command_message)
            result["published_frames"] += 1
            result["command_output_enabled"] = last_weight > 0.0

        result.update(
            passed=True,
            mode="HARDWARE_RUN_COMPLETED",
            settle_samples=samples,
            maximum_initial_arm_velocity_deg_s=math.degrees(maximum_velocity),
        )
    except (Exception, KeyboardInterrupt) as exc:
        result["fault"] = f"{type(exc).__name__}: {exc}"
        print(f"[FAULT] {result['fault']}")
        print("[ACTION] Keep the handheld remote ready and do not retry until fixed.")
    finally:
        if publisher is not None and command_message is not None and command_crc is not None:
            try:
                release_started = time.monotonic()
                period_s = 1.0 / load_gate7_config(args.gate7_config).command_hz
                hardware_config = LoadLiveHardwareConfig(args.hardware_config)
                while time.monotonic() - release_started < hardware_config.release_ramp_s:
                    current = buffer.snapshot()
                    if current is None or last_target is None:
                        break
                    elapsed = time.monotonic() - release_started
                    weight = ReleaseWeight(
                        elapsed, hardware_config.release_ramp_s, last_weight
                    )
                    frame = build_measured_hold_frame(
                        current.all_q_rad,
                        last_target,
                        mode_pr=current.mode_pr,
                        mode_machine=current.mode_machine,
                        weight=weight,
                    )
                    _apply_frame(command_message, frame)
                    command_message.crc = command_crc.Crc(command_message)
                    publisher.Write(command_message)
                    time.sleep(period_s)
                current = buffer.snapshot()
                if current is not None:
                    zero_target = dual_arm_from_all_joints(current.all_q_rad)
                    for _ in range(hardware_config.release_zero_cycles):
                        frame = build_measured_hold_frame(
                            current.all_q_rad,
                            zero_target,
                            mode_pr=current.mode_pr,
                            mode_machine=current.mode_machine,
                            weight=0.0,
                        )
                        _apply_frame(command_message, frame)
                        command_message.crc = command_crc.Crc(command_message)
                        publisher.Write(command_message)
                        result["release_zero_frames"] += 1
                        time.sleep(period_s)
            except Exception as release_exc:
                result["release_fault"] = f"{type(release_exc).__name__}: {release_exc}"
            result["command_output_enabled"] = False

        if mink_socket is not None:
            mink_socket.close()
        if unity_socket is not None:
            unity_socket.close()

        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Result saved to: {result_path.resolve()}")
    return 0 if result.get("passed") else 2


if __name__ == "__main__":
    sys.exit(main())
