#!/usr/bin/env python3
"""Supported WSL entrypoint for right-arm Jog safety guards.

The physical controller remains in ``g1_right_arm_jog.py``. This wrapper creates
no DDS entity itself. Before delegating to the controller it installs fail-closed
result semantics, permit provenance validation, all-29-joint precheck binding,
final swept-segment collision checks, and LowState IMU/motor supervision.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import g1_right_arm_jog as jog
from gate7_mink_arm_sdk_offline import CollisionPathValidator
from lowstate_health_guard import (
    install_lowstate_health_tracking,
    require_latest_lowstate_health,
)
from right_arm_jog_safety_guard import (
    validate_jog_final_segment,
    validate_jog_permit_provenance,
    validate_jog_runtime_full_body,
)


def _argument_path(argv: list[str], name: str, default: Path) -> Path:
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise ValueError(f"{name} requires a path")
            return Path(argv[index + 1])
        prefix = name + "="
        if value.startswith(prefix):
            return Path(value[len(prefix) :])
    return default


def _config_path(argv: list[str]) -> Path:
    return _argument_path(argv, "--config", jog.DEFAULT_CONFIG_PATH)


def apply_release_result_guard(
    payload: dict[str, Any],
    *,
    release_zero_cycles: int,
) -> dict[str, Any]:
    """Fail closed when a publisher existed but the zero tail is incomplete."""

    if not isinstance(release_zero_cycles, int) or isinstance(release_zero_cycles, bool):
        raise ValueError("release_zero_cycles must be an integer")
    if release_zero_cycles < 1:
        raise ValueError("release_zero_cycles must be positive")

    publisher_created = payload.get("publisher_created") is True
    try:
        zero_sent = int(payload.get("release_zero_frames", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("release_zero_frames must be an integer") from exc
    zero_sent = max(0, zero_sent)

    existing_release_error = payload.get("emergency_zero_release_error")
    if existing_release_error is None:
        existing_release_error = payload.get("release_fault")
    release_error = None if existing_release_error in (None, "") else str(existing_release_error)

    release_attempted = publisher_created
    zero_completed = bool(
        publisher_created
        and zero_sent >= release_zero_cycles
        and release_error is None
    )
    output_state_unknown = bool(publisher_created and not zero_completed)

    if publisher_created and not zero_completed and release_error is None:
        release_error = (
            "zero_tail_incomplete: "
            f"{zero_sent}/{release_zero_cycles} zero-weight frames"
        )

    payload["release_attempted"] = release_attempted
    payload["release_ramp_completed"] = bool(
        publisher_created and payload.get("passed") is True and zero_completed
    )
    payload["release_zero_frames_requested"] = (
        release_zero_cycles if publisher_created else 0
    )
    payload["release_zero_frames_sent"] = zero_sent
    payload["zero_release_completed"] = zero_completed
    payload["last_successful_weight"] = 0.0 if zero_completed else None
    payload.setdefault("last_successful_write_unix_ns", None)
    payload["release_fault"] = release_error
    payload["output_state_unknown"] = output_state_unknown
    payload["external_authority_handoff_confirmed"] = False

    if output_state_unknown:
        payload["command_output_enabled"] = True
        payload["passed"] = False
        payload.setdefault(
            "error",
            "release result is incomplete; Arm SDK output state is unknown",
        )
    elif publisher_created:
        payload["command_output_enabled"] = False

    return payload


def install_jog_safety_guards(
    *,
    config,
    config_path: Path,
    collision_validator,
) -> None:
    if getattr(jog, "_supported_jog_entry_guards_installed", False):
        return

    install_lowstate_health_tracking(jog.LowStateBuffer)
    state: dict[str, Any] = {"precheck": None}

    original_validate_precheck = jog.validate_precheck

    def guarded_validate_precheck(path, maximum_age_s):
        precheck = original_validate_precheck(path, maximum_age_s)
        state["precheck"] = precheck
        return precheck

    jog.validate_precheck = guarded_validate_precheck

    original_snapshot_match = jog.validate_snapshot_matches_precheck

    def guarded_snapshot_match(snapshot, precheck, maximum_delta_rad):
        require_latest_lowstate_health(jog.LowStateBuffer)
        original_snapshot_match(snapshot, precheck, maximum_delta_rad)
        return validate_jog_runtime_full_body(
            snapshot.all_q_rad,
            precheck,
            maximum_delta_rad,
        )

    jog.validate_snapshot_matches_precheck = guarded_snapshot_match

    original_load_path_permit = jog.load_path_permit

    def guarded_load_path_permit(path, precheck, config_value):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_jog_permit_provenance(payload, config_path)
        return original_load_path_permit(path, precheck, config_value)

    jog.load_path_permit = guarded_load_path_permit

    original_advance = jog.ArmJointJogController.advance

    def guarded_advance(
        self,
        measured_all_q_rad,
        dt_s,
        *,
        mode_pr,
        mode_machine,
        weight,
        hold_config,
    ):
        require_latest_lowstate_health(jog.LowStateBuffer)
        precheck = state.get("precheck")
        if precheck is None:
            raise RuntimeError("startup precheck is unavailable during Jog control")
        validate_jog_runtime_full_body(
            measured_all_q_rad,
            precheck,
            config.maximum_precheck_pose_delta_rad,
        )
        tick = original_advance(
            self,
            measured_all_q_rad,
            dt_s,
            mode_pr=mode_pr,
            mode_machine=mode_machine,
            weight=weight,
            hold_config=hold_config,
        )
        validate_jog_final_segment(
            tick.frame,
            measured_all_q_rad,
            collision_validator,
        )
        return tick

    jog.ArmJointJogController.advance = guarded_advance
    jog._supported_jog_entry_guards_installed = True


def main() -> int:
    argv = sys.argv[1:]
    config_path = _config_path(argv)
    config = jog.load_config(config_path)

    collision_validator = CollisionPathValidator()
    install_jog_safety_guards(
        config=config,
        config_path=config_path,
        collision_validator=collision_validator,
    )

    original_write_result = jog.write_result

    def guarded_write_result(path: Path, payload: dict[str, Any]) -> None:
        apply_release_result_guard(
            payload,
            release_zero_cycles=config.release_zero_cycles,
        )
        original_write_result(path, payload)

    jog.write_result = guarded_write_result
    return jog.main()


if __name__ == "__main__":
    raise SystemExit(main())
