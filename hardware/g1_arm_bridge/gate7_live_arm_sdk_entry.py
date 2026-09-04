#!/usr/bin/env python3
"""Supported Gate 7 physical entrypoint with fail-closed safety guards.

This wrapper creates no command publisher itself. It installs safety guards before
calling the existing live adapter: relay/live provenance, retired-session
rejection, ACTIVE collision evidence, final post-shaping collision validation,
continuous acquisition freshness, provenance-bound full-body/startup-odometry
binding, LowState IMU/motor health, and read-only runtime base supervision.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import time
from typing import Any

import gate7_live_arm_sdk as live
from gate7_acquisition_guard import (
    ActiveAcquisitionGuard,
    validate_acquisition_hold_target,
    validate_full_body_snapshot_matches_precheck,
)
from gate7_live_safety_guard import (
    require_active_collision_evidence,
    validate_final_command_segment,
)
from gate7_relay_provenance_guard import (
    RetiredSessionGuard,
    require_live_hardware_provenance,
    require_relay_token,
    validate_relay_token,
)
from lowstate_health_guard import (
    install_lowstate_health_tracking,
    require_latest_lowstate_health,
)
from precheck_provenance_guard import require_provenance_bound_precheck
from runtime_base_state_guard import (
    install_unitree_base_state_subscription,
    require_latest_runtime_base_state,
    require_runtime_base_matches_precheck,
)


def _argument_path(name: str, default: Path) -> Path:
    argv = sys.argv[1:]
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise ValueError(f"{name} requires a path")
            return Path(argv[index + 1])
        prefix = name + "="
        if value.startswith(prefix):
            return Path(value[len(prefix) :])
    return default


def _pop_argument(name: str) -> str | None:
    argv = sys.argv[1:]
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise ValueError(f"{name} requires a value")
            result = argv[index + 1]
            del sys.argv[index + 1 : index + 3]
            return result
        prefix = name + "="
        if value.startswith(prefix):
            result = value[len(prefix) :]
            del sys.argv[index + 1]
            return result
    return None


def install_supported_path_guards(
    *,
    acquisition_timeout_s: float,
    expected_relay_token: str,
) -> None:
    if getattr(live, "_supported_gate7_entry_guards_installed", False):
        return

    relay_token = validate_relay_token(expected_relay_token)
    relay_sessions = RetiredSessionGuard()
    install_lowstate_health_tracking(live.LowStateBuffer)

    original_precheck = live.validate_precheck

    def guarded_precheck(path, maximum_age_s):
        payload = original_precheck(path, maximum_age_s)
        return require_provenance_bound_precheck(payload)

    live.validate_precheck = guarded_precheck

    original_parse = live.parse_mink_arm_sample

    def guarded_parse(payload):
        require_relay_token(payload, relay_token)
        require_live_hardware_provenance(payload)
        sample = require_active_collision_evidence(original_parse(payload))
        relay_sessions.accept(sample.session_id, sample.sequence)
        return sample

    live.parse_mink_arm_sample = guarded_parse

    original_snapshot_match = live.validate_snapshot_matches_precheck

    def guarded_snapshot_match(snapshot, precheck, maximum_delta_rad):
        require_latest_lowstate_health(live.LowStateBuffer)
        require_latest_runtime_base_state()
        require_runtime_base_matches_precheck(precheck)
        original_snapshot_match(snapshot, precheck, maximum_delta_rad)
        return validate_full_body_snapshot_matches_precheck(
            snapshot,
            precheck,
            maximum_delta_rad,
        )

    live.validate_snapshot_matches_precheck = guarded_snapshot_match

    acquisition_guard = ActiveAcquisitionGuard(acquisition_timeout_s)
    original_wait_for_active = live.WaitForFirstActiveMink
    original_acquire_weight = live.AcquireWeight
    original_receive_latest = live._ReceiveLatestMink

    def guarded_wait_for_active(sock, timeout_s):
        first_sample = original_wait_for_active(sock, timeout_s)
        acquisition_guard.seed(first_sample)
        guarded_wait_for_active.socket = sock

        confirmation_deadline = time.monotonic() + acquisition_timeout_s
        while time.monotonic() < confirmation_deadline:
            sample = original_receive_latest(sock)
            if sample is not None:
                acquisition_guard.observe(sample)
                return sample
            time.sleep(min(0.005, acquisition_timeout_s / 10.0))
        raise TimeoutError(
            "ACTIVE Mink stream did not remain live before publisher creation"
        )

    guarded_wait_for_active.socket = None

    def guarded_acquire_weight(elapsed_s, ramp_s, maximum_weight):
        require_latest_lowstate_health(live.LowStateBuffer)
        require_latest_runtime_base_state()
        sock = guarded_wait_for_active.socket
        if sock is None:
            raise RuntimeError("Mink acquisition socket was not registered")
        sample = original_receive_latest(sock)
        if sample is not None:
            acquisition_guard.observe(sample)
        acquisition_guard.require_fresh()
        return original_acquire_weight(elapsed_s, ramp_s, maximum_weight)

    live.WaitForFirstActiveMink = guarded_wait_for_active
    live.AcquireWeight = guarded_acquire_weight

    original_build_hold = live.build_measured_hold_frame

    def guarded_build_hold(
        measured_all_q_rad,
        target_dual_arm_q_rad,
        *,
        mode_pr,
        mode_machine,
        weight,
        config=None,
    ):
        effective_config = config
        if effective_config is None:
            return original_build_hold(
                measured_all_q_rad,
                target_dual_arm_q_rad,
                mode_pr=mode_pr,
                mode_machine=mode_machine,
                weight=weight,
            )
        validate_acquisition_hold_target(
            measured_all_q_rad,
            target_dual_arm_q_rad,
            effective_config,
        )
        return original_build_hold(
            measured_all_q_rad,
            target_dual_arm_q_rad,
            mode_pr=mode_pr,
            mode_machine=mode_machine,
            weight=weight,
            config=effective_config,
        )

    live.build_measured_hold_frame = guarded_build_hold

    session_type = live.Gate7LiveDryRunSession
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
        require_latest_lowstate_health(live.LowStateBuffer)
        require_latest_runtime_base_state()
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
    live._supported_gate7_entry_guards_installed = True


def main() -> int:
    gate7_config_path = _argument_path("--gate7-config", live.DEFAULT_GATE7_CONFIG)
    expected_relay_token = _pop_argument("--expected-relay-token")
    if expected_relay_token is None:
        raise SystemExit("supported Gate 7 hardware path requires --expected-relay-token")
    gate7_config = live.load_gate7_config(gate7_config_path)
    install_supported_path_guards(
        acquisition_timeout_s=gate7_config.input_timeout_s,
        expected_relay_token=expected_relay_token,
    )
    install_unitree_base_state_subscription()
    return live.main()


if __name__ == "__main__":
    raise SystemExit(main())
