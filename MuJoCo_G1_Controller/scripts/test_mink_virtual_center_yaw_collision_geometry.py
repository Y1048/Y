"""Trace collision geometry during pure virtual-center wrist yaw.

No Unity, Quest, UDP, DDS, or robot hardware is used. Collision avoidance is
intentionally disabled so this test can measure the raw geometry distances of
the wrist-only solution without the QP moving the proximal arm to escape.
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
from test_mink_virtual_wrist_center_compare import OrientationOnlyTask, _axis_angle  # noqa: E402

MAX_VELOCITY_DEG_S = 50.0
SETTLE_STEPS = 180
TARGET_PAIR_NAMES = (
    "mink_collision_right_shoulder_yaw_link_0_32",
    "mink_collision_right_wrist_yaw_link_0_36",
)


def _geom_id(model: mujoco.MjModel, name: str) -> int:
    value = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
    if value < 0:
        raise RuntimeError(f"collision geom not found: {name}")
    return int(value)


def _distance(model, data, g1: int, g2: int, distmax: float = 0.30) -> float:
    fromto = np.zeros(6, dtype=float)
    return float(mujoco.mj_geomDistance(model, data, g1, g2, distmax, fromto))


def _nearest(model, data, pairs, distmax: float = 0.30):
    nearest = None
    nearest_names = None
    fromto = np.zeros(6, dtype=float)
    for g1, g2 in pairs:
        d = float(mujoco.mj_geomDistance(model, data, int(g1), int(g2), distmax, fromto))
        if d >= distmax:
            continue
        if nearest is None or d < nearest:
            nearest = d
            n1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g1))
            n2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(g2))
            nearest_names = [n1 or f"geom#{g1}", n2 or f"geom#{g2}"]
    return nearest, nearest_names


def _make_state():
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    cfg = mink.Configuration(model)
    cfg.update(base._initial_configuration(model))

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos = [
        int(model.jnt_qposadr[base._joint_id(model, n)])
        for n in base.g1.RIGHT_ARM_JOINTS
    ]
    frozen = base._frozen_dof_indices(model, right_dofs)
    _, geom_pairs = base._build_collision_pairs(model)

    velocity_limits = {
        n: math.radians(MAX_VELOCITY_DEG_S)
        for n in base.g1.RIGHT_ARM_JOINTS
    }
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen)]

    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture.set_target(cfg.q.copy())

    costs = np.zeros(int(model.nv), dtype=float)
    for i, n in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, n)])
        costs[dof] = 0.03 if i < 4 else 0.015
    damping = mink.DampingTask(model, cost=costs)

    roll0 = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")

    pos_task = mink.FrameTask(
        frame_name="right_wrist_roll_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=0.0,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    pos_task.set_target(base._matrix_to_se3(roll0.rotation().as_matrix(), roll0.translation()))

    rot_task = OrientationOnlyTask(model)

    return (
        model,
        cfg,
        right_dofs,
        right_qpos,
        geom_pairs,
        limits,
        constraints,
        posture,
        damping,
        pos_task,
        rot_task,
        yaw0.rotation().as_matrix().copy(),
        yaw0.translation().copy(),
        base._select_solver(),
    )


def main() -> None:
    (
        model, cfg, right_dofs, right_qpos, geom_pairs, limits, constraints,
        posture, damping, pos_task, rot_task, yaw_r0, yaw_p0, solver,
    ) = _make_state()

    target_g1 = _geom_id(model, TARGET_PAIR_NAMES[0])
    target_g2 = _geom_id(model, TARGET_PAIR_NAMES[1])
    q_start = cfg.q[right_qpos].copy()

    print("G1 virtual-center pure-yaw collision geometry trace")
    print("----------------------------------------------------")
    print("Collision avoidance: OFF")
    print("Position center     : right_wrist_roll_link")
    print("Orientation frame   : right_wrist_yaw_link")
    print(f"Tracked pair        : {TARGET_PAIR_NAMES[0]} <-> {TARGET_PAIR_NAMES[1]}\n")

    for angle_deg in range(0, 71, 10):
        target_r = yaw_r0 @ _axis_angle(np.array([0.0, 0.0, 1.0]), math.radians(angle_deg))
        rot_task.set_target(base._matrix_to_se3(target_r, yaw_p0))

        for _ in range(SETTLE_STEPS):
            velocity = mink.solve_ik(
                configuration=cfg,
                tasks=[pos_task, rot_task, posture, damping],
                dt=base.DT,
                solver=solver,
                damping=base.QP_DAMPING,
                limits=limits,
                constraints=constraints,
            )
            cfg.integrate_inplace(velocity, base.DT)
            mujoco.mj_fwdPosition(model, cfg.data)

        pair_distance = _distance(model, cfg.data, target_g1, target_g2)
        nearest_distance, nearest_names = _nearest(model, cfg.data, geom_pairs)
        pose = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        rot_error = math.degrees(
            base._rotation_error_radians(target_r, pose.rotation().as_matrix())
        )
        dq = np.degrees(cfg.q[right_qpos] - q_start)
        prox = float(np.max(np.abs(dq[:4])))
        nearest_text = "n/a" if nearest_names is None else " <-> ".join(nearest_names)
        nearest_mm = float("nan") if nearest_distance is None else nearest_distance * 1000.0

        print(
            f"yaw={angle_deg:2d} deg | tracked={pair_distance*1000.0:7.2f} mm "
            f"nearest={nearest_mm:7.2f} mm prox={prox:5.2f} deg rot_err={rot_error:5.2f} deg"
        )
        print(f"             nearest pair: {nearest_text}")

    print("\nInterpretation:")
    print("- tracked distance < 0 mm: the two collision meshes physically penetrate in MuJoCo.")
    print("- tracked distance 0..12 mm: the current safety clearance will intentionally react.")
    print("- tracked distance > 12 mm while the live solver reacts: investigate another pair/constraint.")


if __name__ == "__main__":
    main()
