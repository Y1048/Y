"""텔레오퍼레이션 제어 루프용 non-blocking UDP 수신 계층."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Protocol

from .command_adapter import InternalCommand, parse_command_packet
from .protocol import ProtocolError
from .runtime_state import RuntimeTransition, TeleopRuntimeStateMachine
from .source_provenance import CommandSourceGuard
from .watchdog import SessionSequenceWatchdog


class DatagramSocket(Protocol):
    def recvfrom(self, bufsize: int): ...


@dataclass(frozen=True)
class ReceiveBatch:
    latest_command: InternalCommand | None
    latest_active_command: InternalCommand | None
    accepted_count: int
    rejected_count: int
    workspace_exit: bool
    operator_disengage: bool
    transition: RuntimeTransition | None
    latest_source_lag_s: float | None = None
    latest_source_host: str | None = None


def receive_available_commands(
    sock: DatagramSocket,
    watchdog: SessionSequenceWatchdog,
    runtime_state: TeleopRuntimeStateMachine | None = None,
    *,
    allow_v2_control: bool = False,
    source_guard: CommandSourceGuard | None = None,
    buffer_size: int = 4096,
) -> ReceiveBatch:
    """대기 중인 UDP 패킷을 읽고 이번 제어 주기에 적용할 명령을 반환한다.

    The local receive timestamp is captured immediately after ``recvfrom`` and
    before JSON parsing. When ``source_guard`` is supplied, sender host, source
    frame and relative source-clock lag must pass before session/sequence
    ownership can advance.

    workspace_exit 또는 operator disengage는 제어 주기 경계다. 해당 이벤트를
    승인한 즉시 이번 poll을 끝내고 뒤에 쌓인 패킷은 다음 주기로 미룬다.
    """
    latest: InternalCommand | None = None
    latest_active: InternalCommand | None = None
    accepted_count = 0
    rejected_count = 0
    workspace_exit = False
    operator_disengage = False
    transition: RuntimeTransition | None = None
    latest_source_lag_s: float | None = None
    latest_source_host: str | None = None

    while True:
        try:
            payload, source = sock.recvfrom(buffer_size)
            arrival_time_ns = time.monotonic_ns()
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

        source_host = None
        if isinstance(source, tuple) and source:
            source_host = str(source[0])
        if source_guard is not None:
            if source_host is None:
                rejected_count += 1
                continue
            source_acceptance = source_guard.accept(
                command,
                source_host=source_host,
                arrival_time_ns=arrival_time_ns,
            )
            if not source_acceptance.accepted:
                rejected_count += 1
                continue
        else:
            source_acceptance = None

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
        latest_source_host = source_host
        latest_source_lag_s = (
            None
            if source_acceptance is None
            else source_acceptance.estimated_source_lag_s
        )
        if command.mode == "active" and command.valid:
            latest_active = command
        accepted_count += 1
        workspace_exit = workspace_exit or command.workspace_exit
        operator_disengage = operator_disengage or command.operator_disengage
        if runtime_state is not None:
            transition = runtime_state.apply(command)

        if command.workspace_exit or command.operator_disengage:
            latest_active = None
            break

    return ReceiveBatch(
        latest_command=latest,
        latest_active_command=latest_active,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        workspace_exit=workspace_exit,
        operator_disengage=operator_disengage,
        transition=transition,
        latest_source_lag_s=latest_source_lag_s,
        latest_source_host=latest_source_host,
    )
