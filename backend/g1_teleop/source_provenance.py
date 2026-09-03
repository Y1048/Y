"""Unity command source identity and clock-domain freshness checks.

The sender's monotonic timestamp is never subtracted directly from Python's
monotonic clock. Instead, each sender session gets an offset-free anchor and the
relative clock progress is compared with local receive progress. This detects a
stalled controller draining old packets from an already-established session
without pretending the two clock epochs are equal.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math
from typing import Iterable

from .command_adapter import InternalCommand


@dataclass(frozen=True)
class SourceAcceptance:
    accepted: bool
    reason: str
    estimated_source_lag_s: float | None = None


@dataclass
class _SessionClock:
    anchor_source_ns: int
    anchor_arrival_ns: int
    last_source_ns: int
    last_arrival_ns: int


class CommandSourceGuard:
    """Validate same-PC Unity sender identity and relative source-clock age."""

    def __init__(
        self,
        *,
        maximum_source_lag_s: float,
        allowed_source_hosts: Iterable[str] = ("127.0.0.1",),
        allowed_frame_ids: Iterable[str] = ("quest3s_head_relative",),
        maximum_tracked_sessions: int = 8,
    ) -> None:
        if (
            not isinstance(maximum_source_lag_s, (int, float))
            or isinstance(maximum_source_lag_s, bool)
            or not math.isfinite(float(maximum_source_lag_s))
            or float(maximum_source_lag_s) <= 0.0
        ):
            raise ValueError("maximum_source_lag_s must be positive and finite")
        if (
            not isinstance(maximum_tracked_sessions, int)
            or isinstance(maximum_tracked_sessions, bool)
            or maximum_tracked_sessions < 1
        ):
            raise ValueError("maximum_tracked_sessions must be a positive integer")

        hosts = frozenset(str(value).strip() for value in allowed_source_hosts)
        frames = frozenset(str(value).strip() for value in allowed_frame_ids)
        if not hosts or "" in hosts:
            raise ValueError("allowed_source_hosts must contain non-empty hosts")
        if not frames or "" in frames:
            raise ValueError("allowed_frame_ids must contain non-empty frame ids")

        self.maximum_source_lag_ns = int(float(maximum_source_lag_s) * 1_000_000_000)
        self.allowed_source_hosts = hosts
        self.allowed_frame_ids = frames
        self.maximum_tracked_sessions = maximum_tracked_sessions
        self._sessions: OrderedDict[str, _SessionClock] = OrderedDict()

    def accept(
        self,
        command: InternalCommand,
        *,
        source_host: str,
        arrival_time_ns: int,
    ) -> SourceAcceptance:
        if source_host not in self.allowed_source_hosts:
            return SourceAcceptance(False, f"unexpected sender host:{source_host}")
        if command.frame_id not in self.allowed_frame_ids:
            return SourceAcceptance(False, f"unexpected command source:{command.frame_id}")
        if command.source_time_ns is None:
            return SourceAcceptance(False, "source timestamp missing")
        if (
            not isinstance(command.source_time_ns, int)
            or isinstance(command.source_time_ns, bool)
            or command.source_time_ns < 0
        ):
            return SourceAcceptance(False, "source timestamp invalid")
        if (
            not isinstance(arrival_time_ns, int)
            or isinstance(arrival_time_ns, bool)
            or arrival_time_ns < 0
        ):
            return SourceAcceptance(False, "arrival timestamp invalid")

        state = self._sessions.get(command.session_id)
        if state is None:
            self._sessions[command.session_id] = _SessionClock(
                anchor_source_ns=command.source_time_ns,
                anchor_arrival_ns=arrival_time_ns,
                last_source_ns=command.source_time_ns,
                last_arrival_ns=arrival_time_ns,
            )
            self._sessions.move_to_end(command.session_id)
            while len(self._sessions) > self.maximum_tracked_sessions:
                self._sessions.popitem(last=False)
            return SourceAcceptance(True, "source clock anchored", 0.0)

        if command.source_time_ns <= state.last_source_ns:
            return SourceAcceptance(False, "source timestamp did not increase")
        if arrival_time_ns < state.last_arrival_ns:
            return SourceAcceptance(False, "local arrival clock moved backwards")

        source_elapsed_ns = command.source_time_ns - state.anchor_source_ns
        local_elapsed_ns = arrival_time_ns - state.anchor_arrival_ns
        estimated_lag_ns = max(0, local_elapsed_ns - source_elapsed_ns)

        # Advance monotonic sender evidence even when the packet is too old. This
        # lets a later packet from the same queue catch up to real time without
        # accepting the stale intermediate targets.
        state.last_source_ns = command.source_time_ns
        state.last_arrival_ns = arrival_time_ns
        self._sessions.move_to_end(command.session_id)

        estimated_lag_s = estimated_lag_ns / 1_000_000_000.0
        if estimated_lag_ns > self.maximum_source_lag_ns:
            return SourceAcceptance(
                False,
                "source packet exceeded relative freshness budget",
                estimated_lag_s,
            )
        return SourceAcceptance(True, "source provenance accepted", estimated_lag_s)
