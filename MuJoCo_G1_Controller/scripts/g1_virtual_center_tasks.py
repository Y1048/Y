"""G1 virtual-center Mink task and joint-preference policies."""

from __future__ import annotations

import math

import mujoco
import numpy as np
import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base


# Quest 추종에 사용한 빠른 프로파일. 어깨/팔꿈치와 손목을 구분한다.
PROXIMAL_MAX_JOINT_VELOCITY_DEG_S = 90.0
WRIST_MAX_JOINT_VELOCITY_DEG_S = 180.0
JOINT_MAX_ACCELERATION_RAD_S2 = math.radians(60.0)
JOINT_MAX_JERK_RAD_S3 = base.RIGHT_ARM_MAX_JERK_RAD_S3

# 관절 이동 비용과 자세 복원 비용을 구분한다. 모터 감쇠 게인과는 별개다.
VIRTUAL_CENTER_PROXIMAL_DAMPING_COST = 0.03
VIRTUAL_CENTER_WRIST_DAMPING_COST = 0.015
VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE = 0.05

# 계층형 QP에서 위치는 근위축, 회전은 손목축을 우선하도록 만드는 유한 비용이다.
# hard freeze가 아니므로 충돌/관절 한계 때문에 필요하면 다른 축도 계속 사용할 수 있다.
POSITION_WRIST_DAMPING_COST = 0.50
# Orientation cost 2.0보다 충분히 크게 두어 정상 구간에서 손목 해를 우선한다.
# 100.0은 혼합 6D 도달성과 25도 wrist-only 회귀를 함께 통과한 현재 기준값이다.
ORIENTATION_PROXIMAL_DAMPING_MAX = 100.0
ORIENTATION_PROXIMAL_DAMPING_MIN = VIRTUAL_CENTER_PROXIMAL_DAMPING_COST
WRIST_SINGULARITY_ASSIST_START = 0.35
WRIST_SINGULARITY_ASSIST_FULL = 0.08

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


def hierarchical_position_damping_costs(model: mujoco.MjModel) -> np.ndarray:
    """위치 단계에서는 어깨/팔꿈치를 손목보다 우선한다."""
    costs = np.zeros(int(model.nv), dtype=float)
    for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, name)])
        costs[dof] = (
            VIRTUAL_CENTER_PROXIMAL_DAMPING_COST
            if index < 4
            else POSITION_WRIST_DAMPING_COST
        )
    return costs


def hierarchical_orientation_damping_costs(
    model: mujoco.MjModel,
    assist_gain: float,
) -> np.ndarray:
    """회전 단계의 근위축 비용을 assist 0..1에 따라 연속적으로 낮춘다."""
    assist = float(np.clip(assist_gain, 0.0, 1.0))
    proximal_cost = (
        ORIENTATION_PROXIMAL_DAMPING_MAX * (1.0 - assist)
        + ORIENTATION_PROXIMAL_DAMPING_MIN * assist
    )
    costs = np.zeros(int(model.nv), dtype=float)
    for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, name)])
        costs[dof] = (
            proximal_cost if index < 4 else VIRTUAL_CENTER_WRIST_DAMPING_COST
        )
    return costs


def _smooth_pressure(value: float, start: float, full: float) -> float:
    if start <= full:
        raise ValueError("assist start must be greater than full threshold")
    normalized = float(np.clip((start - value) / (start - full), 0.0, 1.0))
    return normalized * normalized * (3.0 - 2.0 * normalized)


def orientation_limit_policy(
    min_margin_deg: float,
    assist_latched: bool,
) -> tuple[bool, float, float, float]:
    """손목 한계에 가까워질수록 근위축 허용량을 0..1로 연속 증가시킨다."""
    del assist_latched  # 서명 호환성만 유지하며 불연속 latch는 사용하지 않는다.
    pressure = _smooth_pressure(
        min_margin_deg,
        ASSIST_RELEASE_MARGIN_DEG,
        ASSIST_FULL_MARGIN_DEG,
    )
    return (
        pressure > 0.0,
        float(pressure * ASSIST_MAX),
        1.0,
        ORIENTATION_ERROR_NORMAL_MAX_DEG,
    )


class VirtualCenterOrientationTask(Task):
    """정확한 yaw-link 회전식과 손목 한계 근처의 추종 완화를 사용한다."""

    last_assist_gain = 0.0
    last_min_wrist_margin_deg = float("inf")
    last_orientation_cost_scale = 1.0
    last_orientation_error_cap_deg = ORIENTATION_ERROR_NORMAL_MAX_DEG
    last_unclipped_orientation_error_deg = 0.0
    last_wrist_jacobian_sigma_min = 1.0
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
        self.wrist_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS[4:]
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

        latched, limit_assist, cost_scale, error_cap_deg = orientation_limit_policy(
            min_margin,
            VirtualCenterOrientationTask.assist_latched,
        )
        rotation_jacobian = self.inner.compute_jacobian(configuration)[3:6]
        wrist_jacobian = rotation_jacobian[:, self.wrist_dofs]
        singular_values = np.linalg.svd(wrist_jacobian, compute_uv=False)
        sigma_min = float(np.min(singular_values)) if singular_values.size else 0.0
        singularity_assist = _smooth_pressure(
            sigma_min,
            WRIST_SINGULARITY_ASSIST_START,
            WRIST_SINGULARITY_ASSIST_FULL,
        )
        assist = 1.0 - (1.0 - limit_assist) * (1.0 - singularity_assist)
        VirtualCenterOrientationTask.assist_latched = latched
        VirtualCenterOrientationTask.last_assist_gain = assist
        VirtualCenterOrientationTask.last_wrist_jacobian_sigma_min = sigma_min
        VirtualCenterOrientationTask.last_orientation_cost_scale = cost_scale
        VirtualCenterOrientationTask.last_orientation_error_cap_deg = error_cap_deg
        self.cost[3:6] = base.ORIENTATION_COST * cost_scale

    def UpdatePolicy(self, configuration) -> float:
        """현재 자세의 연속 assist를 갱신하고 0..1 값을 반환한다."""
        self._update_limit_policy(configuration)
        return VirtualCenterOrientationTask.last_assist_gain

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
