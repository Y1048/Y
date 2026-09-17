"""Mink objective/contact Jacobians with reduced velocity QP, simulation only.

CollisionAvoidanceLimit supplies geometry/Jacobians; the installed 1.3.0
velocity-distance bound is converted to the delta-q units used by build_ik.
Acceleration bounds are a project extension inside the same QP, not a filter
that changes the collision-avoiding direction after solving. No tracking jerk
bound is imposed by this flow. Return still uses the checked Ruckig trajectory.
Integrated candidates retain an exact geometry guard. QP failure or rejection
first attempts checked acceleration-limited braking. If braking also violates
geometry, the model holds; continuity across that hard stop is not guaranteed.
"""
import numpy as np
import mink
import qpsolvers
import mujoco
from g1_mink_feasible_target import base
from mink.limits.limit import Constraint
from g1_mink_trajectory import StatefulMinkTrajectory, TrajectoryStep
from hardware.g1_arm_bridge.ruckig_joint_motion_limiter import RuckigJointMotionLimiter


class AccelerationBound(mink.Limit):
    def __init__(self, model, dofs, acceleration):
        self.projection = np.eye(model.nv)[dofs]
        self.acceleration = np.asarray(acceleration)
        self.previous = np.zeros(len(dofs))

    def compute_qp_inequalities(self, configuration, dt):
        return Constraint(G=np.vstack((self.projection, -self.projection)),
                          h=np.hstack(((self.previous+self.acceleration*dt)*dt,
                                       (-self.previous+self.acceleration*dt)*dt)))


class UpstreamMinkTracking(StatefulMinkTrajectory):
    def __init__(self, *args):
        super().__init__(*args)
        self.acceleration_bound = AccelerationBound(self.planner.model,
            self.planner.right_dofs, self.acceleration_limits)
        self.last_acceleration = np.zeros(7)
        self.goal_braking = True
        self.distance_probe_data = mujoco.MjData(self.planner.model)
        self.corrected_zero_distances = 0
        self.elbow_assist_active = False
        self.orientation_priority_enabled = True
        self.orientation_priority_scale = 1.
        self.position_priority_active = False
        self._priority_dwell = 0.
        self._orientation_cost = np.asarray(self.planner.wrist_task.orientation_cost).copy()
        self.elbow_task = mink.FrameTask('right_elbow_link', 'body',
            position_cost=[0., 0., 8.], orientation_cost=0., gain=.6*self.dt_s)
        self.torso_geom_ids = tuple(
            geom_id for geom_id in range(self.planner.model.ngeom)
            if (mujoco.mj_id2name(
                self.planner.model, mujoco.mjtObj.mjOBJ_GEOM, geom_id
            ) or '').startswith('mink_collision_torso_link_')
        )
        wrist_collision_radii = [
            float(np.min(self.planner.model.geom_size[geom_id]))
            for geom_id in range(self.planner.model.ngeom)
            if (mujoco.mj_id2name(
                self.planner.model, mujoco.mjtObj.mjOBJ_GEOM, geom_id
            ) or '').startswith('mink_collision_right_wrist_')
        ]
        self.wrist_target_radius_m = max(wrist_collision_radii)
        self.target_projected = False
        self.collision_orientation_relaxed = False
        self.raw_target_position = np.zeros(3)
        self.effective_target_position = np.zeros(3)
        self.target_projection_distance_m = 0.

    def _project_target_outside_torso(self, goal, reference_position):
        """Project a wrist origin out of model-derived torso exclusion boxes."""
        raw = np.asarray(goal.translation(), dtype=float)
        projected = raw.copy()
        reference = np.asarray(reference_position, dtype=float)
        margin = self.wrist_target_radius_m + float(self.planner.clearance_m)
        changed = False
        # Torso mesh bounds can overlap, so repeat until the point is outside
        # every expanded oriented box. Keep the exit side consistent with the
        # current wrist to prevent a target near the center jumping sides.
        for _ in range(max(1, len(self.torso_geom_ids) * 2)):
            pass_changed = False
            for geom_id in self.torso_geom_ids:
                center = self.planner.configuration.data.geom_xpos[geom_id]
                rotation = self.planner.configuration.data.geom_xmat[geom_id].reshape(3, 3)
                half = np.asarray(self.planner.model.geom_size[geom_id]) + margin
                local = rotation.T @ (projected - center)
                if np.any(np.abs(local) >= half):
                    continue
                reference_local = rotation.T @ (reference - center)
                outside = np.flatnonzero(np.abs(reference_local) >= half)
                if outside.size:
                    axis = int(outside[np.argmax(
                        np.abs(reference_local[outside]) / half[outside]
                    )])
                    sign = 1. if reference_local[axis] >= 0. else -1.
                else:
                    distance = half - np.abs(local)
                    axis = int(np.argmin(distance))
                    sign_source = local[axis] if abs(local[axis]) > 1e-9 else reference_local[axis]
                    sign = 1. if sign_source >= 0. else -1.
                local[axis] = sign * half[axis]
                projected = center + rotation @ local
                changed = pass_changed = True
            if not pass_changed:
                break
        effective = base._matrix_to_se3(goal.rotation().as_matrix(), projected)
        return effective, changed

    def _reset_orientation_priority(self):
        self.position_priority_active = False
        self.orientation_priority_scale = 1.
        self._priority_dwell = 0.
        self.planner.wrist_task.set_orientation_cost(self._orientation_cost)

    def _update_orientation_priority(self, current_q, goal, clearance):
        # Keep the original SE3 target. Only its orientation penalty changes;
        # returning to a reachable region can therefore recover the same rotation.
        p = self.planner
        pose = p.configuration.get_transform_frame_to_world('right_wrist_yaw_link', 'body')
        error = float(np.linalg.norm(pose.translation()-goal.translation()))
        lower, upper = p.model.jnt_range[p.joint_ids].T
        arm = current_q[p.qpos_ids]
        margin = float(np.min(np.minimum(arm-lower, upper-arm)))
        constrained = clearance < .012 or margin < np.deg2rad(5.)
        if not self.orientation_priority_enabled:
            self._reset_orientation_priority()
            return
        if not self.position_priority_active:
            condition = error > .08 and constrained
        else:
            condition = error < .03 or (clearance > .025 and margin > np.deg2rad(8.))
        self._priority_dwell = self._priority_dwell+self.dt_s if condition else 0.
        if self._priority_dwell >= .3:
            self.position_priority_active = not self.position_priority_active
            self._priority_dwell = 0.
        # A nonzero residual orientation cost can keep a redundant solution at
        # a joint limit while leaving several centimetres of position error.
        # Position priority therefore removes orientation cost completely;
        # the original rotation target remains stored and is restored after
        # position recovery by the existing hysteresis.
        target = 0. if self.position_priority_active else 1.
        self.orientation_priority_scale += float(np.clip(
            target-self.orientation_priority_scale, -self.dt_s, self.dt_s))
        p.wrist_task.set_orientation_cost(self._orientation_cost*self.orientation_priority_scale)

    def _collision_constraint(self, limit):
        p = self.planner
        constraint = limit.compute_qp_inequalities(p.configuration, self.dt_s)
        g, h = constraint.G.copy(), constraint.h.copy()
        self.corrected_zero_distances = 0
        for index in np.flatnonzero(h == limit.bound_relaxation):
            a, b = limit.geom_id_pairs[index]
            raw = mujoco.mj_geomDistance(p.model, p.configuration.data, a, b,
                limit.collision_detection_distance, None)
            if abs(raw) > base.ZERO_DISTANCE_TOLERANCE_M or base._has_exact_geom_contact(p.configuration.data, a, b):
                continue
            data = self.distance_probe_data
            origin = p.configuration.q.copy()
            def distance(q):
                data.qpos[:] = q
                mujoco.mj_forward(p.model, data)
                return base._robust_geom_distance(p.model, data, a, b,
                    limit.collision_detection_distance, np.zeros(6))
            corrected = distance(origin)
            if corrected <= base.ZERO_DISTANCE_TOLERANCE_M:
                continue  # Unresolved/real contact remains constrained.
            self.corrected_zero_distances += 1
            if corrected >= limit.collision_detection_distance:
                g[index] = 0.; h[index] = np.inf
                continue
            # The zero-distance witness points are unusable. Differentiate
            # the same robust distance used by the exact pose checker.
            g[index] = 0.
            for dof, address in zip(p.right_dofs, p.qpos_ids):
                plus, minus = origin.copy(), origin.copy()
                plus[address] += 1e-5; minus[address] -= 1e-5
                g[index, dof] = -(distance(plus)-distance(minus))/(2e-5)
            h[index] = limit.gain * max(0., corrected-limit.minimum_distance_from_collisions)/self.dt_s + limit.bound_relaxation
        return Constraint(G=g, h=h)

    def Reset(self, current_q):
        super().Reset(current_q)
        self._reset_orientation_priority()
        self.acceleration_bound.previous.fill(0)
        self.last_acceleration.fill(0)
        self.elbow_assist_active = False
        self.target_projected = False
        self.collision_orientation_relaxed = False
        self.target_projection_distance_m = 0.

    def BeginReturn(self, current_q):
        self._reset_orientation_priority()
        self.elbow_assist_active = False
        self.target_projected = False
        self.collision_orientation_relaxed = False
        self.target_projection_distance_m = 0.
        self.limiter = RuckigJointMotionLimiter(current_q[self.right_qpos_ids],
            self.velocity_limits, self.acceleration_limits, self.jerk_limits, self.dt_s,
            initial_velocity_rad_s=self.acceleration_bound.previous,
            initial_acceleration_rad_s2=self.last_acceleration)

    def _solve_velocity(self):
        p = self.planner
        dt = self.dt_s
        # Mink's objective uses delta-q. Eliminate frozen DOFs exactly, then
        # solve in rad/s to avoid tiny acceleration bounds (a * dt**2).
        original_gain = p.wrist_task.gain
        original_posture_gain = p.posture_task.gain
        if self.goal_braking:
            # A fixed gain=.35 at 60 Hz requests error removal at 21/s,
            # even when acceleration limits require a long braking distance.
            # Estimate the joint correction and reduce the approach rate so
            # the requested motion has deceleration headroom. This is local
            # IK scheduling, not a global guarantee for moving/unreachable goals.
            error = p.wrist_task.compute_error(p.configuration)
            jacobian = p.wrist_task.compute_jacobian(p.configuration)[:, p.right_dofs]
            correction = np.linalg.lstsq(jacobian, -error, rcond=1e-4)[0]
            rate = min(1., float(np.min(np.sqrt(np.asarray(self.acceleration_limits) /
                (4. * np.maximum(np.abs(correction), 1e-6))))))
            p.wrist_task.gain = min(original_gain, dt * rate)
            # Preserve the task/posture equilibrium when slowing the approach.
            p.posture_task.gain = original_posture_gain * p.wrist_task.gain / original_gain
        try:
            tasks = p.standard_tasks + ([self.elbow_task] if self.elbow_assist_active else [])
            problem = mink.build_ik(p.configuration, tasks, dt,
                damping=1e-6, limits=[], constraints=p.constraints)
        finally:
            p.wrist_task.gain = original_gain
            p.posture_task.gain = original_posture_gain
        ids = p.right_dofs
        if problem.A is not None:
            if np.any(np.abs(problem.A[:, ids]) > 1e-12) or np.any(np.abs(problem.b) > 1e-12):
                raise ValueError("reduced tracking requires zero frozen-DOF constraints")
        matrices, bounds = [], []
        for limit in [*p.limits, self.acceleration_bound]:
            c = self._collision_constraint(limit) if isinstance(limit, mink.CollisionAvoidanceLimit) else limit.compute_qp_inequalities(p.configuration, dt)
            if c.inactive:
                continue
            g = c.G[:, ids] * dt
            h = c.h.copy()
            if isinstance(limit, mink.CollisionAvoidanceLimit):
                # Installed Mink 1.3.0 returns a velocity-distance bound
                # (gain * distance / dt); convert it to delta-q units.
                h *= dt
                # Reserve 0.5 mm ahead of the exact guard. A small outward
                # recovery request avoids getting stuck on the linearized
                # boundary; the exact checked path remains authoritative.
                recovery = .1 * (np.abs(c.G[:, ids]) @
                    np.asarray(self.acceleration_limits)) * dt**2
                h = np.maximum(h - limit.gain * .0005, -recovery)
                normal_acceleration = .25 * (np.abs(c.G[:, ids]) @
                    np.asarray(self.acceleration_limits))
                remaining = np.maximum(0., np.where(np.isfinite(c.h),
                    (c.h-limit.bound_relaxation)*dt/limit.gain, 0.))
                stopping_speed = .5 * (np.sqrt((normal_acceleration*dt)**2 +
                    2*normal_acceleration*remaining)-normal_acceleration*dt)
                finite_stopping = np.isfinite(c.h) & np.isfinite(stopping_speed)
                h[finite_stopping] = np.minimum(h[finite_stopping], stopping_speed[finite_stopping]*dt)
            norm = np.linalg.norm(g, axis=1)
            finite = np.isfinite(h)
            if np.any(finite & (norm < 1e-12) & (h < -1e-10)):
                return None
            keep = finite & (norm >= 1e-12)
            matrices.append(g[keep] / norm[keep, None])
            bounds.append(h[keep] / norm[keep])
        # Brake before a joint bound instead of reaching it with nonzero speed.
        a = np.asarray(self.acceleration_limits)
        q = p.configuration.q[p.qpos_ids]
        lower, upper = p.model.jnt_range[p.joint_ids].T
        def stopping_speed(distance):
            return .8 * (np.sqrt((a*dt)**2+2*a*np.maximum(0., distance))-a*dt)
        matrices.append(np.vstack((np.eye(7), -np.eye(7))))
        bounds.append(np.hstack((stopping_speed(upper-q), stopping_speed(q-lower))))
        hessian = problem.P[np.ix_(ids, ids)] * dt**2
        linear = problem.q[ids] * dt
        scale = max(float(np.max(np.abs(hessian))), 1e-12)
        result = qpsolvers.solve_problem(qpsolvers.Problem(
            hessian / scale, linear / scale, np.vstack(matrices), np.hstack(bounds)),
            solver=p.solver)
        if not result.found or result.x is None:
            return None
        velocity = np.zeros(p.model.nv)
        velocity[ids] = result.x
        return velocity

    def Track(self, current_q, goal):
        p = self.planner
        p.configuration.update(current_q)
        if p.posture_reference is None:
            p.posture_reference = current_q.copy()
            p.posture_task.set_target(p.posture_reference)
        current_pose = p.configuration.get_transform_frame_to_world(
            'right_wrist_yaw_link', 'body')
        projected_goal, self.target_projected = self._project_target_outside_torso(
            goal, current_pose.translation())
        if self.target_projected:
            # Continue sliding the position goal around the model-derived torso
            # boundary, but do not chase an infeasible wrist orientation while
            # the raw hand goal is inside the body. Requiring both at once can
            # drive a redundant shoulder solution toward a joint limit.
            effective_goal = base._matrix_to_se3(
                current_pose.rotation().as_matrix(),
                projected_goal.translation().copy(),
            )
            self.collision_orientation_relaxed = True
        else:
            effective_goal = goal
            self.collision_orientation_relaxed = False
        self.raw_target_position = np.asarray(goal.translation(), dtype=float).copy()
        self.effective_target_position = np.asarray(
            effective_goal.translation(), dtype=float).copy()
        self.target_projection_distance_m = float(np.linalg.norm(
            np.asarray(projected_goal.translation()) - self.raw_target_position))
        p.wrist_task.set_target(effective_goal)
        clearance = p.GetClearance(current_q)
        self._update_orientation_priority(current_q, effective_goal, clearance)
        if self.elbow_assist_active and clearance > .025:
            self.elbow_assist_active = False
        if (not self.target_projected and not self.elbow_assist_active
                and clearance < .012
                and current_q[p.qpos_ids[3]] < np.deg2rad(20.)):
            elbow = p.configuration.get_transform_frame_to_world('right_elbow_link', 'body')
            shoulder = p.configuration.get_transform_frame_to_world('right_shoulder_pitch_link', 'body')
            position = elbow.translation().copy()
            position[2] = min(position[2]+.08, shoulder.translation()[2]-.04)
            if position[2] > elbow.translation()[2]+.005:
                self.elbow_task.set_target(base._matrix_to_se3(elbow.rotation().as_matrix(), position))
                self.elbow_assist_active = True
        self.rejected_sample = None
        previous = self.acceleration_bound.previous.copy()
        velocity = self._solve_velocity()
        braking = velocity is None
        if braking:
            # A failed target solve must not invent an instantaneous stop.
            # Attempt one acceleration-limited braking step, still exact-checked.
            velocity = np.zeros(p.model.nv)
            velocity[p.right_dofs] = previous - np.clip(previous,
                -np.asarray(self.acceleration_limits)*self.dt_s,
                np.asarray(self.acceleration_limits)*self.dt_s)
        arm_velocity = velocity[p.right_dofs]
        acceleration = (arm_velocity-previous)/self.dt_s
        if (not np.isfinite(velocity).all()
                or np.any(np.abs(arm_velocity)>np.asarray(self.velocity_limits)+1e-6)
                or np.any(np.abs(acceleration)>np.asarray(self.acceleration_limits)+1e-5)
                or np.any(np.abs(velocity[p.frozen_dofs])>1e-7)):
            self.Reset(current_q)
            return TrajectoryStep(current_q.copy(), False, "upstream_invalid_velocity", (0.,)*7, (0.,)*7)
        # Same integration operation used by upstream humanoid_g1.py.
        p.configuration.integrate_inplace(velocity, self.dt_s)
        candidate = p.configuration.q.copy()
        # The upstream constraint is local/linearized. Keep the project's
        # exact geometry check; never publish an unchecked integrated pose.
        if not self._safe_path(current_q, candidate):
            rejected = self.rejected_sample.copy()
            p.configuration.update(current_q)
            velocity = np.zeros(p.model.nv)
            arm_velocity = previous - np.clip(previous,
                -np.asarray(self.acceleration_limits)*self.dt_s,
                np.asarray(self.acceleration_limits)*self.dt_s)
            velocity[p.right_dofs] = arm_velocity
            acceleration = (arm_velocity-previous)/self.dt_s
            p.configuration.integrate_inplace(velocity, self.dt_s)
            candidate = p.configuration.q.copy()
            braking = True
            if not self._safe_path(current_q, candidate):
                p.configuration.update(current_q)
                self.Reset(current_q)
                self.rejected_sample = rejected
                return TrajectoryStep(current_q.copy(), False,
                                      "upstream_collision_hold", (0.,)*7, (0.,)*7)
        self.acceleration_bound.previous = arm_velocity.copy()
        self.last_acceleration = acceleration.copy()
        return TrajectoryStep(candidate, True, "upstream_braking" if braking else "trajectory_following",
                              tuple(arm_velocity), tuple(acceleration))
