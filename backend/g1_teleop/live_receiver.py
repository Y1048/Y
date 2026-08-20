"""Non-blocking command reception for the teleoperation control loop."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol

from .command_adapter import InternalCommand, parse_command_packet
from .protocol import ProtocolError
from .runtime_state import RuntimeTransition, TeleopRuntimeStateMachine
from .watchdog import SessionSequenceWatchdog


class DatagramSocket(Protocol):
    def recvfrom(self, bufsize: int): ...


@dataclass(frozen=True)
class ReceiveBatch:
    latest_command: InternalCommand | None
    accepted_count: int
    rejected_count: int
    workspace_exit: bool
    transition: RuntimeTransition | None


def receive_available_commands(
    sock: DatagramSocket,
    watchdog: SessionSequenceWatchdog,
    runtime_state: TeleopRuntimeStateMachine | None = None,
    *,
    allow_v2_control: bool = False,
    buffer_size: int = 4096,
) -> ReceiveBatch:
    """Drain queued UDP datagrams and keep only the newest accepted command.

    Legacy V0 remains the live-control format. V2 packets are parsed strictly,
    but cannot take control until the raw tracking-frame mapping is explicitly
    enabled. This prevents a V2 pose in ``unity_ovr_tracking`` coordinates from
    being mistaken for the legacy robot-target coordinates.
    """
    latest: InternalCommand | None = None
    accepted_count = 0
    rejected_count = 0
    workspace_exit = False
    transition: RuntimeTransition | None = None

    while True:
        try:
            payload, _ = sock.recvfrom(buffer_size)
        except BlockingIOError:
            break

        try:
            command = parse_command_packet(payload)
        except (ProtocolError, TypeError, ValueError):
            rejected_count += 1
            continue

        if command.protocol == "pose_v2" and not allow_v2_control:
            rejected_count += 1
            continue

        arrival_time_ns = time.monotonic_ns()
        acceptance = watchdog.accept(
            command.session_id,
            command.sequence,
            command.valid,
            arrival_time_ns,
        )
        if not acceptance.accepted:
            rejected_count += 1
            continue

        latest = command
        accepted_count += 1
        workspace_exit = workspace_exit or command.workspace_exit
        if runtime_state is not None:
            transition = runtime_state.apply(command)

    return ReceiveBatch(
        latest_command=latest,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        workspace_exit=workspace_exit,
        transition=transition,
    )
