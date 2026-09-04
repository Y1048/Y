"""Simulation-only Gate 7 feedback adapter for the G1 Mink runtime."""

from __future__ import annotations

import socket

import mink

from g1_teleop.gate7_simulation_feedback import (
    DUAL_ARM_JOINT_INDICES,
    Gate7SimulationFeedback,
    Gate7SimulationFeedbackError,
    parse_packet as parse_gate7_feedback_packet,
    should_apply as should_apply_gate7_feedback,
)


GATE7_SIMULATION_FEEDBACK_HOST = "127.0.0.1"
GATE7_SIMULATION_FEEDBACK_PORT = 5012
GATE7_SIMULATION_FEEDBACK_TIMEOUT_S = 0.25
MAX_GATE7_FEEDBACK_PACKET_BYTES = 16384


def drain_gate7_simulation_feedback(
    sock: socket.socket,
    last_stream_id: str | None,
    last_sequence: int,
) -> tuple[Gate7SimulationFeedback | None, str | None, int, int, int]:
    """Drain localhost feedback and retain only the newest ordered packet."""
    latest = None
    accepted = 0
    rejected = 0
    stream_id = last_stream_id
    sequence = last_sequence

    while True:
        try:
            payload, source = sock.recvfrom(MAX_GATE7_FEEDBACK_PACKET_BYTES)
        except BlockingIOError:
            break
        if source[0] != GATE7_SIMULATION_FEEDBACK_HOST:
            rejected += 1
            continue
        try:
            packet = parse_gate7_feedback_packet(payload)
        except (Gate7SimulationFeedbackError, TypeError, ValueError):
            rejected += 1
            continue
        if packet.stream_id != stream_id:
            stream_id = packet.stream_id
            sequence = -1
        if packet.sequence <= sequence:
            rejected += 1
            continue
        sequence = packet.sequence
        latest = packet
        accepted += 1

    return latest, stream_id, sequence, accepted, rejected


def apply_gate7_simulation_feedback(
    configuration: mink.Configuration,
    all_qpos_ids: list[int],
    feedback: Gate7SimulationFeedback,
) -> None:
    """Apply only the 14 arm joints to the in-memory MuJoCo configuration."""
    if len(all_qpos_ids) != 29:
        raise ValueError("all_qpos_ids must contain all 29 G1 joints")

    feedback_q = configuration.q.copy()
    for joint_index, value in zip(
        DUAL_ARM_JOINT_INDICES,
        feedback.dual_arm_q_rad,
    ):
        feedback_q[all_qpos_ids[joint_index]] = value
    configuration.update(feedback_q)
