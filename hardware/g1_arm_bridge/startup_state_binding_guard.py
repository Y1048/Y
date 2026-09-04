#!/usr/bin/env python3
"""SDK-neutral startup state/model binding for supported physical paths (R40)."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "g1.startup_precheck.state_binding.v1"
DEFAULT_STARTUP_CONFIG = PROJECT_ROOT / "config" / "g1_startup_precheck.json"
G1_MODEL = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "external"
    / "unitree_mujoco"
    / "unitree_robots"
    / "g1"
    / "g1_29dof.xml"
)
COLLISION_CONTROLLER = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "run_mink_g1_right_arm_prototype.py"
)
MODEL_COMMON = (
    PROJECT_ROOT
    / "MuJoCo_G1_Controller"
    / "scripts"
    / "g1_right_arm_common.py"
)


def file_sha256(path: Path) -> str:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_state_binding(config_path: Path = DEFAULT_STARTUP_CONFIG) -> dict[str, Any]:
    """Return the exact static collision/precheck identity used by this checkout."""

    return {
        "schema": SCHEMA,
        "startup_config_sha256": file_sha256(Path(config_path)),
        "g1_model_sha256": file_sha256(G1_MODEL),
        "collision_controller_sha256": file_sha256(COLLISION_CONTROLLER),
        "model_common_sha256": file_sha256(MODEL_COMMON),
    }


def base_state_to_dict(base_state: Any) -> dict[str, Any]:
    if base_state is None:
        raise ValueError("startup precheck requires a base_state sample")
    return {
        "valid": bool(base_state.valid),
        "topic": str(base_state.topic),
        "received_packets": int(base_state.received_packets),
        "invalid_packets": int(base_state.invalid_packets),
        "last_packet_age_s": base_state.last_packet_age_s,
        "position_m": list(base_state.position_m),
        "quaternion_xyzw": list(base_state.quaternion_xyzw),
        "velocity_mps": list(base_state.velocity_mps),
        "yaw_speed_rad_s": float(base_state.yaw_speed_rad_s),
    }


def require_state_binding(
    payload: dict[str, Any],
    config_path: Path = DEFAULT_STARTUP_CONFIG,
) -> dict[str, Any]:
    """Fail closed if precheck base/model evidence is absent or stale relative to code."""

    if not isinstance(payload, dict):
        raise ValueError("startup precheck must be an object")
    binding = payload.get("startup_state_binding")
    if not isinstance(binding, dict) or binding.get("schema") != SCHEMA:
        raise ValueError("startup precheck lacks supported state/model binding")
    expected = build_state_binding(config_path)
    if binding != expected:
        raise ValueError("startup precheck state/model binding does not match current checkout")

    base = payload.get("latest_base_state")
    if not isinstance(base, dict) or base.get("valid") is not True:
        raise ValueError("startup precheck lacks a valid base-state sample")
    age = base.get("last_packet_age_s")
    if not isinstance(age, (int, float)) or isinstance(age, bool) or not math.isfinite(float(age)) or float(age) < 0.0:
        raise ValueError("startup precheck base-state age is invalid")
    position = base.get("position_m")
    quaternion = base.get("quaternion_xyzw")
    velocity = base.get("velocity_mps")
    yaw_speed = base.get("yaw_speed_rad_s")
    vectors = ((position, 3, "position"), (quaternion, 4, "quaternion"), (velocity, 3, "velocity"))
    for value, length, label in vectors:
        if not isinstance(value, list) or len(value) != length:
            raise ValueError(f"startup precheck base-state {label} is invalid")
        if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)) for item in value):
            raise ValueError(f"startup precheck base-state {label} is non-finite")
    if not isinstance(yaw_speed, (int, float)) or isinstance(yaw_speed, bool) or not math.isfinite(float(yaw_speed)):
        raise ValueError("startup precheck base-state yaw speed is invalid")
    return payload
