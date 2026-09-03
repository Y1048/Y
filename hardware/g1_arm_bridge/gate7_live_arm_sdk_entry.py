#!/usr/bin/env python3
"""Supported Gate 7 physical entrypoint with fail-closed collision guards.

This wrapper does not create DDS entities itself. It patches the existing live
adapter before delegating to its main function so the supported WSL path requires
finite ACTIVE collision evidence and validates the final shaped Arm SDK command
segment against the latest full-body measured pose.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import gate7_live_arm_sdk as live
from gate7_live_safety_guard import (
    require_active_collision_evidence,
    validate_final_command_segment,
)


def install_supported_path_guards() -> None:
    original_parse = live.parse_mink_arm_sample

    def guarded_parse(payload):
        return require_active_collision_evidence(original_parse(payload))

    live.parse_mink_arm_sample = guarded_parse

    session_type = live.Gate7LiveDryRunSession
    if getattr(session_type, "_supported_gate7_collision_guard_installed", False):
        return

    original_init = session_type.__init__
    original_step = session_type.Step

    def guarded_init(self, *args: Any, **kwargs: Any) -> None:
        validator = kwargs.get("return_path_validator")
        original_init(self, *args, **kwargs)
        self._supported_final_command_collision_validator = validator

    def guarded_step(
        self,
        sample,
        measured_all_q_rad,
        dt_s,
        *,
        lowstate_age_s,
        mode_pr,
        mode_machine,
    ):
        tick = original_step(
            self,
            sample,
            measured_all_q_rad,
            dt_s,
            lowstate_age_s=lowstate_age_s,
            mode_pr=mode_pr,
            mode_machine=mode_machine,
        )
        if tick.frame is None:
            return tick
        validator = getattr(
            self,
            "_supported_final_command_collision_validator",
            None,
        )
        allowed, reason = validate_final_command_segment(
            tick.frame,
            measured_all_q_rad,
            validator,
        )
        if allowed:
            return tick
        return replace(
            tick,
            validation_allowed=False,
            validation_reason="final_command_collision:" + reason,
            frame=None,
        )

    session_type.__init__ = guarded_init
    session_type.Step = guarded_step
    session_type._supported_gate7_collision_guard_installed = True


def main() -> int:
    install_supported_path_guards()
    return live.main()


if __name__ == "__main__":
    raise SystemExit(main())
