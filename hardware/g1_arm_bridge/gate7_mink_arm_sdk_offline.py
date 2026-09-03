#!/usr/bin/env python3
"""Locked offline verification for Mink -> Arm SDK and Regular return.

The program creates no socket, imports no Unitree SDK, creates no DDS entity,
and sends no robot command.  It validates a synthetic active right-arm segment,
an intentional pinch event, a collision-checked dual-arm return to the captured
Regular pose, the 10-second safety-hold policy, and SDK-neutral 35-slot
command-frame construction.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Final

import mujoco

from arm_sdk_hold_contract import (
    DUAL_ARM_INDICES,
    ArmSdkHoldConfig,
    build_measured_hold_frame,
    validate_measured_hold,
)
from arm_sdk_teleop_contract import (
    Gate7Decision,
    Gate7TeleopController,
    MinimumJerkTrajectory,
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from g1_joint_contract import G1_29_JOINT_NAMES

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_CONFIG_PATH: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
)
DEFAULT_REGULAR_POSE_PATH: Final[Path] = (
    PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"
)


def _set_full_body_pose(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    all_q_rad: tuple[float, ...],
) -> None:
    data.qpos[:] = model.qpos0.copy()
    for name, value in zip(G1_29_JOINT_NAMES, all_q_rad):
        joint_name = name + "_joint"
        joint_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_JOINT, joint_name
        )
        if joint_id < 0:
            raise RuntimeError(f"MuJoCo joint missing: {joint_name}")
        qpos_id = int(model.jnt_qposadr[joint_id])
        data.qpos[qpos_id] = float(value)
    mujoco.mj_forward(model, data)


class CollisionPathValidator:
    """Validate the complete return path with the active Mink collision set."""

    def __init__(self) -> None:
        os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import run_mink_g1_right_arm_prototype as controller
        from diagnose_initial_pose_collision import _nearby_pairs

        controller._prepare_mink_xml()
        self.controller = controller
        self.nearby_pairs = _nearby_pairs
        self.model = mujoco.MjModel.from_xml_path(
            str(controller.g1.DEMO_XML)
        )
        controller._apply_operational_joint_limits(self.model)
        self.data = mujoco.MjData(self.model)
        dual_arm_bodies = (
            controller.g1.LEFT_ARM_BODY_NAMES
            | controller.g1.RIGHT_ARM_BODY_NAMES
        )
        _, self.geom_pairs = controller._build_collision_pairs(
            self.model,
            controlled_body_names=dual_arm_bodies,
        )
        self.minimum_distance_m = float("inf")
        self.nearest_geoms: tuple[str | None, str | None] | None = None
        self.sample_count = 0

    def __call__(
        self,
        trajectory: MinimumJerkTrajectory,
        measured_all_q_rad: tuple[float, ...],
    ) -> tuple[bool, str]:
        minimum_allowed = self.controller.COLLISION_MIN_DISTANCE_M
        self.minimum_distance_m = float("inf")
        self.nearest_geoms = None
        self.sample_count = 0

        for point in trajectory.discrete_samples():
            posture = list(measured_all_q_rad)
            for joint_index, value in zip(DUAL_ARM_INDICES, point.q_rad):
                posture[joint_index] = value
            _set_full_body_pose(self.model, self.data, tuple(posture))
            nearby = self.nearby_pairs(
                self.model,
                self.data,
                self.controller,
                self.geom_pairs,
            )
            nearest = None if not nearby else nearby[0]
            distance = (
                self.controller.COLLISION_DETECTION_DISTANCE_M
                if nearest is None
                else float(nearest["distance_m"])
            )
            if distance < self.minimum_distance_m:
                self.minimum_distance_m = distance
                self.nearest_geoms = (
                    None if nearest is None else str(nearest["first_geom"]),
                    None if nearest is None else str(nearest["second_geom"]),
                )
            self.sample_count += 1
            if distance < minimum_allowed:
                return (
                    False,
                    f"collision_clearance:{distance * 1000.0:.2f}mm",
                )
        return True, "collision_path_clear"


def _replace_dual_arm(
    all_q_rad: tuple[float, ...], dual_arm_q_rad: tuple[float, ...]
) -> tuple[float, ...]:
    values = list(all_q_rad)
    for index, value in zip(DUAL_ARM_INDICES, dual_arm_q_rad):
        values[index] = value
    return tuple(values)


def _mink_packet(
    *,
    sequence: int,
    session_id: str,
    input_mode: str,
    all_q_rad: tuple[float, ...],
    active: bool,
    workspace_limited: bool = False,
    collision_limited: bool = False,
) -> bytes:
    value = {
        "schema": "g1.mink.right_arm.state.v1",
        "sequence": sequence,
        "state_source": "mink_simulation",
        "all_joint_names": list(G1_29_JOINT_NAMES),
        "all_joint_q_rad": list(all_q_rad),
        "right_arm": {
            "joints": list(all_q_rad[22:29]),
            "active": active,
            "workspace_limited": workspace_limited,
            "collision_limited": collision_limited,
            "minimum_clearance_m": (
                0.011 if collision_limited else 0.040
            ),
            "command_state": "active" if active else "idle",
        },
        "input_command_mode": input_mode,
        "session_id": session_id,
        "input_packet_age_s": 0.0,
        "timestamp": time.time(),
    }
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _target_right_arm(
    regular_right_q_rad: tuple[float, ...], elapsed_s: float
) -> tuple[float, ...]:
    phase = min(max(elapsed_s, 0.0), 1.0)
    offsets_deg = (2.0, -1.0, 1.0, 2.0, 5.0, -3.0, 4.0)
    smooth = phase * phase * (3.0 - 2.0 * phase)
    return tuple(
        value + math.radians(offset) * smooth
        for value, offset in zip(regular_right_q_rad, offsets_deg)
    )


def _frame_is_arm_only(frame) -> bool:
    for index in range(29):
        if index in DUAL_ARM_INDICES:
            if frame.motor_mode[index] != 1:
                return False
        elif (
            frame.motor_mode[index] != 0
            or frame.motor_kp[index] != 0.0
            or frame.motor_kd[index] != 0.0
            or frame.motor_dq_rad_s[index] != 0.0
            or frame.motor_tau_nm[index] != 0.0
        ):
            return False
    return True


def run_offline_verification(
    config_path: Path,
    regular_pose_path: Path,
) -> dict[str, object]:
    config = load_gate7_config(config_path)
    regular_pose = load_regular_arm_pose(regular_pose_path)
    collision_validator = CollisionPathValidator()
    controller = Gate7TeleopController(
        regular_pose,
        config,
        return_path_validator=collision_validator,
    )

    measured_all = _replace_dual_arm(
        regular_pose.reference_all_joint_q_rad,
        regular_pose.dual_arm_q_rad,
    )
    regular_right = regular_pose.dual_arm_q_rad[7:]
    session_id = "offline-gate7-verification"
    sequence = 0
    decisions: list[Gate7Decision] = []
    arm_only_frames = 0
    maximum_step_rad = 0.0
    previous_target = tuple(measured_all[index] for index in DUAL_ARM_INDICES)
    hold_config = ArmSdkHoldConfig(
        maximum_target_error_rad=config.maximum_target_error_rad
    )

    def accept_decision(decision: Gate7Decision) -> None:
        nonlocal measured_all, arm_only_frames, maximum_step_rad, previous_target
        validation = validate_measured_hold(
            measured_all,
            decision.target_dual_arm_q_rad,
            0.0,
            hold_config,
        )
        if not validation.allowed:
            raise RuntimeError("Arm SDK candidate rejected: " + validation.reason)
        frame = build_measured_hold_frame(
            measured_all,
            decision.target_dual_arm_q_rad,
            mode_pr=0,
            mode_machine=5,
            weight=config.command_weight,
            config=hold_config,
        )
        if not _frame_is_arm_only(frame):
            raise RuntimeError("candidate frame affected a non-arm joint")
        arm_only_frames += 1
        maximum_step_rad = max(
            maximum_step_rad,
            max(
                abs(current - previous)
                for current, previous in zip(
                    decision.target_dual_arm_q_rad,
                    previous_target,
                )
            ),
        )
        previous_target = decision.target_dual_arm_q_rad
        measured_all = _replace_dual_arm(
            measured_all,
            decision.target_dual_arm_q_rad,
        )
        decisions.append(decision)

    # First packet establishes ownership.  Subsequent active packets track only
    # the right arm while the left arm remains at the measured Regular seed.
    first = parse_mink_arm_sample(
        _mink_packet(
            sequence=sequence,
            session_id=session_id,
            input_mode="active",
            all_q_rad=measured_all,
            active=True,
        )
    )
    accept_decision(controller.step(first, measured_all, 1.0 / 60.0))
    sequence += 1

    for frame_index in range(1, 61):
        elapsed_s = frame_index / 60.0
        mink_all = _replace_dual_arm(
            regular_pose.reference_all_joint_q_rad,
            regular_pose.dual_arm_q_rad[:7]
            + _target_right_arm(regular_right, elapsed_s),
        )
        sample = parse_mink_arm_sample(
            _mink_packet(
                sequence=sequence,
                session_id=session_id,
                input_mode="active",
                all_q_rad=mink_all,
                active=True,
            )
        )
        accept_decision(controller.step(sample, measured_all, 1.0 / 60.0))
        sequence += 1

    pinch_all = _replace_dual_arm(
        regular_pose.reference_all_joint_q_rad,
        tuple(measured_all[index] for index in DUAL_ARM_INDICES),
    )
    pinch_sample = parse_mink_arm_sample(
        _mink_packet(
            sequence=sequence,
            session_id=session_id,
            input_mode="pinch_disengaged",
            all_q_rad=pinch_all,
            active=False,
        )
    )
    accept_decision(controller.step(pinch_sample, measured_all, 1.0 / config.command_hz))
    sequence += 1

    command_ticks = 1
    state_packet_period_ticks = max(1, round(config.command_hz / 60.0))
    while controller.state == "REGULAR_RETURN":
        sample = None
        if command_ticks % state_packet_period_ticks == 0:
            sample = parse_mink_arm_sample(
                _mink_packet(
                    sequence=sequence,
                    session_id=session_id,
                    input_mode="pinch_disengaged",
                    all_q_rad=pinch_all,
                    active=False,
                )
            )
            sequence += 1
        decision = controller.step(
            sample,
            measured_all,
            1.0 / config.command_hz,
        )
        accept_decision(decision)
        command_ticks += 1
        if command_ticks > int(config.command_hz * 20.0):
            raise RuntimeError("Regular return did not complete within 20 seconds")

    final_dual = tuple(measured_all[index] for index in DUAL_ARM_INDICES)
    final_error = max(
        abs(value - target)
        for value, target in zip(final_dual, regular_pose.dual_arm_q_rad)
    )

    # 별도 컨트롤러로 의도치 않은 연동 해제의 10초 HOLD 정책을 검증한다.
    timeout_controller = Gate7TeleopController(
        regular_pose,
        config,
        return_path_validator=lambda _trajectory, _all_q: (
            True,
            "offline_timeout_policy_validated",
        ),
    )
    timeout_session = "offline-gate7-timeout-verification"
    timeout_controller.step(
        parse_mink_arm_sample(
            _mink_packet(
                sequence=0,
                session_id=timeout_session,
                input_mode="active",
                all_q_rad=measured_all,
                active=True,
            )
        ),
        measured_all,
        0.01,
    )
    timeout_controller.step(
        parse_mink_arm_sample(
            _mink_packet(
                sequence=1,
                session_id=timeout_session,
                input_mode="active",
                all_q_rad=measured_all,
                active=True,
            )
        ),
        measured_all,
        0.01,
    )
    timeout_hold = timeout_controller.step(
        parse_mink_arm_sample(
            _mink_packet(
                sequence=2,
                session_id=timeout_session,
                input_mode="tracking_disengaged",
                all_q_rad=measured_all,
                active=False,
            )
        ),
        measured_all,
        5.0,
    )
    timeout_return = timeout_controller.step(None, measured_all, 5.0)
    timeout_policy_passed = (
        timeout_hold.state == "SAFETY_HOLD"
        and timeout_return.state == "REGULAR_RETURN"
        and timeout_return.reason == "unintended_hold_timeout_return"
    )

    states = [decision.state for decision in decisions]
    passed = (
        "TRACK_MINK_RIGHT" in states
        and "REGULAR_RETURN" in states
        and controller.state == "REGULAR_HOLD"
        and timeout_policy_passed
        and final_error <= 1e-9
        and arm_only_frames == len(decisions)
        and not config.hardware_output_authorized
    )
    return {
        "schema": "g1.gate7.mink_arm_sdk.offline_result.v1",
        "passed": passed,
        "mode": "OFFLINE_ONLY",
        "unitree_sdk_imported": False,
        "dds_entity_created": False,
        "publisher_present": False,
        "command_output_enabled": False,
        "hardware_output_authorized": config.hardware_output_authorized,
        "mink_input_schema": "g1.mink.right_arm.state.v1",
        "regular_pose": {
            "name": regular_pose.name,
            "source": regular_pose.source,
            "captured_at": regular_pose.captured_at,
        },
        "state_counts": {
            state: states.count(state) for state in sorted(set(states))
        },
        "candidate_frame_count": arm_only_frames,
        "dynamic_joint_indices": list(DUAL_ARM_INDICES),
        "waist_or_leg_target_updated": False,
        "return": {
            "trigger": "pinch_immediate_or_unintended_hold_timeout_10s",
            "final_state": controller.state,
            "final_error_rad": final_error,
            "minimum_collision_clearance_m": collision_validator.minimum_distance_m,
            "nearest_collision_geoms": collision_validator.nearest_geoms,
            "collision_sample_count": collision_validator.sample_count,
        },
        "unintended_disengagement": {
            "hold_duration_s": config.unintended_hold_before_regular_return_s,
            "hold_state": timeout_hold.state,
            "timeout_state": timeout_return.state,
            "timeout_reason": timeout_return.reason,
            "passed": timeout_policy_passed,
        },
        "limits": {
            "proximal_max_velocity_deg_s": math.degrees(
                config.proximal_max_velocity_rad_s
            ),
            "wrist_max_velocity_deg_s": math.degrees(
                config.wrist_max_velocity_rad_s
            ),
            "maximum_discrete_step_deg": math.degrees(maximum_step_rad),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Locked offline Gate 7 Mink-to-Arm-SDK verification"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--regular-pose", type=Path, default=DEFAULT_REGULAR_POSE_PATH
    )
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()

    print("G1 Gate 7 Mink -> Arm SDK OFFLINE verification")
    print("------------------------------------------------")
    print("Unitree SDK: NONE")
    print("DDS entity: NONE")
    print("Robot command: NONE")
    try:
        result = run_offline_verification(args.config, args.regular_pose)
        exit_code = 0 if result["passed"] else 2
    except Exception as exc:
        result = {
            "schema": "g1.gate7.mink_arm_sdk.offline_result.v1",
            "passed": False,
            "mode": "OFFLINE_ONLY",
            "publisher_present": False,
            "command_output_enabled": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        exit_code = 3

    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if result["passed"]:
        print("[PASS] Pinch return and 10-second safety-hold fallback passed.")
        print("[PASS] Both arms reached the captured Regular posture offline.")
        print("[PASS] No Unitree SDK, DDS publisher, or robot command was used.")
    else:
        print("[FAIL] " + str(result.get("error", "offline contract rejected")))
        print("[ACTION] Keep Gate 7 locked and inspect the saved result before retrying.")
    print(f"Result saved to: {args.result_json.resolve()}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
