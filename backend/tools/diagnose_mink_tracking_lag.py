"""Offline candidate speed/hold ablation; no network, SDK or physical output."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from benchmark_mink_candidate import BuildCandidate, comparison
from benchmark_mink_rendered_replay import LoadReplay
from diagnose_recorded_reach import GetReachUpperBound


def GetSchedule(duration, speed, dt, hold_s=6.):
    values = np.asarray([duration, speed, dt, hold_s])
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Positive finite duration, speed, dt and hold required")
    motion_s = max(dt, duration / speed)
    for index in range(math.ceil((motion_s + 2 * hold_s) / dt)):
        seconds = index * dt
        phase = "recorded" if seconds < motion_s else "hold" if seconds < motion_s + hold_s else "return"
        yield phase, seconds * speed


def GetSustainedSettleTime(rows, dt, minimum_s=.5):
    # A brief threshold crossing is not settling: require a good suffix to the end.
    good = np.array([r["position_cm"] <= 1. and r["rotation_deg"] <= 5. for r in rows])
    bad = np.flatnonzero(~good)
    start = int(bad[-1] + 1) if len(bad) else 0
    return start * dt if (len(rows) - start) * dt >= minimum_s else None


def GetReachSummary(rows, upper_bound_m):
    distances = np.array([r["shoulder_target_distance_m"] for r in rows])
    outside = distances > upper_bound_m + 1e-6
    result = {"upper_bound_m": upper_bound_m, "maximum_target_distance_m": float(distances.max()),
        "provably_outside_frames": int(outside.sum()), "provably_outside_percent": float(100 * outside.mean()),
        "maximum_position_error_lower_bound_cm": float(100 * max(0., distances.max() - upper_bound_m)),
        "boundary": "Chain-length upper bound for yaw-wrist origin, not palm/tool. Inside does not prove pose reachability or collision freedom."}
    for label, mask in (("inside", ~outside), ("outside", outside)):
        selected = [r for r, include in zip(rows, mask) if include]
        result[label + "_position_cm_p95"] = float(np.percentile([r["position_cm"] for r in selected], 95)) if selected else None
    return result


def Step(planner, q, goal):
    probe = comparison.probe
    return comparison.EvaluateLookahead(planner, q, goal, consistent_position=True,
        center_redundancy=True, limit_margin_rad=math.radians(probe.live.ASSIST_ENTER_MARGIN_DEG),
        horizon_steps=3, diagnostic_geometry=False)


def GetSample(planner, before, q, goal, decision):
    probe = comparison.probe
    planner.configuration.update(q)
    pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    shoulder = planner.configuration.get_transform_frame_to_world("right_shoulder_pitch_link", "body")
    velocity = np.zeros(planner.model.nv)
    probe.mujoco.mj_differentiatePos(planner.model, velocity, probe.base.DT, before, q)
    speed = np.rad2deg(velocity[planner.right_dofs])
    lower, upper = planner.model.jnt_range[planner.joint_ids].T
    return {"qpos": q.tolist(), "goal_matrix": goal.as_matrix().tolist(),
        "shoulder_target_distance_m": float(np.linalg.norm(goal.translation() - shoulder.translation())),
        "position_cm": float(np.linalg.norm(goal.translation() - pose.translation()) * 100),
        "rotation_deg": math.degrees(probe.base._rotation_error_radians(
            goal.rotation().as_matrix(), pose.rotation().as_matrix())),
        "speed_deg_s": np.abs(speed).tolist(), "signed_speed_deg_s": speed.tolist(),
        "joint_margin_deg": np.rad2deg(np.minimum(q[planner.qpos_ids] - lower, upper - q[planner.qpos_ids])).tolist(),
        "clearance_mm": min(planner.GetClearance(before) * 1000, planner.GetClearance(q) * 1000,
                            decision["minimum_path_clearance_mm"] or float("inf")),
        "frozen_velocity_rad_s": float(np.max(np.abs(velocity[planner.frozen_dofs]))),
        "decision": decision}


def Summarize(rows, planner):
    dt = comparison.probe.base.DT
    result = comparison.Summarize(rows, dt)
    caps = np.rad2deg(planner.velocity_caps)
    speeds = np.array([r["speed_deg_s"] for r in rows])
    result.update({"frames": len(rows), "duration_s": len(rows) * dt,
        "reach": GetReachSummary(rows, GetReachUpperBound(planner.model)),
        "sustained_settle_time_s": GetSustainedSettleTime(rows, dt),
        "joint_at_99pct_velocity_cap_percent": (100 * np.mean(speeds >= .99 * caps, axis=0)).tolist(),
        "any_joint_at_99pct_velocity_cap_percent": float(100 * np.mean(np.any(speeds >= .99 * caps, axis=1))),
        "max_frozen_velocity_rad_s": max(r["frozen_velocity_rad_s"] for r in rows)})
    if np.any(speeds > caps + 1e-5) or result["max_frozen_velocity_rad_s"] > 1e-8:
        raise ValueError("Candidate violated unchanged velocity or frozen-joint contract")
    if min(result["joint_minimum_margin_deg"]) < -1e-5:
        raise ValueError("Candidate violated operational joint bounds")
    if result["minimum_clearance_mm"] < comparison.probe.live.TELEOP_COLLISION_TARGET_DISTANCE_M * 1000 - .5:
        raise ValueError("Candidate violated sampled clearance contract")
    return result


def RunSpeed(model, initial, times, targets, speed, expected):
    planner = BuildCandidate(model, initial, True, True, True)
    q = initial.copy()
    planner.configuration.update(q)
    return_goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    rows = []
    parity = 0.
    for index, (phase, source_s) in enumerate(GetSchedule(float(times[-1]), speed, comparison.probe.base.DT)):
        goal = return_goal if phase == "return" else targets[comparison.GetTargetIndex(times, source_s, 1.)]
        next_q, decision = Step(planner, q, goal)
        row = GetSample(planner, q, next_q, goal, decision)
        row.update({"frame": index, "phase": phase, "source_time_s": source_s})
        rows.append(row)
        if speed == 1.:
            parity = max(parity, float(np.max(np.abs(next_q - expected[index]["qpos"]))))
            if decision["lookahead_steps"] != expected[index]["decision"]["lookahead_steps"]:
                raise ValueError("Baseline lookahead acceptance differs from reference")
        q = next_q
    if speed == 1. and (len(rows) != len(expected) or parity > 1e-10):
        raise ValueError(f"Baseline differs from reference: {parity}")
    return {"speed": speed, "reference_qpos_max_error": parity if speed == 1. else None,
        "phases": {phase: Summarize([r for r in rows if r["phase"] == phase], planner)
                   for phase in ("recorded", "hold", "return")}}, rows


def RunFreeze(model, initial, times, targets, frame, expected):
    planner = BuildCandidate(model, initial, True, True, True)
    q = initial.copy()
    dt = comparison.probe.base.DT
    # Reconstruct the complete prefix, preserving orientation hysteresis and task state.
    for index in range(frame + 1):
        goal = targets[comparison.GetTargetIndex(times, index * dt, 1.)]
        q, _ = Step(planner, q, goal)
    error = float(np.max(np.abs(q - expected[frame]["qpos"])))
    if error > 1e-10:
        raise ValueError("Freeze prefix no longer matches the baseline")
    rows = []
    for index in range(round(10. / dt)):
        next_q, decision = Step(planner, q, goal)
        row = GetSample(planner, q, next_q, goal, decision)
        row.update({"frame": index, "phase": "freeze"})
        rows.append(row)
        q = next_q
    metrics = Summarize(rows, planner)
    result = {"source_frame": frame, "source_time_s": frame * dt,
        "prefix_qpos_max_error": error, "initial_position_cm": expected[frame]["position_cm"],
        "initial_rotation_deg": expected[frame]["rotation_deg"], "hold": metrics}
    if metrics["final_position_cm"] > 1 or metrics["final_rotation_deg"] > 5:
        result["endpoint_audit"] = comparison.InspectEndpointSolutions(planner, q, goal)
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("reference_report", type=Path)
    parser.add_argument("--result-json", required=True, type=Path)
    args = parser.parse_args()
    model, initial, goals, expected, hashes = LoadReplay(args.capture, args.reference_report, 2)
    times, targets = comparison.GetRecordedTargets(goals)
    result = {"robot_command": False, "mujoco_version": comparison.probe.mujoco.__version__,
        "segment": 2, "hashes": hashes, "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "boundary": "Offline kinematic candidate, fixed dt and unchanged 40/100 deg/s, joint and collision limits. Slowed zero-order-held targets, not original real-time input or a dynamics test. Endpoint search is not a safe path or proof of infeasibility; only targets outside the model-derived chain-length upper bound are proven unreachable.",
        "speeds": [], "freezes": []}
    args.result_json.parent.mkdir(parents=True, exist_ok=True)

    def SaveTrace(label, rows):
        path = args.result_json.with_name(args.result_json.stem + "_" + label + ".jsonl")
        with path.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
        return str(path.resolve())

    for speed in (1., .5, .25):
        metrics, rows = RunSpeed(model, initial, times, targets, speed, expected)
        metrics["trace"] = SaveTrace("speed" + str(speed), rows)
        result["speeds"].append(metrics)
        print(json.dumps({"speed": speed, "recorded": metrics["phases"]["recorded"]}), flush=True)
    recorded = [r for r in expected if r["phase"] == "recorded"]
    for name in ("position_cm", "rotation_deg"):
        frame = max(range(len(recorded)), key=lambda index: recorded[index][name])
        metrics, rows = RunFreeze(model, initial, times, targets, frame, expected)
        metrics["selection"] = "maximum_" + name
        metrics["trace"] = SaveTrace(name, rows)
        result["freezes"].append(metrics)
        print(json.dumps({"selection": name, "hold": metrics["hold"]}), flush=True)
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve(), flush=True)


if __name__ == "__main__":
    main()
