#!/usr/bin/env python3
"""Supported Gate 6 entrypoint with LowState/base health and precheck guards."""

from __future__ import annotations

import sys

import gate6_arm_sdk_hold as hold
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


def install_supported_gate6_guards() -> None:
    if getattr(hold, "_supported_gate6_guards_installed", False):
        return
    install_lowstate_health_tracking(hold.LowStateBuffer)
    state = {"precheck": None}

    original_precheck = hold.validate_precheck

    def guarded_precheck(path, maximum_age_s):
        payload = original_precheck(path, maximum_age_s)
        payload = require_provenance_bound_precheck(payload)
        state["precheck"] = payload
        return payload

    hold.validate_precheck = guarded_precheck

    original_collect = hold._collect_settled_snapshot

    def guarded_collect(buffer, config):
        result = original_collect(buffer, config)
        require_latest_lowstate_health(hold.LowStateBuffer)
        require_latest_runtime_base_state()
        precheck = state.get("precheck")
        if precheck is None:
            raise RuntimeError("startup precheck is unavailable for Gate 6 base binding")
        require_runtime_base_matches_precheck(precheck)
        return result

    hold._collect_settled_snapshot = guarded_collect

    original_blend_weight = hold.blend_weight

    def guarded_blend_weight(*args, **kwargs):
        require_latest_lowstate_health(hold.LowStateBuffer)
        require_latest_runtime_base_state()
        return original_blend_weight(*args, **kwargs)

    hold.blend_weight = guarded_blend_weight
    hold._supported_gate6_guards_installed = True


def main() -> int:
    install_supported_gate6_guards()
    # Validate-only is intentionally SDK-free. Any run that can reach a physical
    # DDS subscriber installs the additional read-only odometry subscriber first.
    if "--validate-only" not in sys.argv[1:]:
        install_unitree_base_state_subscription()
    return hold.main()


if __name__ == "__main__":
    raise SystemExit(main())
