"""Experimental G1 right-arm Mink controller with soft kinematic role separation.

This keeps the normal Mink controller untouched and changes only the Jacobian
used by the 6D right_wrist_yaw_link task:

- Cartesian position is dominated by shoulder pitch/roll/yaw + elbow.
- Orientation is dominated by wrist roll/pitch/yaw.
- The non-primary group keeps a small continuous assist gain so joint limits and
  collision avoidance retain an escape route instead of producing a hard 90 deg
  orientation failure near wrist saturation.

There is deliberately NO speed threshold, mode switch, or hard-freeze based on
operator motion. Slow/millimetric translation remains a normal position task.
Joint, velocity and collision limits are still handled by the normal Mink QP.
"""

from __future__ import annotations

import math
import numpy as np

import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base


# Keep only light instantaneous regularization in this experiment. The soft role
# split itself strongly prefers shoulder/elbow for position and the three wrist
# joints for orientation without making either assignment mathematically rigid.
base.PROXIMAL_DAMPING_COST = 0.03
base.WRIST_DAMPING_COST = 0.015

# Continuous Jacobian assist factors. Primary-role columns stay at 1.0.
# These small non-zero values preserve the desired teleoperation feel while
# allowing the QP to escape wrist saturation and collision-constrained poses.
WRIST_POSITION_ASSIST_GAIN = 0.10
PROXIMAL_ORIENTATION_ASSIST_GAIN = 0.12

# Preserve one-to-one low-speed/millimetric control, but soften abrupt operator
# motions by clipping the QP joint velocity. The base controller uses 75 deg/s;
# 50 deg/s is intentionally only a moderate reduction, not a smoothing filter.
ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S = 50.0
base.RIGHT_ARM_MAX_VELOCITY_RAD_S = math.radians(
    ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S
)

_OriginalFrameTask = mink.FrameTask
_original_write_status = base._write_status


class RoleSplitFrameTask(Task):
    """FrameTask with continuously weighted proximal/wrist Jacobian roles."""

    def __init__(
        self,
        frame_name: str,
        frame_type: str,
        position_cost: float,
        orientation_cost: float,
        gain: float = 1.0,
        lm_damping: float = 0.0,
        **kwargs,
    ) -> None:
        # Use Mink's own FrameTask for the SE(3) error and geometric Jacobian.
        self._frame_task = _OriginalFrameTask(
            frame_name=frame_name,
            frame_type=frame_type,
            position_cost=1.0,
            orientation_cost=1.0,
            gain=gain,
            lm_damping=lm_damping,
            **kwargs,
        )
        self._frame_name = frame_name
        self._cached_nv: int | None = None
        self._proximal_dofs: list[int] = []
        self._wrist_dofs: list[int] = []

        cost = np.array(
            [position_cost, position_cost, position_cost,
             orientation_cost, orientation_cost, orientation_cost],
            dtype=float,
        )
        super().__init__(cost=cost, gain=gain, lm_damping=lm_damping)

    def set_target(self, transform_target_to_world) -> None:
        self._frame_task.set_target(transform_target_to_world)

    def set_target_from_configuration(self, configuration) -> None:
        self._frame_task.set_target_from_configuration(configuration)

    def compute_error(self, configuration) -> np.ndarray:
        return self._frame_task.compute_error(configuration)

    def _resolve_dofs(self, configuration) -> None:
        model = configuration.model
        if self._cached_nv == int(model.nv):
            return

        right_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS
        ]
        self._proximal_dofs = right_dofs[:4]
        self._wrist_dofs = right_dofs[4:]
        self._cached_nv = int(model.nv)

    def compute_jacobian(self, configuration) -> np.ndarray:
        self._resolve_dofs(configuration)
        jacobian = self._frame_task.compute_jacobian(configuration).copy()

        # Mink FrameTask error ordering is [translation(3), rotation(3)].
        # Position is dominated by shoulder(3)+elbow(1), with only a small wrist
        # contribution retained for feasibility/collision escape.
        jacobian[0:3, self._wrist_dofs] *= WRIST_POSITION_ASSIST_GAIN

        # Orientation is dominated by wrist roll/pitch/yaw, with a small proximal
        # contribution retained so wrist limits do not cause a hard orientation
        # failure. This is a continuous preference, not a mode switch.
        jacobian[3:6, self._proximal_dofs] *= PROXIMAL_ORIENTATION_ASSIST_GAIN
        return jacobian


def _write_role_split_status(payload: dict) -> None:
    payload["kinematic_role_split"] = "soft_proximal_position__wrist_orientation"
    payload["position_joints"] = base.g1.RIGHT_ARM_JOINTS[:4]
    payload["orientation_joints"] = base.g1.RIGHT_ARM_JOINTS[4:]
    payload["wrist_position_assist_gain"] = WRIST_POSITION_ASSIST_GAIN
    payload["proximal_orientation_assist_gain"] = PROXIMAL_ORIENTATION_ASSIST_GAIN
    payload["speed_based_mode_switch"] = False
    payload["proximal_hard_freeze"] = False
    payload["max_joint_velocity_deg_s"] = ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S
    _original_write_status(payload)


def main() -> None:
    # base.main() constructs one FrameTask for right_wrist_yaw_link. Replacing
    # only that class preserves the rest of the proven controller path.
    base.mink.FrameTask = RoleSplitFrameTask
    base._write_status = _write_role_split_status

    print("============================================================")
    print("G1 Mink SOFT role-split IK experiment")
    print("Position    : proximal 100%, wrist assist 10%")
    print("Orientation : wrist 100%, proximal assist 12%")
    print("Speed modes : NONE")
    print("Hard freeze : NONE")
    print(
        "Joint speed  : max "
        f"{ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S:.0f} deg/s"
    )
    print("============================================================")
    base.main()


if __name__ == "__main__":
    main()
