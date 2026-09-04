"""G1 virtual-center Mink task and joint-preference policies."""

from __future__ import annotations

import math

import mujoco
import numpy as np
import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base


# static stand 키보드 기본 1배 속도: 모든 팔 관절에 0.08 rad/s.
PROXIMAL_MAX_JOINT_VELOCITY_DEG_S = math.degrees(0.08)
WRIST_MAX_JOINT_VELOCITY_DEG_S = math.degrees(0.08)

# 관절 이동 비용과 자세 복원 비용을 구분한다. 모터 감쇠 게인과는 별개다.
VIRTUAL_CENTER_PROXIMAL_DAMPING_COST = 0.03
VIRTUAL_CENTER_WRIST_DAMPING_COST = 0.015
VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE = 0.05

ASSIST_ENTER_MARGIN_DEG = 18.0
ASSIST_RELEASE_MARGIN_DEG = 28.0
ASSIST_FULL_MARGIN_DEG = 5.0
ASSIST_LATCH_FLOOR = 0.08
ASSIST_MAX = 1.0
ORIENTATION_COST_MIN_SCALE = 0.25
ORIENTATION_ERROR_NORMAL_MAX_DEG = 180.0
ORIENTATION_ERROR_LIMIT_MAX_DEG = 12.0


def virtual_center_damping_costs(model: mujoco.MjModel) -> np.ndarray:
    """기준 제어기 상수를 바꾸지 않고 이 제어기 전용 관절 감쇠를 만든다."""
    costs = np.zeros(int(model.nv), dtype=float)
    for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
        joint_id = base._joint_id(model, name)
        dof = int(model.jnt_dofadr[joint_id])
        costs[dof] = (
            VIRTUAL_CENTER_PROXIMAL_DAMPING_COST
            if index < 4
            else VIRTUAL_CENTER_WRIST_DAMPING_COST
        )
    return costs


def virtual_center_posture_costs(model: mujoco.MjModel) -> np.ndarray:
    """회전식을 변형하지 않고 손목의 중립 자세 복원 비용만 낮춘다."""
    costs = np.full(int(model.nv), base.POSTURE_COST, dtype=float)
    for name in base.g1.RIGHT_ARM_JOINTS[4:]:
        dof = int(model.jnt_dofadr[base._joint_id(model, name)])
        costs[dof] *= VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE
    return costs


def virtual_center_velocity_limits() -> dict[str, float]:
    """어깨/팔꿈치는 안정적으로, 손목 3축은 더 빠르게 제한한다."""
    return {
        name: math.radians(
            PROXIMAL_MAX_JOINT_VELOCITY_DEG_S
            if index < 4
            else WRIST_MAX_JOINT_VELOCITY_DEG_S
        )
        for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS)
    }


def orientation_limit_policy(
    min_margin_deg: float,
    assist_latched: bool,
) -> tuple[bool, float, float, float]:
    """손목 한계 여유로 보조 상태 표시값과 회전 비용/오차 상한을 정한다."""
    if assist_latched:
        assist_latched = min_margin_deg < ASSIST_RELEASE_MARGIN_DEG
    elif min_margin_deg <= ASSIST_ENTER_MARGIN_DEG:
        assist_latched = True

    if not assist_latched:
        return False, 0.0, 1.0, ORIENTATION_ERROR_NORMAL_MAX_DEG

    span = ASSIST_ENTER_MARGIN_DEG - ASSIST_FULL_MARGIN_DEG
    normalized = np.clip(
        (ASSIST_ENTER_MARGIN_DEG - min_margin_deg) / span,
        0.0,
        1.0,
    )
    pressure = float(normalized * normalized * (3.0 - 2.0 * normalized))
    assist_gain = ASSIST_LATCH_FLOOR + pressure * (
        ASSIST_MAX - ASSIST_LATCH_FLOOR
    )
    orientation_cost_scale = 1.0 - pressure * (
        1.0 - ORIENTATION_COST_MIN_SCALE
    )
    orientation_error_max_deg = ORIENTATION_ERROR_NORMAL_MAX_DEG - pressure * (
        ORIENTATION_ERROR_NORMAL_MAX_DEG - ORIENTATION_ERROR_LIMIT_MAX_DEG
    )
    return (
        True,
        float(assist_gain),
        float(orientation_cost_scale),
        float(orientation_error_max_deg),
    )


class VirtualCenterOrientationTask(Task):
    """정확한 yaw-link 회전식과 손목 한계 근처의 추종 완화를 사용한다."""

    last_assist_gain = 0.0
    last_min_wrist_margin_deg = float("inf")
    last_orientation_cost_scale = 1.0
    last_orientation_error_cap_deg = ORIENTATION_ERROR_NORMAL_MAX_DEG
    last_unclipped_orientation_error_deg = 0.0
    assist_latched = False

    def __init__(self, model) -> None:
        self.inner = mink.FrameTask(
            frame_name="right_wrist_yaw_link",
            frame_type="body",
            position_cost=0.0,
            orientation_cost=1.0,
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )
        self.model = model
        self.proximal_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS[:4]
        ]
        self.wrist_joint_ids = [
            base._joint_id(model, name)
            for name in base.g1.RIGHT_ARM_JOINTS[4:]
        ]
        super().__init__(
            cost=np.array(
                [
                    0.0,
                    0.0,
                    0.0,
                    base.ORIENTATION_COST,
                    base.ORIENTATION_COST,
                    base.ORIENTATION_COST,
                ],
                dtype=float,
            ),
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )

    def set_target(self, target) -> None:
        self.inner.set_target(target)

    def set_target_from_configuration(self, configuration) -> None:
        self.inner.set_target_from_configuration(configuration)

    def compute_error(self, configuration) -> np.ndarray:
        error = self.inner.compute_error(configuration)
        rotation_error = error[3:6]
        rotation_norm = float(np.linalg.norm(rotation_error))
        VirtualCenterOrientationTask.last_unclipped_orientation_error_deg = (
            math.degrees(rotation_norm)
        )
        maximum = math.radians(
            VirtualCenterOrientationTask.last_orientation_error_cap_deg
        )
        if rotation_norm > maximum and rotation_norm > 1e-9:
            error = error.copy()
            error[3:6] *= maximum / rotation_norm
        return error

    def _update_limit_policy(self, configuration) -> None:
        model = configuration.model
        q = configuration.q
        margins: list[float] = []

        for joint_id in self.wrist_joint_ids:
            if not bool(model.jnt_limited[joint_id]):
                continue
            qpos = int(model.jnt_qposadr[joint_id])
            low, high = model.jnt_range[joint_id]
            value = float(q[qpos])
            margin = max(0.0, min(value - float(low), float(high) - value))
            margins.append(math.degrees(margin))

        min_margin = min(margins) if margins else float("inf")
        VirtualCenterOrientationTask.last_min_wrist_margin_deg = min_margin

        latched, assist, cost_scale, error_cap_deg = orientation_limit_policy(
            min_margin,
            VirtualCenterOrientationTask.assist_latched,
        )
        VirtualCenterOrientationTask.assist_latched = latched
        VirtualCenterOrientationTask.last_assist_gain = assist
        VirtualCenterOrientationTask.last_orientation_cost_scale = cost_scale
        VirtualCenterOrientationTask.last_orientation_error_cap_deg = error_cap_deg
        self.cost[3:6] = base.ORIENTATION_COST * cost_scale

    def compute_qp_objective(self, configuration):
        self._update_limit_policy(configuration)
        return super().compute_qp_objective(configuration)

    def compute_qp_residual(self, configuration):
        # Mink 0.0.13+ assembles low-rank tasks through this optimized path.
        # Keep the adaptive policy active for both old and new solver versions.
        self._update_limit_policy(configuration)
        return super().compute_qp_residual(configuration)

    def compute_jacobian(self, configuration) -> np.ndarray:
        # 어깨/팔꿈치 열을 줄이면 실제 회전 변화와 QP의 예측이 달라진다.
        # 손목 우선 선택은 별도의 자세 비용에서 처리한다.
        return self.inner.compute_jacobian(configuration)
