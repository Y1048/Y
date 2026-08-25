"""Offline A/B comparison for G1 wrist-orientation role splitting.

No Unity, Quest, UDP, DDS, or robot hardware is required.

A = current yaw-link role split used by the live experiment.
B = candidate virtual-wrist-center formulation:
    - position task at right_wrist_roll_link,
    - orientation task at right_wrist_yaw_link,
    - proximal orientation Jacobian suppressed during ordinary wrist motion.

This test exists to decide whether candidate B is worth promoting to live VR.
It does not modify the live controller.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np

import mink
from mink.tasks.task import Task

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parents[1]
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_mink_virtual_wrist_center_compare.json"

sys.path.insert(0, str(THIS_DIR))
import run_mink_g1_right_arm_prototype as base  # noqa: E402
import run_mink_g1_right_arm_role_split as role_split  # noqa: E402
import run_mink_g1_right_arm_role_split_hysteresis as hysteresis  # noqa: E402

SETTLE_STEPS = 240
MAX_VELOCITY_DEG_S = 50.0


@dataclass
class Result:
    controller: str
    case: str
    position_error_m: float
    orientation_error_deg: float
    proximal_max_change_deg: float
    wrist_max_change_deg: float
    peak_velocity_deg_s: float
    minimum_clearance_m: float | None
    nearest_pair: list[str] | None


def _axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    v = 1.0 - c
    return np.array(
        [
            [c + x*x*v, x*y*v - z*s, x*z*v + y*s],
            [y*x*v + z*s, c + y*y*v, y*z*v - x*s],
            [z*x*v - y*s, z*y*v + x*s, c + z*z*v],
        ],
        dtype=float,
    )


def _nearest_pair(model, data, geom_pairs, distmax: float = 0.20):
    nearest = None
    names = None
    fromto = np.zeros(6, dtype=float)
    for g1, g2 in geom_pairs:
        d = float(mujoco.mj_geomDistance(model, data, int(g1), int(g2), distmax, fromto))
        if d >= distmax:
            continue
        if nearest is None or d < nearest:
            nearest = d
            n1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g1))
            n2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g2))
            names = [n1 or f"geom#{g1}", n2 or f"geom#{g2}"]
    return nearest, names


def _common_state():
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    configuration.update(base._initial_configuration(model))

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.RIGHT_ARM_JOINTS
    ]
    frozen_dofs = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_ids = base._build_collision_pairs(model)

    velocity_limits = {
        name: math.radians(MAX_VELOCITY_DEG_S)
        for name in base.g1.RIGHT_ARM_JOINTS
    }
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
        mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=base.COLLISION_MIN_DISTANCE_M,
            collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
            gain=base.COLLISION_GAIN,
            broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)]
    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture.set_target(configuration.q.copy())

    # Keep regularization identical to the role-split experiment.
    costs = np.zeros(int(model.nv), dtype=float)
    for i, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, name)])
        costs[dof] = 0.03 if i < 4 else 0.015
    damping = mink.DampingTask(model, cost=costs)

    return model, configuration, right_dofs, right_qpos, collision_geom_ids, limits, constraints, posture, damping, base._select_solver()


class OrientationOnlyTask(Task):
    """Yaw-link orientation task; proximal joints do not solve normal orientation."""

    def __init__(self, model):
        self.inner = mink.FrameTask(
            frame_name="right_wrist_yaw_link",
            frame_type="body",
            position_cost=0.0,
            orientation_cost=1.0,
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )
        self.proximal_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS[:4]
        ]
        super().__init__(
            cost=np.array([0.0, 0.0, 0.0, base.ORIENTATION_COST, base.ORIENTATION_COST, base.ORIENTATION_COST]),
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )

    def set_target(self, target):
        self.inner.set_target(target)

    def compute_error(self, configuration):
        return self.inner.compute_error(configuration)

    def compute_jacobian(self, configuration):
        jac = self.inner.compute_jacobian(configuration).copy()
        jac[3:6, self.proximal_dofs] = 0.0
        return jac


def _run_current(axis_index: int, angle_deg: float) -> Result:
    model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, solver = _common_state()

    role_split.PROXIMAL_ORIENTATION_ASSIST_MIN = 0.0
    role_split.PROXIMAL_ORIENTATION_ASSIST_MAX = 0.14
    role_split.WRIST_LIMIT_ASSIST_START_DEG = hysteresis.ASSIST_ENTER_MARGIN_DEG
    role_split.WRIST_LIMIT_ASSIST_FULL_DEG = hysteresis.ASSIST_FULL_MARGIN_DEG
    role_split.RoleSplitFrameTask._proximal_orientation_assist = hysteresis._hysteretic_proximal_orientation_assist
    hysteresis.HysteresisState.assist_latched = False

    task = role_split.RoleSplitFrameTask(
        frame_name="right_wrist_yaw_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=base.ORIENTATION_COST,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    pose0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    p0 = pose0.translation().copy()
    r0 = pose0.rotation().as_matrix().copy()
    target_r = r0 @ _axis_angle(np.eye(3)[:, axis_index], math.radians(angle_deg))
    task.set_target(base._matrix_to_se3(target_r, p0))

    q0 = cfg.q[right_qpos].copy()
    peak = 0.0
    near = None
    pair = None
    for _ in range(SETTLE_STEPS):
        v = mink.solve_ik(cfg, [task, posture, damping], base.DT, solver, base.QP_DAMPING, limits=limits, constraints=constraints)
        peak = max(peak, float(np.max(np.abs(np.degrees(v[right_dofs])))))
        cfg.integrate_inplace(v, base.DT)
        mujoco.mj_fwdPosition(model, cfg.data)
        d, n = _nearest_pair(model, cfg.data, geom_pairs)
        if d is not None and (near is None or d < near):
            near, pair = d, n

    pose = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    dq = np.degrees(cfg.q[right_qpos] - q0)
    return Result(
        controller="current_yaw_pose",
        case=f"{['roll','pitch','yaw'][axis_index]}_{angle_deg:+.0f}",
        position_error_m=float(np.linalg.norm(p0 - pose.translation())),
        orientation_error_deg=math.degrees(base._rotation_error_radians(target_r, pose.rotation().as_matrix())),
        proximal_max_change_deg=float(np.max(np.abs(dq[:4]))),
        wrist_max_change_deg=float(np.max(np.abs(dq[4:]))),
        peak_velocity_deg_s=peak,
        minimum_clearance_m=near,
        nearest_pair=pair,
    )


def _run_virtual_center(axis_index: int, angle_deg: float) -> Result:
    model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, solver = _common_state()

    roll0 = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    roll_target_p = roll0.translation().copy()
    yaw_r0 = yaw0.rotation().as_matrix().copy()
    target_r = yaw_r0 @ _axis_angle(np.eye(3)[:, axis_index], math.radians(angle_deg))

    pos_task = mink.FrameTask(
        frame_name="right_wrist_roll_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=0.0,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    pos_task.set_target(base._matrix_to_se3(roll0.rotation().as_matrix(), roll_target_p))

    rot_task = OrientationOnlyTask(model)
    rot_task.set_target(base._matrix_to_se3(target_r, yaw0.translation()))

    q0 = cfg.q[right_qpos].copy()
    peak = 0.0
    near = None
    pair = None
    for _ in range(SETTLE_STEPS):
        v = mink.solve_ik(cfg, [pos_task, rot_task, posture, damping], base.DT, solver, base.QP_DAMPING, limits=limits, constraints=constraints)
        peak = max(peak, float(np.max(np.abs(np.degrees(v[right_dofs])))))
        cfg.integrate_inplace(v, base.DT)
        mujoco.mj_fwdPosition(model, cfg.data)
        d, n = _nearest_pair(model, cfg.data, geom_pairs)
        if d is not None and (near is None or d < near):
            near, pair = d, n

    roll = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    dq = np.degrees(cfg.q[right_qpos] - q0)
    return Result(
        controller="virtual_wrist_center",
        case=f"{['roll','pitch','yaw'][axis_index]}_{angle_deg:+.0f}",
        position_error_m=float(np.linalg.norm(roll_target_p - roll.translation())),
        orientation_error_deg=math.degrees(base._rotation_error_radians(target_r, yaw.rotation().as_matrix())),
        proximal_max_change_deg=float(np.max(np.abs(dq[:4]))),
        wrist_max_change_deg=float(np.max(np.abs(dq[4:]))),
        peak_velocity_deg_s=peak,
        minimum_clearance_m=near,
        nearest_pair=pair,
    )


def main():
    cases = [(0,30.0),(0,-30.0),(1,30.0),(1,-30.0),(2,30.0),(2,-30.0),(0,60.0),(1,60.0),(2,60.0)]
    results = []

    print("G1 Mink virtual-wrist-center OFFLINE A/B")
    print("----------------------------------------")
    print("A=current yaw-link pose task")
    print("B=virtual center position + yaw orientation")
    print("Unity / Quest / UDP / robot: NONE\n")

    for axis, angle in cases:
        a = _run_current(axis, angle)
        b = _run_virtual_center(axis, angle)
        results.extend([a,b])
        print(f"{a.case:11s} | A prox={a.proximal_max_change_deg:6.2f}° pos={a.position_error_m*100:5.2f}cm rot={a.orientation_error_deg:5.2f}° | B prox={b.proximal_max_change_deg:6.2f}° pos={b.position_error_m*100:5.2f}cm rot={b.orientation_error_deg:5.2f}°")

    def mean_prox(name):
        vals=[r.proximal_max_change_deg for r in results if r.controller==name]
        return float(np.mean(vals))

    a_mean=mean_prox("current_yaw_pose")
    b_mean=mean_prox("virtual_wrist_center")
    print()
    print(f"[SUMMARY] mean proximal motion: A={a_mean:.2f}°  B={b_mean:.2f}°")
    if b_mean < a_mean:
        print(f"[RESULT] Candidate B reduces mean proximal wrist-rotation motion by {(1.0-b_mean/max(a_mean,1e-9))*100:.1f}%.")
    else:
        print("[RESULT] Candidate B does not improve proximal stability; do not promote it to VR.")

    payload={"suite":"g1_mink_virtual_wrist_center_compare","results":[asdict(r) for r in results],"summary":{"current_mean_proximal_deg":a_mean,"candidate_mean_proximal_deg":b_mean}}
    RESULT_PATH.parent.mkdir(parents=True,exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    print(f"[INFO] Detailed JSON: {RESULT_PATH}")


if __name__ == "__main__":
    main()
