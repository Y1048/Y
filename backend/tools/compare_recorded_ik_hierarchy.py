"""Local recorded-delta IK comparison. No sockets, SDK or physical commands."""

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np

from compare_recorded_pose_speeds import GetActiveSegments, GetRecordedTargets, GetTargetIndex
from verify_feasible_target import BuildPlanner, probe
import g1_virtual_center_tasks as task_policy


@contextmanager
def UseOfflineProximalCost(value):
    """Change only this offline process and restore even when a trial fails."""
    if not math.isfinite(value) or value < task_policy.ORIENTATION_PROXIMAL_DAMPING_MIN:
        raise ValueError("proximal cost must be finite and at least the assist minimum")
    original = task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX
    try:
        task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX = value
        yield
    finally:
        task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX = original


def GetNormalizedGoal(reference, target, initial_center, initial_rotation):
    """Rebase recorded world-frame deltas once; do not assume old marker origin."""
    center = initial_center + target.translation() - reference.translation()
    rotation = target.rotation().as_matrix() @ reference.rotation().as_matrix().T @ initial_rotation
    return probe.base._matrix_to_se3(rotation, center)


def RunDiagnosedPlan(planner, q, goal, rows):
    """Observe the first QP pair; a shadow solve never becomes an applied command."""
    solve = probe.mink.solve_ik
    primary = None
    recorded = False

    def Observe(configuration, tasks, *args, **kwargs):
        nonlocal primary, recorded
        velocity = solve(configuration, tasks, *args, **kwargs)
        if tasks is planner.position_tasks and primary is None:
            primary = velocity.copy()
        elif tasks is planner.orientation_tasks and primary is not None and not recorded:
            recorded = True
            error = planner.orientation_task.inner.compute_error(configuration)[3:]
            jacobian = planner.orientation_task.inner.compute_jacobian(configuration)[3:]
            row = {
                "primary_saturated": (np.abs(primary[planner.right_dofs]) >= planner.velocity_caps * .99).tolist(),
                "final_saturated": (np.abs(velocity[planner.right_dofs]) >= planner.velocity_caps * .99).tolist(),
                "rotation_error_deg": math.degrees(float(np.linalg.norm(error))),
                "constrained_predicted_error_deg": math.degrees(float(np.linalg.norm(error + jacobian @ velocity * probe.base.DT))),
            }
            shadow_options = dict(kwargs, constraints=planner.orientation_constraints)
            try:
                shadow = solve(configuration, tasks, *args, **shadow_options)
                if not np.isfinite(shadow).all():
                    raise ValueError("non-finite diagnostic solve")
                row["shadow_predicted_error_deg"] = math.degrees(float(np.linalg.norm(error + jacobian @ shadow * probe.base.DT)))
            except probe.mink.NoSolutionFound:
                row["shadow_predicted_error_deg"] = None
            rows.append(row)
        return velocity

    with patch.object(probe.mink, "solve_ik", side_effect=Observe):
        return planner.Plan(q, goal, position_target=goal.translation())


def SummarizeQP(rows):
    if not rows:
        return None
    available = [r for r in rows if r["shadow_predicted_error_deg"] is not None]
    all_benefits = [r["constrained_predicted_error_deg"] - r["shadow_predicted_error_deg"] for r in available]
    high_error = [r for r in rows if r["rotation_error_deg"] > 30 and r["shadow_predicted_error_deg"] is not None]
    benefits = [r["constrained_predicted_error_deg"] - r["shadow_predicted_error_deg"] for r in high_error]
    return {
        "first_pair_frames": len(rows),
        "all_shadow_frames": len(available),
        "all_shadow_improves_fraction": float(np.mean(np.array(all_benefits) > 1e-6)) if all_benefits else None,
        "all_shadow_advantage_deg_p50_p95": np.percentile(all_benefits, [50, 95]).tolist() if all_benefits else None,
        "primary_any_saturation_fraction": float(np.mean([any(r["primary_saturated"]) for r in rows])),
        "primary_joint_saturation_fraction": np.mean([r["primary_saturated"] for r in rows], axis=0).tolist(),
        "final_joint_saturation_fraction": np.mean([r["final_saturated"] for r in rows], axis=0).tolist(),
        "rotation_over_30_deg_frames": len(high_error),
        "shadow_improves_prediction_fraction": float(np.mean(np.array(benefits) > 1e-6)) if benefits else None,
        "shadow_error_reduction_advantage_deg_p50_p95": np.percentile(benefits, [50, 95]).tolist() if benefits else None,
        "interpretation": "First QP pair per moving frame only. Shadow removes position-progress equality but retains tasks and other constraints. Prediction is first order for one dt, not executed, not an end-to-end improvement or safety proof.",
    }


def SummarizeTargetEvents(trace):
    """Exploratory 5-degree target steps and two-second windows, not causality."""
    moving = [r for r in trace if r["moving"]]
    events = []
    for i, row in enumerate(trace):
        if not row["moving"] or row["target_step_deg"] < 5.0:
            continue
        window = [r for r in trace[i:] if r["time_s"] <= row["time_s"] + 2.0]
        events.append({
            "time_s": row["time_s"], "target_step_deg": row["target_step_deg"],
            "error_before_deg": trace[max(0, i - 1)]["error_deg"],
            "error_after_step_deg": row["error_deg"],
            "next_2s_max_error_deg": max(r["error_deg"] for r in window),
        })
    away = [r for r in moving if all(not (0 <= r["time_s"] - e["time_s"] <= 2.0) for e in events)]
    return {"threshold_deg": 5.0, "window_s": 2.0, "events": events,
            "peak_error_frame": max(moving, key=lambda r: r["error_deg"]) if moving else None,
            "outside_event_window_frames": len(away),
            "outside_event_window_error_p95_deg": float(np.percentile([r["error_deg"] for r in away], 95)) if away else None}


def ApplySingleQPStep(planner, configuration, q, velocity, backtrack=False):
    """Offline only: accept the first fully checked duration, without relaxing limits."""
    if planner._VelocityValid(velocity, planner.right_dofs):
        for fraction in ((1., .5, .25, .125, .0625, .03125) if backtrack else (1.,)):
            duration = probe.base.DT * fraction
            if planner._PathClear(q, velocity, duration):
                configuration.update(q)
                configuration.integrate_inplace(velocity, duration)
                return configuration.q.copy(), "single_qp_step" if fraction == 1 else "single_qp_reduced_step"
    return q.copy(), "guard_rejected"


def RunComparison(model, initial_q, targets, times, mode, hold_s, profile, playback_speed=1.0, diagnose_qp=False, single_qp_backtrack=False):
    if not math.isfinite(playback_speed) or playback_speed <= 0:
        raise ValueError("playback_speed must be finite and positive")
    planner = BuildPlanner(model, initial_q, collision_profile=profile)
    invalid_velocities = []
    validate_velocity = planner._VelocityValid

    def ValidateVelocity(velocity, dofs):
        valid = validate_velocity(velocity, dofs)
        if not valid:
            finite = bool(np.isfinite(velocity).all())
            invalid_velocities.append({
                "finite": finite,
                "max_speed_excess_rad_s": float(np.max(np.abs(velocity[planner.right_dofs]) - planner.velocity_caps)) if finite else None,
                "max_frozen_velocity_rad_s": float(np.max(np.abs(velocity[planner.frozen_dofs]))) if finite else None,
            })
        return valid

    planner._VelocityValid = ValidateVelocity
    configuration = probe.mink.Configuration(model)
    configuration.update(initial_q)
    center_start = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body").translation()
    rotation_start = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").rotation().as_matrix()
    q = initial_q.copy()
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                 for name in probe.base.g1.RIGHT_ARM_JOINTS]
    positions, rotations, clearances, durations = [], [], [], []
    total_travel = np.zeros(7)
    max_speed = 0.0
    status = Counter()
    motion_duration = times[-1] / playback_speed
    motion_positions, motion_rotations = [], []
    saturated_frames = 0
    qp_rows = []
    trace = []
    previous_goal_rotation = rotation_start.copy()
    previous_robot_rotation = rotation_start.copy()
    frames = math.ceil((motion_duration + hold_s) / probe.base.DT)
    for frame in range(max(1, frames)):
        goal = GetNormalizedGoal(targets[0], targets[GetTargetIndex(times, frame * probe.base.DT, playback_speed)],
                                 center_start, rotation_start)
        configuration.update(q)
        before = time.perf_counter()
        if mode == "hierarchy":
            if diagnose_qp and frame * probe.base.DT < motion_duration:
                plan = RunDiagnosedPlan(planner, q, goal, qp_rows)
            else:
                plan = planner.Plan(q, goal, position_target=goal.translation())
            candidate, outcome = plan.next_q, plan.status
        else:
            planner.configuration.update(q)
            roll = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
            planner.position_task.set_target(probe.base._matrix_to_se3(roll.rotation().as_matrix(), goal.translation()))
            planner.orientation_task.set_target(goal)
            velocity = probe.mink.solve_ik(planner.configuration, planner.tasks, probe.base.DT,
                solver=planner.solver, damping=probe.base.QP_DAMPING,
                limits=planner.limits, constraints=planner.constraints)
            candidate, outcome = ApplySingleQPStep(planner, configuration, q, velocity, single_qp_backtrack)
        durations.append((time.perf_counter() - before) * 1000)
        status[outcome] += 1
        total_travel += np.abs(candidate[addresses] - q[addresses])
        joint_speed = np.abs(candidate[addresses] - q[addresses]) / probe.base.DT
        moving = frame * probe.base.DT < motion_duration
        if moving and np.any(joint_speed >= planner.velocity_caps * 0.99):
            saturated_frames += 1
        max_speed = max(max_speed, float(np.max(np.abs(candidate[addresses] - q[addresses]))) / probe.base.DT)
        q = candidate.copy()
        configuration.update(q)
        center = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body").translation()
        rotation = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").rotation().as_matrix()
        positions.append(float(np.linalg.norm(center - goal.translation())) * 1000)
        rotations.append(math.degrees(probe.base._rotation_error_radians(goal.rotation().as_matrix(), rotation)))
        clearances.append(planner.GetClearance(q) * 1000)
        trace.append({
            "time_s": frame * probe.base.DT, "moving": bool(moving), "status": outcome,
            "target_step_deg": math.degrees(probe.base._rotation_error_radians(goal.rotation().as_matrix(), previous_goal_rotation)),
            "robot_step_deg": math.degrees(probe.base._rotation_error_radians(rotation, previous_robot_rotation)),
            "error_deg": rotations[-1], "position_error_mm": positions[-1],
            "saturated": bool(np.any(joint_speed >= planner.velocity_caps * .99)),
        })
        previous_goal_rotation = goal.rotation().as_matrix().copy()
        previous_robot_rotation = rotation.copy()
        if moving:
            motion_positions.append(positions[-1])
            motion_rotations.append(rotations[-1])
    return {
        "frames": frames, "status_counts": dict(status),
        "qp_diagnostic": SummarizeQP(qp_rows),
        "target_event_summary": SummarizeTargetEvents(trace),
        "trace": trace,
        "playback_speed": playback_speed, "motion_duration_s": float(motion_duration),
        "motion_frames": len(motion_positions),
        "motion_position_p95_mm": float(np.percentile(motion_positions, 95)) if motion_positions else None,
        "motion_rotation_p95_deg": float(np.percentile(motion_rotations, 95)) if motion_rotations else None,
        "motion_saturated_frame_fraction": saturated_frames / len(motion_positions) if motion_positions else None,
        "invalid_velocity_checks": invalid_velocities,
        "position_p95_mm": float(np.percentile(positions, 95)), "position_final_mm": positions[-1],
        "rotation_p95_deg": float(np.percentile(rotations, 95)), "rotation_final_deg": rotations[-1],
        "proximal_total_travel_deg": float(np.rad2deg(total_travel[:4]).sum()),
        "joint_total_travel_deg": np.rad2deg(total_travel).tolist(),
        "minimum_clearance_mm": min(clearances), "maximum_velocity_rad_s": max_speed,
        "compute_p95_ms": float(np.percentile(durations, 95)),
        "clearance_violating_frames": sum(x < planner.clearance_m * 1000 - 0.001 for x in clearances),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", required=True, type=Path)
    parser.add_argument("--hold-s", type=float, default=5.0)
    parser.add_argument("--playback-speed", type=float, default=1.0)
    parser.add_argument("--mode", choices=("both", "single_weighted_qp", "hierarchy"), default="both")
    parser.add_argument("--diagnose-qp", action="store_true")
    parser.add_argument("--proximal-damping-max", type=float, default=task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX)
    parser.add_argument("--collision-profile", choices=("mink-default", "hardware-guarded"), default="mink-default")
    args = parser.parse_args()
    if not math.isfinite(args.hold_s) or args.hold_s <= 0:
        parser.error("hold-s must be finite and positive")
    if not math.isfinite(args.playback_speed) or args.playback_speed <= 0:
        parser.error("playback-speed must be finite and positive")
    if not math.isfinite(args.proximal_damping_max) or args.proximal_damping_max < task_policy.ORIENTATION_PROXIMAL_DAMPING_MIN:
        parser.error("proximal-damping-max must be finite and at least the assist minimum")
    manifest, packets = probe._decode_capture(args.capture)
    segments = GetActiveSegments(packets)
    if not segments:
        parser.error("capture has no active segments")
    model = probe.base.LoadMinkModel()
    probe.base._apply_operational_joint_limits(model)
    initial = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.RIGHT_ARM_JOINTS]
    initial[addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
    result = {
        "capture_id": manifest["capture_id"], "capture_path": str(args.capture.resolve()),
        "capture_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
        "robot_command": False, "collision_profile": args.collision_profile,
        "speed_rad_s": probe.live.virtual_center_velocity_limits(), "hold_s": args.hold_s,
        "playback_speed": args.playback_speed,
        "hierarchy_proximal_damping_max": args.proximal_damping_max,
        "hierarchy_proximal_damping_min": task_policy.ORIENTATION_PROXIMAL_DAMPING_MIN,
        "interpretation": "Normalized recorded target deltas; not bit-exact replay or raw Quest input. Single Mink weighted QP uses project tasks/costs, not upstream vanilla defaults. Hierarchy includes lookahead/acceptance checks; single QP has sampled rejection but no detour. Neither includes runtime Ruckig or PD dynamics. Total proximal travel is not necessarily unnecessary motion on a mixed capture. No global or physical safety guarantee.",
        "segments": [],
    }
    for index, (_, active) in enumerate(segments, 1):
        times, targets = GetRecordedTargets(active)
        entry = {"segment": index, "duration_s": float(times[-1]), "modes": {}}
        for mode in (("single_weighted_qp", "hierarchy") if args.mode == "both" else (args.mode,)):
            with UseOfflineProximalCost(args.proximal_damping_max):
                entry["modes"][mode] = RunComparison(model, initial, targets, times, mode, args.hold_s, args.collision_profile, args.playback_speed, args.diagnose_qp)
            summary = {k: v for k, v in entry["modes"][mode].items() if k != "trace"}
            print(f"segment={index} mode={mode}: {json.dumps(summary)}", flush=True)
        result["segments"].append(entry)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
