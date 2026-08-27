"""텔레오퍼레이션 패킷의 도착 시간, 순서, 송신 세션을 감시하는 watchdog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


WatchdogStatus = Literal["awaiting", "ok", "hold", "disarm"]


@dataclass(frozen=True)
class PacketAcceptance:
    accepted: bool
    reason: str


class SequenceWatchdog:
    """서로 다른 장치의 시계를 비교하지 않고 재전송 패킷과 입력 단절을 판별한다."""

    def __init__(self, hold_after_s: float = 0.10, disarm_after_s: float = 0.30) -> None:
        if hold_after_s <= 0.0 or disarm_after_s <= hold_after_s:
            raise ValueError("timeouts must satisfy 0 < hold_after_s < disarm_after_s")
        self.hold_after_ns = int(hold_after_s * 1_000_000_000)
        self.disarm_after_ns = int(disarm_after_s * 1_000_000_000)
        self.last_sequence = -1
        self.last_arrival_ns: int | None = None

    def reset(self) -> None:
        self.last_sequence = -1
        self.last_arrival_ns = None

    def accept(self, sequence: int, arrival_time_ns: int) -> PacketAcceptance:
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return PacketAcceptance(False, "invalid sequence type")
        if not isinstance(arrival_time_ns, int) or isinstance(arrival_time_ns, bool):
            return PacketAcceptance(False, "invalid arrival time type")
        if sequence < 0 or arrival_time_ns < 0:
            return PacketAcceptance(False, "negative sequence or arrival time")
        if sequence <= self.last_sequence:
            return PacketAcceptance(False, "duplicate or out-of-order sequence")
        if self.last_arrival_ns is not None and arrival_time_ns < self.last_arrival_ns:
            return PacketAcceptance(False, "arrival clock moved backwards")

        self.last_sequence = sequence
        self.last_arrival_ns = arrival_time_ns
        return PacketAcceptance(True, "accepted")

    def status(self, now_ns: int) -> WatchdogStatus:
        if self.last_arrival_ns is None:
            return "awaiting"
        elapsed = max(0, now_ns - self.last_arrival_ns)
        if elapsed >= self.disarm_after_ns:
            return "disarm"
        if elapsed >= self.hold_after_ns:
            return "hold"
        return "ok"


class SessionSequenceWatchdog:
    """Accept ordered packets from one sender session at a time.

    A different sender can take ownership only after the current session is
    stale. This prevents delayed invalid packets from a previous Unity run from
    stealing ownership from the active sender.
    """

    def __init__(self, takeover_after_s: float = 0.30) -> None:
        if takeover_after_s < 0.0:
            raise ValueError("takeover_after_s must be non-negative")
        self.takeover_after_ns = int(takeover_after_s * 1_000_000_000)
        self.reset()

    def reset(self) -> None:
        self.session_id: str | None = None
        self.last_sequence = -1
        self.last_arrival_time_ns = -1

    def accept(
        self,
        session_id: str,
        sequence: int,
        valid: bool,
        arrival_time_ns: int,
    ) -> PacketAcceptance:
        if not isinstance(session_id, str) or not session_id.strip():
            return PacketAcceptance(False, "invalid session id")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            return PacketAcceptance(False, "invalid sequence type")
        if not isinstance(valid, bool):
            return PacketAcceptance(False, "invalid valid flag")
        if not isinstance(arrival_time_ns, int) or isinstance(arrival_time_ns, bool):
            return PacketAcceptance(False, "invalid arrival time type")
        if sequence < 0:
            return PacketAcceptance(False, "negative sequence")
        if arrival_time_ns < 0:
            return PacketAcceptance(False, "negative arrival time")

        if self.session_id is None:
            self._take_ownership(session_id, sequence, arrival_time_ns)
            return PacketAcceptance(True, "initial session")

        if session_id == self.session_id:
            if sequence <= self.last_sequence:
                return PacketAcceptance(False, "stale or duplicate sequence")
            if arrival_time_ns < self.last_arrival_time_ns:
                return PacketAcceptance(False, "arrival time moved backwards")
            self.last_sequence = sequence
            self.last_arrival_time_ns = arrival_time_ns
            return PacketAcceptance(True, "ordered packet")

        current_session_age_ns = arrival_time_ns - self.last_arrival_time_ns
        current_session_stale = current_session_age_ns >= self.takeover_after_ns
        if not current_session_stale:
            return PacketAcceptance(False, "active session owns the stream")

        self._take_ownership(session_id, sequence, arrival_time_ns)
        return PacketAcceptance(True, "stale session takeover")

    def _take_ownership(self, session_id: str, sequence: int, arrival_time_ns: int) -> None:
        self.session_id = session_id
        self.last_sequence = sequence
        self.last_arrival_time_ns = arrival_time_ns


class WorkspaceFaultLatch:
    """Require an explicit workspace exit before fault re-engagement.

    A workspace fault remains visible and blocks valid commands until the active
    sender acknowledges the workspace exit and then transmits a new active
    packet. Idle or stale input must not arm the reset sequence.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.latched = False
        self.reset_armed = False

    def trip(self) -> None:
        self.latched = True
        self.reset_armed = False

    def trip_and_arm_reset(self) -> None:
        """Latch a locally confirmed exit and allow the next active packet.

        The local workspace checker is authoritative, so its confirmed exit
        also satisfies the acknowledgement required before re-engagement.
        """
        self.trip()
        self.observe_workspace_exit()

    def observe_workspace_exit(self) -> None:
        if self.latched:
            self.reset_armed = True

    def permit_valid(self) -> bool:
        if not self.latched:
            return True
        if not self.reset_armed:
            return False

        self.reset()
        return True


class WorkspaceExitDebounce:
    """Confirm a continuous workspace violation before reporting an exit."""

    def __init__(self, confirm_after_s: float) -> None:
        if not isinstance(confirm_after_s, (int, float)) or confirm_after_s <= 0.0:
            raise ValueError("confirm_after_s must be positive")
        self.confirm_after_s = float(confirm_after_s)
        self.reset()

    def reset(self) -> None:
        self.unsafe_duration_s = 0.0

    def update(self, is_safe: bool, delta_time_s: float) -> bool:
        if not isinstance(is_safe, bool):
            raise TypeError("is_safe must be a bool")
        if not isinstance(delta_time_s, (int, float)) or delta_time_s < 0.0:
            raise ValueError("delta_time_s must be non-negative")

        if is_safe:
            self.reset()
            return False

        self.unsafe_duration_s += float(delta_time_s)
        return self.unsafe_duration_s >= self.confirm_after_s
