"""Offline unreachable hold/inward return, with actual and preview FK audits."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp

from diagnose_mink_tracking_lag import BuildCandidate, Step, GetSample, Summarize, comparison
from benchmark_mink_rendered_replay import ReplayRenderer


def InterpolateGoal(start, end, fraction):
    if not np.isfinite(fraction) or not 0 <= fraction <= 1:
        raise ValueError("Fraction must lie in [0, 1]")
    rotation = Slerp([0., 1.], Rotation.from_matrix(np.stack((
        start.rotation().as_matrix(), end.rotation().as_matrix()))))(fraction).as_matrix()
    position = (1 - fraction) * start.translation() + fraction * end.translation()
    return comparison.probe.base._matrix_to_se3(rotation, position)


def SummarizePreview(rows, dt):
    preview = np.array([r["preview_position_m"] for r in rows])
    actual = np.array([r["actual_position_m"] for r in rows])
    tail = max(1, round(1. / dt))
    result = {"invalid_preview_frames": sum(not r["preview_valid"] for r in rows),
        "preview_fk_residual_max_m": max(r["preview_fk_residual_m"] for r in rows),
        "preview_to_actual_gap_max_cm": float(100 * np.linalg.norm(preview - actual, axis=1).max()),
        "preview_to_actual_gap_final_cm": float(100 * np.linalg.norm(preview[-1] - actual[-1])),
        "last_second_preview_spread_cm": float(100 * np.linalg.norm(preview[-tail:] - preview[-1], axis=1).max()),
        "last_second_actual_spread_cm": float(100 * np.linalg.norm(actual[-tail:] - actual[-1], axis=1).max()),
        "preview_frame_step_max_cm": float(100 * np.linalg.norm(np.diff(preview, axis=0), axis=1).max()) if len(rows) > 1 else 0.,
        "minimum_preview_clearance_mm": min(r["preview_clearance_mm"] for r in rows)}
    return result


def GetVerdict(phases):
    valid = all(p["preview"]["invalid_preview_frames"] == 0
                and p["preview"]["preview_fk_residual_max_m"] < 1e-8 for p in phases.values())
    stopped = (phases["outside_hold"]["last_second_max_joint_speed_deg_s"] <= .1
               and phases["outside_hold"]["preview"]["last_second_preview_spread_cm"] <= .05)
    returned = phases["inside_hold"]["sustained_settle_time_s"] is not None
    return {"preview_valid": valid, "outside_stopped": stopped, "inside_return_settled": returned,
            "status": "OFFLINE_CRITERIA_MET" if valid and stopped and returned else "REVIEW_REQUIRED"}


def Run(model, initial, goals, expected, variant, output):
    probe = comparison.probe
    times, targets = comparison.GetRecordedTargets(goals)
    dt = probe.base.DT
    recorded = [r for r in expected if r["phase"] == "recorded"]
    stop_frame = max(range(len(recorded)), key=lambda i: recorded[i]["position_cm"])
    outside_goal = targets[comparison.GetTargetIndex(times, stop_frame * dt, 1.)]
    planner = (BuildCandidate(model, initial, True, True, True) if variant == "candidate"
               else comparison.BuildPlanner(model, initial))
    planner.configuration.update(initial)
    inside_goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    validator = probe.mink.Configuration(model)
    q = initial.copy()
    rows = []
    parity = 0.
    counts = {"prefix": stop_frame + 1, "outside_hold": round(10 / dt),
              "inward_return": round(4 / dt), "inside_hold": round(6 / dt)}
    for phase, count in counts.items():
        for index in range(count):
            goal = (targets[comparison.GetTargetIndex(times, index * dt, 1.)] if phase == "prefix"
                    else outside_goal if phase == "outside_hold"
                    else InterpolateGoal(outside_goal, inside_goal, (index + 1) / count) if phase == "inward_return"
                    else inside_goal)
            goal_before = goal.as_matrix().copy()
            if variant == "candidate":
                next_q, decision = Step(planner, q, goal)
                preview_q = np.array(decision["lookahead_target_qpos"])
                preview_position = np.array(decision["lookahead_target_position"])
                preview_valid = True
            else:
                plan = planner.Plan(q, goal)
                next_q, preview_q, preview_position = plan.next_q, plan.target_q, plan.target_position
                preview_valid = plan.valid
                decision = {"status": plan.status, "merit_only_block": False,
                    "minimum_path_clearance_mm": None, "accepted_steps": plan.accepted_steps}
            if not np.array_equal(goal_before, goal.as_matrix()):
                raise ValueError("Raw operator goal was modified by planning")
            row = GetSample(planner, q, next_q, goal, decision)
            actual_position = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
            validator.update(preview_q)
            preview_fk = validator.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
            row.update({"phase": phase, "phase_frame": index, "preview_qpos": preview_q.tolist(),
                "actual_position_m": actual_position.tolist(), "preview_position_m": preview_position.tolist(),
                "preview_fk_residual_m": float(np.linalg.norm(preview_fk - preview_position)),
                "preview_valid": bool(preview_valid and planner.CheckConfiguration(preview_q)),
                "preview_clearance_mm": planner.GetClearance(preview_q) * 1000})
            rows.append(row)
            if variant == "candidate" and phase == "prefix":
                parity = max(parity, float(np.max(np.abs(next_q - expected[index]["qpos"]))))
            q = next_q
        print(variant, phase, "final error cm", rows[-1]["position_cm"], flush=True)
    if variant == "candidate" and parity > 1e-10:
        raise ValueError("Candidate prefix differs from the reference")
    phases = {}
    for name in counts:
        selected = [r for r in rows if r["phase"] == name]
        phases[name] = Summarize(selected, planner)
        phases[name]["preview"] = SummarizePreview(selected, dt)
    trace_path = output.with_suffix(".jsonl")
    with trace_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
    renderer = ReplayRenderer(model, 960, 720)
    # The XML has a separate, unnamed mocap marker unrelated to this preview.
    renderer.hidden.update(i for i in range(model.ngeom)
                           if model.body_mocapid[model.geom_bodyid[i]] >= 0)
    snapshots = []
    try:
        for phase in counts:
            row = [r for r in rows if r["phase"] == phase][-1]
            pixels = renderer.Draw(np.array(row["qpos"]), np.array(row["goal_matrix"])[:3, 3],
                                   np.array(row["preview_position_m"]))
            if pixels.std() < 1:
                raise ValueError("Blank offline preview image")
            path = output.with_name(output.stem + "_" + phase + ".png")
            Image.fromarray(pixels).save(path)
            snapshots.append(str(path.resolve()))
    finally:
        renderer.Close()
    return {"variant": variant, "mujoco_version": probe.mujoco.__version__, "stop_frame": stop_frame,
        "prefix_qpos_max_error": parity if variant == "candidate" else None,
        "raw_goal_preserved": True, "phases": phases, "verdict": GetVerdict(phases),
        "trace": str(trace_path.resolve()), "snapshots": snapshots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("reference_report", type=Path)
    parser.add_argument("--variant", choices=("current", "candidate"), required=True)
    parser.add_argument("--result-json", required=True, type=Path)
    args = parser.parse_args()
    probe = comparison.probe
    report = json.loads(args.reference_report.read_text(encoding="utf-8"))
    model_path = Path(probe.base.g1.DEMO_XML)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(args.capture) != report["capture_sha256"] or digest(model_path) != report["model_xml_sha256"]:
        raise ValueError("Capture or model does not match reference")
    if args.variant == "candidate" and probe.mujoco.__version__ != report["mujoco_version"]:
        raise ValueError("Candidate engine must match the reference")
    trace_path = args.reference_report.with_name(args.reference_report.stem + "_s2_limit_avoidance.jsonl")
    expected = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    _, packets = probe._decode_capture(args.capture)
    reference, goals = comparison.GetActiveSegments(packets)[1]
    model = probe.mujoco.MjModel.from_xml_path(str(model_path))
    probe.base._apply_operational_joint_limits(model)
    initial = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, n)]) for n in probe.base.g1.G1_29_JOINTS]
    initial[addresses] = reference["value"]["all_joint_q_rad"]
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    result = Run(model, initial, goals, expected, args.variant, args.result_json)
    result.update(robot_command=False, settings_modified=False,
        hashes={"capture": digest(args.capture), "model": digest(model_path), "reference_trace": digest(trace_path),
                "tool": digest(Path(__file__))},
        boundary="Offline kinematic actual/preview endpoints and planner's sampled path checks. No Unity runtime, network, PD/physics, continuous collision proof or physical authorization. Current/candidate engine versions may differ; not a single-variable causal comparison.")
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(result["verdict"], flush=True)
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
