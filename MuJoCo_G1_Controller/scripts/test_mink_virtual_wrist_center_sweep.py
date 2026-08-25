"""Broad offline A/B sweep for G1 Mink wrist-control formulations.

No Unity, Quest, UDP, DDS, or robot hardware is required.

A = current yaw-link role-split formulation.
B = virtual wrist-center candidate:
    position at right_wrist_roll_link,
    orientation at right_wrist_yaw_link.

The sweep varies initial arm posture, wrist rotation, mixed-axis rotation, and
small Cartesian translations. Its purpose is to decide whether B is robust
across the operating region before any VR/live-controller promotion.
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
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_mink_virtual_wrist_center_sweep.json"

sys.path.insert(0, str(THIS_DIR))
import run_mink_g1_right_arm_prototype as base  # noqa: E402
import run_mink_g1_right_arm_role_split as role_split  # noqa: E402
import run_mink_g1_right_arm_role_split_hysteresis as hysteresis  # noqa: E402

DT = base.DT
SETTLE_STEPS = 180
MAX_VELOCITY_DEG_S = 50.0

POSITION_LIMIT_M = 0.015
ORIENTATION_LIMIT_DEG = 3.0
PROXIMAL_PREFERRED_DEG = 2.0
COLLISION_MIN_M = base.COLLISION_MIN_DISTANCE_M

# Six intentionally different but moderate right-arm starting configurations.
# Values are degrees in G1.RIGHT_ARM_JOINTS order.
START_POSTURES = {
    "ready": [10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0],
    "forward_low": [-10.0, -28.0, 8.0, 72.0, 0.0, -10.0, 0.0],
    "forward_high": [28.0, -30.0, -8.0, 45.0, 0.0, 12.0, 0.0],
    "outboard": [5.0, -48.0, 20.0, 68.0, 5.0, 0.0, 0.0],
    "inboard": [-18.0, -8.0, -22.0, 82.0, -5.0, 0.0, 0.0],
    "extended": [-22.0, -25.0, 5.0, 32.0, 0.0, 0.0, 0.0],
}


@dataclass
class Case:
    name: str
    rotation_deg_xyz: tuple[float, float, float]
    translation_m_xyz: tuple[float, float, float]
    family: str


@dataclass
class Result:
    controller: str
    start_posture: str
    case: str
    family: str
    position_error_m: float
    orientation_error_deg: float
    proximal_max_change_deg: float
    proximal_rms_change_deg: float
    wrist_max_change_deg: float
    peak_velocity_deg_s: float
    min_wrist_limit_margin_deg: float
    minimum_clearance_m: float | None
    collision_violation: bool
    nearest_pair: list[str] | None
    passed_tracking: bool


def _axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    v = 1.0 - c
    return np.array(
        [
            [c+x*x*v, x*y*v-z*s, x*z*v+y*s],
            [y*x*v+z*s, c+y*y*v, y*z*v-x*s],
            [z*x*v-y*s, z*y*v+x*s, c+z*z*v],
        ], dtype=float,
    )


def _rotation_xyz(deg_xyz: tuple[float, float, float]) -> np.ndarray:
    rx, ry, rz = [math.radians(v) for v in deg_xyz]
    return (
        _axis_angle(np.array([1.0, 0.0, 0.0]), rx)
        @ _axis_angle(np.array([0.0, 1.0, 0.0]), ry)
        @ _axis_angle(np.array([0.0, 0.0, 1.0]), rz)
    )


def _nearest_pair(model, data, geom_pairs, distmax: float = 0.20):
    nearest = None
    names = None
    fromto = np.zeros(6, dtype=float)
    for g1_id, g2_id in geom_pairs:
        d = float(mujoco.mj_geomDistance(model, data, int(g1_id), int(g2_id), distmax, fromto))
        if d >= distmax:
            continue
        if nearest is None or d < nearest:
            nearest = d
            n1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g1_id))
            n2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g2_id))
            names = [n1 or f"geom#{g1_id}", n2 or f"geom#{g2_id}"]
    return nearest, names


def _wrist_margin_deg(model, q) -> float:
    margins = []
    for name in base.g1.RIGHT_ARM_JOINTS[4:]:
        jid = base._joint_id(model, name)
        if not bool(model.jnt_limited[jid]):
            continue
        adr = int(model.jnt_qposadr[jid])
        low, high = model.jnt_range[jid]
        value = float(q[adr])
        margins.append(math.degrees(max(0.0, min(value-low, high-value))))
    return min(margins) if margins else float("inf")


def _new_state(start_deg: list[float]):
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    cfg = mink.Configuration(model)
    q0 = base._initial_configuration(model)
    data = mujoco.MjData(model)
    data.qpos[:] = q0
    for name, deg in zip(base.g1.RIGHT_ARM_JOINTS, start_deg):
        base.g1.set_joint(model, data, name, math.radians(deg))
    base.g1.clamp_joint_angles(model, data, base.g1.RIGHT_ARM_JOINTS)
    mujoco.mj_forward(model, data)
    cfg.update(data.qpos.copy())

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos = [int(model.jnt_qposadr[base._joint_id(model, n)]) for n in base.g1.RIGHT_ARM_JOINTS]
    frozen = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, geom_pairs = base._build_collision_pairs(model)

    velocity_limits = {n: math.radians(MAX_VELOCITY_DEG_S) for n in base.g1.RIGHT_ARM_JOINTS}
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
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen)]
    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture.set_target(cfg.q.copy())
    costs = np.zeros(int(model.nv))
    for i, n in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, n)])
        costs[dof] = 0.03 if i < 4 else 0.015
    damping = mink.DampingTask(model, cost=costs)
    return model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, base._select_solver()


class OrientationOnlyTask(Task):
    def __init__(self, model):
        self.inner = mink.FrameTask(
            frame_name="right_wrist_yaw_link", frame_type="body",
            position_cost=0.0, orientation_cost=1.0,
            gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING,
        )
        self.proximal_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, n)])
            for n in base.g1.RIGHT_ARM_JOINTS[:4]
        ]
        super().__init__(
            cost=np.array([0.0,0.0,0.0,base.ORIENTATION_COST,base.ORIENTATION_COST,base.ORIENTATION_COST]),
            gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING,
        )

    def set_target(self, target):
        self.inner.set_target(target)

    def compute_error(self, configuration):
        return self.inner.compute_error(configuration)

    def compute_jacobian(self, configuration):
        jac = self.inner.compute_jacobian(configuration).copy()
        jac[3:6, self.proximal_dofs] = 0.0
        return jac


def _configure_current_task(model):
    role_split.PROXIMAL_ORIENTATION_ASSIST_MIN = 0.0
    role_split.PROXIMAL_ORIENTATION_ASSIST_MAX = 0.14
    role_split.WRIST_LIMIT_ASSIST_START_DEG = hysteresis.ASSIST_ENTER_MARGIN_DEG
    role_split.WRIST_LIMIT_ASSIST_FULL_DEG = hysteresis.ASSIST_FULL_MARGIN_DEG
    role_split.RoleSplitFrameTask._proximal_orientation_assist = hysteresis._hysteretic_proximal_orientation_assist
    hysteresis.HysteresisState.assist_latched = False
    return role_split.RoleSplitFrameTask(
        frame_name="right_wrist_yaw_link", frame_type="body",
        position_cost=base.POSITION_COST, orientation_cost=base.ORIENTATION_COST,
        gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING,
    )


def _run(controller: str, start_name: str, start_deg: list[float], case: Case) -> Result:
    model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, solver = _new_state(start_deg)
    q_start = cfg.q[right_qpos].copy()
    yaw0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    yaw_r0 = yaw0.rotation().as_matrix().copy()
    rot_target = yaw_r0 @ _rotation_xyz(case.rotation_deg_xyz)
    translation = np.asarray(case.translation_m_xyz, dtype=float)

    if controller == "A":
        task = _configure_current_task(model)
        target_p = yaw0.translation().copy() + translation
        task.set_target(base._matrix_to_se3(rot_target, target_p))
        tasks = [task, posture, damping]
        position_frame = "right_wrist_yaw_link"
        position_target = target_p
    else:
        roll0 = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
        position_target = roll0.translation().copy() + translation
        pos_task = mink.FrameTask(
            frame_name="right_wrist_roll_link", frame_type="body",
            position_cost=base.POSITION_COST, orientation_cost=0.0,
            gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING,
        )
        pos_task.set_target(base._matrix_to_se3(roll0.rotation().as_matrix(), position_target))
        rot_task = OrientationOnlyTask(model)
        rot_task.set_target(base._matrix_to_se3(rot_target, yaw0.translation()))
        tasks = [pos_task, rot_task, posture, damping]
        position_frame = "right_wrist_roll_link"

    peak = 0.0
    nearest = None
    nearest_names = None
    for _ in range(SETTLE_STEPS):
        velocity = mink.solve_ik(
            configuration=cfg, tasks=tasks, dt=DT, solver=solver,
            damping=base.QP_DAMPING, limits=limits, constraints=constraints,
        )
        peak = max(peak, float(np.max(np.abs(np.degrees(velocity[right_dofs])))))
        cfg.integrate_inplace(velocity, DT)
        mujoco.mj_fwdPosition(model, cfg.data)
        d, names = _nearest_pair(model, cfg.data, geom_pairs)
        if d is not None and (nearest is None or d < nearest):
            nearest, nearest_names = d, names

    pos_pose = cfg.get_transform_frame_to_world(position_frame, "body")
    yaw_pose = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    dq = np.degrees(cfg.q[right_qpos] - q_start)
    pos_err = float(np.linalg.norm(position_target - pos_pose.translation()))
    rot_err = math.degrees(base._rotation_error_radians(rot_target, yaw_pose.rotation().as_matrix()))
    collision = bool(nearest is not None and nearest < COLLISION_MIN_M)
    passed_tracking = pos_err <= POSITION_LIMIT_M and rot_err <= ORIENTATION_LIMIT_DEG and not collision

    return Result(
        controller=controller,
        start_posture=start_name,
        case=case.name,
        family=case.family,
        position_error_m=pos_err,
        orientation_error_deg=rot_err,
        proximal_max_change_deg=float(np.max(np.abs(dq[:4]))),
        proximal_rms_change_deg=float(np.sqrt(np.mean(np.square(dq[:4])))),
        wrist_max_change_deg=float(np.max(np.abs(dq[4:]))),
        peak_velocity_deg_s=peak,
        min_wrist_limit_margin_deg=_wrist_margin_deg(model, cfg.q),
        minimum_clearance_m=nearest,
        collision_violation=collision,
        nearest_pair=nearest_names,
        passed_tracking=passed_tracking,
    )


def _cases() -> list[Case]:
    result: list[Case] = []
    for axis_i, axis in enumerate(("roll", "pitch", "yaw")):
        for angle in (-60,-45,-30,-15,15,30,45,60):
            r = [0.0,0.0,0.0]
            r[axis_i] = float(angle)
            result.append(Case(f"{axis}_{angle:+d}", tuple(r), (0.0,0.0,0.0), "single_rotation"))

    mixed = [
        (30,30,0), (30,-30,0), (-30,30,0),
        (0,30,30), (0,30,-30), (0,-30,30),
        (30,0,30), (-30,0,30),
    ]
    for r in mixed:
        result.append(Case(f"mix_{r[0]:+d}_{r[1]:+d}_{r[2]:+d}", tuple(float(v) for v in r), (0,0,0), "mixed_rotation"))

    translation_cases = [
        (0.02,0,0), (-0.02,0,0), (0,0.02,0), (0,-0.02,0), (0,0,0.02), (0,0,-0.02),
        (0.05,0,0), (-0.05,0,0), (0,0,0.05), (0,0,-0.05),
    ]
    for i, t in enumerate(translation_cases):
        # Combine translation with a representative 25 degree wrist pitch/yaw.
        rot = (0.0, 25.0 if i % 2 == 0 else -25.0, 20.0 if i % 3 == 0 else 0.0)
        result.append(Case(f"trans_{i:02d}", rot, tuple(float(v) for v in t), "translation_mixed"))
    return result


def _aggregate(results: list[Result], controller: str):
    rows = [r for r in results if r.controller == controller]
    return {
        "count": len(rows),
        "tracking_pass_count": sum(r.passed_tracking for r in rows),
        "collision_count": sum(r.collision_violation for r in rows),
        "mean_proximal_deg": float(np.mean([r.proximal_max_change_deg for r in rows])),
        "p95_proximal_deg": float(np.percentile([r.proximal_max_change_deg for r in rows], 95)),
        "worst_proximal_deg": float(np.max([r.proximal_max_change_deg for r in rows])),
        "mean_position_error_cm": float(np.mean([r.position_error_m for r in rows]) * 100.0),
        "mean_orientation_error_deg": float(np.mean([r.orientation_error_deg for r in rows])),
    }


def main() -> None:
    cases = _cases()
    total_pairs = len(START_POSTURES) * len(cases)
    print("G1 Mink virtual-wrist-center BROAD OFFLINE SWEEP")
    print("------------------------------------------------")
    print(f"Start postures : {len(START_POSTURES)}")
    print(f"Target cases   : {len(cases)}")
    print(f"A/B pairs      : {total_pairs}")
    print(f"QP runs total  : {total_pairs * 2}")
    print("Unity / Quest / UDP / robot: NONE")
    print()

    results: list[Result] = []
    pair_index = 0
    b_better = 0
    b_worse = 0
    ties = 0

    for start_name, start_deg in START_POSTURES.items():
        print(f"[START] {start_name}")
        for case in cases:
            pair_index += 1
            a = _run("A", start_name, start_deg, case)
            b = _run("B", start_name, start_deg, case)
            results.extend([a,b])
            if b.proximal_max_change_deg + 0.25 < a.proximal_max_change_deg:
                b_better += 1
            elif a.proximal_max_change_deg + 0.25 < b.proximal_max_change_deg:
                b_worse += 1
            else:
                ties += 1

            if pair_index % 20 == 0 or pair_index == total_pairs:
                print(f"  progress {pair_index}/{total_pairs}")

    a_summary = _aggregate(results, "A")
    b_summary = _aggregate(results, "B")

    family_summary = {}
    for family in sorted({r.family for r in results}):
        family_summary[family] = {}
        for controller in ("A","B"):
            rows = [r for r in results if r.family == family and r.controller == controller]
            family_summary[family][controller] = {
                "count": len(rows),
                "mean_proximal_deg": float(np.mean([r.proximal_max_change_deg for r in rows])),
                "tracking_pass_count": sum(r.passed_tracking for r in rows),
                "collision_count": sum(r.collision_violation for r in rows),
            }

    print()
    print("[SUMMARY]")
    print(
        f"A current : mean prox={a_summary['mean_proximal_deg']:.2f}° "
        f"p95={a_summary['p95_proximal_deg']:.2f}° worst={a_summary['worst_proximal_deg']:.2f}° "
        f"tracking={a_summary['tracking_pass_count']}/{a_summary['count']} collisions={a_summary['collision_count']}"
    )
    print(
        f"B virtual : mean prox={b_summary['mean_proximal_deg']:.2f}° "
        f"p95={b_summary['p95_proximal_deg']:.2f}° worst={b_summary['worst_proximal_deg']:.2f}° "
        f"tracking={b_summary['tracking_pass_count']}/{b_summary['count']} collisions={b_summary['collision_count']}"
    )
    print(f"Pairwise proximal result: B better={b_better}, worse={b_worse}, tie={ties}")

    payload = {
        "suite": "g1_mink_virtual_wrist_center_broad_sweep",
        "start_postures": START_POSTURES,
        "case_count_per_posture": len(cases),
        "pair_count": total_pairs,
        "pairwise": {"b_better": b_better, "b_worse": b_worse, "tie": ties},
        "summary": {"A": a_summary, "B": b_summary},
        "family_summary": family_summary,
        "results": [asdict(r) for r in results],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[INFO] Detailed JSON: {RESULT_PATH}")

    # This is intentionally diagnostic: promotion requires interpreting both
    # proximal stability and tracking/collision robustness, not one scalar score.
    print("[PASS] Broad offline A/B sweep completed.")


if __name__ == "__main__":
    main()
