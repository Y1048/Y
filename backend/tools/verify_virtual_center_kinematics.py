"""Offline FK-target comparison; never imports a robot SDK or opens a socket."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import mink
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MuJoCo_G1_Controller" / "scripts"))
sys.path.insert(0, str(ROOT / "hardware" / "g1_arm_bridge"))

import run_mink_g1_right_arm_prototype as base
import run_mink_g1_right_arm_virtual_center_live as live
from gate7_capture_quality import _decode_capture


class LegacyOrientationTask(live.VirtualCenterOrientationTask):
    def compute_jacobian(self, configuration):
        jacobian = self.inner.compute_jacobian(configuration).copy()
        jacobian[3:6, self.proximal_dofs] *= self.last_assist_gain
        return jacobian


class ExactOrientationTask(live.VirtualCenterOrientationTask):
    def compute_jacobian(self, configuration):
        return self.inner.compute_jacobian(configuration)


def CheckJacobian(model, initial_q):
    configuration = mink.Configuration(model)
    configuration.update(initial_q)
    task = LegacyOrientationTask(model)
    task.set_target_from_configuration(configuration)
    live.VirtualCenterOrientationTask.last_assist_gain = 0.0
    epsilon = 1e-6
    finite = np.zeros((6, model.nv))
    for dof in base._right_arm_dof_indices(model):
        velocity = np.zeros(model.nv)
        velocity[dof] = 1.0
        configuration.update(initial_q)
        configuration.integrate_inplace(velocity, epsilon)
        plus = task.inner.compute_error(configuration)
        configuration.update(initial_q)
        configuration.integrate_inplace(velocity, -epsilon)
        minus = task.inner.compute_error(configuration)
        finite[:, dof] = (plus - minus) / (2.0 * epsilon)
    configuration.update(initial_q)
    dofs = base._right_arm_dof_indices(model)
    current_task = live.VirtualCenterOrientationTask(model)
    current_task.set_target_from_configuration(configuration)
    return {
        "legacy_max_derivative_error": float(np.max(np.abs(
            task.compute_jacobian(configuration)[3:, dofs] - finite[3:, dofs]
        ))),
        "exact_max_derivative_error": float(np.max(np.abs(
            task.inner.compute_jacobian(configuration)[3:, dofs] - finite[3:, dofs]
        ))),
        "current_max_derivative_error": float(np.max(np.abs(
            current_task.compute_jacobian(configuration)[3:, dofs] - finite[3:, dofs]
        ))),
    }


def RunCase(model, initial_q, target, mode, duration_s, target_function=None, clearance_stride=10,
            trajectory_duration_s=None, position_frame=None, posture_scale=1.0):
    configuration = mink.Configuration(model)
    configuration.update(initial_q)
    dofs = base._right_arm_dof_indices(model)
    pairs, geom_pairs = base._build_collision_pairs(model)
    if position_frame is None:
        position_frame = "right_wrist_yaw_link" if mode == "exact_pose" else "right_wrist_roll_link"
    yaw_position = position_frame == "right_wrist_yaw_link"
    position = mink.FrameTask(
        frame_name=position_frame, frame_type="body", position_cost=base.POSITION_COST,
        orientation_cost=0.0, gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING,
    )
    live.VirtualCenterOrientationTask.assist_latched = False
    live.VirtualCenterOrientationTask.last_assist_gain = 0.0
    orientation_class = LegacyOrientationTask if mode == "legacy" else ExactOrientationTask
    if mode == "exact_posture":
        orientation_class = live.VirtualCenterOrientationTask
    orientation = orientation_class(model)
    orientation.set_target(target)
    posture = mink.PostureTask(model, cost=base.POSTURE_COST)
    if mode == "exact_posture":
        posture.cost[:] = live.virtual_center_posture_costs(model)
    posture.cost[:] *= posture_scale
    posture.set_target(initial_q)
    damping = mink.DampingTask(model, cost=live.virtual_center_damping_costs(model))
    if mode == "exact_damped":
        damping.cost[dofs[:4]] = 0.3
    limits = [
        mink.ConfigurationLimit(model),
        mink.VelocityLimit(model, live.virtual_center_velocity_limits()),
        mink.CollisionAvoidanceLimit(
            model, geom_pairs=pairs,
            minimum_distance_from_collisions=live.TELEOP_COLLISION_TARGET_DISTANCE_M,
            collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
            gain=base.COLLISION_GAIN, broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model, dof_indices=base._frozen_dof_indices(model, dofs))]
    maximum_velocity = np.zeros(7)
    minimum_clearance = float("inf")
    position_errors = []
    rotation_errors = []
    maximum_proximal_excursion = 0.0
    maximum_joint_limit_violation = 0.0
    maximum_frozen_drift = 0.0
    qpos = [int(model.jnt_qposadr[base._joint_id(model, name)]) for name in base.g1.RIGHT_ARM_JOINTS]
    solver = base._select_solver()
    for step in range(round(duration_s / base.DT)):
        if target_function is not None:
            target = target_function(step * base.DT)
        orientation.set_target(target)
        yaw = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        roll = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
        target_position = target.translation()
        if not yaw_position:
            target_position = target_position - (yaw.translation() - roll.translation())
        # live 제어기와 같이 위치 task의 목표 회전은 현재 프레임 회전이다.
        # yaw 목표 회전을 여기에도 넣으면 SE(3) log의 위치 오차까지 달라진다.
        position_rotation = yaw.rotation().as_matrix() if yaw_position else roll.rotation().as_matrix()
        position.set_target(base._matrix_to_se3(position_rotation, target_position))
        velocity = mink.solve_ik(
            configuration, [position, orientation, posture, damping], base.DT,
            solver=solver, damping=base.QP_DAMPING, limits=limits, constraints=constraints,
        )
        maximum_velocity = np.maximum(maximum_velocity, np.abs(velocity[dofs]))
        configuration.integrate_inplace(velocity, base.DT)
        actual = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        position_errors.append(float(np.linalg.norm(target.translation() - actual.translation()) * 100))
        rotation_errors.append(math.degrees(base._rotation_error_radians(
            target.rotation().as_matrix(), actual.rotation().as_matrix()
        )))
        maximum_proximal_excursion = max(maximum_proximal_excursion, float(np.max(
            np.abs(np.rad2deg(configuration.q[qpos[:4]] - initial_q[qpos[:4]]))
        )))
        for joint_id in range(model.njnt):
            if model.jnt_type[joint_id] != mujoco.mjtJoint.mjJNT_HINGE:
                continue
            address = int(model.jnt_qposadr[joint_id])
            value = configuration.q[address]
            if address not in qpos:
                maximum_frozen_drift = max(maximum_frozen_drift, abs(float(value - initial_q[address])))
            if model.jnt_limited[joint_id]:
                low, high = model.jnt_range[joint_id]
                maximum_joint_limit_violation = max(maximum_joint_limit_violation, float(low - value), float(value - high))
        if step % clearance_stride == 0:
            nearest = base._nearest_pair_distance(model, configuration.data, geom_pairs)
            if nearest:
                minimum_clearance = min(minimum_clearance, nearest[0])
    actual = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    qpos = [int(model.jnt_qposadr[base._joint_id(model, name)]) for name in base.g1.RIGHT_ARM_JOINTS]
    result = {
        "position_error_cm": float(np.linalg.norm(target.translation() - actual.translation()) * 100),
        "orientation_error_deg": math.degrees(base._rotation_error_radians(
            target.rotation().as_matrix(), actual.rotation().as_matrix()
        )),
        "sampled_minimum_clearance_mm": float(minimum_clearance * 1000),
        "maximum_joint_velocity_deg_s": np.rad2deg(maximum_velocity).tolist(),
        "final_joint_delta_deg": np.rad2deg(configuration.q[qpos] - initial_q[qpos]).tolist(),
        "position_error_p95_cm": float(np.percentile(position_errors, 95)),
        "orientation_error_p95_deg": float(np.percentile(rotation_errors, 95)),
        "maximum_proximal_excursion_deg": maximum_proximal_excursion,
        "maximum_joint_limit_violation_rad": maximum_joint_limit_violation,
        "maximum_frozen_joint_drift_rad": maximum_frozen_drift,
        "final_position_error_vector_m": (target.translation() - actual.translation()).tolist(),
        "final_right_arm_q_rad": configuration.q[qpos].tolist(),
        "final_joint_velocity_deg_s": np.rad2deg(velocity[dofs]).tolist(),
        "last_second_position_error_range_cm": [float(np.min(position_errors[-60:])), float(np.max(position_errors[-60:]))],
    }
    if trajectory_duration_s is not None:
        boundary = min(len(position_errors), max(1, math.ceil(trajectory_duration_s / base.DT)))
        result["motion_position_error_p95_cm"] = float(np.percentile(position_errors[:boundary], 95))
        result["motion_orientation_error_p95_deg"] = float(np.percentile(rotation_errors[:boundary], 95))
        result["settled_after_hold_s"] = None
        # 최소 1초 이상 1 cm / 5도 이내를 계속 유지한 시점만 수렴으로 표시한다.
        acceptable = (np.array(position_errors[boundary:]) <= 1.0) & (np.array(rotation_errors[boundary:]) <= 5.0)
        for index in range(max(0, len(acceptable) - math.ceil(1.0 / base.DT) + 1)):
            if acceptable[index:].all():
                result["settled_after_hold_s"] = index * base.DT
                break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6.0)
    args = parser.parse_args()
    if not 0 < args.duration <= 30:
        parser.error("duration must be in (0, 30]")
    manifest, packets = _decode_capture(args.capture)
    active = [p for p in packets if p["sample"].active and p["sample"].input_command_mode == "active"]
    if not active:
        raise ValueError("capture contains no active samples")
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    qpos = [int(model.jnt_qposadr[base._joint_id(model, name)]) for name in base.g1.G1_29_JOINTS]
    initial_q = base._initial_configuration(model)
    initial_q[qpos] = active[0]["value"]["all_joint_q_rad"]
    result = {
        "capture_id": manifest["capture_id"], "robot_command": False,
        "interpretation": "FK of recorded poses gives known reachable static targets, NOT original Quest target replay; clearance sampled every 10 solver ticks.",
        "jacobian": CheckJacobian(model, initial_q), "cases": [],
    }
    for seconds in (2.0, 6.0, 10.0, 14.0, 18.0):
        packet = min(active, key=lambda p: abs(p["offset_s"] - active[0]["offset_s"] - seconds))
        target_configuration = mink.Configuration(model)
        target_q = initial_q.copy()
        target_q[qpos] = packet["value"]["all_joint_q_rad"]
        target_configuration.update(target_q)
        target = target_configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        case = {"recorded_seconds": seconds, "variants": {}}
        for mode in ("legacy", "exact_orientation", "exact_pose", "exact_damped", "exact_posture"):
            case["variants"][mode] = RunCase(model, initial_q, target, mode, args.duration)
            print(seconds, mode, json.dumps(case["variants"][mode]), flush=True)
        result["cases"].append(case)
    result["wrist_only_trajectories"] = []
    for wrist_index in (4, 5, 6):
        target_configuration = mink.Configuration(model)
        wrist_qpos = int(model.jnt_qposadr[base._joint_id(model, base.g1.RIGHT_ARM_JOINTS[wrist_index])])

        def TargetAt(seconds):
            target_q = initial_q.copy()
            target_q[wrist_qpos] += math.radians(25) * math.sin(2 * math.pi * seconds / 12.0)
            target_configuration.update(target_q)
            return target_configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

        case = {"wrist_index": wrist_index, "variants": {}}
        for mode in ("legacy", "exact_orientation", "exact_pose", "exact_damped", "exact_posture"):
            case["variants"][mode] = RunCase(model, initial_q, TargetAt(0), mode, 12.0, TargetAt)
            print("wrist", wrist_index, mode, json.dumps(case["variants"][mode]), flush=True)
        result["wrist_only_trajectories"].append(case)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
