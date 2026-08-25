"""Offline diagnostic for collision influence on the virtual-wrist-center candidate.

B candidate:
- Cartesian position task at right_wrist_roll_link (virtual wrist center).
- Orientation task at right_wrist_yaw_link.
- Proximal joints are excluded from the normal orientation objective.

Each representative rotation is solved with collision avoidance OFF and ON.
No Unity, Quest, UDP, DDS, or robot hardware is used.
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
from test_mink_virtual_wrist_center_compare import OrientationOnlyTask, _axis_angle, _nearest_pair  # noqa: E402

SETTLE_STEPS = 240
MAX_VELOCITY_DEG_S = 50.0


def _state(collision_enabled: bool):
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
    collision_pairs, geom_pairs = base._build_collision_pairs(model)

    velocity_limits = {
        n: math.radians(MAX_VELOCITY_DEG_S)
        for n in base.g1.RIGHT_ARM_JOINTS
    }
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
    ]
    if collision_enabled:
        limits.append(
            mink.CollisionAvoidanceLimit(
                model=model,
                geom_pairs=collision_pairs,
                minimum_distance_from_collisions=base.COLLISION_MIN_DISTANCE_M,
                collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
                gain=base.COLLISION_GAIN,
                broadphase=True,
            )
        )

    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen)]
    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture.set_target(cfg.q.copy())

    costs = np.zeros(int(model.nv), dtype=float)
    for i, n in enumerate(base.g1.RIGHT_ARM_JOINTS):
        dof = int(model.jnt_dofadr[base._joint_id(model, n)])
        costs[dof] = 0.03 if i < 4 else 0.015
    damping = mink.DampingTask(model, cost=costs)

    roll0 = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    position_task = mink.FrameTask(
        frame_name="right_wrist_roll_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=0.0,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    position_task.set_target(
        base._matrix_to_se3(
            roll0.rotation().as_matrix(),
            roll0.translation().copy(),
        )
    )

    orientation_task = OrientationOnlyTask(model)

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
        position_task,
        orientation_task,
        base._select_solver(),
    )


def run_case(axis_index: int, angle_deg: float, collision_enabled: bool):
    (
        model,
        cfg,
        right_dofs,
        right_qpos,
        geom_pairs,
        limits,
        constraints,
        posture,
        damping,
        position_task,
        orientation_task,
        solver,
    ) = _state(collision_enabled)

    q0 = cfg.q[right_qpos].copy()
    roll0 = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw0 = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    position_target = roll0.translation().copy()
    target_r = yaw0.rotation().as_matrix() @ _axis_angle(
        np.eye(3)[:, axis_index], math.radians(angle_deg)
    )
    orientation_task.set_target(
        base._matrix_to_se3(target_r, yaw0.translation())
    )

    first_collision_step = None
    first_collision_pair = None
    minimum_clearance = None

    for step in range(SETTLE_STEPS):
        v = mink.solve_ik(
            configuration=cfg,
            tasks=[position_task, orientation_task, posture, damping],
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

    roll = cfg.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw = cfg.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    dq = np.degrees(cfg.q[right_qpos] - q0)
    return {
        "prox": float(np.max(np.abs(dq[:4]))),
        "pos_cm": float(np.linalg.norm(position_target - roll.translation()) * 100.0),
        "rot_deg": math.degrees(
            base._rotation_error_radians(target_r, yaw.rotation().as_matrix())
        ),
        "min_mm": None if minimum_clearance is None else minimum_clearance * 1000.0,
        "first_step": first_collision_step,
        "pair": first_collision_pair,
    }


def main() -> None:
    cases = [(1, 30.0), (1, -30.0), (1, 60.0), (2, 60.0)]
    names = ["pitch_+30", "pitch_-30", "pitch_+60", "yaw_+60"]

    print("G1 Mink virtual-center collision influence diagnostic")
    print("-----------------------------------------------------")
    print("Virtual wrist center candidate, ready pose")
    print("Comparing collision avoidance ON vs OFF\n")

    for name, (axis, angle) in zip(names, cases):
        off = run_case(axis, angle, False)
        on = run_case(axis, angle, True)
        print(
            f"{name:10s} | OFF prox={off['prox']:6.2f}° pos={off['pos_cm']:5.2f}cm rot={off['rot_deg']:5.2f}° "
            f"| ON prox={on['prox']:6.2f}° pos={on['pos_cm']:5.2f}cm rot={on['rot_deg']:5.2f}°"
        )
        if on['first_step'] is None:
            if on['min_mm'] is None:
                print("           collision ON trajectory: no measured pair")
            else:
                print(
                    "           collision ON trajectory: no <12mm event, "
                    f"min={on['min_mm']:.1f} mm"
                )
        else:
            pair = " <-> ".join(on['pair']) if on['pair'] else "unknown"
            print(
                f"           first <12mm at step {on['first_step']}, "
                f"min={on['min_mm']:.1f} mm, pair={pair}"
            )

    print("\nInterpretation:")
    print("- Pitch OFF near 0 deg proximal => virtual center removed pitch coupling.")
    print("- Large ON-OFF difference => collision avoidance is the remaining source of arm motion.")
    print("- Do not remove a collision pair solely from this output; verify whether the geometry is a true physical contact first.")


if __name__ == "__main__":
    main()
