#!/usr/bin/env python3
"""Supported startup-precheck entrypoint with per-run LowState provenance.

The underlying precheck remains read-only and creates no DDS entity. This wrapper
requires an explicit run token, persists the latest validated base-state sample,
and binds the result to the exact startup config/model/collision sources used by
the current checkout before supported physical consumers may reuse it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import check_startup_readiness as precheck
from startup_state_binding_guard import base_state_to_dict, build_state_binding


TOKEN_MIN_LENGTH = 16
TOKEN_MAX_LENGTH = 128


def _pop_option(argv: list[str], name: str) -> str | None:
    for index, value in enumerate(list(argv)):
        if value == name:
            if index + 1 >= len(argv):
                raise SystemExit(f"{name} requires a value")
            result = argv[index + 1]
            del argv[index : index + 2]
            return result
        prefix = name + "="
        if value.startswith(prefix):
            result = value[len(prefix) :]
            del argv[index]
            return result
    return None


def _option_path(argv: list[str], name: str, default: Path) -> Path:
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise SystemExit(f"{name} requires a value")
            return Path(argv[index + 1])
        prefix = name + "="
        if value.startswith(prefix):
            return Path(value[len(prefix) :])
    return default


def validate_forward_token(token: str) -> str:
    value = token.strip()
    if not TOKEN_MIN_LENGTH <= len(value) <= TOKEN_MAX_LENGTH:
        raise ValueError(
            f"forward token must contain {TOKEN_MIN_LENGTH}..{TOKEN_MAX_LENGTH} characters"
        )
    if not value.isalnum():
        raise ValueError("forward token must be alphanumeric")
    return value


def install_forward_token_guard(expected_token: str) -> dict[str, int]:
    """Require the exact token before the canonical LowState parser is called."""

    token = validate_forward_token(expected_token)
    original_parse = precheck.parse_lowstate_telemetry
    state = {"verified_packets": 0}

    def guarded_parse(payload: bytes):
        try:
            raw = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return original_parse(payload)
        if not isinstance(raw, dict):
            return original_parse(payload)
        if raw.get("forward_token") != token:
            raise precheck.LowStatePacketError("forward_token_mismatch")
        packet = original_parse(payload)
        state["verified_packets"] += 1
        return packet

    precheck.parse_lowstate_telemetry = guarded_parse
    return state


def install_latest_base_state_persistence() -> None:
    """Extend the existing 29-joint persisted snapshot with validated base state."""

    original = precheck.latest_full_body_snapshot

    def enriched(packet):
        result = original(packet)
        result["latest_base_state"] = base_state_to_dict(packet.telemetry.base_state)
        return result

    precheck.latest_full_body_snapshot = enriched


def main() -> int:
    argv = sys.argv[1:]
    token = _pop_option(argv, "--expected-forward-token")
    if token is None:
        raise SystemExit(
            "supported startup precheck requires --expected-forward-token"
        )
    token = validate_forward_token(token)
    output_path = _option_path(argv, "--output", precheck.DEFAULT_RESULT_PATH)
    config_path = _option_path(argv, "--config", precheck.DEFAULT_CONFIG_PATH)
    state = install_forward_token_guard(token)
    install_latest_base_state_persistence()
    sys.argv = [sys.argv[0], *argv]
    result_code = precheck.main()

    # Add provenance and exact static model/config evidence without persisting
    # the nonce itself. If this write fails, supported physical consumers reject
    # the artifact because the required evidence is absent.
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["lowstate_forward_provenance"] = {
                "mode": "per_run_token",
                "forward_token_verified": state["verified_packets"] > 0,
                "verified_packet_count": state["verified_packets"],
            }
            payload["startup_state_binding"] = build_state_binding(config_path)
            temporary = output_path.with_suffix(output_path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(output_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
