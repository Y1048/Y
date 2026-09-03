#!/usr/bin/env python3
"""SDK-neutral provenance requirement for physical startup-precheck consumers."""

from __future__ import annotations

from typing import Any


def require_provenance_bound_precheck(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject a precheck not produced from the supported per-run token path."""

    if not isinstance(payload, dict):
        raise ValueError("startup precheck must be an object")
    provenance = payload.get("lowstate_forward_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("startup precheck lacks LowState forward provenance")
    if provenance.get("mode") != "per_run_token":
        raise ValueError("startup precheck provenance mode is not per_run_token")
    if provenance.get("forward_token_verified") is not True:
        raise ValueError("startup precheck forward token was not verified")
    verified_count = provenance.get("verified_packet_count")
    if (
        isinstance(verified_count, bool)
        or not isinstance(verified_count, int)
        or verified_count < 1
    ):
        raise ValueError("startup precheck has no token-verified LowState packets")
    lowstate_packet_count = payload.get("lowstate_packet_count")
    if (
        isinstance(lowstate_packet_count, int)
        and not isinstance(lowstate_packet_count, bool)
        and verified_count != lowstate_packet_count
    ):
        raise ValueError(
            "startup precheck token-verified packet count does not match accepted LowState count"
        )
    return payload
