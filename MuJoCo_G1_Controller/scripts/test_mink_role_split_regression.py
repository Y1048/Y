"""Offline regression suite for G1 Mink role-split teleoperation.

No Unity, Quest, UDP, DDS, or robot hardware is required. The suite applies
synthetic wrist-orientation targets while holding Cartesian position fixed, then
measures whether the role-split controller keeps shoulder/elbow motion small.
It also reports position/orientation tracking, velocity usage, joint-limit margin,
and the nearest collision geometry pair.
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

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parents[1]
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_mink_role_split_regression.json"

sys.path.insert(0, str(THIS_DIR))
import run_mink_g1_right_arm_prototype as base  # noqa: E402
import run_mink_g1_right_arm_role_split as role_split  # noqa: E402
import run_mink_g1_right_arm_role_split_hysteresis as hysteresis  # noqa: E402


SETTLE_STEPS = 240
POSITION_ERROR_PASS_M = 0.015
ORIENTATION_ERROR_PASS_DEG = 3.0
PROXIMAL_MAX_CHANGE_PASS_DEG = 2.0
VELOCITY_TOLERANCE_DEG_S = 0.5


@dataclass
class CaseResult:
    name: str
    axis: str
    target_angle_deg: float
    position_error_m: float
    orientation_error_deg: float
    proximal_max_change_deg: float
    proximal_rms_change_deg: float
    wrist_max_change_deg: float
    peak_joint_velocity_deg_s: float
    min_wrist_limit_margin_deg: float
    minimum_clearance_m: float | None
    nearest_collision_pair: list[str] | None
    proximal_assist_gain: float
    assist_latched: bool
    pass_position: bool
    pass_orientation: bool
    pass_proximal_stability: bool
    pass_velocity: bool
    passed: bool


def _axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    one_c = 1.0 - c
    return np.array(
        [
            [c + x * x * one_c, x * y * one_c - z * s, x * z * one_c + y * s],
            [y * x * one_c + z * s, c + y * y * one_c, y * z * one_c - x * s],
            [z * x * one_c - y * s, z * y * one_c + x * s, c + z * z * one_c],
        ],
        dtype=float,
    )


def _nearest_collision_pair(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    geom_pairs: list[tuple[int, int]],
    distmax: float = 0.20,
) -> tuple[float | None, list[str] | None]:
    nearest: float | None = None
    nearest_names: list[str] | None = None
    fromto = np.zeros(6, dtype=float)

    for geom1, geom2 in geom_pairs:
        distance = float(
            mujoco.mj_geomDistance(
                model,
                data,
                int(geom1),
                int(geom2),
                distmax,
                fromto,
            )
        )
        if distance >= distmax:
            continue
        if nearest is None or distance < nearest:
            nearest = distance
            name1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(geom1))
            name2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, int(geom2))
            nearest_names = [name1 or f"geom#{geom1}", name2 or f"geom#{geom2}"]

    return nearest, nearest_names


def _wrist_limit_margin_deg(model: mujoco.MjModel, q: np.ndarray) -> float:
    margins: list[float] = []
    for name in base.g1.RIGHT_ARM_JOINTS[4:]:
        joint_id = base._joint_id(model, name)
        if not bool(model.jnt_limited[joint_id]):
            continue
        qpos = int(model.jnt_qposadr[joint_id])
        low, high = model.jnt_range[joint_id]
        value = float(q[qpos])
        margins.append(math.degrees(max(0.0, min(value - low, high - value))))
    return min(margins) if margins else float("inf")


def _new_controller_state():
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    configuration.update(base._initial_configuration(model))

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos_ids = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.RIGHT_ARM_JOINTS
    ]
    frozen_dofs = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_ids = base._build_collision_pairs(model)

    # Match the live role-split+hysteresis controller exactly.
    role_split.PROXIMAL_ORIENTATION_ASSIST_MIN = 0.0
    role_split.PROXIMAL_ORIENTATION_ASSIST_MAX = 0.14
    role_split.WRIST_LIMIT_ASSIST_START_DEG = hysteresis.ASSIST_ENTER_MARGIN_DEG
    role_split.WRIST_LIMIT_ASSIST_FULL_DEG = hysteresis.ASSIST_FULL_MARGIN_DEG
    role_split.RoleSplitFrameTask._proximal_orientation_assist = (
        hysteresis._hysteretic_proximal_orientation_assist
    )
    hysteresis.HysteresisState.assist_latched = False
    role_split.RoleSplitFrameTask.last_proximal_orientation_assist = 0.0
    role_split.RoleSplitFrameTask.last_min_wrist_limit_margin_deg = float("inf")

    wrist_task = role_split.RoleSplitFrameTask(
        frame_name="right_wrist_yaw_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=base.ORIENTATION_COST,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    wrist_task.set_target_from_configuration(configuration)

    posture_task = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(model, cost=base._damping_costs(model))

    velocity_limits = {
        name: role_split.ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S * math.pi / 180.0
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

    return (
        model,
        configuration,
        right_qpos_ids,
        collision_geom_ids,
        wrist_task,
        posture_task,
        damping_task,
        limits,
        constraints,
        base._select_solver(),
    )


def _run_case(axis_index: int, angle_deg: float) -> CaseResult:
    (
        model,
        configuration,
        right_qpos_ids,
        collision_geom_ids,
        wrist_task,
        posture_task,
        damping_task,
        limits,
        constraints,
        solver,
    ) = _new_controller_state()

    initial_q = configuration.q[right_qpos_ids].copy()
    initial_pose = configuration.get_transform_frame_to_world(
        "right_wrist_yaw_link", "body"
    )
    target_position = initial_pose.translation().copy()
    initial_rotation = initial_pose.rotation().as_matrix().copy()

    local_axis = np.eye(3, dtype=float)[:, axis_index]
    target_rotation = initial_rotation @ _axis_angle(local_axis, math.radians(angle_deg))
    wrist_task.set_target(base._matrix_to_se3(target_rotation, target_position))

    peak_velocity = 0.0
    nearest_distance: float | None = None
    nearest_names: list[str] | None = None

    for _ in range(SETTLE_STEPS):
        velocity = mink.solve_ik(
            configuration=configuration,
            tasks=[wrist_task, posture_task, damping_task],
            dt=base.DT,
            solver=solver,
            damping=base.QP_DAMPING,
            limits=limits,
            constraints=constraints,
        )
        right_dofs = base._right_arm_dof_indices(model)
        if right_dofs:
            peak_velocity = max(
                peak_velocity,
                float(np.max(np.abs(np.degrees(velocity[right_dofs])))),
            )
        configuration.integrate_inplace(velocity, base.DT)
        mujoco.mj_fwdPosition(model, configuration.data)

        distance, names = _nearest_collision_pair(
            model,
            configuration.data,
            collision_geom_ids,
        )
        if distance is not None and (
            nearest_distance is None or distance < nearest_distance
        ):
            nearest_distance = distance
            nearest_names = names

    final_pose = configuration.get_transform_frame_to_world(
        "right_wrist_yaw_link", "body"
    )
    final_rotation = final_pose.rotation().as_matrix()
    position_error = float(np.linalg.norm(target_position - final_pose.translation()))
    orientation_error = math.degrees(
        base._rotation_error_radians(target_rotation, final_rotation)
    )

    final_q = configuration.q[right_qpos_ids].copy()
    delta_deg = np.degrees(final_q - initial_q)
    proximal_delta = delta_deg[:4]
    wrist_delta = delta_deg[4:]
    proximal_max = float(np.max(np.abs(proximal_delta)))
    proximal_rms = float(np.sqrt(np.mean(np.square(proximal_delta))))
    wrist_max = float(np.max(np.abs(wrist_delta)))
    wrist_margin = _wrist_limit_margin_deg(model, configuration.q)

    pass_position = position_error <= POSITION_ERROR_PASS_M
    pass_orientation = orientation_error <= ORIENTATION_ERROR_PASS_DEG
    pass_proximal = proximal_max <= PROXIMAL_MAX_CHANGE_PASS_DEG
    pass_velocity = peak_velocity <= (
        role_split.ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S
        + VELOCITY_TOLERANCE_DEG_S
    )
    passed = pass_position and pass_orientation and pass_proximal and pass_velocity

    return CaseResult(
        name=f"{['roll','pitch','yaw'][axis_index]}_{angle_deg:+.0f}deg",
        axis=["roll", "pitch", "yaw"][axis_index],
        target_angle_deg=angle_deg,
        position_error_m=position_error,
        orientation_error_deg=orientation_error,
        proximal_max_change_deg=proximal_max,
        proximal_rms_change_deg=proximal_rms,
        wrist_max_change_deg=wrist_max,
        peak_joint_velocity_deg_s=peak_velocity,
        min_wrist_limit_margin_deg=wrist_margin,
        minimum_clearance_m=nearest_distance,
        nearest_collision_pair=nearest_names,
        proximal_assist_gain=float(
            role_split.RoleSplitFrameTask.last_proximal_orientation_assist
        ),
        assist_latched=bool(hysteresis.HysteresisState.assist_latched),
        pass_position=pass_position,
        pass_orientation=pass_orientation,
        pass_proximal_stability=pass_proximal,
        pass_velocity=pass_velocity,
        passed=passed,
    )


def main() -> None:
    cases = [
        (0, +30.0),
        (0, -30.0),
        (1, +30.0),
        (1, -30.0),
        (2, +30.0),
        (2, -30.0),
        (0, +60.0),
        (1, +60.0),
        (2, +60.0),
    ]

    print("G1 Mink role-split OFFLINE regression")
    print("-------------------------------------")
    print("Unity / Quest / UDP / robot: NONE")
    print(
        "Thresholds: position <= "
        f"{POSITION_ERROR_PASS_M*100:.1f} cm, orientation <= "
        f"{ORIENTATION_ERROR_PASS_DEG:.1f} deg, proximal max <= "
        f"{PROXIMAL_MAX_CHANGE_PASS_DEG:.1f} deg"
    )
    print()

    results: list[CaseResult] = []
    for axis, angle in cases:
        result = _run_case(axis, angle)
        results.append(result)
        state = "PASS" if result.passed else "FAIL"
        clearance = (
            "n/a"
            if result.minimum_clearance_m is None
            else f"{result.minimum_clearance_m*1000:.1f} mm"
        )
        pair = (
            "n/a"
            if result.nearest_collision_pair is None
            else " <-> ".join(result.nearest_collision_pair)
        )
        print(
            f"[{state}] {result.name:12s} "
            f"pos={result.position_error_m*100:.2f} cm "
            f"rot={result.orientation_error_deg:.2f} deg "
            f"prox={result.proximal_max_change_deg:.2f} deg "
            f"wrist={result.wrist_max_change_deg:.2f} deg "
            f"vmax={result.peak_joint_velocity_deg_s:.1f} deg/s"
        )
        print(
            f"       wrist-margin={result.min_wrist_limit_margin_deg:.1f} deg "
            f"assist={result.proximal_assist_gain*100:.1f}% "
            f"latched={result.assist_latched} "
            f"clearance={clearance}"
        )
        print(f"       nearest={pair}")

    passed_count = sum(1 for result in results if result.passed)
    payload = {
        "suite": "g1_mink_role_split_regression",
        "thresholds": {
            "position_error_m": POSITION_ERROR_PASS_M,
            "orientation_error_deg": ORIENTATION_ERROR_PASS_DEG,
            "proximal_max_change_deg": PROXIMAL_MAX_CHANGE_PASS_DEG,
            "max_joint_velocity_deg_s": role_split.ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S,
        },
        "passed": passed_count == len(results),
        "passed_count": passed_count,
        "total_count": len(results),
        "cases": [asdict(result) for result in results],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"[SUMMARY] {passed_count}/{len(results)} cases passed")
    print(f"[INFO] Detailed JSON: {RESULT_PATH}")
    if passed_count != len(results):
        print("[INFO] A regression failure is diagnostic at this stage; use the numbers to tune the controller before the next VR test.")
        raise SystemExit(2)

    print("[PASS] Role-split regression suite passed without VR.")


if __name__ == "__main__":
    main()
