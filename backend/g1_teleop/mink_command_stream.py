"""실시간 Mink 제어기가 공통으로 사용하는 상태 보존형 UDP 명령 입력 계층.

호출: Mink 제어 루프 -> poll -> live_receiver -> command_adapter/watchdog.
현재 same-PC Link 경로는 loopback sender, Unity source id, ordered session sequence와
relative source-clock freshness를 모두 통과해야 active command로 사용된다.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterable

import numpy as np

from .live_receiver import DatagramSocket, receive_available_commands
from .runtime_state import TeleopRuntimeStateMachine
from .source_provenance import CommandSourceGuard
from .transforms import normalize_quaternion
from .watchdog import SessionSequenceWatchdog


@dataclass(frozen=True)
class MinkCommandUpdate:
    """검증된 UDP 명령을 한 제어 주기에서 사용할 수 있게 고정한 스냅샷."""

    target_position_m: np.ndarray
    target_quaternion_xyzw: np.ndarray
    command_active: bool
    clutch_engaged: bool
    engage_clutch: bool
    reset_clutch: bool
    workspace_fault: bool
    accepted_count: int
    rejected_count: int
    control_state: str
    input_command_mode: str
    session_id: str | None
    packet_age_s: float | None
    input_source_lag_s: float | None = None
    input_source_host: str | None = None


class MinkCommandStream:
    """Validate Unity UDP source/session freshness while preserving clutch state."""

    def __init__(
        self,
        initial_position_m: np.ndarray,
        initial_quaternion_xyzw: np.ndarray,
        *,
        input_timeout_s: float,
        takeover_after_s: float | None = None,
        allowed_source_hosts: Iterable[str] = ("127.0.0.1",),
        allowed_frame_ids: Iterable[str] = ("quest3s_head_relative",),
    ) -> None:
        if (
            not isinstance(input_timeout_s, (int, float))
            or isinstance(input_timeout_s, bool)
            or input_timeout_s <= 0.0
        ):
            raise ValueError("input_timeout_s must be positive")
        if takeover_after_s is None:
            takeover_after_s = float(input_timeout_s)

        position = np.asarray(initial_position_m, dtype=float)
        quaternion = np.asarray(initial_quaternion_xyzw, dtype=float)
        if position.shape != (3,) or not np.all(np.isfinite(position)):
            raise ValueError("initial_position_m must contain 3 finite values")
        if quaternion.shape != (4,) or not np.all(np.isfinite(quaternion)):
            raise ValueError("initial_quaternion_xyzw must contain 4 finite values")

        self.input_timeout_ns = int(float(input_timeout_s) * 1_000_000_000)
        self.watchdog = SessionSequenceWatchdog(
            takeover_after_s=float(takeover_after_s)
        )
        self.source_guard = CommandSourceGuard(
            maximum_source_lag_s=float(input_timeout_s),
            allowed_source_hosts=allowed_source_hosts,
            allowed_frame_ids=allowed_frame_ids,
        )
        self.runtime_state = TeleopRuntimeStateMachine()
        self._target_position_m = position.copy()
        self._target_quaternion_xyzw = normalize_quaternion(quaternion)
        self._clutch_engaged = False
        self._input_command_mode = "idle"
        self._latest_source_lag_s: float | None = None
        self._latest_source_host: str | None = None
        self.accepted_total = 0
        self.rejected_total = 0

    def poll(
        self,
        sock: DatagramSocket,
        *,
        now_ns: int | None = None,
    ) -> MinkCommandUpdate:
        """Return the latest source-validated target and clutch events.

        Unity and Python monotonic epochs are never directly subtracted. The
        source guard estimates transport/backlog lag from relative clock
        progress, and that lag is added to local time-since-dequeue when
        reporting `packet_age_s` downstream.
        """
        previous_session_id = self.watchdog.session_id
        batch = receive_available_commands(
            sock,
            self.watchdog,
            self.runtime_state,
            source_guard=self.source_guard,
        )
        self.accepted_total += batch.accepted_count
        self.rejected_total += batch.rejected_count
        if batch.latest_command is not None:
            self._input_command_mode = batch.latest_command.mode
            self._latest_source_lag_s = batch.latest_source_lag_s
            self._latest_source_host = batch.latest_source_host

        current_session_id = self.watchdog.session_id
        session_changed = (
            previous_session_id is not None
            and current_session_id != previous_session_id
        )
        safety_reset = bool(batch.workspace_exit or batch.operator_disengage)
        reset_clutch = bool(session_changed or safety_reset)
        if reset_clutch:
            self._clutch_engaged = False

        if batch.latest_active_command is not None and not safety_reset:
            self._target_position_m = (
                batch.latest_active_command.position_m.copy()
            )
            self._target_quaternion_xyzw = (
                batch.latest_active_command.quaternion_xyzw.copy()
            )

        engage_clutch = False
        latest = batch.latest_command
        if (
            not safety_reset
            and latest is not None
            and latest.mode == "active"
            and latest.valid
            and self.runtime_state.state == "active"
            and not self._clutch_engaged
        ):
            self._clutch_engaged = True
            engage_clutch = True

        if self.runtime_state.state in {"workspace_fault", "shutdown"}:
            self._clutch_engaged = False

        if now_ns is None:
            now_ns = time.monotonic_ns()
        if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
            raise ValueError("now_ns must be a non-negative integer")

        packet_age_s: float | None = None
        input_fresh = False
        if self.watchdog.last_arrival_time_ns >= 0:
            local_receive_age_ns = max(
                0,
                now_ns - self.watchdog.last_arrival_time_ns,
            )
            source_lag_ns = int(
                max(0.0, self._latest_source_lag_s or 0.0) * 1_000_000_000
            )
            packet_age_ns = local_receive_age_ns + source_lag_ns
            packet_age_s = packet_age_ns / 1_000_000_000.0
            input_fresh = packet_age_ns <= self.input_timeout_ns

        command_active = bool(
            self._clutch_engaged
            and self.runtime_state.state == "active"
            and input_fresh
        )
        workspace_fault = self.runtime_state.state == "workspace_fault"
        if workspace_fault:
            control_state = "workspace_fault"
        elif command_active:
            control_state = "active"
        elif self._clutch_engaged:
            control_state = "hold"
        else:
            control_state = "idle"

        return MinkCommandUpdate(
            target_position_m=self._target_position_m.copy(),
            target_quaternion_xyzw=self._target_quaternion_xyzw.copy(),
            command_active=command_active,
            clutch_engaged=self._clutch_engaged,
            engage_clutch=engage_clutch,
            reset_clutch=reset_clutch,
            workspace_fault=workspace_fault,
            accepted_count=batch.accepted_count,
            rejected_count=batch.rejected_count,
            control_state=control_state,
            input_command_mode=self._input_command_mode,
            session_id=current_session_id,
            packet_age_s=packet_age_s,
            input_source_lag_s=self._latest_source_lag_s,
            input_source_host=self._latest_source_host,
        )
