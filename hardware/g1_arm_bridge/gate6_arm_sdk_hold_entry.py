#!/usr/bin/env python3
"""Supported Gate 6 entrypoint with LowState health supervision (R50)."""

from __future__ import annotations

import gate6_arm_sdk_hold as hold
from lowstate_health_guard import (
    install_lowstate_health_tracking,
    require_latest_lowstate_health,
)


def install_supported_gate6_health_guard() -> None:
    if getattr(hold, "_supported_gate6_health_guard_installed", False):
        return
    install_lowstate_health_tracking(hold.LowStateBuffer)

    original_collect = hold._collect_settled_snapshot

    def guarded_collect(buffer, config):
        result = original_collect(buffer, config)
        require_latest_lowstate_health(hold.LowStateBuffer)
        return result

    hold._collect_settled_snapshot = guarded_collect

    original_blend_weight = hold.blend_weight

    def guarded_blend_weight(*args, **kwargs):
        require_latest_lowstate_health(hold.LowStateBuffer)
        return original_blend_weight(*args, **kwargs)

    hold.blend_weight = guarded_blend_weight
    hold._supported_gate6_health_guard_installed = True


def main() -> int:
    install_supported_gate6_health_guard()
    return hold.main()


if __name__ == "__main__":
    raise SystemExit(main())
