"""Offline A/B trajectory experiment; never imported by a live launcher."""

import math
import numpy as np

from verify_feasible_target import BuildPlanner, probe
from g1_standard_mink_planner import StandardMinkPlanner
from g1_mink_trajectory import StatefulMinkTrajectory


def ForwardWristGoal(seconds):
    """4 cm forward, settle, then local wrist X rotation with fixed position."""
    reach = math.sin(math.pi * min(max(seconds, 0.), 5.) / 10.) ** 2
    turn = math.sin(math.pi * min(max(seconds - 20., 0.), 10.) / 20.) ** 2
    return np.array([.04 * reach, 0., 0.]), math.radians(35.) * turn


class ThroughTrajectory(StatefulMinkTrajectory):
    """Experimental waypoint velocity; inherited path checks remain active."""

    def Step(self, current_q, target_q):
        current = np.asarray(current_q, dtype=float)
        target = np.asarray(target_q, dtype=float)
        if current.shape != target.shape or not np.isfinite(current).all() or not np.isfinite(target).all():
            raise ValueError("finite matching joint vectors required")
        if self.limiter is None or np.max(np.abs(
                np.asarray(self.limiter.q_rad) - current[self.right_qpos_ids])) > 1e-6:
            self.Reset(current)
        # Local experiment only: do not expand the shared limiter API yet.
        velocity = (target[self.right_qpos_ids] - current[self.right_qpos_ids]) / (3 * self.dt_s)
        caps = np.asarray(self.velocity_limits)
        self.limiter._input.target_velocity = np.clip(0.1 * velocity, -caps, caps).tolist()
        return super().Step(current, target)


class TrajectoryComparison:
    def __init__(self, model, profile):
        self.model, self.profile = model, profile
        self.initial = probe.base._initial_configuration(model)
        self.addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                          for name in probe.base.g1.RIGHT_ARM_JOINTS]
        self.initial[self.addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
        self.config = probe.mink.Configuration(model)
        self.config.update(self.initial)
        pose = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        self.origin, self.rotation = pose.translation().copy(), pose.rotation().as_matrix().copy()
        self.Reset()

    def Reset(self):
        self.planners, self.trajectories = [], []
        for mode in range(2):
            reference = BuildPlanner(self.model, self.initial, self.profile)
            caps = dict(zip(probe.base.g1.RIGHT_ARM_JOINTS, reference.velocity_caps))
            planner = StandardMinkPlanner(self.model, *reference.tasks,
                reference.limits, reference.constraints, reference.solver,
                reference.clearance_m, caps)
            trajectory_class = StatefulMinkTrajectory if mode == 0 else ThroughTrajectory
            self.trajectories.append(trajectory_class(planner, self.addresses,
                reference.velocity_caps, [probe.live.JOINT_MAX_ACCELERATION_RAD_S2] * 7,
                [probe.live.JOINT_MAX_JERK_RAD_S3] * 7, probe.base.DT))
            self.planners.append(planner)
        self.q = [self.initial.copy(), self.initial.copy()]
        self.seconds, self.rows = 0., []
        self.goal = probe.base._matrix_to_se3(self.rotation, self.origin)
        self.joint_travel = np.zeros((2, 7))
        self.peak_velocity = np.zeros(2)
        self.rejections = np.zeros(2, dtype=int)
        self.rotation_start = [None, None]
        self.rotation_travel = np.zeros((2, 4))
        self.rotation_ready = [False, False]

    def Step(self, case):
        from view_ik_comparison import GetCompositeGoal
        # Identical analytic targets; final half of clip holds its target.
        seconds = min(self.seconds, 10.)
        wave = math.sin(math.pi * seconds / 20.) ** 2
        delta, rotation = np.zeros(3), self.rotation.copy()
        if case == 9:
            delta, angle = ForwardWristGoal(self.seconds)
            rotation = self.rotation @ probe.mink.SO3.from_x_radians(angle).as_matrix()
        elif case >= 6:
            delta, relative = GetCompositeGoal(case, seconds)
            rotation = self.rotation @ relative
        else:
            if case < 3 or case == 4:
                axis = case if case < 3 else 1
                factory = (probe.mink.SO3.from_x_radians, probe.mink.SO3.from_y_radians,
                           probe.mink.SO3.from_z_radians)[axis]
                rotation = self.rotation @ factory(.35 * wave).as_matrix()
            if case in (3, 4):
                delta = np.array([.04, -.03, .04]) * wave
            if case == 5:
                delta = np.array([-.10, .20, -.06]) * wave
        self.goal = probe.base._matrix_to_se3(rotation, self.origin + delta)
        self.rows = []
        for mode, (planner, trajectory) in enumerate(zip(self.planners, self.trajectories)):
            previous = self.q[mode].copy()
            if case == 9 and self.seconds >= 20. and self.rotation_start[mode] is None:
                self.rotation_start[mode] = previous[self.addresses].copy()
                self.config.update(previous)
                before = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
                self.rotation_ready[mode] = bool(np.linalg.norm(before.translation()-self.goal.translation()) < .005
                    and probe.base._rotation_error_radians(self.rotation, before.rotation().as_matrix()) < math.radians(2.))
            plan = planner.Plan(previous, self.goal, position_target=self.goal.translation())
            if plan.accepted_steps:
                step = trajectory.Step(previous, plan.target_q)
                self.q[mode] = step.q.copy()
                status = step.status
                self.rejections[mode] += int(not step.applied)
            else:
                trajectory.Reset(previous)
                status = plan.status
                self.rejections[mode] += 1
            change = np.abs(self.q[mode][self.addresses] - previous[self.addresses])
            self.joint_travel[mode] += np.degrees(change)
            if self.rotation_start[mode] is not None:
                self.rotation_travel[mode] += np.degrees(change[:4])
            self.peak_velocity[mode] = max(self.peak_velocity[mode], float(max(change) / probe.base.DT))
            self.config.update(self.q[mode])
            pose = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
            self.rows.append(dict(position_mm=float(np.linalg.norm(pose.translation()-self.goal.translation())*1000),
                rotation_deg=math.degrees(probe.base._rotation_error_radians(rotation, pose.rotation().as_matrix())),
                clearance_mm=float(planner.GetClearance(self.q[mode])*1000),
                proximal_travel_deg=float(self.joint_travel[mode,:4].sum()),
                wrist_travel_deg=float(self.joint_travel[mode,4:].sum()),
                peak_velocity_deg_s=math.degrees(self.peak_velocity[mode]),
                rotation_start_settled=self.rotation_ready[mode],
                rotation_phase_arm_travel_deg=self.rotation_travel[mode].tolist(),
                rejected_steps=int(self.rejections[mode]), status=status))
        self.seconds += probe.base.DT
