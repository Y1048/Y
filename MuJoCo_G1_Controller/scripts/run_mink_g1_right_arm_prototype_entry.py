#!/usr/bin/env python3
"""Supported baseline live entrypoint with explicit command provenance."""

from __future__ import annotations

import g1_mink_command_provenance as provenance
import run_mink_g1_right_arm_prototype as controller


def main() -> None:
    if not getattr(controller, "_live_mink_provenance_wrapper_installed", False):
        controller._state_packet = provenance.wrap_state_packet_factory(
            controller._state_packet
        )
        controller._live_mink_provenance_wrapper_installed = True
    controller.main()


if __name__ == "__main__":
    main()
