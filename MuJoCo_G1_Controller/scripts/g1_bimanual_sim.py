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
import g1_mink_shared as base
from g1_bimanual_runtime import require_validated_engine
from g1_bimanual_motion_policy import ArmMotionPolicy
from g1_bimanual_return import BimanualReturnMotion
from g1_bimanual_safety import BimanualSafetyEnvelope
from g1_bimanual_profile import RETURN as RETURN_PROFILE, TRACKING as PROFILE


class BimanualSimulation:
    dt = 1.0 / PROFILE.control_hz
    clearance_m = PROFILE.hard_clearance_m

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
        self.base_yaw_rad = 0.
        self.base_rotation = np.eye(3)
        self.names = base.g1.LEFT_ARM_JOINTS + base.g1.RIGHT_ARM_JOINTS
        ids = [base._joint_id(self.model, name) for name in self.names]
        self.qids = self.model.jnt_qposadr[ids]
        self.dofs = self.model.jnt_dofadr[ids]
        for side in ("left", "right"):
            jid = base._joint_id(self.model, side + "_elbow_joint")
            self.model.jnt_range[jid] = [
                PROFILE.elbow_operational_min_rad,
                PROFILE.elbow_operational_max_rad,
            ]
        self.home = base._initial_configuration(self.model)
        self.config = mink.Configuration(self.model)
        self.config.update(self.home)
        free_ids = np.flatnonzero(self.model.jnt_type == mujoco.mjtJoint.mjJNT_FREE)
        if len(free_ids) != 1:
            raise ValueError('Expected one prescribed G1 base joint')
        self.base_qadr = int(self.model.jnt_qposadr[free_ids[0]])
        self.initial_base_pose = self.home[self.base_qadr:self.base_qadr+7].copy()
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
        self.home_targets = {side: self.config.get_transform_frame_to_world(
            side + "_wrist_yaw_link", "body") for side in ("left", "right")}
        self.caps = np.asarray(PROFILE.joint_velocity_limits_rad_s, dtype=float)
        self.return_caps = np.asarray(
            RETURN_PROFILE.joint_velocity_limits_rad_s, dtype=float)
        self.profile = PROFILE
        self.return_profile = RETURN_PROFILE
        self.safety = BimanualSafetyEnvelope(
            self, [pairs[i] for i in keep])
        # Compatibility aliases: implementation ownership is in SafetyEnvelope.
        self.limits = self.safety.limits
        self.check_data = self.safety.check_data
        self.pair_array = self.safety.pair_array
        self._clearance_local_centers = self.safety.clearance_local_centers
        self._clearance_bounding_radii = self.safety.clearance_bounding_radii
        self.ranges = self.model.jnt_range[ids].copy()
        self.motion = {side: ArmMotionPolicy(self.model, self.config, side,
                       self.home, self.dt, self.clearance_m) for side in ('left', 'right')}
        self._motion_returning = False
        self.policy_pairs = {}
        for side in self.motion:
            bodies = getattr(base.g1, side.upper() + '_ARM_BODY_NAMES')
            self.policy_pairs[side] = [pair for pair in self.pairs if any(
                mujoco.mj_id2name(self.model, mujoco.mjtObj.mjOBJ_BODY,
                                 int(self.model.geom_bodyid[g])) in bodies for g in pair)]
        self.brake_plan = []
        self.checked_target_data = mujoco.MjData(self.model)
        self.checked_target_body_ids = {
            side: mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_BODY,
                side + "_wrist_yaw_link")
            for side in ("left", "right")
        }
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
        """Compatibility proxy for hard geometry safety."""
        return self.safety.clearance(q, threshold=threshold)

    def set_base_yaw(self, yaw):
        """Prescribed Omni base pose; not a joint and never optimized by IK."""
        if not np.isfinite(yaw):
            raise ValueError('base_yaw')
        if yaw == self.base_yaw_rad:
            return
        rotation = mink.SO3.exp(np.array([0., 0., yaw]))
        self.base_yaw_rad = float(yaw)
        delta_rotation = rotation.as_matrix() @ self.base_rotation.T
        self.base_rotation = rotation.as_matrix()
        address = self.base_qadr
        pose = np.r_[self.base_rotation @ self.initial_base_pose[:3],
            (rotation @ mink.SO3(self.initial_base_pose[3:])).wxyz]
        self.home[address:address+7] = pose
        q = self.config.q.copy()
        q[address:address+7] = pose
        self.config.update(q)
        # Cached stopping tails contain complete qpos, including the prescribed base.
        # A common yaw preserves self-collision distances and arm velocity bounds.
        for candidate, _ in self.brake_plan:
            candidate[address:address+7] = pose
        self.check_data.qpos[address:address+7] = pose
        mujoco.mj_forward(self.model, self.check_data)
        for policy in self.motion.values():
            policy.posture_reference[address:address+7] = pose
            policy.posture_task.set_target(policy.posture_reference)
            policy.distance_probe_data.qpos[address:address+7] = pose
            policy.elbow_task.world_to_base = self.base_rotation.T
            if policy._elbow_reference_q is not None:
                policy._elbow_reference_q[address:address+7] = pose
                policy._reference_wrist_position = delta_rotation @ policy._reference_wrist_position
                policy._reference_elbow_position = delta_rotation @ policy._reference_elbow_position
            if policy.elbow_task.target_position is not None:
                policy.elbow_task.target_position = delta_rotation @ policy.elbow_task.target_position

    def step(self, targets=None, *, returning=False):
        """Both wrist poses in MuJoCo world; return is a checked staged joint trajectory.

        Accept steps only with a checked stopping tail. Infeasible/unsafe QP
        results follow the previous tail; no valid tail latches blocked.
        This is deliberately not a physical stopping controller.
        """
        if self.state == "blocked":
            return False
        if returning:
            if not self._motion_returning:
                self.return_motion.reset()
                transition_plan, reason = (
                    self.safety.return_transition_stop_plan())
                if transition_plan is None:
                    # A slower stop travels farther and may be unsafe. Never
                    # discard the already-verified tracking tail or freeze at
                    # speed merely because the conservative alternative fails.
                    self.return_motion.recovering = True
                    self.return_motion.rejected_reason = (
                        "return_transition_original_tail:" + reason)
                else:
                    self.brake_plan = transition_plan
                    if np.any(np.abs(self.velocity[self.dofs])
                              > self.return_caps + 1e-6):
                        # Do not seed the low-speed return trajectory from an
                        # above-cap tracking velocity. Finish this checked stop.
                        self.return_motion.recovering = True
                        self.return_motion.rejected_reason = (
                            "return_transition_above_velocity_cap")
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
        problem = mink.build_ik(
            self.config, tasks, self.dt, damping=PROFILE.build_ik_damping,
                                limits=self.limits[:2], constraints=[])
        problem = self.safety.constrain_problem(
            problem, returning=returning)
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
            plan, reason = self.checked_stop_plan(velocity, returning=returning)
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
            plan, rejected = self.checked_stop_plan(
                np.zeros(self.model.nv), returning=returning)
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

    def checked_stop_target_poses(self):
        """FK of the already-validated stationary endpoint of the active stop tail."""
        if not self.brake_plan:
            return None
        q, velocity = self.brake_plan[-1]
        if np.any(np.abs(velocity) > 1e-12):
            return None
        data = self.checked_target_data
        data.qpos[:] = q
        mujoco.mj_kinematics(self.model, data)
        return {
            side: (
                data.xpos[body_id].copy(),
                data.xmat[body_id].reshape(3, 3).copy(),
            )
            for side, body_id in self.checked_target_body_ids.items()
        }

    def checked_stop_plan(self, first_velocity, *, returning=False):
        """Compatibility proxy for the named safety boundary."""
        return self.safety.checked_stop_plan(
            first_velocity, returning=returning)


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
