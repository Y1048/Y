"""Stateful motion shaping for checked Mink right-arm joint targets.

The Mink planner remains responsible for IK, joint limits and collision
avoidance. This layer only makes its checked look-ahead target continuous under
the static-stand 0.08 rad/s operating-speed requirement. Every shaped pose is
checked again before it can update the local MuJoCo configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Sequence

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hardware.g1_arm_bridge.ruckig_joint_motion_limiter import (
    RuckigJointMotionLimiter,
)


@dataclass(frozen=True)
class TrajectoryStep:
    q: np.ndarray
    applied: bool
    status: str
    velocity_rad_s: tuple[float, ...]
    acceleration_rad_s2: tuple[float, ...]


class StatefulMinkTrajectory:
    """Apply Ruckig to seven right-arm joints and recheck the shaped path."""

    def __init__(
        self,
        planner,
        right_qpos_ids: Sequence[int],
        velocity_limits_rad_s: Sequence[float],
        acceleration_limits_rad_s2: Sequence[float],
        jerk_limits_rad_s3: Sequence[float],
        dt_s: float,
    ) -> None:
        self.planner = planner
        self.right_qpos_ids = np.asarray(right_qpos_ids, dtype=int)
        if self.right_qpos_ids.shape != (7,):
            raise ValueError("right_qpos_ids must contain seven joints")
        self.velocity_limits = tuple(float(value) for value in velocity_limits_rad_s)
        self.acceleration_limits = tuple(
            float(value) for value in acceleration_limits_rad_s2
        )
        self.jerk_limits = tuple(float(value) for value in jerk_limits_rad_s3)
        if not all(len(values) == 7 for values in (
            self.velocity_limits,
            self.acceleration_limits,
            self.jerk_limits,
        )):
            raise ValueError("trajectory limits must contain seven values")
        self.dt_s = float(dt_s)
        self.limiter: RuckigJointMotionLimiter | None = None
        self.rejected_sample = None

    def Reset(self, current_q: np.ndarray) -> None:
        current = np.asarray(current_q, dtype=float)
        self.limiter = RuckigJointMotionLimiter(
            current[self.right_qpos_ids],
            self.velocity_limits,
            self.acceleration_limits,
            self.jerk_limits,
            self.dt_s,
        )

    def _safe_path(self, start_q: np.ndarray, candidate_q: np.ndarray) -> bool:
        self.rejected_sample = None
        for fraction in (0.25, 0.5, 0.75, 1.0):
            sample = start_q + fraction * (candidate_q - start_q)
            if not self.planner.CheckConfiguration(sample):
                self.rejected_sample = sample.copy()
                return False
        return True

    def Step(self, current_q: np.ndarray, target_q: np.ndarray) -> TrajectoryStep:
        current = np.asarray(current_q, dtype=float)
        target = np.asarray(target_q, dtype=float)
        if current.shape != target.shape or not np.isfinite(current).all() \
                or not np.isfinite(target).all():
            raise ValueError("current_q and target_q must be finite matching vectors")
        if self.limiter is None:
            self.Reset(current)
        assert self.limiter is not None

        internal_q = np.asarray(self.limiter.q_rad, dtype=float)
        if np.max(np.abs(internal_q - current[self.right_qpos_ids])) > 1.0e-6:
            self.Reset(current)
            assert self.limiter is not None

        shaped_right = self.limiter.Step(
            target[self.right_qpos_ids],
            self.dt_s,
        )
        candidate = current.copy()
        candidate[self.right_qpos_ids] = shaped_right
        if not self._safe_path(current, candidate):
            self.Reset(current)
            return TrajectoryStep(
                current.copy(),
                False,
                "trajectory_collision_hold",
                (0.0,) * 7,
                (0.0,) * 7,
            )

        return TrajectoryStep(
            candidate,
            True,
            "trajectory_following",
            self.limiter.velocity_rad_s,
            self.limiter.acceleration_rad_s2,
        )
