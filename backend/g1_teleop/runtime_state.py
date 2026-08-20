"""Runtime teleoperation state machine shared by simulation and real control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .command_adapter import InternalCommand


RuntimeState = Literal["idle", "active", "hold", "workspace_fault", "shutdown"]


@dataclass(frozen=True)
class RuntimeTransition:
    previous: RuntimeState
    current: RuntimeState
    reason: str


class TeleopRuntimeStateMachine:
    """Deterministic high-level state machine for teleoperation intent.

    The controller, not Unity, remains the final safety authority. A workspace
    fault cannot be cleared by a normal active packet until an explicit reset
    acknowledgement has been recorded.
    """

    def __init__(self) -> None:
        self.state: RuntimeState = "idle"
        self._workspace_reset_armed = False

    @property
    def workspace_reset_armed(self) -> bool:
        return self._workspace_reset_armed

    def reset(self) -> None:
        self.state = "idle"
        self._workspace_reset_armed = False

    def acknowledge_workspace_reset(self) -> None:
        if self.state == "workspace_fault":
            self._workspace_reset_armed = True

    def trip_workspace_fault(self, reason: str = "workspace fault") -> RuntimeTransition:
        previous = self.state
        self.state = "workspace_fault"
        self._workspace_reset_armed = False
        return RuntimeTransition(previous, self.state, reason)

    def apply(self, command: InternalCommand) -> RuntimeTransition:
        previous = self.state

        if self.state == "shutdown":
            return RuntimeTransition(previous, self.state, "shutdown is terminal")

        if command.mode == "shutdown":
            self.state = "shutdown"
            return RuntimeTransition(previous, self.state, "shutdown command")

        if command.mode == "workspace_exit":
            self.state = "workspace_fault"
            self._workspace_reset_armed = True
            return RuntimeTransition(previous, self.state, "workspace exit acknowledged")

        if self.state == "workspace_fault":
            if command.mode == "active" and command.valid and self._workspace_reset_armed:
                self.state = "active"
                self._workspace_reset_armed = False
                return RuntimeTransition(previous, self.state, "workspace re-engaged")
            return RuntimeTransition(previous, self.state, "workspace reset required")

        if command.mode == "active" and command.valid:
            self.state = "active"
            return RuntimeTransition(previous, self.state, "active command")

        if command.mode == "hold" or (command.mode == "idle" and previous in {"active", "hold"}):
            self.state = "hold"
            return RuntimeTransition(previous, self.state, "hold last safe target")

        self.state = "idle"
        return RuntimeTransition(previous, self.state, "idle")
