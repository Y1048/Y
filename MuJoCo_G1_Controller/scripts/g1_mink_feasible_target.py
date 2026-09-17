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
from g1_virtual_center_tasks import (
    hierarchical_orientation_damping_costs,
    hierarchical_position_damping_costs,
)


class PositionProgressConstraint(mink.Task):
    """같은 선형화 지점에서 1단계의 위치 변위를 보존하는 등식 제약."""

    def __init__(self, jacobian, displacement):
        super().__init__(cost=np.ones(3), gain=1.0, lm_damping=0.0)
        self.jacobian = np.asarray(jacobian, dtype=float).copy()
        self.error = -(self.jacobian @ displacement)

    def compute_error(self, configuration):
        return self.error

    def compute_jacobian(self, configuration):
        return self.jacobian


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
                 velocity_limits, horizon_steps=3,
                 require_merit_decrease=True, allow_local_detour=False):
        if horizon_steps < 1 or clearance_m <= 0:
            raise ValueError("positive look-ahead and clearance required")
        self.model = model
        self.configuration = mink.Configuration(model)
        self.validation_data = mujoco.MjData(model)
        self.position_task = position_task
        self.orientation_task = orientation_task
        self.tasks = [position_task, orientation_task, posture_task, damping_task]
        self.position_damping_task = mink.DampingTask(
            model, cost=hierarchical_position_damping_costs(model)
        )
        self.orientation_damping_task = mink.DampingTask(
            model, cost=hierarchical_orientation_damping_costs(model, 0.0)
        )
        self.position_tasks = [position_task, self.position_damping_task]
        self.orientation_tasks = [
            position_task,
            orientation_task,
            posture_task,
            self.orientation_damping_task,
        ]
        self.limits = limits
        self.constraints = constraints
        self.solver = solver
        self.clearance_m = clearance_m
        self.horizon_steps = horizon_steps
        self.require_merit_decrease = require_merit_decrease
        self.allow_local_detour = allow_local_detour
        self.detour_goal = None
        self.detour_position_target = None
        self.detour_start_position = None
        self.detour_frames = 0
        self.geom_pairs = base._build_collision_pairs(model)[1]
        self.right_dofs = base._right_arm_dof_indices(model)
        self.proximal_dofs = self.right_dofs[:4]
        self.wrist_dofs = self.right_dofs[4:]
        self.frozen_dofs = base._frozen_dof_indices(model, self.right_dofs)
        # 계층형 live 경로에서는 오른팔 내부 DOF를 hard freeze하지 않는다.
        # 두 단계 모두 비오른팔 고정과 hard limit/collision constraint만 공유한다.
        self.position_constraints = list(constraints)
        self.orientation_constraints = list(constraints)
        self.velocity_caps = np.array([
            velocity_limits[name] for name in base.g1.RIGHT_ARM_JOINTS
        ])
        self.joint_ids = [base._joint_id(model, name) for name in base.g1.RIGHT_ARM_JOINTS]
        self.qpos_ids = [int(model.jnt_qposadr[joint]) for joint in self.joint_ids]

    def _VelocityValid(self, velocity, moving_dofs):
        if not np.isfinite(velocity).all():
            return False
        if np.any(np.abs(velocity[self.right_dofs]) > self.velocity_caps + 1e-6):
            return False
        moving = set(moving_dofs)
        stationary = self.frozen_dofs + [
            dof for dof in self.right_dofs if dof not in moving
        ]
        return not np.any(np.abs(velocity[stationary]) > 1e-7)

    def _PathClear(self, origin, velocity, duration):
        for interval in (0.25, 0.5, 0.75, 1.0):
            q = origin.copy()
            mujoco.mj_integratePos(self.model, q, velocity, duration * interval)
            if not self.CheckConfiguration(q):
                return False
        return True

    def GetClearance(self, q):
        self.validation_data.qpos[:] = q
        mujoco.mj_forward(self.model, self.validation_data)
        nearest = base._nearest_pair_distance(self.model, self.validation_data, self.geom_pairs)
        return float("inf") if nearest is None else nearest[0]

    def CheckConfiguration(self, q):
        return self.CheckConfigurationWithClearance(q)[0]

    def CheckConfigurationWithClearance(self, q):
        """유효성과 이번 검사의 거리(m)를 반환한다. FK 전 거부하면 거리는 None."""
        if not np.isfinite(q).all():
            return False, None
        for joint, address in zip(self.joint_ids, self.qpos_ids):
            low, high = self.model.jnt_range[joint]
            if self.model.jnt_limited[joint] and not low - 1e-9 <= q[address] <= high + 1e-9:
                return False, None
        clearance = self.GetClearance(q)
        return clearance >= self.clearance_m - 1e-7, clearance

    def GetMerit(self, goal, rotation_scale, position_target=None):
        return (
            self.GetPositionMerit(goal, position_target)
            + self.GetRotationMerit(goal, rotation_scale)
        )

    def GetPositionMerit(self, goal, position_target=None):
        pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        if position_target is None:
            position_error = goal.translation() - pose.translation()
        else:
            center = self.configuration.get_transform_frame_to_world(
                "right_wrist_roll_link", "body"
            )
            position_error = np.asarray(position_target) - center.translation()
        return base.POSITION_COST ** 2 * float(position_error @ position_error)

    def GetPositionError(self, goal, position_target=None):
        pose = self.configuration.get_transform_frame_to_world(
            "right_wrist_yaw_link", "body"
        )
        if position_target is None:
            error = goal.translation() - pose.translation()
        else:
            center = self.configuration.get_transform_frame_to_world(
                "right_wrist_roll_link", "body"
            )
            error = np.asarray(position_target) - center.translation()
        return float(np.linalg.norm(error))

    def GetRotationMerit(self, goal, rotation_scale):
        pose = self.configuration.get_transform_frame_to_world(
            "right_wrist_yaw_link", "body"
        )
        rotation_error = base._rotation_error_radians(
            goal.rotation().as_matrix(), pose.rotation().as_matrix())
        return rotation_scale ** 2 * rotation_error ** 2

    def _PlanGoal(self, current_q, goal, position_target=None):
        """모델 qpos와 yaw-link 목표를 받아 검증된 첫 단계 및 예측 끝점을 반환한다.

        current_q는 오른팔 7개 배열이 아니라 모델 전체 qpos다. 목표 위치는 m,
        회전은 SE(3)이며, 위치/회전 오차가 줄고 중간 자세가 허용될 때만 진행한다.
        허용 경로가 없으면 현재 자세를 유지한다. 사용자 기준점을 재설정하지 않는다.
        """
        self.configuration.update(current_q)
        initial_pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        initial_position_pose = (
            self.configuration.get_transform_frame_to_world(
                "right_wrist_roll_link", "body"
            )
            if position_target is not None
            else initial_pose
        )
        result = FeasiblePlan(current_q.copy(), current_q.copy(),
                              initial_position_pose.translation().copy(),
                              False, "invalid_start", 0)
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
            center = (
                goal.translation() - (yaw.translation() - roll.translation())
                if position_target is None
                else np.asarray(position_target, dtype=float)
            )
            self.position_task.set_target(base._matrix_to_se3(roll.rotation().as_matrix(), center))
            self.orientation_task.set_target(base._matrix_to_se3(goal.rotation().as_matrix(), yaw.translation()))
            if position_target is None:
                # Backward-compatible public path: preserve the original combined QP.
                velocity = mink.solve_ik(
                    self.configuration,
                    self.tasks,
                    base.DT,
                    solver=self.solver,
                    damping=base.QP_DAMPING,
                    limits=self.limits,
                    constraints=self.constraints,
                )
                if current_policy is None:
                    current_policy = {
                        name: value
                        for name, value in vars(type(self.orientation_task)).items()
                        if name.startswith("last_") or name == "assist_latched"
                    }
                    current_cost = self.orientation_task.cost.copy()
                if not self._VelocityValid(velocity, self.right_dofs):
                    result.status = "invalid_velocity"
                    break
                rotation_scale = float(self.orientation_task.cost[3])
                merit = self.GetMerit(goal, rotation_scale)
                accepted = False
                for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
                    self.configuration.update(origin)
                    duration = base.DT * fraction
                    if not self._PathClear(origin, velocity, duration):
                        continue
                    self.configuration.integrate_inplace(velocity, duration)
                    candidate = self.configuration.q.copy()
                    improvement = merit - self.GetMerit(goal, rotation_scale)
                    merit_improved = improvement > max(1e-10, merit * 1e-8)
                    if self.require_merit_decrease and not merit_improved:
                        continue
                    if result.accepted_steps == 0:
                        result.next_q = candidate.copy()
                    result.accepted_steps += 1
                    result.target_q = candidate.copy()
                    result.target_position = self.configuration.get_transform_frame_to_world(
                        "right_wrist_yaw_link", "body"
                    ).translation().copy()
                    result.status = (
                        "following" if merit_improved else "following_tangent"
                    )
                    accepted = True
                    break
                if not accepted:
                    self.configuration.update(origin)
                    result.status = "local_limit" if merit > 1e-6 else "settled"
                    break
                continue

            # 두 QP 모두 origin에서 풀고 최종 속도 하나만 적분한다.
            position_velocity = mink.solve_ik(
                self.configuration, self.position_tasks, base.DT, solver=self.solver,
                damping=base.QP_DAMPING, limits=self.limits,
                constraints=self.position_constraints,
            )
            if not self._VelocityValid(position_velocity, self.right_dofs):
                result.status = "invalid_velocity"
                break
            if current_policy is None:
                current_policy = {
                    name: value for name, value in vars(type(self.orientation_task)).items()
                    if name.startswith("last_") or name == "assist_latched"
                }
                current_cost = self.orientation_task.cost.copy()
            assist_gain = self.orientation_task.UpdatePolicy(self.configuration)
            self.orientation_damping_task.cost[:] = hierarchical_orientation_damping_costs(
                self.model, assist_gain
            )
            progress = PositionProgressConstraint(
                self.position_task.compute_jacobian(self.configuration)[:3],
                position_velocity * base.DT,
            )
            velocity = mink.solve_ik(
                self.configuration, self.orientation_tasks, base.DT, solver=self.solver,
                damping=base.QP_DAMPING, limits=self.limits,
                constraints=[*self.orientation_constraints, progress],
            )
            if not self._VelocityValid(velocity, self.right_dofs):
                result.status = "invalid_velocity"
                break
            rotation_scale = float(self.orientation_task.cost[3])
            merit = self.GetMerit(goal, rotation_scale, position_target)
            position_merit = self.GetPositionMerit(goal, position_target)
            rotation_merit = self.GetRotationMerit(goal, rotation_scale)
            accepted = False
            for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
                self.configuration.update(origin)
                duration = base.DT * fraction
                if not self._PathClear(origin, velocity, duration):
                    continue
                self.configuration.integrate_inplace(velocity, duration)
                candidate = self.configuration.q.copy()
                final_position = self.GetPositionMerit(goal, position_target)
                final_rotation = self.GetRotationMerit(goal, rotation_scale)
                moved = bool(np.max(np.abs(candidate - origin)) > 1e-12)
                step_improved = moved and (
                    position_merit - final_position > max(1e-10, position_merit * 1e-8)
                    or (final_position <= position_merit + 1e-10
                        and rotation_merit - final_rotation > max(1e-10, rotation_merit * 1e-8))
                )
                if self.require_merit_decrease and not step_improved:
                    continue
                if result.accepted_steps == 0:
                    result.next_q = candidate.copy()
                result.accepted_steps += 1
                result.target_q = candidate.copy()
                result.target_position = self.configuration.get_transform_frame_to_world(
                    "right_wrist_roll_link", "body"
                ).translation().copy()
                result.status = "following" if step_improved else "following_tangent"
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
            self.configuration.update(result.next_q)
            self.orientation_task.UpdatePolicy(self.configuration)
        return result

    def ResetDetour(self):
        self.detour_goal = None
        self.detour_position_target = None
        self.detour_start_position = None
        self.detour_frames = 0

    def Plan(self, current_q, goal, position_target=None):
        """Track the operator goal and locally escape a blocked simulation QP."""
        if not self.allow_local_detour:
            return self._PlanGoal(current_q, goal, position_target)

        self.configuration.update(current_q)
        current_pose = self.configuration.get_transform_frame_to_world(
            "right_wrist_roll_link" if position_target is not None
            else "right_wrist_yaw_link",
            "body",
        )
        if self.detour_goal is not None:
            plan = self._PlanGoal(
                current_q, self.detour_goal, self.detour_position_target
            )
            self.detour_frames += 1
            self.configuration.update(plan.next_q)
            next_pose = self.configuration.get_transform_frame_to_world(
                "right_wrist_yaw_link", "body"
            )
            travelled = float(np.linalg.norm(
                next_pose.translation() - self.detour_start_position
            ))
            if plan.accepted_steps == 0 or travelled >= 0.04 or self.detour_frames >= 30:
                self.ResetDetour()
            if plan.accepted_steps > 0:
                plan.status = "detour_following"
            return plan

        direct = self._PlanGoal(current_q, goal, position_target)
        if direct.accepted_steps > 0 or not direct.valid:
            return direct
        requested_position = (
            goal.translation() if position_target is None
            else np.asarray(position_target, dtype=float)
        )
        if np.linalg.norm(requested_position - current_pose.translation()) < 0.02:
            return direct

        # Right-arm robot frame: negative Y moves away from the torso.
        directions = (
            np.array([0.0, -1.0, 0.0]),
            np.array([0.0, -0.70710678, 0.70710678]),
            np.array([0.70710678, -0.70710678, 0.0]),
        )
        for direction in directions:
            waypoint_position = current_pose.translation() + 0.08 * direction
            waypoint = base._matrix_to_se3(
                goal.rotation().as_matrix(), waypoint_position
            )
            candidate = self._PlanGoal(
                current_q,
                waypoint,
                waypoint_position if position_target is not None else None,
            )
            if candidate.accepted_steps == 0:
                continue
            self.detour_goal = waypoint
            self.detour_position_target = (
                waypoint_position.copy() if position_target is not None else None
            )
            self.detour_start_position = current_pose.translation().copy()
            self.detour_frames = 1
            candidate.status = "detour_following"
            return candidate
        return direct
