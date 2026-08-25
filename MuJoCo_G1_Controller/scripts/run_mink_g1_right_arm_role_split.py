"""Experimental G1 right-arm Mink controller with soft kinematic role separation.

This keeps the normal Mink controller untouched and changes only the Jacobian
used by the 6D right_wrist_yaw_link task:

- Cartesian position is dominated by shoulder pitch/roll/yaw + elbow.
- Orientation is dominated by wrist roll/pitch/yaw.
- Proximal orientation assistance is normally almost zero and increases only as
  a wrist joint approaches its mechanical limit. This keeps forearm motion low
  during ordinary wrist rotation while preserving an escape route near wrist
  saturation.

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

# Position remains primarily a proximal-arm responsibility. A small wrist term is
# retained because wrist roll/pitch change the right_wrist_yaw_link position by a
# few centimetres in the physical G1 kinematic chain.
WRIST_POSITION_ASSIST_GAIN = 0.10

# Orientation is almost entirely a wrist responsibility in normal operation.
# Assistance from shoulder/elbow grows continuously only when the closest wrist
# joint approaches a mechanical limit. No operator-speed classification is used.
PROXIMAL_ORIENTATION_ASSIST_MIN = 0.015
PROXIMAL_ORIENTATION_ASSIST_MAX = 0.14
WRIST_LIMIT_ASSIST_START_DEG = 25.0
WRIST_LIMIT_ASSIST_FULL_DEG = 8.0

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

    last_proximal_orientation_assist = PROXIMAL_ORIENTATION_ASSIST_MIN
    last_min_wrist_limit_margin_deg = float("inf")

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
        self._wrist_joint_ids: list[int] = []

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

        right_joint_ids = [
            base._joint_id(model, name)
            for name in base.g1.RIGHT_ARM_JOINTS
        ]
        right_dofs = [
            int(model.jnt_dofadr[joint_id])
            for joint_id in right_joint_ids
        ]
        self._proximal_dofs = right_dofs[:4]
        self._wrist_dofs = right_dofs[4:]
        self._wrist_joint_ids = right_joint_ids[4:]
        self._cached_nv = int(model.nv)

    def _proximal_orientation_assist(self, configuration) -> float:
        model = configuration.model
        q = configuration.q
        margins: list[float] = []

        for joint_id in self._wrist_joint_ids:
            qpos_adr = int(model.jnt_qposadr[joint_id])
            if not bool(model.jnt_limited[joint_id]):
                continue
            low, high = model.jnt_range[joint_id]
            value = float(q[qpos_adr])
            margin_rad = max(0.0, min(value - float(low), float(high) - value))
            margins.append(math.degrees(margin_rad))

        if not margins:
            RoleSplitFrameTask.last_min_wrist_limit_margin_deg = float("inf")
            RoleSplitFrameTask.last_proximal_orientation_assist = (
                PROXIMAL_ORIENTATION_ASSIST_MIN
            )
            return PROXIMAL_ORIENTATION_ASSIST_MIN

        min_margin = min(margins)
        RoleSplitFrameTask.last_min_wrist_limit_margin_deg = min_margin

        if min_margin >= WRIST_LIMIT_ASSIST_START_DEG:
            assist = PROXIMAL_ORIENTATION_ASSIST_MIN
        elif min_margin <= WRIST_LIMIT_ASSIST_FULL_DEG:
            assist = PROXIMAL_ORIENTATION_ASSIST_MAX
        else:
            span = WRIST_LIMIT_ASSIST_START_DEG - WRIST_LIMIT_ASSIST_FULL_DEG
            fraction = (WRIST_LIMIT_ASSIST_START_DEG - min_margin) / span
            # Smoothstep avoids a visible slope change when assistance begins.
            smooth = fraction * fraction * (3.0 - 2.0 * fraction)
            assist = (
                PROXIMAL_ORIENTATION_ASSIST_MIN
                + smooth
                * (PROXIMAL_ORIENTATION_ASSIST_MAX - PROXIMAL_ORIENTATION_ASSIST_MIN)
            )

        RoleSplitFrameTask.last_proximal_orientation_assist = float(assist)
        return float(assist)

    def compute_jacobian(self, configuration) -> np.ndarray:
        self._resolve_dofs(configuration)
        jacobian = self._frame_task.compute_jacobian(configuration).copy()

        # Mink FrameTask error ordering is [translation(3), rotation(3)].
        # Position is dominated by shoulder(3)+elbow(1), with only a small wrist
        # contribution retained for the physical wrist-link position offset.
        jacobian[0:3, self._wrist_dofs] *= WRIST_POSITION_ASSIST_GAIN

        # During ordinary wrist rotation, proximal contribution is only ~1.5%.
        # It grows continuously as a wrist joint approaches its mechanical limit.
        # This is driven by joint margin, never by hand speed, so millimetric slow
        # translation remains fully controllable through the proximal position role.
        proximal_assist = self._proximal_orientation_assist(configuration)
        jacobian[3:6, self._proximal_dofs] *= proximal_assist
        return jacobian


def _write_role_split_status(payload: dict) -> None:
    payload["kinematic_role_split"] = "adaptive_soft_proximal_position__wrist_orientation"
    payload["position_joints"] = base.g1.RIGHT_ARM_JOINTS[:4]
    payload["orientation_joints"] = base.g1.RIGHT_ARM_JOINTS[4:]
    payload["wrist_position_assist_gain"] = WRIST_POSITION_ASSIST_GAIN
    payload["proximal_orientation_assist_gain"] = (
        RoleSplitFrameTask.last_proximal_orientation_assist
    )
    payload["min_wrist_limit_margin_deg"] = (
        RoleSplitFrameTask.last_min_wrist_limit_margin_deg
    )
    payload["proximal_orientation_assist_min"] = PROXIMAL_ORIENTATION_ASSIST_MIN
    payload["proximal_orientation_assist_max"] = PROXIMAL_ORIENTATION_ASSIST_MAX
    payload["wrist_limit_assist_start_deg"] = WRIST_LIMIT_ASSIST_START_DEG
    payload["wrist_limit_assist_full_deg"] = WRIST_LIMIT_ASSIST_FULL_DEG
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
    print("G1 Mink ADAPTIVE SOFT role-split IK experiment")
    print("Position    : proximal 100%, wrist assist 10%")
    print(
        "Orientation : wrist 100%, proximal assist "
        f"{PROXIMAL_ORIENTATION_ASSIST_MIN*100:.1f}% normally -> "
        f"{PROXIMAL_ORIENTATION_ASSIST_MAX*100:.0f}% near wrist limits"
    )
    print(
        "Wrist margin : assist begins at "
        f"{WRIST_LIMIT_ASSIST_START_DEG:.0f} deg, full by "
        f"{WRIST_LIMIT_ASSIST_FULL_DEG:.0f} deg"
    )
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
