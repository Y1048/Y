"""현재 관절 자세에서 짧은 Mink 경로를 예측하고 중간 충돌을 검사한다.

호출: virtual-center 제어기의 main -> FeasibleTargetPlanner.Plan.
입력: 모델 전체 qpos와 로봇 월드 기준 yaw 손목 목표 SE(3), 거리 m/각도 rad.
출력: 이번 주기의 next_q, 앞쪽 예측 target_q와 표시용 target_position.
Mink QP와 MuJoCo FK를 사용하며 네트워크 송신이나 모터 명령은 만들지 않는다.
"""

from dataclasses import dataclass

import mink
import mujoco
import numpy as np

import run_mink_g1_right_arm_prototype as base


@dataclass
class FeasiblePlan:
    """next_q만 실행하고 target_q의 FK를 초록 표식으로 표시하는 계획 결과.

    valid는 입력 자세/목표가 검사를 통과했다는 뜻이며 목표 도달을 보장하지 않는다.
    accepted_steps와 status를 함께 확인해야 정체와 정상 진행을 구분할 수 있다.
    """
    next_q: np.ndarray
    target_q: np.ndarray
    target_position: np.ndarray
    valid: bool
    status: str
    accepted_steps: int


class FeasibleTargetPlanner:
    """Replan from current q; execute one step, display the checked look-ahead FK.

    A local feasible path is not a global workspace projection. Intermediate
    collision samples reduce discrete QP overshoot, but are not a continuous
    collision proof or a hardware authorization.
    """

    def __init__(self, model, position_task, orientation_task, posture_task,
                 damping_task, limits, constraints, solver, clearance_m,
                 velocity_limits, horizon_steps=3):
        if horizon_steps < 1 or clearance_m <= 0:
            raise ValueError("positive look-ahead and clearance required")
        self.model = model
        self.configuration = mink.Configuration(model)
        self.validation_data = mujoco.MjData(model)
        self.position_task = position_task
        self.orientation_task = orientation_task
        self.tasks = [position_task, orientation_task, posture_task, damping_task]
        self.limits = limits
        self.constraints = constraints
        self.solver = solver
        self.clearance_m = clearance_m
        self.horizon_steps = horizon_steps
        self.geom_pairs = base._build_collision_pairs(model)[1]
        self.right_dofs = base._right_arm_dof_indices(model)
        self.frozen_dofs = base._frozen_dof_indices(model, self.right_dofs)
        self.velocity_caps = np.array([
            velocity_limits[name] for name in base.g1.RIGHT_ARM_JOINTS
        ])
        self.joint_ids = [base._joint_id(model, name) for name in base.g1.RIGHT_ARM_JOINTS]
        self.qpos_ids = [int(model.jnt_qposadr[joint]) for joint in self.joint_ids]

    def GetClearance(self, q):
        self.validation_data.qpos[:] = q
        mujoco.mj_forward(self.model, self.validation_data)
        nearest = base._nearest_pair_distance(self.model, self.validation_data, self.geom_pairs)
        return float("inf") if nearest is None else nearest[0]

    def CheckConfiguration(self, q):
        if not np.isfinite(q).all():
            return False
        for joint, address in zip(self.joint_ids, self.qpos_ids):
            low, high = self.model.jnt_range[joint]
            if self.model.jnt_limited[joint] and not low - 1e-9 <= q[address] <= high + 1e-9:
                return False
        return self.GetClearance(q) >= self.clearance_m - 1e-7

    def GetMerit(self, goal, rotation_scale):
        pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        position_error = goal.translation() - pose.translation()
        rotation_error = base._rotation_error_radians(
            goal.rotation().as_matrix(), pose.rotation().as_matrix())
        return (base.POSITION_COST ** 2 * float(position_error @ position_error)
                + rotation_scale ** 2 * rotation_error ** 2)

    def Plan(self, current_q, goal):
        """모델 qpos와 yaw-link 목표를 받아 검증된 첫 단계 및 예측 끝점을 반환한다.

        current_q는 오른팔 7개 배열이 아니라 모델 전체 qpos다. 목표 위치는 m,
        회전은 SE(3)이며, 위치/회전 오차가 줄고 중간 자세가 허용될 때만 진행한다.
        허용 경로가 없으면 현재 자세를 유지한다. 사용자 기준점을 재설정하지 않는다.
        """
        self.configuration.update(current_q)
        initial_pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        result = FeasiblePlan(current_q.copy(), current_q.copy(),
                              initial_pose.translation().copy(), False, "invalid_start", 0)
        if not self.CheckConfiguration(current_q):
            return result
        if not np.isfinite(goal.as_matrix()).all():
            result.status = "invalid_goal"
            return result
        result.valid = True
        result.status = "holding"
        current_policy = None
        current_cost = None
        for _ in range(self.horizon_steps):
            origin = self.configuration.q.copy()
            yaw = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
            roll = self.configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
            center = goal.translation() - (yaw.translation() - roll.translation())
            self.position_task.set_target(base._matrix_to_se3(roll.rotation().as_matrix(), center))
            self.orientation_task.set_target(base._matrix_to_se3(goal.rotation().as_matrix(), yaw.translation()))
            # Mink는 task 오차/Jacobian과 제한을 QP로 조립하고 solver가 푼 dq/dt를 반환한다.
            velocity = mink.solve_ik(
                self.configuration, self.tasks, base.DT, solver=self.solver,
                damping=base.QP_DAMPING, limits=self.limits, constraints=self.constraints)
            if current_policy is None:
                # Predicted future wrist margins must not latch the actual
                # controller's hysteresis or overwrite its diagnostics.
                current_policy = {
                    name: value for name, value in vars(type(self.orientation_task)).items()
                    if name.startswith("last_") or name == "assist_latched"
                }
                current_cost = self.orientation_task.cost.copy()
            if (not np.isfinite(velocity).all()
                    or np.any(np.abs(velocity[self.right_dofs]) > self.velocity_caps + 1e-6)
                    or np.any(np.abs(velocity[self.frozen_dofs]) > 1e-7)):
                result.status = "invalid_velocity"
                break
            rotation_scale = float(self.orientation_task.cost[3])
            merit = self.GetMerit(goal, rotation_scale)
            accepted = False
            # Backtrack in joint space; never change the operator reference.
            # Check intermediate FK geometry as well as the final configuration.
            for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
                self.configuration.update(origin)
                self.configuration.integrate_inplace(velocity, base.DT * fraction)
                candidate = self.configuration.q.copy()
                improvement = merit - self.GetMerit(goal, rotation_scale)
                if improvement <= max(1e-10, merit * 1e-8):
                    continue
                path_clear = True
                for interval in (0.25, 0.5, 0.75, 1.0):
                    q = origin.copy()
                    mujoco.mj_integratePos(self.model, q, velocity, base.DT * fraction * interval)
                    if not self.CheckConfiguration(q):
                        path_clear = False
                        break
                if not path_clear:
                    continue
                self.configuration.update(candidate)
                if result.accepted_steps == 0:
                    result.next_q = candidate.copy()
                result.accepted_steps += 1
                result.target_q = candidate.copy()
                result.target_position = self.configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body").translation().copy()
                result.status = "following"
                accepted = True
                break
            if not accepted:
                self.configuration.update(origin)
                result.status = "local_limit" if merit > 1e-6 else "settled"
                break
        if current_policy is not None:
            for name, value in current_policy.items():
                setattr(type(self.orientation_task), name, value)
            self.orientation_task.cost[:] = current_cost
        return result
