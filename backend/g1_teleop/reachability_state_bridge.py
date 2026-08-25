"""Mirror the gross reachability gate into the 5006 Unity state packet."""

from __future__ import annotations

from types import ModuleType
from typing import Any


def install_reachability_state_bridge(base: ModuleType) -> None:
    if getattr(base, "_REACHABILITY_STATE_BRIDGE_INSTALLED", False):
        return

    original_send_robot_state = base.send_robot_state

    def send_robot_state_with_reachability(*args: Any, **kwargs: Any):
        gate_active = bool(getattr(base, "RUNTIME_REACHABILITY_GATE_ACTIVE", False))

        if "workspace_limited" in kwargs:
            kwargs = dict(kwargs)
            kwargs["workspace_limited"] = bool(kwargs["workspace_limited"] or gate_active)
            return original_send_robot_state(*args, **kwargs)

        positional = list(args)
        if len(positional) > 8:
            positional[8] = bool(positional[8] or gate_active)
        return original_send_robot_state(*positional, **kwargs)

    base.send_robot_state = send_robot_state_with_reachability
    base._REACHABILITY_STATE_BRIDGE_INSTALLED = True
