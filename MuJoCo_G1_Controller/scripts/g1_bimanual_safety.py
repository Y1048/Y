"""Named safety boundary for the current bilateral IK controller.

This module does not change tuning or authorize physical motor output. It owns
the existing live-QP safety inequalities and the existing sampled checked
stopping-tail proof so the IK loop can be read independently of safety math.
"""

import numpy as np
import mujoco
import mink

import g1_mink_shared as base


class BimanualSafetyEnvelope:
    """Existing bilateral safety calculations, grouped behind one interface."""

    def __init__(self, simulation, collision_pairs):
        self.sim = simulation
        self.profile = simulation.profile
        self.check_data = mujoco.MjData(simulation.model)
        self.pair_array = np.asarray(simulation.pairs, dtype=int)
        self.clearance_local_centers = (
            simulation.model.geom_aabb[:, :3].copy())
        self.clearance_bounding_radii = np.linalg.norm(
            simulation.model.geom_aabb[:, 3:], axis=1)
        self.limits = [
            mink.ConfigurationLimit(simulation.model),
            mink.VelocityLimit(
                simulation.model,
                dict(zip(simulation.names, simulation.caps)),
            ),
            mink.CollisionAvoidanceLimit(
                simulation.model,
                geom_pairs=collision_pairs,
                minimum_distance_from_collisions=self.profile.collision_minimum_m,
                collision_detection_distance=(
                    self.profile.collision_detection_distance_m),
                gain=self.profile.collision_gain,
            ),
        ]

    def clearance(self, q, threshold=None):
        """Return minimum controlled-geometry clearance for one qpos."""
        s = self.sim
        data = self.check_data
        data.qpos[:] = q
        # Geometry distance needs only kinematics in the normal non-contact
        # path. Promote exact-zero cases once so contact probes remain valid.
        mujoco.mj_kinematics(s.model, data)
        pairs = s.pairs
        if threshold is not None:
            rotation = data.geom_xmat.reshape(-1, 3, 3)
            center = data.geom_xpos + np.einsum(
                "nij,nj->ni", rotation, self.clearance_local_centers)
            first, second = self.pair_array.T
            lower = (
                np.linalg.norm(center[first] - center[second], axis=1)
                - self.clearance_bounding_radii[first]
                - self.clearance_bounding_radii[second]
            )
            if not np.isfinite(lower).all():
                return float("nan")
            pairs = self.pair_array[lower <= threshold + 1e-8]

        nearest = None
        fromto = np.zeros(6, dtype=float)
        promoted = False
        for first, second in pairs:
            distance = float(mujoco.mj_geomDistance(
                s.model, data, int(first), int(second), .2, fromto))
            if abs(distance) <= base.ZERO_DISTANCE_TOLERANCE_M:
                if not promoted:
                    mujoco.mj_fwdPosition(s.model, data)
                    promoted = True
                distance = base._robust_geom_distance(
                    s.model, data, int(first), int(second), .2, fromto)
            if distance < .2 and (nearest is None or distance < nearest):
                nearest = distance
        return .2 if nearest is None else nearest

    def constrain_problem(self, problem, *, returning=False):
        """Add the pre-existing collision, acceleration and braking bounds."""
        s = self.sim
        collision = self.limits[2]
        bound = collision.compute_qp_inequalities(s.config, s.dt)
        cg, ch = bound.G.copy(), bound.h.copy()

        # Installed Mink collision bounds are velocity units; build_ik solves
        # displacement. Preserve the existing zero-distance mesh correction.
        for index in np.flatnonzero(ch == collision.bound_relaxation):
            first, second = collision.geom_id_pairs[index]
            raw = mujoco.mj_geomDistance(
                s.model,
                s.config.data,
                first,
                second,
                self.profile.collision_detection_distance_m,
                None,
            )
            if (
                abs(raw) > 1e-12
                or base._has_exact_geom_contact(
                    s.config.data, first, second)
            ):
                continue

            def distance(q):
                self.check_data.qpos[:] = q
                mujoco.mj_forward(s.model, self.check_data)
                return base._robust_geom_distance(
                    s.model,
                    self.check_data,
                    first,
                    second,
                    self.profile.collision_detection_distance_m,
                    np.zeros(6),
                )

            corrected = distance(s.config.q)
            if corrected <= 1e-12:
                continue
            cg[index] = 0
            if corrected >= self.profile.collision_detection_distance_m:
                ch[index] = np.inf
                continue
            for dof, address in zip(s.dofs, s.qids):
                plus = s.config.q.copy()
                minus = s.config.q.copy()
                plus[address] += 1e-5
                minus[address] -= 1e-5
                cg[index, dof] = -(
                    distance(plus) - distance(minus)
                ) / 2e-5
            ch[index] = collision.gain * max(
                0.0, corrected - self.profile.collision_minimum_m
            ) / s.dt

        collision_h = ch * s.dt
        if not returning:
            normal_acceleration = (
                self.profile.collision_stopping_acceleration_scale
                * (
                    np.abs(cg[:, s.dofs])
                    @ np.full(
                        len(s.dofs),
                        self.profile.joint_acceleration_limit_rad_s2,
                    )
                )
            )
            remaining = np.maximum(
                0.0,
                np.where(
                    np.isfinite(ch),
                    (
                        (ch - collision.bound_relaxation)
                        * s.dt
                        / collision.gain
                    ),
                    0.0,
                ),
            )
            stopping_speed = 0.5 * (
                np.sqrt(
                    (normal_acceleration * s.dt) ** 2
                    + 2 * normal_acceleration * remaining
                )
                - normal_acceleration * s.dt
            )
            finite_stop = np.isfinite(ch) & np.isfinite(stopping_speed)
            collision_h[finite_stop] = np.minimum(
                collision_h[finite_stop],
                stopping_speed[finite_stop] * s.dt,
            )

        problem.G = np.vstack([problem.G, cg])
        problem.h = np.r_[problem.h, collision_h]

        # Mink solves joint displacement, not velocity.
        eye = np.eye(s.model.nv)[s.dofs]
        dv = self.profile.joint_acceleration_limit_rad_s2 * s.dt
        hi = (s.velocity[s.dofs] + dv) * s.dt
        lo = (s.velocity[s.dofs] - dv) * s.dt
        problem.G = np.vstack([problem.G, eye, -eye])
        problem.h = np.concatenate([problem.h, hi, -lo])

        if not returning:
            acceleration = self.profile.joint_acceleration_limit_rad_s2
            q = s.config.q[s.qids]

            def stopping_bound(distance):
                return self.profile.joint_limit_stopping_speed_scale * (
                    np.sqrt(
                        (acceleration * s.dt) ** 2
                        + 2 * acceleration * np.maximum(0.0, distance)
                    )
                    - acceleration * s.dt
                )

            problem.G = np.vstack([problem.G, eye, -eye])
            problem.h = np.r_[
                problem.h,
                stopping_bound(s.ranges[:, 1] - q) * s.dt,
                stopping_bound(q - s.ranges[:, 0]) * s.dt,
            ]
            for policy in s.motion.values():
                rows, bounds = policy.yaw_velocity_bounds()
                problem.G = np.vstack([problem.G, rows])
                problem.h = np.r_[problem.h, bounds * s.dt]

        return problem

    def checked_stop_plan(self, first_velocity):
        """Return the existing discrete acceleration-bounded checked stop tail."""
        s = self.sim
        dv = self.profile.joint_acceleration_limit_rad_s2 * s.dt
        if (
            not np.isfinite(first_velocity).all()
            or np.any(np.abs(first_velocity[s.dofs]) > s.caps + 1e-6)
            or np.any(np.abs(first_velocity - s.velocity) > dv + 1e-6)
        ):
            return None, "velocity_acceleration"

        q = s.config.q.copy()
        velocity = first_velocity.copy()
        plan = []
        frozen = np.ones(s.model.nq, dtype=bool)
        frozen[s.qids] = False

        for _ in range(int(np.ceil(np.max(s.caps) / dv)) + 2):
            candidate = q.copy()
            mujoco.mj_integratePos(
                s.model, candidate, velocity, s.dt)
            candidate[frozen] = s.home[frozen]
            if (
                np.any(
                    candidate[s.qids] < s.ranges[:, 0] - 1e-8)
                or np.any(
                    candidate[s.qids] > s.ranges[:, 1] + 1e-8)
            ):
                return None, "joint_range"

            substeps = max(
                2,
                int(
                    np.ceil(
                        np.max(np.abs(candidate - q))
                        / self.profile.checked_stop_substep_rad
                    )
                ),
            )
            for fraction in np.linspace(0, 1, substeps + 1)[1:]:
                # Call through the simulation compatibility proxy so
                # existing safety fault-injection tests and diagnostics keep
                # their public hook while implementation stays here.
                clearance = s.clearance(
                    q + fraction * (candidate - q),
                    threshold=s.clearance_m,
                )
                if (
                    not np.isfinite(clearance)
                    or clearance < s.clearance_m
                ):
                    return None, "swept_clearance"

            plan.append((candidate.copy(), velocity.copy()))
            if not np.any(velocity):
                # Keep a checked stationary tail available even at rest.
                if len(plan) == 1:
                    plan.append(
                        (candidate.copy(), velocity.copy()))
                return plan, ""

            q = candidate
            velocity = np.sign(velocity) * np.maximum(
                0, np.abs(velocity) - dv)

        return None, "braking_horizon"
