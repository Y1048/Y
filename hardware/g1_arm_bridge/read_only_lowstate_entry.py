#!/usr/bin/env python3
"""Supported read-only LowState entrypoint with run provenance and odom binding.

The underlying bridge remains read-only. This wrapper can add a per-run
``forward_token`` and augments the forwarded base-state object with the raw
``rt/odommodestate`` position/quaternion used to bind startup and later runtime
base observations. No DDS publisher or command path is created here.
"""

from __future__ import annotations

import json
import math
import socket
import sys
import time

import read_only_lowstate as bridge
from g1_base_state import NormalizeQuaternionWXYZ


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


def _finite_vector(value, length: int, name: str) -> tuple[float, ...]:
    if len(value) != length:
        raise ValueError(f"{name} must contain {length} values")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} contains a non-finite value")
    return result


def install_raw_odom_binding() -> None:
    """Attach source-odometry coordinates to supported forwarded telemetry."""

    if getattr(bridge.ReadOnlyG1BaseState, "_supported_raw_odom_installed", False):
        return

    original_callback = bridge.ReadOnlyG1BaseState.callback
    original_base_payload = bridge._base_state_payload

    def guarded_callback(self, msg) -> None:
        try:
            position = _finite_vector(msg.position, 3, "odom position")
            quaternion_wxyz = NormalizeQuaternionWXYZ(msg.imu_state.quaternion)
            _finite_vector(msg.velocity, 3, "odom velocity")
            yaw_speed = float(msg.yaw_speed)
            if not math.isfinite(yaw_speed):
                raise ValueError("odom yaw speed is non-finite")
            raw = {
                "odom_position_m": list(position),
                "odom_quaternion_xyzw": [
                    quaternion_wxyz[1],
                    quaternion_wxyz[2],
                    quaternion_wxyz[3],
                    quaternion_wxyz[0],
                ],
            }
        except (AttributeError, TypeError, ValueError):
            raw = None
        original_callback(self, msg)
        if raw is not None:
            self._supported_raw_odom = raw

    def guarded_base_payload(monitor, now_monotonic, timeout_s):
        payload = original_base_payload(monitor, now_monotonic, timeout_s)
        raw = getattr(monitor, "_supported_raw_odom", None)
        if payload.get("valid") is True and isinstance(raw, dict):
            payload.update(raw)
        else:
            payload["odom_position_m"] = None
            payload["odom_quaternion_xyzw"] = None
        return payload

    bridge.ReadOnlyG1BaseState.callback = guarded_callback
    bridge._base_state_payload = guarded_base_payload
    bridge.ReadOnlyG1BaseState._supported_raw_odom_installed = True


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
    install_raw_odom_binding()
    install_forward_token(token)
    return bridge.main()


if __name__ == "__main__":
    raise SystemExit(main())
