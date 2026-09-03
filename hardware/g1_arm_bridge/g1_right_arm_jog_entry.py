#!/usr/bin/env python3
"""Supported WSL entrypoint for right-arm Jog result fail-closure.

The physical controller remains in ``g1_right_arm_jog.py``. This wrapper does not
create DDS entities itself. It patches only the final result writer so a faulted
run cannot report command output disabled unless the configured zero-weight tail
was fully written without a release error.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import g1_right_arm_jog as jog


def _config_path(argv: list[str]) -> Path:
    for index, value in enumerate(argv):
        if value == "--config":
            if index + 1 >= len(argv):
                raise ValueError("--config requires a path")
            return Path(argv[index + 1])
        if value.startswith("--config="):
            return Path(value.split("=", 1)[1])
    return jog.DEFAULT_CONFIG_PATH


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


def main() -> int:
    config = jog.load_config(_config_path(sys.argv[1:]))
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
