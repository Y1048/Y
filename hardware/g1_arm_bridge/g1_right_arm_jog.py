#!/usr/bin/env python3
"""Bounded single-joint keyboard jog of the real G1 right arm.

The publisher is created only after a fresh startup precheck, exact runtime
confirmations, Regular-mode verification and a settled LowState window.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import select
import signal
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from arm_sdk_hold_contract import (
    ARM_SDK_TOPIC,
    DUAL_ARM_INDICES,
    LEFT_ARM_JOINT_NAMES,
    LOWSTATE_TOPIC,
    ArmSdkHoldConfig,
    build_measured_hold_frame,
    dual_arm_from_all_joints,
)
from arm_sdk_hold_contract import RIGHT_ARM_JOINT_NAMES
from arm_sdk_release_contract import ReleaseEvidence, execute_release_sequence
from right_arm_jog_contract import ArmJointJogController, ArmJointJogLimits
from gate6_arm_sdk_hold import (
    LowStateBuffer,
    _apply_frame,
    _wait_for_first_snapshot,
    validate_precheck,
)

try:
    import termios
    import tty
except ImportError:  # Windows validate-only and unit-test path.
    termios = None
    tty = None


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Final[Path] = PROJECT_ROOT / "config" / "g1_right_arm_jog.json"
DEFAULT_PRECHECK_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_startup_precheck.json"
)
DEFAULT_PATH_PERMIT_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_right_arm_jog_path_permit.json"
)
RESULT_DIRECTORY: Final[Path] = PROJECT_ROOT / "logs" / "test_results"


@dataclass(frozen=True)
class RuntimeConfig:
    trial_mode: str
    allowed_joint_names: tuple[str, ...]
    hold_unselected_start_pose: bool
    require_full_weight_before_jog: bool
    arming_tracking_tolerance_rad: float
    arming_timeout_s: float
    expected_form: str
    expected_name: str
    expected_mode_pr: int
    expected_mode_machine: int
    settle_duration_s: float
    minimum_settle_samples: int
    maximum_initial_arm_velocity_rad_s: float
    maximum_precheck_pose_delta_rad: float
    joint_switch_return_tolerance_rad: float
    joint_step_tracking_tolerance_rad: float
    proximal_joint_maximum_velocity_rad_s: float
    wrist_joint_maximum_velocity_rad_s: float
    publish_hz: float
    ramp_up_s: float
    ramp_down_s: float
    maximum_active_duration_s: float
    joint_selection_timeout_s: float
    maximum_weight: float
    release_zero_cycles: int
    precheck_max_age_s: float
    hardware_output_authorized: bool
    hardware_confirmation_phrase: str
    grounded_regular_confirmation_phrase: str
    jog: ArmJointJogLimits
    hold: ArmSdkHoldConfig


class KeyboardReader:
    """Nonblocking arrow-key reader for the interactive WSL terminal."""

    def __init__(self) -> None:
        self.file_descriptor = sys.stdin.fileno()
        self.previous_attributes: list[Any] | None = None
        self.buffer = bytearray()

    def __enter__(self) -> "KeyboardReader":
        if termios is None or tty is None:
            raise RuntimeError("interactive arm jog requires Linux/WSL")
        if not os.isatty(self.file_descriptor):
            raise RuntimeError("interactive arm jog requires a terminal")
        self.previous_attributes = termios.tcgetattr(self.file_descriptor)
        tty.setcbreak(self.file_descriptor)
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        if self.previous_attributes is not None:
            termios.tcsetattr(
                self.file_descriptor,
                termios.TCSADRAIN,
                self.previous_attributes,
            )

    def read_actions(self) -> list[str]:
        while select.select([self.file_descriptor], [], [], 0.0)[0]:
            self.buffer.extend(os.read(self.file_descriptor, 32))

        actions: list[str] = []
        while self.buffer:
            if self.buffer.startswith(b"\x1b[A"):
                del self.buffer[:3]
                actions.append("up")
            elif self.buffer.startswith(b"\x1b[B"):
                del self.buffer[:3]
                actions.append("down")
            elif self.buffer[0] in (ord("q"), ord("Q")):
                del self.buffer[:1]
                actions.append("quit")
            elif self.buffer[0] in (ord("h"), ord("H")):
                del self.buffer[:1]
                actions.append("help")
            elif self.buffer[0] in tuple(ord(str(value)) for value in range(1, 8)):
                value = int(chr(self.buffer[0]))
                del self.buffer[:1]
                actions.append(f"select_{value}")
            elif self.buffer[0] == 0x1B and len(self.buffer) < 3:
                break
            else:
                del self.buffer[:1]
        return actions


def _number(payload: dict[str, Any], key: str) -> float:
    value = float(payload[key])
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def load_config(path: Path) -> RuntimeConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.right_arm_jog.config.v1":
        raise ValueError("unsupported right-arm jog config schema")
    if payload.get("arm_sdk_topic") != ARM_SDK_TOPIC:
        raise ValueError(f"arm_sdk_topic must be {ARM_SDK_TOPIC}")
    if payload.get("lowstate_topic") != LOWSTATE_TOPIC:
        raise ValueError(f"lowstate_topic must be {LOWSTATE_TOPIC}")
    expected_mode = payload["expected_motion_mode"]
    proximal_velocity_rad_s = math.radians(
        _number(payload, "proximal_joint_maximum_velocity_deg_s")
    )
    wrist_velocity_rad_s = math.radians(
        _number(payload, "wrist_joint_maximum_velocity_deg_s")
    )
    jog = ArmJointJogLimits(
        step_rad=math.radians(_number(payload, "joint_step_deg")),
        minimum_offset_rad=-math.radians(
            _number(payload, "joint_maximum_offset_deg")
        ),
        maximum_offset_rad=math.radians(
            _number(payload, "joint_maximum_offset_deg")
        ),
        maximum_velocity_rad_s=max(
            proximal_velocity_rad_s,
            wrist_velocity_rad_s,
        ),
        joint_limit_margin_rad=math.radians(
            _number(payload, "joint_limit_margin_deg")
        ),
    )
    hold = ArmSdkHoldConfig(
        lowstate_timeout_s=_number(payload, "lowstate_timeout_s"),
        joint_limit_margin_rad=jog.joint_limit_margin_rad,
        maximum_target_error_rad=math.radians(
            _number(payload, "maximum_target_error_deg")
        ),
        proximal_kp=_number(payload, "proximal_kp"),
        proximal_kd=_number(payload, "proximal_kd"),
        wrist_kp=_number(payload, "wrist_kp"),
        wrist_kd=_number(payload, "wrist_kd"),
    )
    config = RuntimeConfig(
        trial_mode=str(payload.get("trial_mode", "bounded_jog")),
        allowed_joint_names=tuple(
            str(value)
            for value in payload.get("allowed_joint_names", RIGHT_ARM_JOINT_NAMES)
        ),
        hold_unselected_start_pose=bool(
            payload.get("hold_unselected_start_pose", False)
        ),
        require_full_weight_before_jog=bool(
            payload.get("require_full_weight_before_jog", False)
        ),
        arming_tracking_tolerance_rad=math.radians(
            float(payload.get("arming_tracking_tolerance_deg", 1.0))
        ),
        arming_timeout_s=float(payload.get("arming_timeout_s", 10.0)),
        expected_form=str(expected_mode["form"]),
        expected_name=str(expected_mode["name"]),
        expected_mode_pr=int(payload["expected_mode_pr"]),
        expected_mode_machine=int(payload["expected_mode_machine"]),
        settle_duration_s=_number(payload, "settle_duration_s"),
        minimum_settle_samples=int(payload["minimum_settle_samples"]),
        maximum_initial_arm_velocity_rad_s=math.radians(
            _number(payload, "maximum_initial_arm_velocity_deg_s")
        ),
        maximum_precheck_pose_delta_rad=math.radians(
            _number(payload, "maximum_precheck_pose_delta_deg")
        ),
        joint_switch_return_tolerance_rad=math.radians(
            _number(payload, "joint_switch_return_tolerance_deg")
        ),
        joint_step_tracking_tolerance_rad=math.radians(
            _number(payload, "joint_step_tracking_tolerance_deg")
        ),
        proximal_joint_maximum_velocity_rad_s=proximal_velocity_rad_s,
        wrist_joint_maximum_velocity_rad_s=wrist_velocity_rad_s,
        publish_hz=_number(payload, "publish_hz"),
        ramp_up_s=_number(payload, "ramp_up_s"),
        ramp_down_s=_number(payload, "ramp_down_s"),
        maximum_active_duration_s=_number(
            payload,
            "maximum_active_duration_s",
        ),
        joint_selection_timeout_s=_number(payload, "joint_selection_timeout_s"),
        maximum_weight=_number(payload, "maximum_weight"),
        release_zero_cycles=int(payload["release_zero_cycles"]),
        precheck_max_age_s=_number(payload, "precheck_max_age_s"),
        hardware_output_authorized=bool(payload["hardware_output_authorized"]),
        hardware_confirmation_phrase=str(payload["hardware_confirmation_phrase"]),
        grounded_regular_confirmation_phrase=str(
            payload["grounded_regular_confirmation_phrase"]
        ),
        jog=jog,
        hold=hold,
    )
    validate_config(config)
    return config


def validate_config(config: RuntimeConfig) -> None:
    positive_values = (
        config.settle_duration_s,
        config.maximum_initial_arm_velocity_rad_s,
        config.maximum_precheck_pose_delta_rad,
        config.joint_switch_return_tolerance_rad,
        config.joint_step_tracking_tolerance_rad,
        config.proximal_joint_maximum_velocity_rad_s,
        config.wrist_joint_maximum_velocity_rad_s,
        config.publish_hz,
        config.ramp_up_s,
        config.ramp_down_s,
        config.maximum_active_duration_s,
        config.joint_selection_timeout_s,
        config.maximum_weight,
        config.precheck_max_age_s,
        config.arming_tracking_tolerance_rad,
        config.arming_timeout_s,
    )
    if not all(math.isfinite(value) and value > 0.0 for value in positive_values):
        raise ValueError("right-arm jog runtime values must be finite and positive")
    if config.minimum_settle_samples < 1 or config.release_zero_cycles < 1:
        raise ValueError("sample and release cycle counts must be positive")
    if not config.allowed_joint_names:
        raise ValueError("allowed_joint_names must not be empty")
    if len(set(config.allowed_joint_names)) != len(config.allowed_joint_names):
        raise ValueError("allowed_joint_names contains duplicates")
    if any(name not in RIGHT_ARM_JOINT_NAMES for name in config.allowed_joint_names):
        raise ValueError("allowed_joint_names contains an unsupported joint")
    if config.trial_mode == "bounded_jog":
        if config.maximum_weight > 0.25:
            raise ValueError("bounded right-arm jog weight must not exceed 0.25")
    elif config.trial_mode == "full_authority_shoulder_pitch_trial":
        if config.allowed_joint_names != ("right_shoulder_pitch",):
            raise ValueError("full-authority trial must allow shoulder pitch only")
        if not math.isclose(config.maximum_weight, 1.0, abs_tol=1.0e-12):
            raise ValueError("full-authority trial weight must equal 1.0")
        if config.jog.maximum_offset_rad > math.radians(1.0):
            raise ValueError("full-authority trial offset must not exceed 1 degree")
        if config.jog.minimum_offset_rad < math.radians(-1.0):
            raise ValueError("full-authority trial offset must not be below -1 degree")
        if config.ramp_up_s < 5.0:
            raise ValueError("full-authority trial ramp-up must be at least 5 seconds")
        if config.maximum_active_duration_s > 15.0:
            raise ValueError("full-authority trial must not exceed 15 seconds")
        if not config.hold_unselected_start_pose:
            raise ValueError("full-authority trial must hold the initial 14-axis pose")
        if not config.require_full_weight_before_jog:
            raise ValueError("full-authority trial must block Jog input while arming")
        if config.arming_tracking_tolerance_rad > math.radians(1.5):
            raise ValueError("full-authority arming tolerance must not exceed 1.5 degrees")
    else:
        raise ValueError(f"unsupported right-arm jog trial_mode: {config.trial_mode}")
    if config.jog.maximum_offset_rad > math.radians(20.0):
        raise ValueError("right-arm jog offset must not exceed 20 degrees")
    if config.jog.minimum_offset_rad < math.radians(-20.0):
        raise ValueError("right-arm jog offset must not be below -20 degrees")
    if config.jog.maximum_velocity_rad_s > math.radians(5.0):
        raise ValueError("right-arm jog velocity must not exceed 5 deg/s")
    if config.maximum_active_duration_s > 30.0:
        raise ValueError("right-arm jog duration must not exceed 30 seconds")
    if not config.hardware_confirmation_phrase:
        raise ValueError("hardware confirmation phrase is empty")
    if not config.grounded_regular_confirmation_phrase:
        raise ValueError("grounded confirmation phrase is empty")


def validate_authorization(
    config: RuntimeConfig,
    enabled: bool,
    confirmation: str,
    grounded_confirmation: str,
) -> None:
    if not enabled:
        raise PermissionError("--enable-hardware-output was not provided")
    if not config.hardware_output_authorized:
        raise PermissionError("hardware_output_authorized is false")
    if confirmation != config.hardware_confirmation_phrase:
        raise PermissionError("hardware confirmation phrase does not match")
    if grounded_confirmation != config.grounded_regular_confirmation_phrase:
        raise PermissionError("grounded Regular confirmation phrase does not match")


def validate_snapshot_matches_precheck(
    snapshot: Any,
    precheck: dict[str, Any],
    maximum_delta_rad: float,
) -> float:
    values = precheck.get("latest_all_joint_q_rad")
    if not isinstance(values, list) or len(values) != 29:
        raise ValueError("startup precheck is missing the canonical 29-joint pose")
    precheck_q = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in precheck_q):
        raise ValueError("startup precheck pose contains a non-finite value")
    maximum_delta = max(
        abs(float(snapshot.all_q_rad[index]) - precheck_q[index])
        for index in range(15, 29)
    )
    if maximum_delta > maximum_delta_rad:
        raise RuntimeError(
            "arm pose changed after collision precheck: "
            f"{math.degrees(maximum_delta):.2f} deg > "
            f"{math.degrees(maximum_delta_rad):.2f} deg"
        )
    return maximum_delta


def load_path_permit(
    path: Path,
    precheck: dict[str, Any],
    config: RuntimeConfig,
) -> dict[str, tuple[float, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.right_arm_jog.path_permit.v2":
        raise ValueError("right-arm Jog path permit schema mismatch")
    if payload.get("passed") is not True:
        raise ValueError("right-arm Jog path permit did not pass")
    if payload.get("publisher_present") is not False:
        raise ValueError("path permit unexpectedly reports a publisher")
    if payload.get("command_output_enabled") is not False:
        raise ValueError("path permit unexpectedly enabled command output")
    if int(payload.get("precheck_checked_at_unix_ns", -1)) != int(
        precheck["checked_at_unix_ns"]
    ):
        raise ValueError("path permit belongs to a different startup precheck")
    permit_pose = payload.get("precheck_all_joint_q_rad")
    precheck_pose = precheck.get("latest_all_joint_q_rad")
    if not isinstance(permit_pose, list) or permit_pose != precheck_pose:
        raise ValueError("path permit pose differs from startup precheck pose")
    joints = payload.get("joints")
    if not isinstance(joints, dict):
        raise ValueError("path permit joints must be an object")
    result: dict[str, tuple[float, float]] = {}
    for joint_name in config.allowed_joint_names:
        item = joints.get(joint_name)
        if not isinstance(item, dict):
            raise ValueError(f"path permit is missing {joint_name}")
        minimum_rad = math.radians(float(item["minimum_offset_deg"]))
        maximum_rad = math.radians(float(item["maximum_offset_deg"]))
        if not all(math.isfinite(value) for value in (minimum_rad, maximum_rad)):
            raise ValueError(f"path permit contains non-finite {joint_name} bounds")
        if minimum_rad > 0.0 or maximum_rad < 0.0:
            raise ValueError(f"path permit {joint_name} bounds exclude zero")
        if minimum_rad < config.jog.minimum_offset_rad - 1.0e-12:
            raise ValueError(f"path permit {joint_name} minimum exceeds config")
        if maximum_rad > config.jog.maximum_offset_rad + 1.0e-12:
            raise ValueError(f"path permit {joint_name} maximum exceeds config")
        result[joint_name] = (minimum_rad, maximum_rad)
    return result


def permitted_limits(
    config: RuntimeConfig,
    permit: dict[str, tuple[float, float]],
    joint_name: str,
) -> ArmJointJogLimits:
    minimum_offset, maximum_offset = permit[joint_name]
    arm_index = RIGHT_ARM_JOINT_NAMES.index(joint_name)
    maximum_velocity = (
        config.proximal_joint_maximum_velocity_rad_s
        if arm_index < 4
        else config.wrist_joint_maximum_velocity_rad_s
    )
    return replace(
        config.jog,
        minimum_offset_rad=minimum_offset,
        maximum_offset_rad=maximum_offset,
        maximum_velocity_rad_s=maximum_velocity,
    )


def step_candidate_tracking_error(
    controller: ArmJointJogController,
    measured_all_q_rad: tuple[float, ...],
    direction: int,
) -> tuple[float, float]:
    candidate = controller.preview_step(direction)
    measured = float(measured_all_q_rad[controller.joint_index])
    return candidate, abs(candidate - measured)


def calculate_active_weight(
    active_started_s: float | None,
    now_s: float,
    maximum_weight: float,
    ramp_up_s: float,
) -> float:
    if active_started_s is None:
        return 0.0
    elapsed_s = max(0.0, now_s - active_started_s)
    return min(maximum_weight, maximum_weight * elapsed_s / ramp_up_s)


def maximum_dual_arm_target_error(
    frame: Any,
    measured_all_q_rad: tuple[float, ...],
) -> float:
    """Return the largest absolute error across the 14 Arm SDK joints."""
    return max(
        abs(float(frame.motor_q_rad[index]) - float(measured_all_q_rad[index]))
        for index in range(15, 29)
    )


def dual_arm_target_errors_deg(
    frame: Any,
    measured_all_q_rad: tuple[float, ...],
) -> dict[str, float]:
    names = LEFT_ARM_JOINT_NAMES + RIGHT_ARM_JOINT_NAMES
    return {
        name: math.degrees(
            abs(
                float(frame.motor_q_rad[index])
                - float(measured_all_q_rad[index])
            )
        )
        for name, index in zip(names, DUAL_ARM_INDICES)
    }


def full_authority_ready(
    current_weight: float,
    maximum_weight: float,
    maximum_target_error_rad: float,
    tolerance_rad: float,
) -> bool:
    return (
        math.isclose(current_weight, maximum_weight, abs_tol=1.0e-9)
        and maximum_target_error_rad <= tolerance_rad
    )


def create_joint_tracking_stats(
    controller: ArmJointJogController,
    measured_joint_rad: float,
) -> dict[str, float | int]:
    start_deg = math.degrees(controller.start_joint_rad)
    measured_deg = math.degrees(measured_joint_rad)
    return {
        "start_deg": start_deg,
        "requested_min_deg": start_deg,
        "requested_max_deg": start_deg,
        "commanded_min_deg": start_deg,
        "commanded_max_deg": start_deg,
        "measured_min_deg": measured_deg,
        "measured_max_deg": measured_deg,
        "maximum_command_measurement_error_deg": 0.0,
        "accepted_step_inputs": 0,
        "blocked_step_inputs": 0,
    }


def update_joint_tracking_stats(
    stats: dict[str, float | int],
    tick: Any,
) -> None:
    requested_deg = math.degrees(tick.requested_joint_rad)
    commanded_deg = math.degrees(tick.commanded_joint_rad)
    measured_deg = math.degrees(tick.measured_joint_rad)
    for prefix, value in (
        ("requested", requested_deg),
        ("commanded", commanded_deg),
        ("measured", measured_deg),
    ):
        minimum_key = f"{prefix}_min_deg"
        maximum_key = f"{prefix}_max_deg"
        stats[minimum_key] = min(float(stats[minimum_key]), value)
        stats[maximum_key] = max(float(stats[maximum_key]), value)
    stats["maximum_command_measurement_error_deg"] = max(
        float(stats["maximum_command_measurement_error_deg"]),
        abs(commanded_deg - measured_deg),
    )


def finalize_joint_tracking_stats(
    stats: dict[str, float | int],
) -> dict[str, float | int]:
    result = dict(stats)
    start_deg = float(stats["start_deg"])
    for prefix in ("requested", "commanded", "measured"):
        result[f"maximum_{prefix}_excursion_deg"] = max(
            abs(float(stats[f"{prefix}_min_deg"]) - start_deg),
            abs(float(stats[f"{prefix}_max_deg"]) - start_deg),
        )
    return result


def collect_settled_snapshot(
    buffer: LowStateBuffer,
    config: RuntimeConfig,
) -> tuple[Any, int, float]:
    deadline = time.monotonic() + config.settle_duration_s
    latest = None
    last_sequence = -1
    samples = 0
    maximum_velocity = 0.0
    while time.monotonic() < deadline:
        snapshot = buffer.snapshot()
        if snapshot is None or snapshot.sequence == last_sequence:
            time.sleep(0.001)
            continue
        latest = snapshot
        last_sequence = snapshot.sequence
        samples += 1
        maximum_velocity = max(
            maximum_velocity,
            max(abs(snapshot.all_dq_rad_s[index]) for index in range(15, 29)),
        )
    if latest is None or samples < config.minimum_settle_samples:
        raise RuntimeError(
            f"LowState settle samples {samples} < {config.minimum_settle_samples}"
        )
    if maximum_velocity > config.maximum_initial_arm_velocity_rad_s:
        raise RuntimeError(
            "initial arm velocity too high: "
            f"{math.degrees(maximum_velocity):.2f} deg/s"
        )
    return latest, samples, maximum_velocity


def result_path() -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return RESULT_DIRECTORY / f"g1_right_arm_jog_{timestamp}.json"


def write_result(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded G1 right-arm Arm SDK jog")
    parser.add_argument("network_interface", nargs="?", default="")
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--precheck-json", type=Path, default=DEFAULT_PRECHECK_PATH)
    parser.add_argument(
        "--path-permit-json",
        type=Path,
        default=DEFAULT_PATH_PERMIT_PATH,
    )
    parser.add_argument("--startup-timeout", type=float, default=5.0)
    parser.add_argument("--enable-hardware-output", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--confirm-grounded-regular", default="")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = result_path()
    result: dict[str, Any] = {
        "schema": "g1.right_arm_jog.result.v1",
        "passed": False,
        "network_interface": args.network_interface,
        "dds_lowstate_topic": LOWSTATE_TOPIC,
        "dds_command_topic": ARM_SDK_TOPIC,
        "publisher_created": False,
        "command_output_enabled": False,
        "published_frames": 0,
        "release_zero_frames": 0,
    }
    config: RuntimeConfig | None = None
    publisher = None
    command_message = None
    command_crc = None
    buffer = None
    snapshot = None
    last_snapshot = None
    last_successful_weight = 0.0
    release_evidence: ReleaseEvidence | None = None
    controller: ArmJointJogController | None = None
    pending_joint: str | None = None
    returning_for_switch = False
    last_tick = None
    tracking_stats: dict[str, dict[str, float | int]] = {}
    latest_arming_errors_deg: dict[str, float] = {}
    maximum_arming_errors_deg: dict[str, float] = {}
    try:
        config = load_config(args.config)
        if args.validate_only:
            result.update(
                passed=True,
                mode="VALIDATE_ONLY",
                hardware_output_authorized=config.hardware_output_authorized,
            )
            write_result(output_path, result)
            print("[PASS] Right-arm jog configuration and bounds are valid.")
            print("DDS publisher: NONE")
            print("Robot command: NONE")
            print(f"Result saved to: {output_path.resolve()}")
            return 0

        validate_authorization(
            config,
            args.enable_hardware_output,
            args.confirm,
            args.confirm_grounded_regular,
        )
        precheck = validate_precheck(
            args.precheck_json,
            config.precheck_max_age_s,
        )
        path_permit = load_path_permit(
            args.path_permit_json,
            precheck,
            config,
        )
        if not args.network_interface:
            raise ValueError("network_interface is required for hardware output")

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

        ChannelFactoryInitialize(args.domain_id, args.network_interface)
        motion_client = MotionSwitcherClient()
        motion_client.SetTimeout(args.startup_timeout)
        motion_client.Init()
        mode_code, mode = motion_client.CheckMode()
        if mode_code != 0 or not isinstance(mode, dict):
            raise RuntimeError(f"MotionSwitcher CheckMode failed: {mode_code}")
        if (str(mode.get("form")), str(mode.get("name"))) != (
            config.expected_form,
            config.expected_name,
        ):
            raise RuntimeError(f"motion mode mismatch: {mode}")

        buffer = LowStateBuffer()
        subscriber = ChannelSubscriber(LOWSTATE_TOPIC, LowState_)
        subscriber.Init(buffer.callback, 10)
        _wait_for_first_snapshot(buffer, args.startup_timeout)
        snapshot, settle_samples, maximum_velocity = collect_settled_snapshot(
            buffer,
            config,
        )
        last_snapshot = snapshot
        if snapshot.mode_pr != config.expected_mode_pr:
            raise RuntimeError(f"mode_pr mismatch: {snapshot.mode_pr}")
        if snapshot.mode_machine != config.expected_mode_machine:
            raise RuntimeError(f"mode_machine mismatch: {snapshot.mode_machine}")
        precheck_pose_delta = validate_snapshot_matches_precheck(
            snapshot,
            precheck,
            config.maximum_precheck_pose_delta_rad,
        )

        result.update(
            trial_mode=config.trial_mode,
            allowed_joint_names=list(config.allowed_joint_names),
            selected_joint_history=[],
            permitted_offset_deg={
                name: [math.degrees(bounds[0]), math.degrees(bounds[1])]
                for name, bounds in path_permit.items()
            },
            settle_samples=settle_samples,
            maximum_initial_arm_velocity_deg_s=math.degrees(maximum_velocity),
            maximum_precheck_pose_delta_deg=math.degrees(precheck_pose_delta),
            maximum_offset_deg=math.degrees(config.jog.maximum_offset_rad),
            maximum_velocity_deg_s={
                "proximal": math.degrees(
                    config.proximal_joint_maximum_velocity_rad_s
                ),
                "wrist": math.degrees(
                    config.wrist_joint_maximum_velocity_rad_s
                ),
            },
            step_tracking_tolerance_deg=math.degrees(
                config.joint_step_tracking_tolerance_rad
            ),
            maximum_weight=config.maximum_weight,
            hold_unselected_start_pose=config.hold_unselected_start_pose,
            require_full_weight_before_jog=config.require_full_weight_before_jog,
            blocked_step_inputs=0,
        )

        stop_requested = threading.Event()

        def request_stop(_signal_number: int, _frame: Any) -> None:
            stop_requested.set()

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)

        precheck_q = tuple(
            float(value) for value in precheck["latest_all_joint_q_rad"]
        )

        def create_controller(current: Any, joint_name: str) -> ArmJointJogController:
            if joint_name not in config.allowed_joint_names:
                raise RuntimeError(f"{joint_name} is disabled by this trial config")
            validate_snapshot_matches_precheck(
                current,
                precheck,
                config.maximum_precheck_pose_delta_rad,
            )
            limits = permitted_limits(config, path_permit, joint_name)
            if (
                math.isclose(limits.minimum_offset_rad, 0.0, abs_tol=1.0e-12)
                and math.isclose(limits.maximum_offset_rad, 0.0, abs_tol=1.0e-12)
            ):
                raise RuntimeError(f"{joint_name} has no permitted Jog direction")
            baseline = list(current.all_q_rad)
            joint_index = 22 + RIGHT_ARM_JOINT_NAMES.index(joint_name)
            if not config.hold_unselected_start_pose:
                baseline[joint_index] = precheck_q[joint_index]
            return ArmJointJogController(
                baseline,
                joint_name,
                limits,
                hold_unselected_start_pose=config.hold_unselected_start_pose,
            )

        with KeyboardReader() as keyboard:
            publisher = ChannelPublisher(ARM_SDK_TOPIC, LowCmd_)
            publisher.Init()
            command_message = unitree_hg_msg_dds__LowCmd_()
            command_crc = CRC()
            result["publisher_created"] = True
            result["command_output_enabled"] = True

            print("G1 RIGHT ARM JOG -- PHYSICAL OUTPUT ACTIVE")
            for index, joint_name in enumerate(RIGHT_ARM_JOINT_NAMES, start=1):
                if joint_name not in config.allowed_joint_names:
                    print(f"  {index}: {joint_name} [DISABLED]")
                    continue
                bounds = path_permit[joint_name]
                print(
                    f"  {index}: {joint_name} "
                    f"[{math.degrees(bounds[0]):+.0f}, "
                    f"{math.degrees(bounds[1]):+.0f}] deg"
                )
            print("1-7: select joint / Up/Down: 1 deg / Q: release and stop")
            print("Keep the handheld remote ready for L2+B emergency stop.")
            period_s = 1.0 / config.publish_hz
            session_started_s = time.monotonic()
            authority_started_s: float | None = None
            control_started_s: float | None = None
            next_tick_s = session_started_s
            previous_tick_s = session_started_s
            last_report_s = session_started_s
            current_weight = 0.0
            release_reason = "maximum_duration"
            maximum_observed_error = 0.0

            while not stop_requested.is_set():
                now_s = time.monotonic()
                if now_s < next_tick_s:
                    time.sleep(min(next_tick_s - now_s, period_s))
                    continue
                next_tick_s += period_s
                dt_s = max(1e-6, now_s - previous_tick_s)
                previous_tick_s = now_s

                session_elapsed_s = now_s - session_started_s
                if (
                    authority_started_s is None
                    and session_elapsed_s >= config.joint_selection_timeout_s
                ):
                    release_reason = "joint_selection_timeout"
                    break
                if (
                    control_started_s is not None
                    and now_s - control_started_s >= config.maximum_active_duration_s
                ):
                    release_reason = "maximum_duration"
                    break
                if (
                    config.require_full_weight_before_jog
                    and authority_started_s is not None
                    and control_started_s is None
                    and now_s - authority_started_s >= config.arming_timeout_s
                ):
                    raise RuntimeError("full-authority arming did not settle in time")
                current = buffer.snapshot()
                if current is None:
                    raise RuntimeError("LowState disappeared")
                last_snapshot = current
                age_s = now_s - current.received_monotonic_s
                if age_s > config.hold.lowstate_timeout_s:
                    raise RuntimeError(f"LowState stale: {age_s:.3f}s")
                if current.mode_pr != config.expected_mode_pr:
                    raise RuntimeError(f"mode_pr changed: {current.mode_pr}")
                if current.mode_machine != config.expected_mode_machine:
                    raise RuntimeError(f"mode_machine changed: {current.mode_machine}")

                for action in keyboard.read_actions():
                    if action == "up":
                        if controller is None:
                            print("[IGNORED] Select a joint with 1-7 first.")
                            continue
                        if returning_for_switch:
                            print("[IGNORED] Waiting for the previous joint to return.")
                            continue
                        if (
                            config.require_full_weight_before_jog
                            and control_started_s is None
                        ):
                            print("[IGNORED] Full-authority arming is not complete.")
                            continue
                        candidate, tracking_error = step_candidate_tracking_error(
                            controller,
                            current.all_q_rad,
                            1,
                        )
                        if tracking_error > config.joint_step_tracking_tolerance_rad:
                            result["blocked_step_inputs"] += 1
                            tracking_stats[controller.joint_name][
                                "blocked_step_inputs"
                            ] += 1
                            print(
                                f"[INPUT BLOCKED] {controller.joint_name} "
                                f"target would lead measured by "
                                f"{math.degrees(tracking_error):.2f} deg; "
                                "wait for tracking"
                            )
                            continue
                        target = controller.request_step(1)
                        tracking_stats[controller.joint_name][
                            "accepted_step_inputs"
                        ] += 1
                        print(
                            f"[UP] requested {controller.joint_name}="
                            f"{math.degrees(target):+.2f} deg"
                        )
                    elif action == "down":
                        if controller is None:
                            print("[IGNORED] Select a joint with 1-7 first.")
                            continue
                        if returning_for_switch:
                            print("[IGNORED] Waiting for the previous joint to return.")
                            continue
                        if (
                            config.require_full_weight_before_jog
                            and control_started_s is None
                        ):
                            print("[IGNORED] Full-authority arming is not complete.")
                            continue
                        candidate, tracking_error = step_candidate_tracking_error(
                            controller,
                            current.all_q_rad,
                            -1,
                        )
                        if tracking_error > config.joint_step_tracking_tolerance_rad:
                            result["blocked_step_inputs"] += 1
                            tracking_stats[controller.joint_name][
                                "blocked_step_inputs"
                            ] += 1
                            print(
                                f"[INPUT BLOCKED] {controller.joint_name} "
                                f"target would lead measured by "
                                f"{math.degrees(tracking_error):.2f} deg; "
                                "wait for tracking"
                            )
                            continue
                        target = controller.request_step(-1)
                        tracking_stats[controller.joint_name][
                            "accepted_step_inputs"
                        ] += 1
                        print(
                            f"[DOWN] requested {controller.joint_name}="
                            f"{math.degrees(target):+.2f} deg"
                        )
                    elif action == "help":
                        print("1-7: select, Up/Down: jog, Q: release and stop")
                    elif action == "quit":
                        release_reason = "operator_q"
                        stop_requested.set()
                    elif action.startswith("select_"):
                        selected_index = int(action.removeprefix("select_")) - 1
                        selected_name = RIGHT_ARM_JOINT_NAMES[selected_index]
                        result["last_selection_attempt"] = selected_name
                        if selected_name not in config.allowed_joint_names:
                            print(f"[IGNORED] {selected_name} is disabled for this trial.")
                            continue
                        if controller is None:
                            controller = create_controller(current, selected_name)
                            tracking_stats.setdefault(
                                selected_name,
                                create_joint_tracking_stats(
                                    controller,
                                    current.all_q_rad[controller.joint_index],
                                ),
                            )
                            authority_started_s = now_s
                            if not config.require_full_weight_before_jog:
                                control_started_s = now_s
                            result["selected_joint_history"].append(selected_name)
                            print(
                                f"[SELECTED] {selected_name}; "
                                "Arm SDK weight ramp starts now"
                            )
                        elif controller.joint_name == selected_name:
                            print(f"[SELECTED] {selected_name} is already active")
                        else:
                            pending_joint = selected_name
                            returning_for_switch = True
                            controller.request_home()
                            print(
                                f"[SWITCH] Returning {controller.joint_name} "
                                f"before selecting {selected_name}"
                            )

                if stop_requested.is_set():
                    break

                current_weight = calculate_active_weight(
                    authority_started_s,
                    now_s,
                    config.maximum_weight,
                    config.ramp_up_s,
                )
                tick = None
                if controller is None:
                    frame = build_measured_hold_frame(
                        current.all_q_rad,
                        dual_arm_from_all_joints(current.all_q_rad),
                        mode_pr=current.mode_pr,
                        mode_machine=current.mode_machine,
                        weight=current_weight,
                        config=config.hold,
                    )
                else:
                    tick = controller.advance(
                        current.all_q_rad,
                        dt_s,
                        mode_pr=current.mode_pr,
                        mode_machine=current.mode_machine,
                        weight=current_weight,
                        hold_config=config.hold,
                    )
                    last_tick = tick
                    update_joint_tracking_stats(
                        tracking_stats[tick.joint_name],
                        tick,
                    )
                    frame = tick.frame
                arming_error = maximum_dual_arm_target_error(
                    frame,
                    current.all_q_rad,
                )
                if (
                    config.require_full_weight_before_jog
                    and authority_started_s is not None
                    and control_started_s is None
                ):
                    latest_arming_errors_deg = dual_arm_target_errors_deg(
                        frame,
                        current.all_q_rad,
                    )
                    for joint_name, error_deg in latest_arming_errors_deg.items():
                        maximum_arming_errors_deg[joint_name] = max(
                            maximum_arming_errors_deg.get(joint_name, 0.0),
                            error_deg,
                        )
                if (
                    config.require_full_weight_before_jog
                    and authority_started_s is not None
                    and control_started_s is None
                    and full_authority_ready(
                        current_weight,
                        config.maximum_weight,
                        arming_error,
                        config.arming_tracking_tolerance_rad,
                    )
                ):
                    control_started_s = now_s
                    result["arming_completed_s"] = now_s - authority_started_s
                    result["arming_maximum_error_deg"] = math.degrees(arming_error)
                    print(
                        "[ARMED] Full Arm SDK authority is stable; "
                        "Up/Down input is now enabled."
                    )
                _apply_frame(command_message, frame)
                command_message.crc = command_crc.Crc(command_message)
                publisher.Write(command_message)
                result["published_frames"] += 1
                last_successful_weight = float(current_weight)
                if tick is not None:
                    maximum_observed_error = max(
                        maximum_observed_error,
                        abs(tick.commanded_joint_rad - tick.measured_joint_rad),
                    )
                    if returning_for_switch:
                        command_home_error = abs(
                            tick.commanded_joint_rad - controller.start_joint_rad
                        )
                        measured_home_error = abs(
                            tick.measured_joint_rad - controller.start_joint_rad
                        )
                        if (
                            command_home_error
                            <= config.joint_switch_return_tolerance_rad
                            and measured_home_error
                            <= config.joint_switch_return_tolerance_rad
                        ):
                            if pending_joint is None:
                                raise RuntimeError("joint switch target disappeared")
                            controller = create_controller(current, pending_joint)
                            tracking_stats.setdefault(
                                pending_joint,
                                create_joint_tracking_stats(
                                    controller,
                                    current.all_q_rad[controller.joint_index],
                                ),
                            )
                            result["selected_joint_history"].append(pending_joint)
                            print(f"[SELECTED] {pending_joint}")
                            pending_joint = None
                            returning_for_switch = False
                if now_s - last_report_s >= 0.25:
                    if tick is None:
                        print(
                            f"[WAITING] select=1-7 weight={current_weight:.3f} "
                            f"age={age_s * 1000.0:.1f}ms"
                        )
                    else:
                        if (
                            config.require_full_weight_before_jog
                            and control_started_s is None
                        ):
                            phase = "ARMING"
                        else:
                            phase = "RETURNING" if returning_for_switch else "ACTIVE"
                        print(
                            f"[{phase}] {tick.joint_name} "
                            f"measured={math.degrees(tick.measured_joint_rad):+.2f} "
                            f"command={math.degrees(tick.commanded_joint_rad):+.2f} "
                            f"requested={math.degrees(tick.requested_joint_rad):+.2f} "
                            f"weight={current_weight:.3f} "
                            f"arm_error={math.degrees(arming_error):.2f}deg "
                            f"age={age_s * 1000.0:.1f}ms"
                        )
                    last_report_s = now_s

            print(f"[RELEASE] reason={release_reason}")

            def build_release_frame(weight: float):
                nonlocal last_snapshot
                current = buffer.snapshot() or last_snapshot or snapshot
                if current is None:
                    raise RuntimeError("no measured LowState is available for release")
                last_snapshot = current
                return build_measured_hold_frame(
                    current.all_q_rad,
                    dual_arm_from_all_joints(current.all_q_rad),
                    mode_pr=current.mode_pr,
                    mode_machine=current.mode_machine,
                    weight=weight,
                    config=config.hold,
                )

            def publish_release_frame(frame) -> None:
                _apply_frame(command_message, frame)
                command_message.crc = command_crc.Crc(command_message)
                publisher.Write(command_message)
                result["published_frames"] += 1

            release_evidence = execute_release_sequence(
                start_weight=last_successful_weight,
                ramp_s=config.ramp_down_s,
                zero_cycles=config.release_zero_cycles,
                publish_hz=config.publish_hz,
                build_ramp_frame=build_release_frame,
                build_zero_frame=lambda: build_release_frame(0.0),
                publish_frame=publish_release_frame,
            )
            result.update(release_evidence.as_dict())
            result["release_zero_frames"] = release_evidence.release_zero_frames_sent
            release_ok = bool(
                release_evidence.zero_release_completed
                and release_evidence.release_fault is None
            )
            final = buffer.snapshot() or last_snapshot or snapshot
            result.update(
                passed=release_ok,
                command_output_enabled=release_evidence.output_state_unknown,
                release_reason=release_reason,
                final_right_arm_deg=(
                    []
                    if final is None
                    else [
                        math.degrees(final.all_q_rad[index])
                        for index in range(22, 29)
                    ]
                ),
                maximum_command_measurement_error_deg=math.degrees(
                    maximum_observed_error
                ),
            )
            if release_ok:
                print("[PASS] Right-arm jog ended with a verified zero-weight tail.")
            else:
                print("[FAULT] Right-arm jog release evidence is incomplete or faulted.")

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["passed"] = False
        if controller is not None:
            result["active_joint_at_fault"] = controller.joint_name
            result["pending_joint_at_fault"] = pending_joint
            result["returning_for_switch_at_fault"] = returning_for_switch
            result["requested_joint_deg_at_fault"] = math.degrees(
                controller.requested_joint_rad
            )
            result["commanded_joint_deg_at_fault"] = math.degrees(
                controller.commanded_joint_rad
            )
        if last_tick is not None:
            result["measured_joint_deg_at_fault"] = math.degrees(
                last_tick.measured_joint_rad
            )
        print(f"[FAULT] {result['error']}")
        print("[ACTION] Use the handheld remote emergency stop if any motion remains.")
        print("[ACTION] Do not retry until LowState, mode and precheck are valid.")
    finally:
        if tracking_stats:
            result["joint_tracking_summary"] = {
                joint_name: finalize_joint_tracking_stats(stats)
                for joint_name, stats in tracking_stats.items()
            }
        if latest_arming_errors_deg:
            result["latest_arming_joint_error_deg"] = latest_arming_errors_deg
            result["maximum_arming_joint_error_deg"] = maximum_arming_errors_deg
        if (
            release_evidence is None
            and publisher is not None
            and command_message is not None
            and command_crc is not None
            and last_snapshot is not None
            and config is not None
        ):
            result["emergency_zero_release_attempted"] = True

            def build_fault_release_frame(weight: float):
                nonlocal last_snapshot
                current = buffer.snapshot() if buffer is not None else None
                current = current or last_snapshot
                if current is None:
                    raise RuntimeError("no measured LowState is available for fault release")
                last_snapshot = current
                return build_measured_hold_frame(
                    current.all_q_rad,
                    dual_arm_from_all_joints(current.all_q_rad),
                    mode_pr=current.mode_pr,
                    mode_machine=current.mode_machine,
                    weight=weight,
                    config=config.hold,
                )

            def publish_fault_release_frame(frame) -> None:
                _apply_frame(command_message, frame)
                command_message.crc = command_crc.Crc(command_message)
                publisher.Write(command_message)
                result["published_frames"] += 1

            try:
                release_evidence = execute_release_sequence(
                    start_weight=last_successful_weight,
                    ramp_s=config.ramp_down_s,
                    zero_cycles=config.release_zero_cycles,
                    publish_hz=config.publish_hz,
                    build_ramp_frame=build_fault_release_frame,
                    build_zero_frame=lambda: build_fault_release_frame(0.0),
                    publish_frame=publish_fault_release_frame,
                )
            except Exception as release_exc:
                result["emergency_zero_release_error"] = (
                    f"{type(release_exc).__name__}: {release_exc}"
                )

        if release_evidence is not None:
            result.update(release_evidence.as_dict())
            result["release_zero_frames"] = release_evidence.release_zero_frames_sent
            result["command_output_enabled"] = release_evidence.output_state_unknown
            if release_evidence.release_fault is not None:
                result["passed"] = False
            if not release_evidence.zero_release_completed:
                result["passed"] = False
        elif publisher is not None:
            result["output_state_unknown"] = True
            result["command_output_enabled"] = True
            result["passed"] = False
        else:
            result.setdefault("output_state_unknown", False)
            result["command_output_enabled"] = False

        write_result(output_path, result)
        print(f"Result saved to: {output_path.resolve()}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
