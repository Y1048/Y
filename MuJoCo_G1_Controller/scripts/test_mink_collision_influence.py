"""Offline diagnostic: separate kinematic coupling from collision-avoidance motion.

Runs the current yaw-link role-split controller from the nominal ready pose with
collision avoidance ON and OFF for a few representative wrist rotations.
No Unity, Quest, UDP, DDS, or hardware command path is used.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import mujoco
import numpy as np
import mink

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import run_mink_g1_right_arm_prototype as base  # noqa: E402
import run_mink_g1_right_arm_role_split as role_split  # noqa: E402
import run_mink_g1_right_arm_role_split_hysteresis as hysteresis  # noqa: E402

SETTLE_STEPS = 240
MAX_VELOCITY_DEG_S = 50.0


def _axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    v = 1.0 - c
    return np.array([
        [c+x*x*v, x*y*v-z*s, x*z*v+y*s],
        [y*x*v+z*s, c+y*y*v, y*z*v-x*s],
        [z*x*v-y*s, z*y*v+x*s, c+z*z*v],
    ], dtype=float)


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


def _state(collision_enabled: bool):
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    cfg = mink.Configuration(model)
    cfg.update(base._initial_configuration(model))

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos = [int(model.jnt_qposadr[base._joint_id(model, n)]) for n in base.g1.RIGHT_ARM_JOINTS]
    frozen = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, geom_pairs = base._build_collision_pairs(model)

    velocity_limits = {n: math.radians(MAX_VELOCITY_DEG_S) for n in base.g1.RIGHT_ARM_JOINTS}
    limits = [mink.ConfigurationLimit(model=model), mink.VelocityLimit(model, velocity_limits)]
    if collision_enabled:
        limits.append(mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=base.COLLISION_MIN_DISTANCE_M,
            collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
            gain=base.COLLISION_GAIN,
            broadphase=True,
        ))

    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen)]
    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture.set_target(cfg.q.copy())

    costs = np.zeros(int(model.nv), dtype=float)
    for i, n in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, n)])
        costs[dof] = 0.03 if i < 4 else 0.015
    damping = mink.DampingTask(model, cost=costs)

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

    return model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, task, base._select_solver()


def run_case(axis_index: int, angle_deg: float, collision_enabled: bool):
    model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints, posture, damping, task, solver = _state(collision_enabled)
    q0 = cfg.q[right_qpos].copy()
    pose0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    p0 = pose0.translation().copy()
    r0 = pose0.rotation().as_matrix().copy()
    target_r = r0 @ _axis_angle(np.eye(3)[:, axis_index], math.radians(angle_deg))
    task.set_target(base._matrix_to_se3(target_r, p0))

    first_collision_step = None
    first_collision_pair = None
    minimum_clearance = None

    for step in range(SETTLE_STEPS):
        v = mink.solve_ik(
            configuration=cfg,
            tasks=[task, posture, damping],
            dt=base.DT,
            solver=solver,
            damping=base.QP_DAMPING,
            limits=limits,
            constraints=constraints,
        )
        cfg.integrate_inplace(v, base.DT)
        mujoco.mj_fwdPosition(model, cfg.data)
        d, pair = _nearest_pair(model, cfg.data, geom_pairs)
        if d is not None:
            if minimum_clearance is None or d < minimum_clearance:
                minimum_clearance = d
            if first_collision_step is None and d < base.COLLISION_MIN_DISTANCE_M:
                first_collision_step = step
                first_collision_pair = pair

    pose = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    dq = np.degrees(cfg.q[right_qpos] - q0)
    return {
        "prox": float(np.max(np.abs(dq[:4]))),
        "pos_cm": float(np.linalg.norm(p0 - pose.translation()) * 100.0),
        "rot_deg": math.degrees(base._rotation_error_radians(target_r, pose.rotation().as_matrix())),
        "min_mm": None if minimum_clearance is None else minimum_clearance * 1000.0,
        "first_step": first_collision_step,
        "pair": first_collision_pair,
    }


def main() -> None:
    cases = [(1, 30.0), (1, -30.0), (1, 60.0), (2, 60.0)]
    names = ["pitch_+30", "pitch_-30", "pitch_+60", "yaw_+60"]

    print("G1 Mink collision influence diagnostic")
    print("--------------------------------------")
    print("Current yaw-link role split, ready pose")
    print("Comparing collision avoidance ON vs OFF\n")

    for name, (axis, angle) in zip(names, cases):
        off = run_case(axis, angle, False)
        on = run_case(axis, angle, True)
        print(
            f"{name:10s} | OFF prox={off['prox']:6.2f}° pos={off['pos_cm']:5.2f}cm rot={off['rot_deg']:5.2f}° "
            f"| ON prox={on['prox']:6.2f}° pos={on['pos_cm']:5.2f}cm rot={on['rot_deg']:5.2f}°"
        )
        if on['first_step'] is None:
            print(f"           collision ON trajectory: no <12mm event, min={on['min_mm']:.1f} mm" if on['min_mm'] is not None else "           collision ON trajectory: no measured pair")
        else:
            pair = " <-> ".join(on['pair']) if on['pair'] else "unknown"
            print(f"           first <12mm at step {on['first_step']}, min={on['min_mm']:.1f} mm, pair={pair}")

    print("\nInterpretation:")
    print("- OFF already large proximal motion => kinematic/position coupling is primary.")
    print("- ON much larger than OFF => collision avoidance is adding arm motion.")
    print("- Use the reported first collision pair before changing any collision exclusions.")


if __name__ == "__main__":
    main()
