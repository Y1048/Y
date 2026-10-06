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
        self.return_profile = simulation.return_profile
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

        # MuJoCo 3.12.0 contains the upstream mesh-distance separation fix
        # that made the old 3.11 zero-witness finite-difference repair obsolete.
        # Hard geometry is still rechecked by clearance()/checked_stop_plan().

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
        motion_profile = self.return_profile if returning else self.profile
        dv = motion_profile.joint_acceleration_limit_rad_s2 * s.dt
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

    def _checked_stop_plan(
            self, first_velocity, *, caps, acceleration_rad_s2):
        s = self.sim
        dv = acceleration_rad_s2 * s.dt
        if (
            not np.isfinite(first_velocity).all()
            or np.any(np.abs(first_velocity[s.dofs]) > caps + 1e-6)
            or np.any(np.abs(first_velocity - s.velocity) > dv + 1e-6)
        ):
            return None, "velocity_acceleration"

        q = s.config.q.copy()
        velocity = first_velocity.copy()
        plan = []
        frozen = np.ones(s.model.nq, dtype=bool)
        frozen[s.qids] = False

        for _ in range(int(np.ceil(np.max(caps) / dv)) + 2):
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
                if len(plan) == 1:
                    plan.append(
                        (candidate.copy(), velocity.copy()))
                return plan, ""

            q = candidate
            velocity = np.sign(velocity) * np.maximum(
                0, np.abs(velocity) - dv)

        return None, "braking_horizon"

    def checked_stop_plan(self, first_velocity, *, returning=False):
        """Return a checked stop tail under the active motion profile."""
        profile = self.return_profile if returning else self.profile
        caps = self.sim.return_caps if returning else self.sim.caps
        return self._checked_stop_plan(
            first_velocity,
            caps=caps,
            acceleration_rad_s2=profile.joint_acceleration_limit_rad_s2,
        )

    def return_transition_stop_plan(self):
        """Brake a tracking command with return acceleration before return.

        A tracking pose may legitimately be moving faster than the conservative
        return velocity cap. The transition cannot reduce that speed
        instantaneously, so it preserves the tracking velocity envelope while
        decelerating at the return acceleration limit until rest.
        """
        s = self.sim
        dv = self.return_profile.joint_acceleration_limit_rad_s2 * s.dt
        first_velocity = s.velocity.copy()
        first_velocity[s.dofs] = (
            np.sign(first_velocity[s.dofs])
            * np.maximum(0.0, np.abs(first_velocity[s.dofs]) - dv)
        )
        return self._checked_stop_plan(
            first_velocity,
            caps=s.caps,
            acceleration_rad_s2=(
                self.return_profile.joint_acceleration_limit_rad_s2),
        )
