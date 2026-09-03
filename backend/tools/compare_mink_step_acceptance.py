"""Offline IK acceptance/collision/merit comparisons; no network or robot output."""

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
from mink.limits.collision_avoidance_limit import compute_contact_normal_jacobian

from verify_feasible_target import BuildPlanner, probe
from compare_recorded_pose_speeds import GetActiveSegments, GetRecordedTargets, GetTargetIndex


class WristPositionTask(probe.mink.Task):
    """OFFLINE: exact world-space point error at the unchanged yaw-wrist origin."""

    def __init__(self):
        super().__init__(cost=np.full(3, probe.base.POSITION_COST),
            gain=probe.base.FRAME_GAIN, lm_damping=probe.base.LM_DAMPING)
        self.target_position = None

    def set_target(self, target):
        self.target_position = target.translation().copy()

    def compute_error(self, configuration):
        if self.target_position is None:
            raise ValueError("Wrist position target not set")
        pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        return self.target_position - pose.translation()

    def compute_jacobian(self, configuration):
        # 표시/오차 검사와 같은 손목 원점의 정확한 위치 미분을 사용한다.
        pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        jacobian = configuration.get_frame_jacobian("right_wrist_yaw_link", "body")
        return -pose.rotation().as_matrix() @ jacobian[:3]


class FullOrientationErrorTask(probe.live.VirtualCenterOrientationTask):
    """OFFLINE: keep limits/weights but use the same rotation error as merit."""

    def compute_error(self, configuration):
        return self.inner.compute_error(configuration)


class IncrementCollisionLimit(probe.mink.CollisionAvoidanceLimit):
    """OFFLINE candidate: express the velocity-form bound in QP increment units."""

    def compute_qp_inequalities(self, configuration, dt):
        inequality = super().compute_qp_inequalities(configuration, dt)
        return probe.mink.limits.Constraint(G=inequality.G, h=inequality.h * dt)


class ResolvedCollisionLimit(IncrementCollisionLimit):
    """OFFLINE: resolve isolated mesh zeros and their Jacobian from one witness."""

    def __init__(self, *args, recover_reserve=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.recover_reserve = recover_reserve
        self.probe_data = probe.mujoco.MjData(self.model)
        self.probe_addresses = [int(self.model.jnt_qposadr[probe.base._joint_id(self.model, name)])
            for name in dict.fromkeys(probe.base.g1.RIGHT_ARM_JOINTS + probe.base.g1.LEFT_ARM_JOINTS)]

    def ResolveWitness(self, configuration, pair):
        origin = configuration.q.copy()
        best = None
        points = np.zeros(6)
        # 기존 거리 검사와 같은 양팔 미소변위에서 최소 거리를 선택한다.
        # 원래 configuration은 건드리지 않고 해당 witness의 Jacobian도 함께 구한다.
        for address in self.probe_addresses:
            for direction in (-1.0, 1.0):
                self.probe_data.qpos[:] = origin
                self.probe_data.qpos[address] += direction * probe.base.ZERO_DISTANCE_PROBE_RAD
                probe.mujoco.mj_forward(self.model, self.probe_data)
                distance = probe.mujoco.mj_geomDistance(self.model, self.probe_data,
                    *pair, self.collision_detection_distance, points)
                if not np.isfinite(distance) or abs(distance) <= probe.base.ZERO_DISTANCE_TOLERANCE_M:
                    continue
                if best is None or distance < best[0]:
                    best = (float(distance), points.copy(), self.probe_data.qpos.copy())
        if best is None:
            raise RuntimeError("Unresolved collision witness; do not execute candidate")
        distance, points, q = best
        if distance >= self.collision_detection_distance:
            return distance, np.zeros(self.model.nv)
        self.probe_data.qpos[:] = q
        probe.mujoco.mj_forward(self.model, self.probe_data)
        jacobian = compute_contact_normal_jacobian(self.model, self.probe_data, *pair,
            points, np.zeros(3), np.zeros((3, self.model.nv)), np.zeros((3, self.model.nv)))
        if not np.isfinite(jacobian).all():
            raise RuntimeError("Invalid collision Jacobian; do not execute candidate")
        return distance, jacobian

    def compute_qp_inequalities(self, configuration, dt):
        inequality = super().compute_qp_inequalities(configuration, dt)
        for index, pair in enumerate(self.geom_id_pairs):
            distance = probe.mujoco.mj_geomDistance(self.model, configuration.data, *pair,
                self.collision_detection_distance, None)
            if abs(distance) > probe.base.ZERO_DISTANCE_TOLERANCE_M:
                if distance < self.collision_detection_distance:
                    inequality.h[index] = (self.gain * (distance - self.minimum_distance_from_collisions)
                        + self.bound_relaxation * dt)
                continue
            if probe.base._has_exact_geom_contact(configuration.data, *pair):
                continue
            distance, jacobian = self.ResolveWitness(configuration, pair)
            if distance >= self.collision_detection_distance:
                inequality.G[index] = 0
                inequality.h[index] = np.inf
            else:
                inequality.G[index] = (-1 if distance >= 0 else 1) * jacobian
                inequality.h[index] = (self.gain * (distance - self.minimum_distance_from_collisions)
                    + self.bound_relaxation * dt)
        if not self.recover_reserve:
            # 실험 여유 안쪽에서는 정지/접선 이동도 허용하되 20 mm FK 검사는 유지한다.
            inequality.h[:] = np.maximum(inequality.h, self.bound_relaxation * dt)
        return inequality


def GetLimitAvoidanceStep(endpoint, direction, lower, upper, low, high, margin):
    """Minimize squared near-limit intrusion; choose the nearest minimizer to zero."""
    if not np.isfinite(margin) or margin <= 0 or not np.isfinite([low, high]).all() or low > high:
        raise ValueError("Invalid limit-avoidance margin or feasible interval")
    band = np.minimum(margin, (upper - lower) / 2)

    def GetResidual(step):
        point = endpoint + direction * step
        return point - np.clip(point, lower + band, upper - band)

    def GetDerivative(step):
        return float(direction @ GetResidual(step))

    residual = GetResidual(0)
    origin = float(np.clip(0.0, low, high))
    derivative = GetDerivative(origin)
    step = origin
    # 볼록한 1차원 목적함수이므로 미분의 부호로 최소 이동량을 찾는다.
    if derivative > 1e-12:
        left, right = low, origin
        for _ in range(60):
            middle = (left + right) / 2
            if GetDerivative(middle) > 0:
                right = middle
            else:
                left = middle
        step = (left + right) / 2
    elif derivative < -1e-12:
        left, right = origin, high
        for _ in range(60):
            middle = (left + right) / 2
            if GetDerivative(middle) < 0:
                left = middle
            else:
                right = middle
        step = (left + right) / 2
    return step, {"limit_margin_deg": math.degrees(margin),
        "active_joint_indices": np.flatnonzero(np.abs(residual) > 1e-12).tolist(),
        "limit_cost_before_rad2": float(residual @ residual),
        "limit_cost_after_rad2": float(GetResidual(step) @ GetResidual(step))}


def CenterRedundancy(planner, velocity, limit_margin_rad=None):
    """OFFLINE: center joints without changing the first-order wrist increment."""
    configuration = planner.configuration
    jacobian = configuration.get_frame_jacobian("right_wrist_yaw_link", "body")[:, planner.right_dofs]
    _, singular_values, vectors = np.linalg.svd(jacobian, full_matrices=True)
    if singular_values[-1] < 1e-6:
        return velocity.copy(), {"status": "rank_deficient"}
    direction = np.zeros(planner.model.nv)
    direction[planner.right_dofs] = vectors[-1]
    increment = velocity * probe.base.DT
    low, high = -np.inf, np.inf
    for limit in planner.limits:
        inequality = limit.compute_qp_inequalities(configuration, probe.base.DT)
        if inequality.G is None:
            continue
        if not np.isfinite(inequality.G).all() or np.isnan(inequality.h).any() or np.isneginf(inequality.h).any():
            return velocity.copy(), {"status": "invalid_constraint"}
        for coefficient, remainder in zip(inequality.G @ direction, inequality.h - inequality.G @ increment):
            if not np.isfinite(remainder):
                continue
            if abs(coefficient) < 1e-12:
                if remainder < -1e-8:
                    return velocity.copy(), {"status": "primary_constraint_residual"}
            elif coefficient > 0:
                high = min(high, remainder / coefficient)
            else:
                low = max(low, remainder / coefficient)
    if low > high or low > 1e-7 or high < -1e-7:
        return velocity.copy(), {"status": "no_feasible_nullspace_interval"}
    lower, upper = planner.model.jnt_range[planner.joint_ids].T
    half_range = (upper - lower) / 2
    endpoint = configuration.q[planner.qpos_ids] + increment[planner.right_dofs]
    normalized = (endpoint - (upper + lower) / 2) / half_range
    slope = direction[planner.right_dofs] / half_range
    detail = {}
    if limit_margin_rad is None:
        step = float(np.clip(-(slope @ normalized) / (slope @ slope), low, high))
    else:
        if not np.isfinite([low, high]).all():
            return velocity.copy(), {"status": "invalid_limit_interval"}
        step, detail = GetLimitAvoidanceStep(endpoint, direction[planner.right_dofs],
            lower, upper, low, high, limit_margin_rad)
    centered = increment + direction * step
    return centered / probe.base.DT, {"status": "centered", "step_rad": step,
        "pose_increment_difference": float(np.linalg.norm(jacobian @ (centered - increment)[planner.right_dofs])),
        "normalized_cost_before": float(normalized @ normalized),
        "normalized_cost_after": float(np.sum((normalized + slope * step) ** 2)), **detail}


def EvaluateStep(planner, current_q, goal, require_merit=True, audit=False, consistent_position=False,
                 center_redundancy=False, limit_margin_rad=None, diagnostic_geometry=True):
    """Audit the production planner's FIRST step; no predicted step is executed."""
    base = probe.base
    configuration = planner.configuration
    configuration.update(current_q)
    result = {"status": "invalid_start", "fraction": 0.0, "merit_rejections": 0,
              "geometry_rejections": 0, "merit_only_block": False,
              "minimum_path_clearance_mm": None}
    if not planner.CheckConfiguration(current_q):
        return current_q.copy(), result
    if not np.isfinite(goal.as_matrix()).all():
        result["status"] = "invalid_goal"
        return current_q.copy(), result
    yaw = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    roll = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
    center = goal.translation() - (yaw.translation() - roll.translation())
    planner.position_task.set_target(goal if consistent_position else base._matrix_to_se3(roll.rotation().as_matrix(), center))
    planner.orientation_task.set_target(base._matrix_to_se3(goal.rotation().as_matrix(), yaw.translation()))
    velocity = probe.mink.solve_ik(configuration, planner.tasks, base.DT,
        solver=planner.solver, damping=base.QP_DAMPING,
        limits=planner.limits, constraints=planner.constraints)
    if (not np.isfinite(velocity).all()
            or np.any(np.abs(velocity[planner.right_dofs]) > planner.velocity_caps + 1e-6)
            or np.any(np.abs(velocity[planner.frozen_dofs]) > 1e-7)):
        result["status"] = "invalid_velocity"
        return current_q.copy(), result
    if center_redundancy:
        primary_velocity = velocity.copy()
        velocity, result["redundancy"] = CenterRedundancy(planner, velocity, limit_margin_rad)
        if (not np.isfinite(velocity).all()
                or np.any(np.abs(velocity[planner.right_dofs]) > planner.velocity_caps + 1e-6)
                or np.any(np.abs(velocity[planner.frozen_dofs]) > 1e-7)):
            velocity = primary_velocity
            result["redundancy_fallback"] = True
    rotation_scale = float(planner.orientation_task.cost[3])
    merit = planner.GetMerit(goal, rotation_scale)
    geometry_feasible = False
    for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
        configuration.update(current_q)
        configuration.integrate_inplace(velocity, base.DT * fraction)
        candidate = configuration.q.copy()
        improvement = merit - planner.GetMerit(goal, rotation_scale)
        merit_ok = improvement > max(1e-10, merit * 1e-8)
        if require_merit and not merit_ok and not diagnostic_geometry:
            result["merit_rejections"] += 1
            continue
        path_ok = True
        minimum = float("inf")
        # 오차 검사에서 탈락한 후보도 충돌 검사해 중단 원인을 구분한다.
        for interval in (0.25, 0.5, 0.75, 1.0):
            q = current_q.copy()
            probe.mujoco.mj_integratePos(planner.model, q, velocity, base.DT * fraction * interval)
            if not planner.CheckConfiguration(q):
                path_ok = False
                break
            minimum = min(minimum, planner.GetClearance(q) * 1000)
        result["merit_rejections"] += int(not merit_ok)
        result["geometry_rejections"] += int(not path_ok)
        geometry_feasible |= path_ok
        if path_ok and (merit_ok or not require_merit):
            result.update(status="accepted", fraction=fraction,
                          minimum_path_clearance_mm=minimum)
            return candidate, result
    configuration.update(current_q)
    result["status"] = ("merit_hold" if geometry_feasible else "geometry_hold") if diagnostic_geometry else "no_accepted_step"
    result["merit_only_block"] = geometry_feasible and require_merit
    if audit and not geometry_feasible:
        result["boundary_audit"] = InspectBoundary(planner, current_q, velocity)
    if center_redundancy:
        candidate, fallback = EvaluateStep(planner, current_q, goal, require_merit, audit, consistent_position,
                                          diagnostic_geometry=diagnostic_geometry)
        fallback["redundancy"] = result.get("redundancy", {})
        fallback["redundancy_fallback"] = True
        return candidate, fallback
    return current_q.copy(), result


def InspectBoundary(planner, q, velocity):
    """Compare the QP increment inequality with the independent FK check."""
    model = planner.model
    planner.configuration.update(q)
    collision = next(limit for limit in planner.limits
                     if isinstance(limit, probe.mink.CollisionAvoidanceLimit))
    inequality = collision.compute_qp_inequalities(planner.configuration, probe.base.DT)
    finite = np.isfinite(inequality.h)
    residual = inequality.G @ (velocity * probe.base.DT) - inequality.h
    details = {"q": q.tolist(), "velocity_rad_s": velocity.tolist(),
               "guard_pair_count": len(planner.geom_pairs),
               "qp_pair_count": len(collision.geom_id_pairs),
               "maximum_finite_qp_residual": float(np.max(residual[finite])) if finite.any() else None,
               "candidates": []}
    for fraction in (0.0, 1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.0078125):
        candidate = q.copy()
        probe.mujoco.mj_integratePos(model, candidate, velocity, probe.base.DT * fraction)
        clearance = planner.GetClearance(candidate)
        nearest = probe.base._nearest_pair_distance(model, planner.validation_data, planner.geom_pairs)
        pair = tuple(sorted(nearest[1:])) if nearest else None
        row = collision.geom_id_pairs.index(pair) if pair in collision.geom_id_pairs else None
        margin = min(min(candidate[address] - model.jnt_range[joint, 0],
                         model.jnt_range[joint, 1] - candidate[address])
                     for joint, address in zip(planner.joint_ids, planner.qpos_ids))
        details["candidates"].append({"fraction": fraction, "clearance_mm": clearance * 1000,
            "joint_margin_deg": math.degrees(margin),
            "nearest_bodies": [probe.mujoco.mj_id2name(model, probe.mujoco.mjtObj.mjOBJ_BODY,
                int(model.geom_bodyid[geom])) for geom in pair] if pair else [],
            "qp_pair_index": row,
            "qp_bound": float(inequality.h[row]) if row is not None and np.isfinite(inequality.h[row]) else None,
            "qp_row_dot_increment": float(inequality.G[row] @ (velocity * probe.base.DT)) if row is not None else None})
    return details


def EvaluateLookahead(planner, current_q, goal, require_merit=True, audit=False,
                      consistent_position=False, center_redundancy=False,
                      limit_margin_rad=None, horizon_steps=3, diagnostic_geometry=True):
    """Offline runtime-contract adapter: execute one step, expose checked preview FK."""
    if horizon_steps < 1:
        raise ValueError("Positive lookahead horizon required")
    next_q, decision = EvaluateStep(planner, current_q, goal, require_merit, audit,
        consistent_position, center_redundancy, limit_margin_rad, diagnostic_geometry)
    # 이 클래스의 메서드는 하위 클래스가 아니라 원래 클래스의 상태를 갱신한다.
    policy_owner = probe.live.VirtualCenterOrientationTask
    policy = {name: value for name, value in vars(policy_owner).items()
              if name.startswith("last_") or name == "assist_latched"}
    cost = planner.orientation_task.cost.copy()
    preview = next_q.copy()
    accepted = int(decision["status"] == "accepted")
    preview_status = decision["status"]
    clearance = planner.GetClearance(next_q) * 1000
    if decision["minimum_path_clearance_mm"] is not None:
        clearance = min(clearance, decision["minimum_path_clearance_mm"])
    try:
        if accepted:
            for _ in range(horizon_steps - 1):
                candidate, prediction = EvaluateStep(planner, preview, goal, require_merit,
                    False, consistent_position, center_redundancy, limit_margin_rad, diagnostic_geometry)
                preview_status = prediction["status"]
                if preview_status != "accepted":
                    break
                preview = candidate
                accepted += 1
                clearance = min(clearance, prediction["minimum_path_clearance_mm"])
        planner.configuration.update(preview)
        pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        preview_position = pose.translation().copy()
        planner.configuration.update(next_q)
        executed = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        decision.update(lookahead_steps=accepted, lookahead_final_status=preview_status,
            lookahead_target_position=preview_position.tolist(),
            lookahead_target_qpos=preview.tolist(),
            lookahead_target_right_q_rad=preview[planner.qpos_ids].tolist(),
            lookahead_clearance_mm=clearance,
            lookahead_gap_cm=float(np.linalg.norm(preview_position - executed.translation()) * 100))
    finally:
        for name, value in policy.items():
            setattr(policy_owner, name, value)
        planner.orientation_task.cost[:] = cost
        planner.configuration.update(next_q)
    return next_q, decision


def InspectMerit(planner, q, goal):
    """Compare frozen-target QP gradients with the actual external-wrist merit."""
    configuration = planner.configuration
    configuration.update(q)
    velocity = probe.mink.solve_ik(configuration, planner.tasks, probe.base.DT,
        solver=planner.solver, damping=probe.base.QP_DAMPING,
        limits=planner.limits, constraints=planner.constraints)
    scale = float(planner.orientation_task.cost[3])
    epsilon = 1e-6
    numeric = np.zeros(planner.model.nv)
    tasks = []
    for task in planner.tasks:
        error = task.compute_error(configuration)
        jacobian = task.compute_jacobian(configuration)
        gradient = 2 * jacobian.T @ (task.cost ** 2 * error)
        tasks.append({"task": type(task).__name__,
            "gradient_right": gradient[planner.right_dofs].tolist(),
            "directional_derivative": float(gradient @ velocity),
            "weighted_error_squared": float(np.sum((task.cost * error) ** 2))})
    try:
        # QP의 가상 중심 목표는 고정하고 실제 손목 평가함수를 미분한다.
        for dof in planner.right_dofs:
            axis = np.zeros(planner.model.nv)
            axis[dof] = 1
            values = []
            for sign in (-1, 1):
                candidate = q.copy()
                probe.mujoco.mj_integratePos(planner.model, candidate, axis, sign * epsilon)
                configuration.update(candidate)
                values.append(planner.GetMerit(goal, scale))
            numeric[dof] = (values[1] - values[0]) / (2 * epsilon)
    finally:
        configuration.update(q)
    return {"q": q.tolist(), "goal_matrix": goal.as_matrix().tolist(),
        "merit": planner.GetMerit(goal, scale), "orientation_scale": scale,
        "actual_gradient_right": numeric[planner.right_dofs].tolist(),
        "actual_directional_derivative": float(numeric @ velocity),
        "velocity_right_rad_s": velocity[planner.right_dofs].tolist(),
        "tasks": tasks}


def InspectEndpointSolutions(planner, q, goal):
    """Search endpoints only. A valid endpoint is NOT a safe connecting path."""
    from scipy.optimize import least_squares

    configuration = probe.mink.Configuration(planner.model)
    orientation = probe.mink.FrameTask("right_wrist_yaw_link", "body", 0, 1)
    orientation.set_target(goal)
    lower, upper = planner.model.jnt_range[planner.joint_ids].T
    generator = np.random.default_rng(20260903)
    seeds = [q[planner.qpos_ids], (lower + upper) / 2]
    seeds.extend(generator.uniform(lower, upper) for _ in range(10))

    def GetResidual(joints):
        candidate = q.copy()
        candidate[planner.qpos_ids] = joints
        configuration.update(candidate)
        pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        return np.concatenate((probe.base.POSITION_COST * (goal.translation() - pose.translation()),
            0.5 * orientation.compute_error(configuration)[3:]))

    endpoints = []
    for index, seed in enumerate(seeds):
        solution = least_squares(GetResidual, np.clip(seed, lower + 1e-10, upper - 1e-10),
            bounds=(lower, upper), max_nfev=300, ftol=1e-10, xtol=1e-10, gtol=1e-10)
        residual = GetResidual(solution.x)
        candidate = configuration.q.copy()
        position_cm = float(np.linalg.norm(residual[:3]) / probe.base.POSITION_COST * 100)
        rotation_deg = float(np.rad2deg(np.linalg.norm(residual[3:]) / 0.5))
        valid = planner.CheckConfiguration(candidate)
        endpoints.append({"seed": index, "q": candidate.tolist(),
            "position_cm": position_cm, "rotation_deg": rotation_deg,
            "clearance_mm": planner.GetClearance(candidate) * 1000,
            "configuration_valid": bool(valid), "iterations": int(solution.nfev),
            "pose_match": bool(valid and position_cm < 0.1 and rotation_deg < 1)})
    return {"seed": 20260903, "robot_command": False,
        "boundary": "Joint-bounded least squares with final FK collision checks only. No path, dynamics or safety authorization; no match is not an impossibility proof.",
        "endpoints": endpoints}


def Summarize(samples, dt):
    speed = np.array([s["speed_deg_s"] for s in samples])
    stalled = (speed.max(axis=1) < 0.1) & np.array([
        s["position_cm"] > 1 or s["rotation_deg"] > 5 for s in samples])
    longest = current = 0
    for value in stalled:
        current = current + 1 if value else 0
        longest = max(longest, current)
    tail = samples[-min(60, len(samples)):]
    return {
        "position_cm_p50_p95_max": np.percentile([s["position_cm"] for s in samples], [50, 95, 100]).tolist(),
        "rotation_deg_p50_p95_max": np.percentile([s["rotation_deg"] for s in samples], [50, 95, 100]).tolist(),
        "stalled_with_error_s": float(np.sum(stalled) * dt),
        "longest_stall_s": longest * dt,
        "last_second_max_joint_speed_deg_s": max(max(s["speed_deg_s"]) for s in tail),
        "max_abs_joint_speed_deg_s": speed.max(axis=0).tolist(),
        "max_joint_velocity_step_deg_s": float(np.max(np.abs(np.diff(
            np.array([s["signed_speed_deg_s"] for s in samples]), axis=0)))) if len(samples) > 1 else 0,
        "minimum_clearance_mm": min(s["clearance_mm"] for s in samples),
        "final_position_cm": samples[-1]["position_cm"],
        "final_rotation_deg": samples[-1]["rotation_deg"],
        "decisions": dict(Counter(s["decision"]["status"] for s in samples)),
        "merit_only_blocked_steps": sum(s["decision"]["merit_only_block"] for s in samples),
        "joint_minimum_margin_deg": np.min([s["joint_margin_deg"] for s in samples], axis=0).tolist(),
        "joint_within_5deg_limit_s": (np.sum(np.array([s["joint_margin_deg"] for s in samples]) < 5, axis=0) * dt).tolist(),
    }


def RunVariant(model, initial_q, goals, require_merit, hold_s=6.0, increment_bound=False, reserve_m=0.0,
               resolve_witness=False, consistent_position=False, task_damping=None, cartesian_position=False,
               full_orientation=False, recover_reserve=True, center_redundancy=False, limit_margin_rad=None,
               horizon_steps=1):
    planner = BuildPlanner(model, initial_q)
    if consistent_position:
        planner.position_task = probe.mink.FrameTask("right_wrist_yaw_link", "body", probe.base.POSITION_COST, 0,
            gain=probe.base.FRAME_GAIN, lm_damping=probe.base.LM_DAMPING)
        planner.tasks[0] = planner.position_task
    if cartesian_position:
        planner.position_task = WristPositionTask()
        planner.tasks[0] = planner.position_task
        consistent_position = True
    if full_orientation:
        planner.orientation_task = FullOrientationErrorTask(model)
        planner.tasks[1] = planner.orientation_task
    if task_damping is not None:
        planner.position_task.lm_damping = task_damping
        planner.orientation_task.lm_damping = task_damping
    if increment_bound:
        for index, limit in enumerate(planner.limits):
            if isinstance(limit, probe.mink.CollisionAvoidanceLimit):
                collision_class = ResolvedCollisionLimit if resolve_witness else IncrementCollisionLimit
                planner.limits[index] = collision_class(model,
                    geom_pairs=probe.base._build_collision_pairs(model)[0], gain=limit.gain,
                    minimum_distance_from_collisions=limit.minimum_distance_from_collisions + reserve_m,
                    collision_detection_distance=limit.collision_detection_distance,
                    bound_relaxation=limit.bound_relaxation, broadphase=limit.broadphase,
                    **({"recover_reserve": recover_reserve} if resolve_witness else {}))
    times, targets = GetRecordedTargets(goals)
    dt = probe.base.DT
    duration = max(dt, float(times[-1]))
    q = initial_q.copy()
    planner.configuration.update(q)
    return_goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    phases = {name: [] for name in ("recorded", "hold", "return")}
    frozen_max = 0.0
    samples = []
    audited_phases = set()
    held_goal_audit = None
    step_times_ms = []
    for index in range(math.ceil((duration + 2 * hold_s) / dt)):
        seconds = index * dt
        phase = "recorded" if seconds < duration else "hold" if seconds < duration + hold_s else "return"
        goal = targets[GetTargetIndex(times, seconds, 1.0)] if phase != "return" else return_goal
        if phase == "return" and held_goal_audit is None:
            held_goal_audit = InspectMerit(planner, q, targets[-1])
        started = time.perf_counter()
        if horizon_steps == 1:
            candidate, decision = EvaluateStep(planner, q, goal, require_merit, phase not in audited_phases,
                consistent_position, center_redundancy, limit_margin_rad)
        else:
            candidate, decision = EvaluateLookahead(planner, q, goal, require_merit, phase not in audited_phases,
                consistent_position, center_redundancy, limit_margin_rad, horizon_steps)
        step_times_ms.append((time.perf_counter() - started) * 1000)
        if "boundary_audit" in decision:
            audited_phases.add(phase)
        velocity = np.zeros(model.nv)
        probe.mujoco.mj_differentiatePos(model, velocity, dt, q, candidate)
        frozen_max = max(frozen_max, float(np.max(np.abs(velocity[planner.frozen_dofs]))))
        planner.configuration.update(candidate)
        pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        clearance = min(planner.GetClearance(q) * 1000, planner.GetClearance(candidate) * 1000,
                        decision["minimum_path_clearance_mm"] or float("inf"))
        signed = np.rad2deg(velocity[planner.right_dofs])
        sample = {"time_s": seconds, "phase": phase, "decision": decision,
                  "qpos": candidate.tolist(),
                  "right_q_rad": candidate[planner.qpos_ids].tolist(),
                  "joint_margin_deg": np.rad2deg(np.minimum(
                      candidate[planner.qpos_ids] - model.jnt_range[planner.joint_ids, 0],
                      model.jnt_range[planner.joint_ids, 1] - candidate[planner.qpos_ids])).tolist(),
                  "position_cm": float(np.linalg.norm(goal.translation() - pose.translation()) * 100),
                  "rotation_deg": math.degrees(probe.base._rotation_error_radians(
                      goal.rotation().as_matrix(), pose.rotation().as_matrix())),
                  "clearance_mm": clearance, "signed_speed_deg_s": signed.tolist(),
                  "speed_deg_s": np.abs(signed).tolist()}
        phases[phase].append(sample)
        samples.append(sample)
        q = candidate
    joint_trace = np.array([sample["right_q_rad"] for sample in samples])
    return {"phases": {name: Summarize(rows, dt) for name, rows in phases.items()},
            "horizon_steps": horizon_steps,
            "minimum_lookahead_clearance_mm": min((s["decision"]["lookahead_clearance_mm"] for s in samples
                if "lookahead_clearance_mm" in s["decision"]), default=None),
            "maximum_lookahead_gap_cm": max((s["decision"].get("lookahead_gap_cm", 0) for s in samples), default=0),
            "maximum_joint_excursion_deg": np.rad2deg(np.max(np.abs(
                joint_trace - initial_q[planner.qpos_ids]), axis=0)).tolist(),
            "held_goal_audit": held_goal_audit,
            "first_step_ms_p50_p95_max": np.percentile(step_times_ms, [50, 95, 100]).tolist(),
            "maximum_frozen_velocity_rad_s": frozen_max}, samples


def GetWristOnlySegments(model):
    """Use known FK-reachable wrist cycles from the existing kinematics regression."""
    initial = probe.base._initial_configuration(model)
    all_addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                     for name in probe.base.g1.G1_29_JOINTS]
    right_addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                       for name in probe.base.g1.RIGHT_ARM_JOINTS]
    initial[right_addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
    configuration = probe.mink.Configuration(model)
    for index in (4, 5, 6):
        packets = []
        for seconds in np.linspace(0, 12, 721):
            q = initial.copy()
            q[right_addresses[index]] += math.radians(25) * math.sin(2 * math.pi * seconds / 12)
            configuration.update(q)
            goal = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
            packets.append({"offset_s": float(seconds), "value": {"right_arm": {
                "target_rotation_matrix_robot": goal.rotation().as_matrix().tolist(),
                "target_position": goal.translation().tolist()}}})
        yield {"value": {"all_joint_q_rad": initial[all_addresses].tolist()}}, packets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--segment", type=int, help="One-based active segment; default: all")
    parser.add_argument("--horizon-steps", type=int, choices=(1, 3), default=1,
                        help="3 mirrors the stateful checked-preview contract; only first step is executed")
    parser.add_argument("--wrist-only", action="store_true",
                        help="Use synthetic FK wrist cycles, not capture targets; 1=roll, 2=pitch, 3=yaw")
    parser.add_argument("--endpoint-audit", type=Path,
                        help="Existing result JSON: inspect its held goals only, without replay")
    parser.add_argument("--variants", nargs="+", choices=("current_merit", "geometry_only", "increment_bound", "increment_reserve", "resolved_witness", "resolved_no_merit", "consistent_wrist", "resolved_damped", "exact_cartesian", "consistent_merit", "consistent_tangent", "nullspace_center", "limit_avoidance"),
                        default=["current_merit", "geometry_only"])
    args = parser.parse_args()
    if args.wrist_only and args.endpoint_audit:
        parser.error("Wrist-only cycles cannot be combined with a captured endpoint audit")
    manifest, packets = probe._decode_capture(args.capture)
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    qpos = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    report = {"capture_id": manifest["capture_id"], "robot_command": False,
              "comparison_revision": "selective-limit-avoidance-v6-lookahead",
              "model_xml_path": str(probe.base.g1.DEMO_XML),
              "model_xml_sha256": hashlib.sha256(Path(probe.base.g1.DEMO_XML).read_bytes()).hexdigest(),
              "mujoco_version": probe.mujoco.__version__,
              "horizon_steps": args.horizon_steps,
              "input_kind": "synthetic_fk_wrist_cycles_not_capture" if args.wrist_only else "captured_6d_targets",
              "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "capture_path": str(args.capture.resolve()),
              "capture_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
              "timing_scope": "Offline diagnostic planning includes rejected-candidate collision audits and requested lookahead; not a production runtime benchmark. first_step_ms includes the entire requested horizon.",
              "boundary": "Offline first-step QP ablation. Same model, 20mm sampled collision checks, operational limits, 40/100 deg/s caps. Not original upstream G1, physical dynamics, exact runtime replay or hardware authorization.",
              "segments": []}
    if args.endpoint_audit is not None:
        source = json.loads(args.endpoint_audit.read_text(encoding="utf-8"))
        if source["capture_sha256"] != report["capture_sha256"]:
            raise ValueError("Held-goal audit does not belong to this capture")
        report["endpoint_source_sha256"] = hashlib.sha256(args.endpoint_audit.read_bytes()).hexdigest()
        for segment in source["segments"]:
            if args.segment is not None and segment["segment"] != args.segment:
                continue
            for name, variant in segment["variants"].items():
                audit = variant["held_goal_audit"]
                q = np.array(audit["q"])
                matrix = np.array(audit["goal_matrix"])
                goal = probe.base._matrix_to_se3(matrix[:3, :3], matrix[:3, 3])
                planner = BuildPlanner(model, q)
                report["segments"].append({"segment": segment["segment"], "source_variant": name,
                    "endpoint_audit": InspectEndpointSolutions(planner, q, goal)})
        if not report["segments"]:
            raise ValueError("No held-goal snapshot matched")
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print("Result saved to:", args.result_json.resolve())
        return
    segments = GetWristOnlySegments(model) if args.wrist_only else GetActiveSegments(packets)
    for index, (reference, goals) in enumerate(segments, 1):
        if args.segment is not None and index != args.segment:
            continue
        initial_q = probe.base._initial_configuration(model)
        initial_q[qpos] = reference["value"]["all_joint_q_rad"]
        entry = {"segment": index, "packets": len(goals), "variants": {}}
        for name in args.variants:
            metrics, samples = RunVariant(model, initial_q, goals, name not in ("geometry_only", "resolved_no_merit"),
                                          increment_bound=name != "current_merit" and name != "geometry_only",
                                          reserve_m=0.0005 if name in ("increment_reserve", "resolved_witness", "resolved_no_merit", "consistent_wrist", "resolved_damped", "exact_cartesian", "consistent_merit", "consistent_tangent", "nullspace_center", "limit_avoidance") else 0.0,
                                          resolve_witness=name in ("resolved_witness", "resolved_no_merit", "consistent_wrist", "resolved_damped", "exact_cartesian", "consistent_merit", "consistent_tangent", "nullspace_center", "limit_avoidance"),
                                          consistent_position=name == "consistent_wrist",
                                          task_damping=1.0 if name == "resolved_damped" else None,
                                          cartesian_position=name in ("exact_cartesian", "consistent_merit", "consistent_tangent", "nullspace_center", "limit_avoidance"),
                                          full_orientation=name in ("consistent_merit", "consistent_tangent", "nullspace_center", "limit_avoidance"),
                                          recover_reserve=name not in ("consistent_tangent", "nullspace_center", "limit_avoidance"),
                                          center_redundancy=name in ("nullspace_center", "limit_avoidance"),
                                          limit_margin_rad=math.radians(probe.live.ASSIST_ENTER_MARGIN_DEG) if name == "limit_avoidance" else None,
                                          horizon_steps=args.horizon_steps)
            entry["variants"][name] = metrics
            sample_path = args.result_json.with_name(args.result_json.stem + f"_s{index}_{name}.jsonl")
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            with sample_path.open("w", encoding="utf-8") as stream:
                for sample in samples:
                    stream.write(json.dumps(sample, allow_nan=False) + "\n")
            print(f"Segment {index} {name}: " + json.dumps(metrics), flush=True)
        report["segments"].append(entry)
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    if not report["segments"]:
        raise ValueError("No active segment")
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
