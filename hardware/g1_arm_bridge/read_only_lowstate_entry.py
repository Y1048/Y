#!/usr/bin/env python3
"""Supported read-only LowState entrypoint with optional run-token provenance.

The underlying bridge remains read-only. This wrapper adds one optional
`--forward-token` field to forwarded UDP telemetry and otherwise delegates to
`read_only_lowstate.py` unchanged.
"""

from __future__ import annotations

import json
import socket
import sys
import time

import read_only_lowstate as bridge


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


def install_forward_token(token: str | None) -> None:
    if token is None:
        return
    token = token.strip()
    if not 16 <= len(token) <= 128 or not token.isalnum():
        raise SystemExit("--forward-token must be 16..128 alphanumeric characters")

    def forward_snapshot(
        sock: socket.socket,
        host: str,
        port: int,
        bridge_session_id: str,
        received: int,
        samples,
        mode_pr: int,
        mode_machine: int,
        all_joint_q_rad,
        all_joint_dq_rad_s,
        base_state,
    ) -> dict[str, object]:
        payload = {
            "schema": bridge.LOWSTATE_TELEMETRY_SCHEMA,
            "mode": "READ_ONLY_LOWSTATE",
            "topic": bridge.TOPIC_LOWSTATE,
            "bridge_session_id": bridge_session_id,
            "sequence": received,
            "received_packets": received,
            "mode_pr": mode_pr,
            "mode_machine": mode_machine,
            "sent_at_unix": time.time(),
            "sent_at_unix_ns": time.time_ns(),
            "right_arm_q_rad": [item.q_rad for item in samples],
            "right_arm_dq_rad_s": [item.dq_rad_s for item in samples],
            "all_joint_names": list(bridge.G1_29_JOINT_NAMES),
            "all_joint_q_rad": all_joint_q_rad,
            "all_joint_dq_rad_s": all_joint_dq_rad_s,
            "base_state": base_state,
            "publisher_present": False,
            "command_output_enabled": False,
            "forward_token": token,
        }
        sock.sendto(
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            (host, port),
        )
        return payload

    bridge._forward_snapshot = forward_snapshot


def main() -> int:
    argv = sys.argv[1:]
    token = _pop_option(argv, "--forward-token")
    sys.argv = [sys.argv[0], *argv]
    install_forward_token(token)
    return bridge.main()


if __name__ == "__main__":
    raise SystemExit(main())
