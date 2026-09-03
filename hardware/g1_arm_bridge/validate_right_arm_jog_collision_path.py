#!/usr/bin/env python3
"""Build a pose-bound MuJoCo permit for interactive right-arm joint Jog."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, Final

from arm_sdk_hold_contract import RIGHT_ARM_JOINT_NAMES, dual_arm_from_all_joints
from arm_sdk_teleop_contract import MinimumJerkTrajectory
from g1_joint_contract import G1_29_JOINT_NAMES
from g1_right_arm_jog import DEFAULT_CONFIG_PATH, load_config
from gate7_mink_arm_sdk_offline import CollisionPathValidator
from right_arm_jog_contract import ArmJointJogController


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_PRECHECK_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_startup_precheck.json"
)
DEFAULT_OUTPUT_PATH: Final[Path] = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_right_arm_jog_path_permit.json"
)


def load_precheck(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "g1.startup_precheck.result.v1":
        raise ValueError("startup precheck schema mismatch")
    if payload.get("decision") != "DIRECT_TELEOP_READY":
        raise ValueError("startup precheck did not allow direct teleoperation")
    names = tuple(payload.get("latest_all_joint_names", []))
    if names != G1_29_JOINT_NAMES:
        raise ValueError("startup precheck does not contain canonical joint names")
    values = tuple(float(value) for value in payload.get("latest_all_joint_q_rad", []))
    if len(values) != len(G1_29_JOINT_NAMES):
        raise ValueError("startup precheck does not contain 29 joint positions")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("startup precheck pose contains a non-finite value")
    return payload


def measured_pose(payload: dict[str, Any]) -> tuple[float, ...]:
    return tuple(float(value) for value in payload["latest_all_joint_q_rad"])


def build_offset_trajectory(
    measured_all_q_rad: tuple[float, ...],
    config,
    joint_name: str,
    offset_rad: float,
) -> MinimumJerkTrajectory:
    controller = ArmJointJogController(measured_all_q_rad, joint_name, config.jog)
    endpoint = controller.start_joint_rad + offset_rad
    if endpoint < controller.minimum_joint_rad - 1.0e-12:
        raise ValueError(f"{joint_name} offset is below its safe joint range")
    if endpoint > controller.maximum_joint_rad + 1.0e-12:
        raise ValueError(f"{joint_name} offset is above its safe joint range")
    start_dual = dual_arm_from_all_joints(measured_all_q_rad)
    goal = list(start_dual)
    goal[controller.dual_index] = endpoint
    duration = max(1.0, abs(offset_rad) / config.jog.maximum_velocity_rad_s)
    return MinimumJerkTrajectory(
        tuple(start_dual),
        tuple(goal),
        duration,
        100.0,
    )


def build_endpoint_trajectories(
    measured_all_q_rad: tuple[float, ...],
    config,
    joint_name: str,
) -> tuple[tuple[str, MinimumJerkTrajectory], ...]:
    controller = ArmJointJogController(measured_all_q_rad, joint_name, config.jog)
    return (
        (
            "minimum",
            build_offset_trajectory(
                measured_all_q_rad,
                config,
                joint_name,
                controller.minimum_joint_rad - controller.start_joint_rad,
            ),
        ),
        (
            "maximum",
            build_offset_trajectory(
                measured_all_q_rad,
                config,
                joint_name,
                controller.maximum_joint_rad - controller.start_joint_rad,
            ),
        ),
    )


def validate_offset_path(
    measured_all_q_rad: tuple[float, ...],
    config,
    joint_name: str,
    offset_rad: float,
    validator: CollisionPathValidator | None = None,
) -> dict[str, Any]:
    trajectory = build_offset_trajectory(
        measured_all_q_rad,
        config,
        joint_name,
        offset_rad,
    )
    active_validator = validator or CollisionPathValidator()
    allowed, reason = active_validator(trajectory, measured_all_q_rad)
    return {
        "offset_deg": math.degrees(offset_rad),
        "allowed": allowed,
        "reason": reason,
        "minimum_clearance_m": active_validator.minimum_distance_m,
        "nearest_collision_geoms": active_validator.nearest_geoms,
        "sample_count": active_validator.sample_count,
    }


def find_direction_limit(
    measured_all_q_rad: tuple[float, ...],
    config,
    joint_name: str,
    direction: int,
    validator: CollisionPathValidator | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    controller = ArmJointJogController(measured_all_q_rad, joint_name, config.jog)
    available_rad = (
        controller.maximum_joint_rad - controller.start_joint_rad
        if direction > 0
        else controller.start_joint_rad - controller.minimum_joint_rad
    )
    step_rad = config.jog.step_rad
    maximum_steps = int(math.floor((available_rad + 1.0e-12) / step_rad))
    permitted_steps = 0
    probes: list[dict[str, Any]] = []
    active_validator = validator or CollisionPathValidator()
    for step in range(1, maximum_steps + 1):
        probe = validate_offset_path(
            measured_all_q_rad,
            config,
            joint_name,
            direction * step * step_rad,
            active_validator,
        )
        probes.append(probe)
        if not probe["allowed"]:
            break
        permitted_steps = step
    return direction * permitted_steps * step_rad, probes


def build_joint_permit(
    measured_all_q_rad: tuple[float, ...],
    config,
    joint_name: str,
    validator: CollisionPathValidator | None = None,
) -> dict[str, Any]:
    active_validator = validator or CollisionPathValidator()
    minimum_offset, minimum_probes = find_direction_limit(
        measured_all_q_rad,
        config,
        joint_name,
        -1,
        active_validator,
    )
    maximum_offset, maximum_probes = find_direction_limit(
        measured_all_q_rad,
        config,
        joint_name,
        1,
        active_validator,
    )
    available = minimum_offset < 0.0 or maximum_offset > 0.0
    return {
        "available": available,
        "minimum_offset_deg": math.degrees(minimum_offset),
        "maximum_offset_deg": math.degrees(maximum_offset),
        "negative_direction_probes": minimum_probes,
        "positive_direction_probes": maximum_probes,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build G1 right-arm Jog permit")
    parser.add_argument("--precheck-json", type=Path, default=DEFAULT_PRECHECK_PATH)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--joint", choices=RIGHT_ARM_JOINT_NAMES, action="append")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result: dict[str, Any] = {
        "schema": "g1.right_arm_jog.path_permit.v2",
        "checked_at_unix_ns": time.time_ns(),
        "passed": False,
        "publisher_present": False,
        "command_output_enabled": False,
        "joints": {},
    }
    try:
        precheck = load_precheck(args.precheck_json)
        measured = measured_pose(precheck)
        config = load_config(args.config)
        selected = tuple(args.joint or config.allowed_joint_names)
        if any(name not in config.allowed_joint_names for name in selected):
            raise ValueError("requested joint is not enabled by this trial config")
        result.update(
            precheck_checked_at_unix_ns=int(precheck["checked_at_unix_ns"]),
            precheck_all_joint_q_rad=list(measured),
            maximum_offset_deg=math.degrees(config.jog.maximum_offset_rad),
            step_deg=math.degrees(config.jog.step_rad),
        )
        collision_validator = CollisionPathValidator()
        for joint_name in selected:
            permit = build_joint_permit(
                measured,
                config,
                joint_name,
                collision_validator,
            )
            result["joints"][joint_name] = permit
            print(
                f"[PERMIT] {joint_name}: "
                f"{permit['minimum_offset_deg']:+.0f} to "
                f"{permit['maximum_offset_deg']:+.0f} deg"
            )
        if not any(item["available"] for item in result["joints"].values()):
            raise RuntimeError("no right-arm joint has a collision-safe Jog range")
        result["passed"] = True
        print("[PASS] Pose-bound right-arm Jog permit created.")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(f"[BLOCKED] {result['error']}")
        print("[ACTION] Do not create the rt/arm_sdk publisher for this pose.")
    write_json(args.output, result)
    print(f"Result saved to: {args.output.resolve()}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
