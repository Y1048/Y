"""Optional inspection-contact state machine for NDT teleoperation.

The state machine is intentionally policy-only. It does not command forces or
change the arm trajectory by itself. When disabled, it stays in FREE_SPACE and
the existing teleoperation runtime behaves exactly as before.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from typing import Any

from .config import TeleopConfig


class InspectionContactState(str, Enum):
    FREE_SPACE = "free_space"
    APPROACH = "approach"
    CONTACT_ACQUIRE = "contact_acquire"
    INSPECTION_CONTACT = "inspection_contact"
    SURFACE_FOLLOW = "surface_follow"
    RETRACT = "retract"


@dataclass(frozen=True)
class InspectionContactTransition:
    previous: InspectionContactState
    current: InspectionContactState
    changed: bool
    reason: str


class InspectionContactStateMachine:
    """Track an NDT probe from approach through contact and retraction.

    Inputs are deliberately generic so a later real robot can feed force/torque,
    proximity, vision, or MuJoCo contact observations without changing the state
    model. Surface following is only entered when explicitly requested.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        approach_distance_m: float,
        contact_confirm_s: float,
        contact_release_s: float,
    ) -> None:
        if approach_distance_m <= 0.0:
            raise ValueError("approach_distance_m must be positive")
        if contact_confirm_s < 0.0 or contact_release_s < 0.0:
            raise ValueError("contact timing values must be non-negative")
        self.enabled = bool(enabled)
        self.approach_distance_m = float(approach_distance_m)
        self.contact_confirm_s = float(contact_confirm_s)
        self.contact_release_s = float(contact_release_s)
        self.state = InspectionContactState.FREE_SPACE
        self._contact_since: float | None = None
        self._released_since: float | None = None

    def reset(self) -> None:
        self.state = InspectionContactState.FREE_SPACE
        self._contact_since = None
        self._released_since = None

    def update(
        self,
        *,
        task_contact_active: bool,
        tool_target_distance_m: float | None = None,
        surface_follow_requested: bool = False,
        retract_requested: bool = False,
        now_s: float | None = None,
    ) -> InspectionContactTransition:
        previous = self.state
        now = time.monotonic() if now_s is None else float(now_s)

        if not self.enabled:
            self.reset()
            return InspectionContactTransition(previous, self.state, previous != self.state, "disabled")

        if retract_requested:
            self.state = InspectionContactState.RETRACT
            self._contact_since = None
            return InspectionContactTransition(previous, self.state, previous != self.state, "retract_requested")

        if task_contact_active:
            self._released_since = None
            if self._contact_since is None:
                self._contact_since = now
            held_s = max(0.0, now - self._contact_since)
            if held_s < self.contact_confirm_s:
                self.state = InspectionContactState.CONTACT_ACQUIRE
                reason = "confirming_contact"
            elif surface_follow_requested:
                self.state = InspectionContactState.SURFACE_FOLLOW
                reason = "surface_follow_requested"
            else:
                self.state = InspectionContactState.INSPECTION_CONTACT
                reason = "contact_confirmed"
            return InspectionContactTransition(previous, self.state, previous != self.state, reason)

        self._contact_since = None
        if self.state in {
            InspectionContactState.CONTACT_ACQUIRE,
            InspectionContactState.INSPECTION_CONTACT,
            InspectionContactState.SURFACE_FOLLOW,
        }:
            if self._released_since is None:
                self._released_since = now
            if now - self._released_since < self.contact_release_s:
                return InspectionContactTransition(previous, self.state, False, "release_debounce")

        self._released_since = None
        if tool_target_distance_m is not None and 0.0 <= tool_target_distance_m <= self.approach_distance_m:
            self.state = InspectionContactState.APPROACH
            reason = "within_approach_distance"
        else:
            self.state = InspectionContactState.FREE_SPACE
            reason = "clear_of_surface"
        return InspectionContactTransition(previous, self.state, previous != self.state, reason)


def install_inspection_contact_monitor(base: ModuleType, config: TeleopConfig) -> InspectionContactStateMachine:
    """Expose optional inspection state in runtime status without altering motion."""
    inspection = config.inspection
    machine = InspectionContactStateMachine(
        enabled=inspection.enabled,
        approach_distance_m=inspection.approach_distance_m,
        contact_confirm_s=inspection.contact_confirm_s,
        contact_release_s=inspection.contact_release_s,
    )
    base.INSPECTION_CONTACT_MACHINE = machine
    base.RUNTIME_INSPECTION_STATE = machine.state.value

    original_status_writer = getattr(base, "write_runtime_status", None)
    if callable(original_status_writer) and not getattr(base, "_INSPECTION_STATUS_WRITER_INSTALLED", False):
        def inspection_status_writer(status_value: dict[str, Any]) -> None:
            task_contact_active = bool(
                status_value.get(
                    "task_contact_active",
                    getattr(base, "RUNTIME_TASK_CONTACT_ACTIVE", False),
                )
            )
            transition = machine.update(task_contact_active=task_contact_active)
            base.RUNTIME_INSPECTION_STATE = transition.current.value
            enriched = dict(status_value)
            enriched["inspection_enabled"] = bool(inspection.enabled)
            enriched["inspection_state"] = transition.current.value
            enriched["inspection_transition_reason"] = transition.reason
            original_status_writer(enriched)

        base.write_runtime_status = inspection_status_writer
        base._INSPECTION_STATUS_WRITER_INSTALLED = True

    return machine
