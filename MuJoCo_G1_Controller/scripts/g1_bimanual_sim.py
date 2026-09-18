"""Isolated, kinematic two-arm Mink experiment. No transport or motor output."""
import argparse
import json
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import mujoco
import mink
import qpsolvers
from qpsolvers.exceptions import SolverError
import run_mink_g1_right_arm_prototype as base
from g1_bimanual_runtime import require_validated_engine
from g1_bimanual_motion_policy import ArmMotionPolicy
from g1_bimanual_return import BimanualReturnMotion


class BimanualSimulation:
    dt = 1.0 / 60
    clearance_m = 0.005

    def __init__(self):
        require_validated_engine()
        # Generate privately; never rewrite the shared/right-arm model.
        with tempfile.TemporaryDirectory(prefix="g1_bimanual_") as directory:
            path = base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
            tree = ET.parse(path)
            wrist = base._find_body(tree.getroot(), "left_wrist_yaw_link")
            ET.SubElement(wrist, "geom", name="mink_left_rubber_hand_collision",
                          type="mesh", mesh="left_rubber_hand", pos="0.0415 0.003 0",
                          density="0", contype="1", conaffinity="1", group="3",
                          rgba="0 0 0 0")
            tree.write(path, encoding="unicode")
            self.model = mujoco.MjModel.from_xml_path(str(path))
        self.names = base.g1.LEFT_ARM_JOINTS + base.g1.RIGHT_ARM_JOINTS
        ids = [base._joint_id(self.model, name) for name in self.names]
        self.qids = self.model.jnt_qposadr[ids]
        self.dofs = self.model.jnt_dofadr[ids]
        for side in ("left", "right"):
            jid = base._joint_id(self.model, side + "_elbow_joint")
            self.model.jnt_range[jid] = np.radians([5, 120])
        self.home = base._initial_configuration(self.model)
        self.config = mink.Configuration(self.model)
        self.config.update(self.home)
        self.check_data = mujoco.MjData(self.model)
        controlled = base.g1.LEFT_ARM_BODY_NAMES | base.g1.RIGHT_ARM_BODY_NAMES
        pairs, geom_ids = base._build_collision_pairs(self.model, controlled)
        # Mirror the existing right elbow/wrist structural exemption only.
        keep = []
        for i, (a, b) in enumerate(geom_ids):
            bodies = {mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY,
                                      int(self.model.geom_bodyid[g])) for g in (a, b)}
            if bodies != {"left_elbow_link", "left_wrist_yaw_link"}:
                keep.append(i)
        self.pairs = [geom_ids[i] for i in keep]
        self.pair_array = np.asarray(self.pairs, dtype=int)
        self.tasks = {side: mink.FrameTask(side + "_wrist_yaw_link", "body",
                     position_cost=8., orientation_cost=2., gain=.35,
                     lm_damping=1e-5) for side in ("left", "right")}
        self.home_targets = {s: self.config.get_transform_frame_to_world(
            s + "_wrist_yaw_link", "body") for s in self.tasks}
        self.caps = np.tile(np.radians([90]*4 + [180]*3), 2)
        self.limits = [mink.ConfigurationLimit(self.model),
            mink.VelocityLimit(self.model, dict(zip(self.names, self.caps))),
            mink.CollisionAvoidanceLimit(self.model,
                geom_pairs=[pairs[i] for i in keep],
                minimum_distance_from_collisions=.006,
                collision_detection_distance=.15, gain=.85)]
        frozen = sorted(set(range(self.model.nv)) - set(self.dofs))
        self.constraints = [mink.DofFreezingTask(self.model, dof_indices=frozen)]
        self.ranges = self.model.jnt_range[ids].copy()
        self.motion = {side: ArmMotionPolicy(self.model, self.config, side,
                       self.home, self.dt, self.clearance_m) for side in ('left', 'right')}
        self.tasks = {side: policy.wrist_task for side, policy in self.motion.items()}
        self._motion_returning = False
        self.policy_pairs = {}
        for side in self.motion:
            bodies = getattr(base.g1, side.upper() + '_ARM_BODY_NAMES')
            self.policy_pairs[side] = [pair for pair in self.pairs if any(
                mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY,
                                 int(self.model.geom_bodyid[g])) in bodies for g in pair)]
        self.brake_plan = []
        self.braking_steps = 0
        self.last_solver_error = None
        self.velocity = np.zeros(self.model.nv)
        self.acceleration = np.zeros(self.model.nv)
        self.return_motion = BimanualReturnMotion(self)
        self.state = "ready"
        self.reason = ""
        if self.clearance(self.home) < self.clearance_m:
            raise ValueError("Initial bilateral model violates clearance")

    def clearance(self, q, threshold=None):
        self.check_data.qpos[:] = q
        # Geometry distance needs only kinematics in the normal non-contact path.
        # If MuJoCo reports an exact zero, promote once to fwdPosition so the
        # established exact-contact / zero-mesh probe logic still sees contacts.
        mujoco.mj_kinematics(self.model, self.check_data)
        pairs = self.pairs
        if threshold is not None:
            # World AABBs enclose each rotated local geom AABB. Their separation
            # is a lower bound, so only certainly distant pairs are excluded.
            rotation = self.check_data.geom_xmat.reshape(-1, 3, 3)
            bounds = self.model.geom_aabb
            center = self.check_data.geom_xpos + np.einsum('nij,nj->ni', rotation, bounds[:, :3])
            extent = np.einsum('nij,nj->ni', np.abs(rotation), bounds[:, 3:])
            a, b = self.pair_array.T
            gap = np.maximum(0, np.abs(center[a]-center[b])-extent[a]-extent[b])
            lower = np.linalg.norm(gap, axis=1)
            if not np.isfinite(lower).all():
                return float('nan')
            pairs = self.pair_array[lower <= threshold + 1e-8]
        nearest = None
        fromto = np.zeros(6, dtype=float)
        promoted = False
        for first, second in pairs:
            distance = float(mujoco.mj_geomDistance(
                self.model, self.check_data, int(first), int(second), .2, fromto))
            if abs(distance) <= base.ZERO_DISTANCE_TOLERANCE_M:
                if not promoted:
                    mujoco.mj_fwdPosition(self.model, self.check_data)
                    promoted = True
                distance = base._robust_geom_distance(
                    self.model, self.check_data, int(first), int(second), .2, fromto)
            if distance < .2 and (nearest is None or distance < nearest):
                nearest = distance
        return .2 if nearest is None else nearest

    def step(self, targets=None, *, returning=False):
        """Both wrist poses in robot frame; return is a checked staged joint trajectory.

        Accept steps only with a checked stopping tail. Infeasible/unsafe QP
        results follow the previous tail; no valid tail latches blocked.
        This is deliberately not a physical stopping controller.
        """
        if self.state == "blocked":
            return False
        if returning:
            if not self._motion_returning:
                self.return_motion.reset()
            self._motion_returning = True
            return self.return_motion.step()
        if not isinstance(targets, dict) or set(targets) != {"left", "right"}:
            raise ValueError("Both left and right targets are required")
        for target in targets.values():
            if not np.isfinite(target.as_matrix()).all():
                raise ValueError("Nonfinite target")
        if self._motion_returning:
            for policy in self.motion.values():
                policy.reset(self.config.q)
            self.return_motion.reset()
        tasks = []
        for side, policy in self.motion.items():
            nearest = base._nearest_pair_distance(self.model, self.config.data, self.policy_pairs[side])
            clearance = .2 if nearest is None else nearest[0]
            if not np.isfinite(clearance):
                self.state, self.reason = 'blocked', 'nonfinite_policy_clearance'
                return False
            tasks.extend(policy.prepare(targets[side], clearance))
        self._motion_returning = False
        problem = mink.build_ik(self.config, tasks, self.dt, damping=1e-6,
                                limits=self.limits[:2], constraints=[])
        collision = self.limits[2]
        bound = collision.compute_qp_inequalities(self.config, self.dt)
        cg, ch = bound.G.copy(), bound.h.copy()
        # Installed Mink collision bounds are velocity units; build_ik solves
        # displacement. Correct spurious zero-distance mesh witnesses as the
        # established right-arm path does, now differentiating both arms.
        for i in np.flatnonzero(ch == collision.bound_relaxation):
            a, b = collision.geom_id_pairs[i]
            raw = mujoco.mj_geomDistance(self.model, self.config.data, a, b, .15, None)
            if abs(raw) > 1e-12 or base._has_exact_geom_contact(self.config.data, a, b):
                continue
            def distance(q):
                self.check_data.qpos[:] = q
                mujoco.mj_forward(self.model, self.check_data)
                return base._robust_geom_distance(self.model, self.check_data, a, b, .15, np.zeros(6))
            corrected = distance(self.config.q)
            if corrected <= 1e-12:
                continue
            cg[i] = 0
            if corrected >= .15:
                ch[i] = np.inf
                continue
            for dof, address in zip(self.dofs, self.qids):
                plus, minus = self.config.q.copy(), self.config.q.copy()
                plus[address] += 1e-5
                minus[address] -= 1e-5
                cg[i, dof] = -(distance(plus) - distance(minus)) / 2e-5
            ch[i] = collision.gain * max(0., corrected - .006) / self.dt
        collision_h = ch*self.dt
        if not returning:
            # Shared relative-distance braking headroom from the single-arm
            # policy. For an inter-arm row, both arms contribute acceleration.
            normal_acceleration = .25*(np.abs(cg[:, self.dofs]) @ np.full(len(self.dofs), np.radians(60.)))
            remaining = np.maximum(0., np.where(np.isfinite(ch),
                (ch-collision.bound_relaxation)*self.dt/collision.gain, 0.))
            stopping_speed = .5*(np.sqrt((normal_acceleration*self.dt)**2 +
                2*normal_acceleration*remaining)-normal_acceleration*self.dt)
            finite_stop = np.isfinite(ch) & np.isfinite(stopping_speed)
            collision_h[finite_stop] = np.minimum(collision_h[finite_stop], stopping_speed[finite_stop]*self.dt)
        problem.G = np.vstack([problem.G, cg])
        problem.h = np.r_[problem.h, collision_h]
        # Mink solves joint displacement, not velocity.
        eye = np.eye(self.model.nv)[self.dofs]
        dv = np.radians(60) * self.dt
        hi = (self.velocity[self.dofs] + dv) * self.dt
        lo = (self.velocity[self.dofs] - dv) * self.dt
        problem.G = np.vstack([problem.G, eye, -eye])
        problem.h = np.concatenate([problem.h, hi, -lo])
        if not returning:
            # Approach hard joint limits with braking headroom, not nonzero speed.
            a = np.radians(60.)
            q = self.config.q[self.qids]
            speed = lambda d: .8*(np.sqrt((a*self.dt)**2 + 2*a*np.maximum(0., d))-a*self.dt)
            problem.G = np.vstack([problem.G, eye, -eye])
            problem.h = np.r_[problem.h, speed(self.ranges[:, 1]-q)*self.dt,
                              speed(q-self.ranges[:, 0])*self.dt]
            for policy in self.motion.values():
                rows, bounds = policy.yaw_velocity_bounds()
                problem.G = np.vstack([problem.G, rows])
                problem.h = np.r_[problem.h, bounds*self.dt]
        # Solve in rad/s, normalize constraint rows and objective like the
        # established single-arm path. All original delta-q bounds stay intact.
        g = problem.G[:, self.dofs]*self.dt
        h = problem.h
        norms = np.linalg.norm(g, axis=1)
        finite = np.isfinite(h)
        inconsistent = np.any(finite & (norms < 1e-12) & (h < -1e-10))
        keep = finite & (norms >= 1e-12)
        hessian = problem.P[np.ix_(self.dofs, self.dofs)]*self.dt**2
        linear = problem.q[self.dofs]*self.dt
        scale = max(float(np.max(np.abs(hessian))), 1e-12)
        reduced = qpsolvers.Problem(hessian/scale, linear/scale,
                                    g[keep]/norms[keep, None], h[keep]/norms[keep])
        self.last_solver_error = None
        result = None
        reason = "qp_infeasible"
        if not inconsistent:
            try:
                result = qpsolvers.solve_problem(reduced, solver=base._select_solver())
            except SolverError as error:
                # Numerical solver failure is recoverable; configuration and
                # programming errors are not silently classified as no solution.
                self.last_solver_error = dict(type=type(error).__name__, message=str(error)[:240])
                reason = "solver_error:" + type(error).__name__
        plan = None
        if result is not None and result.found and result.x is not None and np.isfinite(result.x).all():
            velocity = np.zeros(self.model.nv)
            velocity[self.dofs] = result.x
            plan, reason = self.checked_stop_plan(velocity)
        if plan is not None:
            candidate, velocity = plan.pop(0)
            self.brake_plan = plan
            self.reason = ""
        elif self.brake_plan:
            return self.brake(reason, returning=returning)
        else:
            self.state = "blocked"
            self.reason = reason
            return False
        return self._apply_command(candidate, velocity, returning=returning)

    def _apply_command(self, candidate, velocity, *, returning=False):
        self.acceleration = (velocity-self.velocity)/self.dt
        self.config.update(candidate)
        self.velocity = velocity
        self.state = "returning" if returning else "tracking"
        return True

    def brake(self, reason='tracking_unavailable', *, returning=False):
        """Advance one already checked stopping command; do not freeze q at speed.

        The fixed-base scene has no moving external obstacles. A stationary
        initial hold may be checked here, but a missing moving tail is a fault.
        """
        if self.state == 'blocked':
            return False
        if not self.brake_plan:
            if np.any(self.velocity):
                self.state, self.reason = 'blocked', 'missing_checked_tail:' + reason
                return False
            plan, rejected = self.checked_stop_plan(np.zeros(self.model.nv))
            if plan is None:
                self.state, self.reason = 'blocked', rejected
                return False
            self.brake_plan = plan
        candidate, velocity = self.brake_plan[0]
        if len(self.brake_plan) > 1:
            self.brake_plan.pop(0)
        self.braking_steps += 1
        self.reason = 'checked_braking:' + reason
        return self._apply_command(candidate, velocity, returning=returning)

    def checked_stop_plan(self, first_velocity):
        """Discrete acceleration-bounded stopping tail, sampled geometry only.

        Validate every dt and at most .25 degree substeps. This is not a
        continuous collision proof or a physical robot braking model.
        """
        dv = np.radians(60) * self.dt
        if (not np.isfinite(first_velocity).all()
                or np.any(np.abs(first_velocity[self.dofs]) > self.caps + 1e-6)
                or np.any(np.abs(first_velocity-self.velocity) > dv + 1e-6)):
            return None, "velocity_acceleration"
        q = self.config.q.copy()
        velocity = first_velocity.copy()
        plan = []
        frozen = np.ones(self.model.nq, dtype=bool)
        frozen[self.qids] = False
        for _ in range(int(np.ceil(np.max(self.caps)/dv)) + 2):
            candidate = q.copy()
            mujoco.mj_integratePos(self.model, candidate, velocity, self.dt)
            candidate[frozen] = self.home[frozen]
            if (np.any(candidate[self.qids] < self.ranges[:, 0] - 1e-8)
                    or np.any(candidate[self.qids] > self.ranges[:, 1] + 1e-8)):
                return None, "joint_range"
            n = max(2, int(np.ceil(np.max(np.abs(candidate-q)) / np.radians(.25))))
            for fraction in np.linspace(0, 1, n + 1)[1:]:
                clearance = self.clearance(q + fraction*(candidate-q), threshold=self.clearance_m)
                if not np.isfinite(clearance) or clearance < self.clearance_m:
                    return None, "swept_clearance"
            plan.append((candidate.copy(), velocity.copy()))
            if not np.any(velocity):
                # Keep a checked stationary tail available even at rest.
                if len(plan) == 1:
                    plan.append((candidate.copy(), velocity.copy()))
                return plan, ""
            q = candidate
            velocity = np.sign(velocity) * np.maximum(0, np.abs(velocity)-dv)
        return None, "braking_horizon"


def targets_from_json(record):
    if record.get("schema") != "g1.bimanual.sim.v1" or record.get("simulation_only") is not True:
        raise ValueError("Simulation schema/provenance required")
    if record.get("return_home") is True:
        return None
    targets = {}
    for side in ("left", "right"):
        pose = record[side]
        p = np.asarray(pose["position_m"], dtype=float)
        q = np.asarray(pose["quaternion_wxyz"], dtype=float)
        if p.shape != (3,) or q.shape != (4,) or not np.isfinite(np.r_[p, q]).all():
            raise ValueError("Invalid pose")
        if abs(np.linalg.norm(q) - 1) > 1e-5:
            raise ValueError("Quaternion must be normalized")
        targets[side] = mink.SE3.from_rotation_and_translation(mink.SO3(q), p)
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--input", type=Path, help="JSONL: one paired pose or return request per 1/60 s")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sim = BimanualSimulation()
    # Validate the entire replay before advancing any simulation state.
    records = ([targets_from_json(json.loads(line)) for line in args.input.read_text().splitlines()
                if line.strip()] if args.input else None)
    viewer = None
    if args.viewer:
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(sim.model, sim.config.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output:
            for tick in range(len(records) if records is not None else 1800):
                targets = records[tick] if records is not None else dict(sim.home_targets)
                returning = targets is None if records is not None else tick >= 420
                if records is None and not returning:
                    for side, sign in (("left", 1), ("right", -1)):
                        home = sim.home_targets[side]
                        offset = np.array([.08, -sign * .06, .04]) * min(tick / 180, 1)
                        targets[side] = mink.SE3.from_rotation_and_translation(
                            home.rotation(), home.translation() + offset)
                sim.step(targets, returning=returning)
                row = dict(schema="g1.bimanual.sim.result.v1", simulation_only=True,
                           time_s=tick * sim.dt, state=sim.state, reason=sim.reason,
                           joint_names=sim.names, q_rad=sim.config.q[sim.qids].tolist(),
                           clearance_m=sim.clearance(sim.config.q))
                output.write(json.dumps(row, allow_nan=False) + "\n")
                if viewer:
                    if not viewer.is_running():
                        break
                    viewer.sync()
                    time.sleep(sim.dt)
                if sim.state == "blocked":
                    break
    finally:
        if viewer:
            viewer.close()
    print(f"SIMULATION ONLY: {sim.state}; output={args.output}")


if __name__ == "__main__":
    main()
