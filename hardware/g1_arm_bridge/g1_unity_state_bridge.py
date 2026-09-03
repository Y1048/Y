#!/usr/bin/env python3
"""G1 LowState를 Unity 전신 프리뷰 패킷으로 변환하는 읽기 전용 어댑터."""

from __future__ import annotations

import json
import math
import socket
import time
from collections.abc import Sequence
from typing import Final

from g1_joint_contract import G1_29_JOINT_NAMES
from gate5_lowstate_safety_monitor import LowStatePacketError, LowStateTelemetry


UNITY_HARDWARE_STATE_SOURCE: Final[str] = "g1_lowstate_read_only"
DEFAULT_UNITY_HARDWARE_HOST: Final[str] = "127.0.0.1"
DEFAULT_UNITY_HARDWARE_PORT: Final[int] = 5010


def _FiniteVector(
    values: Sequence[float],
    length: int,
    name: str,
) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) != length or not all(math.isfinite(value) for value in result):
        raise LowStatePacketError(f"{name} must contain {length} finite values")
    return result


def _QuaternionAngleDegrees(
    first_xyzw: Sequence[float],
    second_xyzw: Sequence[float],
) -> float:
    first = _FiniteVector(first_xyzw, 4, "first quaternion")
    second = _FiniteVector(second_xyzw, 4, "second quaternion")
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    if first_norm < 1e-9 or second_norm < 1e-9:
        raise LowStatePacketError("mirror quaternion norm is zero")
    dot_value = abs(
        sum(
            first[index] * second[index]
            for index in range(4)
        ) / (first_norm * second_norm)
    )
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot_value))))


def _RequireFullBody(packet: LowStateTelemetry) -> None:
    if (
        packet.all_joint_names is None
        or packet.all_joint_q_rad is None
        or packet.all_joint_dq_rad_s is None
    ):
        raise LowStatePacketError(
            "Unity hardware preview requires full 29-joint names, q, and dq"
        )
    if packet.all_joint_names != G1_29_JOINT_NAMES:
        raise LowStatePacketError(
            "Unity hardware preview joint order does not match G1 contract"
        )
    if not all(
        math.isfinite(value)
        for value in packet.all_joint_q_rad + packet.all_joint_dq_rad_s
    ):
        raise LowStatePacketError(
            "Unity hardware preview contains a non-finite joint value"
        )


def BuildUnityHardwareStatePacket(
    packet: LowStateTelemetry,
    *,
    timestamp: float | None = None,
    displayed_all_joint_q_rad: Sequence[float] | None = None,
    displayed_base_position_m: Sequence[float] | None = None,
    displayed_base_quaternion_xyzw: Sequence[float] | None = None,
) -> dict[str, object]:
    """Unity 5010에 MuJoCo가 실제 표시한 읽기 전용 상태를 전달한다."""
    _RequireFullBody(packet)
    assert packet.all_joint_names is not None
    assert packet.all_joint_q_rad is not None
    assert packet.all_joint_dq_rad_s is not None

    source_joint_positions = _FiniteVector(
        packet.all_joint_q_rad,
        len(G1_29_JOINT_NAMES),
        "source joint positions",
    )
    displayed_joint_positions = (
        source_joint_positions
        if displayed_all_joint_q_rad is None
        else _FiniteVector(
            displayed_all_joint_q_rad,
            len(G1_29_JOINT_NAMES),
            "displayed joint positions",
        )
    )

    has_displayed_base_position = displayed_base_position_m is not None
    has_displayed_base_rotation = displayed_base_quaternion_xyzw is not None
    if has_displayed_base_position != has_displayed_base_rotation:
        raise LowStatePacketError(
            "displayed base position and quaternion must be supplied together"
        )
    if has_displayed_base_position and packet.base_state is None:
        raise LowStatePacketError("displayed base override requires source base_state")

    payload: dict[str, object] = {
        "state_source": UNITY_HARDWARE_STATE_SOURCE,
        "session_id": packet.bridge_session_id,
        "sequence": packet.sequence,
        "all_joint_names": list(packet.all_joint_names),
        "all_joint_q_rad": list(displayed_joint_positions),
        "all_joint_dq_rad_s": list(packet.all_joint_dq_rad_s),
        "right_arm": {
            "joints": list(displayed_joint_positions[22:29]),
            "active": False,
            "workspace_limited": False,
            "collision_limited": False,
        },
        "timestamp": time.time() if timestamp is None else float(timestamp),
    }
    if packet.base_state is not None:
        source_base_position = _FiniteVector(
            packet.base_state.position_m,
            3,
            "source base position",
        )
        source_base_quaternion = _FiniteVector(
            packet.base_state.quaternion_xyzw,
            4,
            "source base quaternion",
        )
        displayed_base_position = (
            source_base_position
            if displayed_base_position_m is None
            else _FiniteVector(
                displayed_base_position_m,
                3,
                "displayed base position",
            )
        )
        displayed_base_quaternion = (
            source_base_quaternion
            if displayed_base_quaternion_xyzw is None
            else _FiniteVector(
                displayed_base_quaternion_xyzw,
                4,
                "displayed base quaternion",
            )
        )
        payload["base_state"] = {
            "valid": packet.base_state.valid,
            "topic": packet.base_state.topic,
            "received_packets": packet.base_state.received_packets,
            "last_packet_age_s": packet.base_state.last_packet_age_s,
            "position_m": list(displayed_base_position),
            "quaternion_xyzw": list(displayed_base_quaternion),
            "velocity_mps": list(packet.base_state.velocity_mps),
            "yaw_speed_rad_s": packet.base_state.yaw_speed_rad_s,
        }
        if has_displayed_base_position or displayed_all_joint_q_rad is not None:
            payload["mirror_diagnostics"] = {
                "source_base_position_m": list(source_base_position),
                "source_base_quaternion_xyzw": list(source_base_quaternion),
                "displayed_base_position_m": list(displayed_base_position),
                "displayed_base_quaternion_xyzw": list(displayed_base_quaternion),
                "base_position_error_m": math.dist(
                    source_base_position,
                    displayed_base_position,
                ),
                "base_orientation_error_deg": _QuaternionAngleDegrees(
                    source_base_quaternion,
                    displayed_base_quaternion,
                ),
                "max_joint_position_error_rad": max(
                    abs(source_joint_positions[index] - displayed_joint_positions[index])
                    for index in range(len(G1_29_JOINT_NAMES))
                ),
            }
    return payload


def EncodeUnityHardwareStatePacket(
    packet: LowStateTelemetry,
    *,
    displayed_all_joint_q_rad: Sequence[float] | None = None,
    displayed_base_position_m: Sequence[float] | None = None,
    displayed_base_quaternion_xyzw: Sequence[float] | None = None,
) -> bytes:
    return json.dumps(
        BuildUnityHardwareStatePacket(
            packet,
            displayed_all_joint_q_rad=displayed_all_joint_q_rad,
            displayed_base_position_m=displayed_base_position_m,
            displayed_base_quaternion_xyzw=displayed_base_quaternion_xyzw,
        ),
        separators=(",", ":"),
    ).encode("utf-8")


def SendUnityHardwareState(
    sock: socket.socket,
    packet: LowStateTelemetry,
    host: str,
    port: int,
    *,
    displayed_all_joint_q_rad: Sequence[float] | None = None,
    displayed_base_position_m: Sequence[float] | None = None,
    displayed_base_quaternion_xyzw: Sequence[float] | None = None,
) -> None:
    sock.sendto(
        EncodeUnityHardwareStatePacket(
            packet,
            displayed_all_joint_q_rad=displayed_all_joint_q_rad,
            displayed_base_position_m=displayed_base_position_m,
            displayed_base_quaternion_xyzw=displayed_base_quaternion_xyzw,
        ),
        (host, port),
    )
