#!/usr/bin/env python3
"""Responsive offline profile built on the common Gate 7 Ruckig controller."""

from __future__ import annotations

from ruckig_gate7_controller import RuckigGate7TeleopController


class ExperimentalStatefulGate7TeleopController(RuckigGate7TeleopController):
    """Use the visually accepted offline-only response scales."""

    def __init__(
        self,
        regular_pose,
        config,
        *,
        return_path_validator,
        velocity_scale: float = 1.25,
        acceleration_scale: float = 3.0,
        jerk_scale: float = 6.0,
    ) -> None:
        super().__init__(
            regular_pose,
            config,
            return_path_validator=return_path_validator,
            velocity_scale=velocity_scale,
            acceleration_scale=acceleration_scale,
            jerk_scale=jerk_scale,
        )
