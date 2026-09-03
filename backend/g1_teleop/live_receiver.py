"""텔레오퍼레이션 제어 루프용 non-blocking UDP 수신 계층."""

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
    latest_active_command: InternalCommand | None
    accepted_count: int
    rejected_count: int
    workspace_exit: bool
    operator_disengage: bool
    transition: RuntimeTransition | None


def receive_available_commands(
    sock: DatagramSocket,
    watchdog: SessionSequenceWatchdog,
    runtime_state: TeleopRuntimeStateMachine | None = None,
    *,
    allow_v2_control: bool = False,
    buffer_size: int = 4096,
) -> ReceiveBatch:
    """대기 중인 UDP 패킷을 읽고 이번 제어 주기에 적용할 명령을 반환한다.

    현재 live 제어는 legacy V0 형식을 사용한다. V2는 엄격히 파싱하지만 raw tracking
    frame 변환이 명시적으로 켜지기 전에는 제어권을 주지 않는다. Unity 추적 좌표가
    기존 로봇 목표 좌표로 잘못 해석되는 것을 막기 위한 경계다.

    workspace_exit 또는 operator disengage는 제어 주기 경계다. 해당 이벤트를
    승인한 즉시 이번 poll을 끝내고 뒤에 쌓인 패킷은 다음 주기로 미룬다. 따라서
    같은 UDP backlog 안의 후속 active 패킷이 안전 이벤트를 덮어쓰지 않는다.
    """
    latest: InternalCommand | None = None
    latest_active: InternalCommand | None = None
    accepted_count = 0
    rejected_count = 0
    workspace_exit = False
    operator_disengage = False
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
        if command.mode == "active" and command.valid:
            latest_active = command
        accepted_count += 1
        workspace_exit = workspace_exit or command.workspace_exit
        operator_disengage = operator_disengage or command.operator_disengage
        if runtime_state is not None:
            transition = runtime_state.apply(command)

        if command.workspace_exit or command.operator_disengage:
            # A safety transition must be observable for at least one controller
            # cycle. Do not expose an earlier active target from the same batch,
            # and leave all later datagrams queued for the next poll.
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
    )
