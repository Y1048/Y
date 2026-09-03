"""Command provenance helpers for live Mink state producers.

This module is SDK-neutral. It marks packets created by the live Mink/MuJoCo
controller before they are sent to the Gate 7 candidate port. Recorded replay
uses a different provenance value and must never be upgraded here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


LIVE_MINK_PROVENANCE = "live_mink"


def mark_live_mink_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Mark a newly produced live Mink state packet in place and return it."""

    if not isinstance(packet, dict):
        raise TypeError("Mink state packet must be a dict")
    existing = packet.get("command_provenance")
    if existing not in (None, LIVE_MINK_PROVENANCE):
        raise ValueError(
            "refusing to relabel non-live command provenance as live_mink"
        )
    packet["command_provenance"] = LIVE_MINK_PROVENANCE
    return packet


def wrap_state_packet_factory(factory: Callable[..., dict[str, Any]]):
    """Wrap the existing state-packet factory without changing packet semantics."""

    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return mark_live_mink_packet(factory(*args, **kwargs))

    return wrapped
