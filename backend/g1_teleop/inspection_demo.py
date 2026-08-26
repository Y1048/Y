"""Inspection-target progress tracking and result logging.

This module observes the simulated probe tip.  It does not modify IK targets,
joint limits, collision constraints, or motor commands.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class InspectionDemoState(str, Enum):
    WAITING = "waiting"
    APPROACH = "approach"
    HOLDING = "holding"
    COMPLETE = "complete"


@dataclass(frozen=True)
class InspectionDemoSnapshot:
    state: InspectionDemoState
    distance_m: float
    hold_progress: float
    elapsed_s: float
    minimum_distance_m: float
    just_completed: bool


class InspectionDemoTracker:
    """Latch completion after the probe remains near one target point."""

    def __init__(
        self,
        *,
        approach_radius_m: float,
        contact_radius_m: float,
        hold_seconds: float,
    ) -> None:
        if approach_radius_m <= 0.0:
            raise ValueError("approach_radius_m must be positive")
        if contact_radius_m <= 0.0 or contact_radius_m >= approach_radius_m:
            raise ValueError("contact_radius_m must be inside approach_radius_m")
        if hold_seconds <= 0.0:
            raise ValueError("hold_seconds must be positive")
        self.approach_radius_m = float(approach_radius_m)
        self.contact_radius_m = float(contact_radius_m)
        self.hold_seconds = float(hold_seconds)
        self.reset()

    def reset(self) -> None:
        self.state = InspectionDemoState.WAITING
        self._started_at: float | None = None
        self._contact_started_at: float | None = None
        self._minimum_distance_m = float("inf")

    def update(
        self,
        *,
        active: bool,
        distance_m: float,
        now_s: float,
    ) -> InspectionDemoSnapshot:
        distance = max(0.0, float(distance_m))
        now = float(now_s)
        just_completed = False

        if self.state == InspectionDemoState.COMPLETE:
            return self._snapshot(distance, now, False)

        if not active:
            self.state = InspectionDemoState.WAITING
            self._started_at = None
            self._contact_started_at = None
            self._minimum_distance_m = min(self._minimum_distance_m, distance)
            return self._snapshot(distance, now, False)

        if self._started_at is None:
            self._started_at = now
            self._minimum_distance_m = distance
        else:
            self._minimum_distance_m = min(self._minimum_distance_m, distance)

        if distance <= self.contact_radius_m:
            if self._contact_started_at is None:
                self._contact_started_at = now
            held_s = max(0.0, now - self._contact_started_at)
            if held_s >= self.hold_seconds:
                self.state = InspectionDemoState.COMPLETE
                just_completed = True
            else:
                self.state = InspectionDemoState.HOLDING
        else:
            self._contact_started_at = None
            self.state = (
                InspectionDemoState.APPROACH
                if distance <= self.approach_radius_m
                else InspectionDemoState.WAITING
            )

        return self._snapshot(distance, now, just_completed)

    def _snapshot(
        self,
        distance_m: float,
        now_s: float,
        just_completed: bool,
    ) -> InspectionDemoSnapshot:
        elapsed_s = (
            0.0
            if self._started_at is None
            else max(0.0, now_s - self._started_at)
        )
        held_s = (
            0.0
            if self._contact_started_at is None
            else max(0.0, now_s - self._contact_started_at)
        )
        progress = (
            1.0
            if self.state == InspectionDemoState.COMPLETE
            else min(1.0, held_s / self.hold_seconds)
        )
        minimum = (
            distance_m
            if self._minimum_distance_m == float("inf")
            else self._minimum_distance_m
        )
        return InspectionDemoSnapshot(
            state=self.state,
            distance_m=distance_m,
            hold_progress=progress,
            elapsed_s=elapsed_s,
            minimum_distance_m=minimum,
            just_completed=just_completed,
        )


def append_inspection_result(path: Path, row: dict[str, object]) -> None:
    """Append one completed inspection run using a stable CSV schema."""
    field_names = [
        "completed_at",
        "session_id",
        "elapsed_s",
        "final_distance_m",
        "minimum_distance_m",
        "mean_ik_position_error_m",
        "minimum_wrist_limit_margin_deg",
        "collision_nearby_ratio",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names)
        if write_header:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in field_names})
