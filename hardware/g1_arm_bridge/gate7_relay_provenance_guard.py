#!/usr/bin/env python3
"""SDK-neutral provenance guards for the Gate 7 relay/hardware boundary."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from arm_sdk_teleop_contract import Gate7ContractError


TOKEN_MIN_LENGTH = 16
TOKEN_MAX_LENGTH = 128
DEFAULT_RETIRED_SESSION_CAPACITY = 16


def validate_relay_token(token: str) -> str:
    value = str(token).strip()
    if not TOKEN_MIN_LENGTH <= len(value) <= TOKEN_MAX_LENGTH:
        raise ValueError(
            f"relay token must contain {TOKEN_MIN_LENGTH}..{TOKEN_MAX_LENGTH} characters"
        )
    if not value.isalnum():
        raise ValueError("relay token must be alphanumeric")
    return value


def require_relay_token(payload: bytes | str, expected_token: str) -> None:
    """Require the exact per-run relay nonce before parsing command content."""

    token = validate_relay_token(expected_token)
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate7ContractError("relay packet is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise Gate7ContractError("relay packet root must be an object")
    if value.get("relay_token") != token:
        raise Gate7ContractError("relay_token_mismatch")


@dataclass
class RetiredSessionGuard:
    """Reject a command session after ownership has moved away from it.

    A new session may replace the current session, but the previous session is
    tombstoned for the lifetime of this bounded guard. This prevents delayed
    A->B->A replay from becoming live control again without an explicit process
    restart/new relay run.
    """

    retired_capacity: int = DEFAULT_RETIRED_SESSION_CAPACITY
    session_id: str | None = None
    sequence: int | None = None
    _retired: deque[str] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.retired_capacity, int)
            or isinstance(self.retired_capacity, bool)
            or self.retired_capacity < 1
        ):
            raise ValueError("retired_capacity must be a positive integer")

    @property
    def retired_sessions(self) -> tuple[str, ...]:
        return tuple(self._retired)

    def accept(self, session_id: str | None, sequence: int) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise Gate7ContractError("Gate 7 relay requires a non-empty session_id")
        session = session_id.strip()
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise Gate7ContractError("Gate 7 relay sequence must be a non-negative integer")

        if self.session_id is None:
            self.session_id = session
            self.sequence = sequence
            return

        if session == self.session_id:
            if self.sequence is not None and sequence <= self.sequence:
                raise Gate7ContractError(
                    f"non-increasing Mink sequence:{sequence}<={self.sequence}"
                )
            self.sequence = sequence
            return

        if session in self._retired:
            raise Gate7ContractError(f"retired Mink session reappeared:{session}")

        previous = self.session_id
        if previous is not None:
            if previous in self._retired:
                self._retired.remove(previous)
            self._retired.append(previous)
            while len(self._retired) > self.retired_capacity:
                self._retired.popleft()

        self.session_id = session
        self.sequence = sequence

    # Existing relay/test naming compatibility.
    def Accept(self, session_id: str | None, sequence: int) -> None:
        self.accept(session_id, sequence)


def add_relay_token(payload: dict[str, Any], relay_token: str) -> dict[str, Any]:
    """Add a validated transport nonce without mutating the caller's object."""

    result = dict(payload)
    result["relay_token"] = validate_relay_token(relay_token)
    return result
