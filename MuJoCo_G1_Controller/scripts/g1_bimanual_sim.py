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
import run_mink_g1_right_arm_prototype as base


class BimanualSimulation:
    dt = 1.0 / 60
    clearance_m = 0.005

    def __init__(self):
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
        self.tasks = {side: mink.FrameTask(side + "_wrist_yaw_link", "body",
                     position_cost=8., orientation_cost=2., gain=.35,
                     lm_damping=1e-5) for side in ("left", "right")}
        self.home_targets = {s: self.config.get_transform_frame_to_world(
            s + "_wrist_yaw_link", "body") for s in self.tasks}
        self.posture = mink.PostureTask(self.model, cost=.04, gain=.01)
        self.posture.set_target(self.home)
        self.caps = np.tile(np.radians([90]*4 + [180]*3), 2)
        self.limits = [mink.ConfigurationLimit(self.model),
            mink.VelocityLimit(self.model, dict(zip(self.names, self.caps))),
            mink.CollisionAvoidanceLimit(self.model,
                geom_pairs=[pairs[i] for i in keep],
                minimum_distance_from_collisions=.006,
                collision_detection_distance=.15, gain=.85)]
        frozen = sorted(set(range(self.model.nv)) - set(self.dofs))
        self.constraints = [mink.DofFreezingTask(self.model, dof_indices=frozen)]
        self.velocity = np.zeros(self.model.nv)
        self.state = "ready"
        self.reason = ""
        if self.clearance(self.home) < self.clearance_m:
            raise ValueError("Initial bilateral model violates clearance")

    def clearance(self, q):
        self.check_data.qpos[:] = q
        mujoco.mj_forward(self.model, self.check_data)
        nearest = base._nearest_pair_distance(self.model, self.check_data, self.pairs)
        return .2 if nearest is None else nearest[0]

    def step(self, targets=None, *, returning=False):
        """Both wrist poses in robot frame; return is constrained joint home motion.

        Infeasible/unsafe steps latch a simulation hold. Reset requires a new
        simulation; this is deliberately not a physical stopping controller.
        """
        if self.state == "blocked":
            return False
        if not returning:
            if not isinstance(targets, dict) or set(targets) != {"left", "right"}:
                raise ValueError("Both left and right targets are required")
            for side, target in targets.items():
                if not np.isfinite(target.as_matrix()).all():
                    raise ValueError("Nonfinite target")
                self.tasks[side].set_target(target)
        tasks = [self.posture] if returning else list(self.tasks.values()) + [self.posture]
        problem = mink.build_ik(self.config, tasks, self.dt, damping=1e-7,
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
        problem.G = np.vstack([problem.G, cg])
        problem.h = np.r_[problem.h, ch * self.dt]
        # Mink solves joint displacement, not velocity.
        eye = np.eye(self.model.nv)[self.dofs]
        dv = np.radians(60) * self.dt
        hi = (self.velocity[self.dofs] + dv) * self.dt
        lo = (self.velocity[self.dofs] - dv) * self.dt
        problem.G = np.vstack([problem.G, eye, -eye])
        problem.h = np.concatenate([problem.h, hi, -lo])
        finite = np.isfinite(problem.h)
        reduced = qpsolvers.Problem(problem.P[np.ix_(self.dofs, self.dofs)],
            problem.q[self.dofs], problem.G[finite][:, self.dofs], problem.h[finite])
        result = qpsolvers.solve_problem(reduced, solver=base._select_solver())
        if not result.found or result.x is None or not np.isfinite(result.x).all():
            self.state = "blocked"
            self.reason = "qp_infeasible"
            return False
        before = self.config.q.copy()
        velocity = np.zeros(self.model.nv)
        velocity[self.dofs] = result.x / self.dt
        candidate = before.copy()
        mujoco.mj_integratePos(self.model, candidate, velocity, self.dt)
        frozen = np.ones(self.model.nq, dtype=bool)
        frozen[self.qids] = False
        candidate[frozen] = self.home[frozen]
        n = max(2, int(np.ceil(np.max(np.abs(result.x)) / np.radians(.25))))
        # Sample the interpolated joint path, including its endpoint.
        for fraction in np.linspace(0, 1, n + 1)[1:]:
            q = before + fraction * (candidate - before)
            if self.clearance(q) < self.clearance_m:
                self.state = "blocked"
                self.reason = "swept_clearance"
                return False
        jid = [base._joint_id(self.model, name) for name in self.names]
        ranges = self.model.jnt_range[jid]
        if np.any(candidate[self.qids] < ranges[:, 0] - 1e-8) or np.any(
                candidate[self.qids] > ranges[:, 1] + 1e-8):
            self.state = "blocked"
            self.reason = "joint_range"
            return False
        self.config.update(candidate)
        self.velocity = velocity
        self.state = "returning" if returning else "tracking"
        if returning and np.max(np.abs(candidate[self.qids] - self.home[self.qids])) < .002 and np.max(np.abs(velocity)) < .01:
            self.state = "ready"
        return True


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
