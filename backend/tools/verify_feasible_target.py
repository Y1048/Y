"""Offline recorded-goal / boundary-hold / inward-return test. No robot output."""

import argparse
import json
import math
import time
from pathlib import Path

import mink
import mujoco
import numpy as np

import verify_virtual_center_kinematics as probe
from compare_recorded_pose_speeds import GetActiveSegments, GetRecordedTargets, GetTargetIndex
from g1_mink_feasible_target import FeasibleTargetPlanner


def BuildPlanner(model, initial_q):
    base, live = probe.base, probe.live
    position = mink.FrameTask("right_wrist_roll_link", "body", base.POSITION_COST, 0,
                              gain=base.FRAME_GAIN, lm_damping=base.LM_DAMPING)
    orientation = live.VirtualCenterOrientationTask(model)
    live.VirtualCenterOrientationTask.assist_latched = False
    posture = mink.PostureTask(model, cost=live.virtual_center_posture_costs(model))
    posture.set_target(initial_q)
    damping = mink.DampingTask(model, cost=live.virtual_center_damping_costs(model))
    dofs = base._right_arm_dof_indices(model)
    limits = [mink.ConfigurationLimit(model),
              mink.VelocityLimit(model, live.virtual_center_velocity_limits()),
              mink.CollisionAvoidanceLimit(model, geom_pairs=base._build_collision_pairs(model)[0],
                  minimum_distance_from_collisions=live.TELEOP_COLLISION_TARGET_DISTANCE_M,
                  collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
                  gain=base.COLLISION_GAIN, broadphase=True)]
    constraints = [mink.DofFreezingTask(model, dof_indices=base._frozen_dof_indices(model, dofs))]
    return FeasibleTargetPlanner(model, position, orientation, posture, damping, limits,
        constraints, base._select_solver(), live.TELEOP_COLLISION_TARGET_DISTANCE_M,
        live.virtual_center_velocity_limits())


def RunSequence(model, initial_q, goals, hold_s=6.0, return_s=6.0):
    times, targets = GetRecordedTargets(goals)
    planner = BuildPlanner(model, initial_q)
    configuration = mink.Configuration(model)
    configuration.update(initial_q)
    return_goal = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    q = initial_q.copy()
    duration = max(probe.base.DT, times[-1])
    phases = {name: [] for name in ("recorded", "stationary_boundary", "inward_return")}
    statuses = {}
    velocities = []
    clearances = []
    timings = []
    frozen_drift = 0.0
    invalid_count = 0
    for index in range(math.ceil((duration + hold_s + return_s) / probe.base.DT)):
        seconds = index * probe.base.DT
        phase = "recorded" if seconds < duration else (
            "stationary_boundary" if seconds < duration + hold_s else "inward_return")
        goal = targets[GetTargetIndex(times, seconds, 1.0)] if phase != "inward_return" else return_goal
        started = time.perf_counter()
        plan = planner.Plan(q, goal)
        timings.append((time.perf_counter() - started) * 1000)
        invalid_count += int(not plan.valid)
        statuses[plan.status] = statuses.get(plan.status, 0) + 1
        velocity = np.zeros(model.nv)
        mujoco.mj_differentiatePos(model, velocity, probe.base.DT, q, plan.next_q)
        velocities.append(np.abs(np.rad2deg(velocity[planner.right_dofs])))
        frozen_drift = max(frozen_drift, float(np.max(np.abs(velocity[planner.frozen_dofs]))))
        q = plan.next_q
        configuration.update(q)
        pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        clearance = min(planner.GetClearance(q), planner.GetClearance(plan.target_q))
        clearances.append(clearance * 1000)
        phases[phase].append({
            "position_cm": float(np.linalg.norm(goal.translation() - pose.translation()) * 100),
            "rotation_deg": math.degrees(probe.base._rotation_error_radians(
                goal.rotation().as_matrix(), pose.rotation().as_matrix())),
            "joint_speed_deg_s": float(np.max(velocities[-1])),
            "green_pink_distance_cm": float(np.linalg.norm(plan.target_position - pose.translation()) * 100),
        })
    metrics = {}
    for phase, samples in phases.items():
        tail = samples[-60:]
        metrics[phase] = {
            "position_p95_cm": float(np.percentile([s["position_cm"] for s in samples], 95)),
            "rotation_p95_deg": float(np.percentile([s["rotation_deg"] for s in samples], 95)),
            "last_second_max_joint_speed_deg_s": max(s["joint_speed_deg_s"] for s in tail),
            "last_second_position_range_cm": [min(s["position_cm"] for s in tail), max(s["position_cm"] for s in tail)],
            "final": samples[-1],
        }
    return {
        "phases": metrics, "statuses": statuses, "invalid_plans": invalid_count,
        "minimum_checked_clearance_mm": min(clearances),
        "maximum_joint_velocity_deg_s": np.max(velocities, axis=0).tolist(),
        "maximum_frozen_velocity_rad_s": frozen_drift,
        "planner_ms_p50_p95_max": np.percentile(timings, [50, 95, 100]).tolist(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    manifest, packets = probe._decode_capture(args.capture)
    model = mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    qpos = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    report = {"capture_id": manifest["capture_id"], "robot_command": False,
              "policy": "checked_local_lookahead_v1", "segments": [], "review_reasons": [],
              "limits": "Local kinematic planning, sampled collision validation only. Not physical dynamics, a global reachability proof, or hardware authorization."}
    for index, (reference, goals) in enumerate(GetActiveSegments(packets), 1):
        q = probe.base._initial_configuration(model)
        q[qpos] = reference["value"]["all_joint_q_rad"]
        metrics = RunSequence(model, q, goals)
        report["segments"].append({"segment": index, **metrics})
        if metrics["invalid_plans"] or metrics["minimum_checked_clearance_mm"] < 19.999:
            report["review_reasons"].append(f"segment {index}: invalid plan or clearance")
        if metrics["phases"]["stationary_boundary"]["last_second_max_joint_speed_deg_s"] > 0.5:
            report["review_reasons"].append(f"segment {index}: boundary did not settle")
        returned = metrics["phases"]["inward_return"]["final"]
        if returned["position_cm"] > 1.0 or returned["rotation_deg"] > 5.0:
            report["review_reasons"].append(f"segment {index}: return goal did not converge")
        print(f"Segment {index}: " + json.dumps(metrics), flush=True)
    if not report["segments"]:
        raise ValueError("capture contains no active segment")
    report["status"] = "REVIEW_REQUIRED" if report["review_reasons"] else "OFFLINE_CRITERIA_MET"
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())
    print(report["status"])


if __name__ == "__main__":
    main()
