#!/usr/bin/env python3
"""SDK-neutral provenance and full-body helpers for right-arm Jog (R42)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from gate7_acquisition_guard import validate_full_body_snapshot_matches_precheck
from gate7_live_safety_guard import validate_final_command_segment


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_SCHEMA = "g1.right_arm_jog.path_permit.provenance.v1"
CRITICAL_SOURCES = {
    "model_controller": PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts" / "run_mink_g1_right_arm_prototype.py",
    "model_common": PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts" / "g1_right_arm_common.py",
    "permit_generator": PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "validate_right_arm_jog_collision_path.py",
    "collision_validator": PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "gate7_mink_arm_sdk_offline.py",
    "jog_controller": PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "g1_right_arm_jog.py",
}


def file_sha256(path: Path) -> str:
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_jog_permit_provenance(config_path: Path, model_metadata=None) -> dict[str, Any]:
    """Build the exact code/config/model identity used by a Jog permit."""

    model_hash = model_metadata.get("model_xml_sha256") if isinstance(model_metadata, dict) else None
    if (not isinstance(model_hash, str) or len(model_hash) != 64
            or any(c not in "0123456789abcdef" for c in model_hash)):
        raise ValueError("Jog permit requires the collision validator model hash")
    return {
        "schema": PROVENANCE_SCHEMA,
        "config_sha256": file_sha256(Path(config_path)),
        "generated_model_sha256": model_hash,
        "model_binding": "collision_validator_loaded_xml",
        "source_sha256": {
            name: file_sha256(path) for name, path in CRITICAL_SOURCES.items()
        },
    }


def validate_jog_permit_provenance(
    permit_payload: dict[str, Any],
    config_path: Path,
    model_metadata=None,
) -> None:
    actual = permit_payload.get("provenance")
    if not isinstance(actual, dict) or actual.get("schema") != PROVENANCE_SCHEMA:
        raise ValueError("Jog path permit is missing supported provenance")
    expected = build_jog_permit_provenance(config_path, model_metadata)
    if actual != expected:
        raise ValueError("Jog path permit provenance does not match current code/config/model")


def validate_jog_runtime_full_body(
    measured_all_q_rad,
    precheck: dict[str, Any],
    maximum_delta_rad: float,
) -> float:
    snapshot = type("JogRuntimeSnapshot", (), {"all_q_rad": tuple(measured_all_q_rad)})()
    return validate_full_body_snapshot_matches_precheck(
        snapshot,
        precheck,
        maximum_delta_rad,
    )


def validate_jog_final_segment(
    frame: Any,
    measured_all_q_rad,
    collision_validator,
) -> None:
    allowed, reason = validate_final_command_segment(
        frame,
        measured_all_q_rad,
        collision_validator,
    )
    if not allowed:
        raise RuntimeError("Jog final command collision rejected: " + reason)
