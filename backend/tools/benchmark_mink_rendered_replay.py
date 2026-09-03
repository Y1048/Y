"""Paced, rendered offline IK replay. No networking, SDK, publisher or physics stepping."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image

from benchmark_mink_candidate import BuildCandidate, SummarizeTiming, comparison


def WaitForRelease(release, clock=time.perf_counter, sleeper=time.sleep):
    while True:
        remaining = release - clock()
        if remaining <= 0:
            return
        sleeper(min(.005, remaining))


def GetNextRelease(start, dt):
    if not np.isfinite([start, dt]).all() or dt <= 0:
        raise ValueError("Finite start and positive timestep required")
    # Never catch up by compressing the next command interval after a late frame.
    return start + dt


def LoadReplay(capture, report_path, segment):
    probe = comparison.probe
    report = json.loads(report_path.read_text(encoding="utf-8"))
    model_path = Path(probe.base.g1.DEMO_XML)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if (report["capture_sha256"] != digest(capture)
            or report["model_xml_sha256"] != digest(model_path)
            or report["mujoco_version"] != probe.mujoco.__version__
            or report["horizon_steps"] != 3):
        raise ValueError("Capture, model, engine or horizon differs from reference")
    trace_path = report_path.with_name(report_path.stem + f"_s{segment}_limit_avoidance.jsonl")
    expected = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    _, packets = probe._decode_capture(capture)
    reference, goals = comparison.GetActiveSegments(packets)[segment - 1]
    model = probe.mujoco.MjModel.from_xml_path(str(model_path))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, n)]) for n in probe.base.g1.G1_29_JOINTS]
    q[addresses] = reference["value"]["all_joint_q_rad"]
    hashes = {"capture_sha256": digest(capture), "model_xml_sha256": digest(model_path),
              "reference_trace_sha256": digest(trace_path), "tool_sha256": digest(Path(__file__)),
              "candidate_tool_sha256": digest(Path(__file__).with_name("benchmark_mink_candidate.py"))}
    return model, q, goals, expected, hashes


class ReplayRenderer:
    def __init__(self, model, width, height):
        mj = comparison.probe.mujoco
        self.model = model
        self.data = mj.MjData(model)
        model.vis.global_.offwidth = max(width, model.vis.global_.offwidth)
        model.vis.global_.offheight = max(height, model.vis.global_.offheight)
        self.renderer = mj.Renderer(model, height=height, width=width)
        self.camera = mj.MjvCamera()
        self.camera.lookat[:] = [.15, 0, .95]
        self.camera.distance = 2.25
        self.camera.azimuth = 135
        self.camera.elevation = -15
        names = ("inspection_demo_target_marker", "inspection_panel", "inspection_tool_tip",
                 "inspection_tool_grip", "inspection_tool_probe")
        self.hidden = {mj.mj_name2id(model, mj.mjtObj.mjOBJ_GEOM, name) for name in names}
        self.hidden.discard(-1)

    def Draw(self, q, goal, preview):
        mj = comparison.probe.mujoco
        self.data.qpos[:] = q
        mj.mj_forward(self.model, self.data)
        self.renderer.update_scene(self.data, camera=self.camera)
        scene = self.renderer.scene
        for geom in scene.geoms[:scene.ngeom]:
            if geom.objtype == mj.mjtObj.mjOBJ_GEOM and geom.objid in self.hidden:
                geom.rgba[3] = 0
        for point, color in ((goal, [0, .8, 1, 1]), (preview, [.1, 1, .1, 1])):
            if scene.ngeom >= scene.maxgeom:
                raise RuntimeError("Renderer scene capacity exceeded")
            mj.mjv_initGeom(scene.geoms[scene.ngeom], mj.mjtGeom.mjGEOM_SPHERE,
                           np.full(3, .016), np.asarray(point), np.eye(3).ravel(), np.asarray(color))
            scene.ngeom += 1
        return self.renderer.render()

    def Close(self):
        self.renderer.close()


def RunRenderedReplay(model, initial, goals, expected, renderer, repeat):
    probe = comparison.probe
    dt = probe.base.DT
    times, targets = comparison.GetRecordedTargets(goals)
    duration = max(dt, float(times[-1]))
    count = math.ceil((duration + 12) / dt)
    if len(expected) != count:
        raise ValueError("Reference length differs from replay")

    def Step(planner, q, goal):
        return comparison.EvaluateLookahead(planner, q, goal, consistent_position=True,
            center_redundancy=True, limit_margin_rad=math.radians(probe.live.ASSIST_ENTER_MARGIN_DEG),
            horizon_steps=3, diagnostic_geometry=False)

    warmup = BuildCandidate(model, initial, True, True, True)
    q = initial.copy()
    for _ in range(30):
        q, decision = Step(warmup, q, targets[0])
        renderer.Draw(q, targets[0].translation(), decision["lookahead_target_position"])
    planner = BuildCandidate(model, initial, True, True, True)
    planner.configuration.update(initial)
    return_goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    q = initial.copy()
    checks = {"calls": 0, "rejected": 0}
    original_check = planner.CheckConfiguration

    def CheckConfiguration(value):
        valid = original_check(value)
        checks["calls"] += 1
        checks["rejected"] += int(not valid)
        return valid

    planner.CheckConfiguration = CheckConfiguration
    timings, samples, snapshots = [], [], {}
    errors = {"actual_qpos_max": 0., "preview_qpos_max": 0., "accepted_step_mismatches": 0}
    changed_frames = 0
    minimum_pixel_std = float("inf")
    previous_pixels = None
    asynchronous = getattr(renderer, "is_async", False)
    if asynchronous:
        renderer.BeginRun()
    release = time.perf_counter()
    epoch = release
    for index in range(count):
        WaitForRelease(release)
        start = time.perf_counter()
        seconds = index * dt
        phase = "recorded" if seconds < duration else "hold" if seconds < duration + 6 else "return"
        goal = targets[comparison.GetTargetIndex(times, seconds, 1.)] if phase != "return" else return_goal
        next_q, decision = Step(planner, q, goal)
        planner_end = time.perf_counter()
        pixels = renderer.Draw(next_q, goal.translation(), decision["lookahead_target_position"])
        render_end = time.perf_counter()
        if pixels is not None:
            small = pixels[::16, ::16].copy()
            minimum_pixel_std = min(minimum_pixel_std, float(small.std()))
            changed_frames += int(previous_pixels is not None and not np.array_equal(previous_pixels, small))
            previous_pixels = small
            if index in {0, count // 3, 2 * count // 3, count - 1}:
                snapshots[index] = pixels.copy()
        pose = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        velocity = np.zeros(model.nv)
        probe.mujoco.mj_differentiatePos(model, velocity, dt, q, next_q)
        speed = np.rad2deg(velocity[planner.right_dofs])
        lower, upper = model.jnt_range[planner.joint_ids].T
        sample = {"phase": phase, "position_cm": float(np.linalg.norm(goal.translation() - pose.translation()) * 100),
            "rotation_deg": math.degrees(probe.base._rotation_error_radians(goal.rotation().as_matrix(), pose.rotation().as_matrix())),
            "speed_deg_s": np.abs(speed).tolist(), "signed_speed_deg_s": speed.tolist(),
            "joint_margin_deg": np.rad2deg(np.minimum(next_q[planner.qpos_ids] - lower, upper - next_q[planner.qpos_ids])).tolist(),
            "clearance_mm": decision["lookahead_clearance_mm"], "decision": decision}
        samples.append(sample)
        baseline = expected[index]
        errors["actual_qpos_max"] = max(errors["actual_qpos_max"], float(np.max(np.abs(next_q - baseline["qpos"]))))
        errors["preview_qpos_max"] = max(errors["preview_qpos_max"], float(np.max(np.abs(
            np.asarray(decision["lookahead_target_qpos"]) - baseline["decision"]["lookahead_target_qpos"]))))
        errors["accepted_step_mismatches"] += int(decision["lookahead_steps"] != baseline["decision"]["lookahead_steps"])
        q = next_q
        finish = time.perf_counter()
        timings.append({"start_s": start - epoch, "planner_ms": (planner_end - start) * 1000,
            "render_ms": (render_end - planner_end) * 1000, "work_ms": (finish - start) * 1000,
            "release_to_finish_ms": (finish - release) * 1000, "wake_lateness_ms": max(0., start - release) * 1000})
        release = GetNextRelease(start, dt)
    elapsed = finish - epoch
    summaries = {key: SummarizeTiming([s[key] for s in timings], dt * 1000)
                 for key in ("planner_ms", "render_ms", "work_ms", "release_to_finish_ms", "wake_lateness_ms")}
    late_frames = [dict(frame=i, phase=samples[i]["phase"], **row) for i, row in enumerate(timings)
                   if row["release_to_finish_ms"] > dt * 1000]
    phases = {phase: comparison.Summarize([s for s in samples if s["phase"] == phase], dt)
              for phase in ("recorded", "hold", "return")}
    intervals = np.diff([s["start_s"] for s in timings]) * 1000
    result = {"repeat": repeat, "frames": count, "nominal_duration_s": count * dt,
        "wall_duration_s": elapsed, "wall_minus_nominal_s": elapsed - count * dt,
        "frame_start_interval_ms_min_p50_p95_max": np.percentile(intervals, [0, 50, 95, 100]).tolist(),
        "timings": summaries, "late_frames": late_frames, "phase_metrics": phases, "configuration_checks": checks,
        "parity": errors, "trajectory_parity": max(errors.values()) == 0,
        "render_check": {"minimum_sampled_pixel_std": minimum_pixel_std, "changed_frames": changed_frames,
                         "nonblank_and_changing": minimum_pixel_std > 5 and changed_frames > 0}}
    if asynchronous:
        result["render_worker"] = renderer.FinishRun()
        result["render_check"] = result["render_worker"]["render_check"]
        result["render_check"]["nonblank_and_changing"] &= result["render_worker"]["state_qpos_mismatches"] == 0
        result["timings"]["state_publish_ms"] = result["timings"].pop("render_ms")
    return result, snapshots


def GetRunStatus(runs):
    if not runs or not all(r["trajectory_parity"] and r["render_check"]["nonblank_and_changing"] for r in runs):
        return "PARITY_OR_RENDER_FAILURE"
    if any(r["late_frames"] for r in runs):
        return "DEADLINE_MISSES"
    if any(r.get("render_worker", {}).get("timings", {}).get(
            "source_age_finish_ms", {}).get("deadline_misses", 0) for r in runs):
        return "DISPLAY_AGE_MISSES"
    return "PACED_RENDER_BUDGET_MET"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("expected_report", type=Path)
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--decoupled-render", action="store_true")
    parser.add_argument("--renderer-stall-ms", type=float, default=0,
                        help="Offline fault injection every 120 rendered states")
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    if min(args.segment, args.repeats, args.width, args.height) < 1:
        parser.error("Positive segment, repeats and dimensions required")
    if not np.isfinite(args.renderer_stall_ms) or args.renderer_stall_ms < 0 or (
            args.renderer_stall_ms and not args.decoupled_render):
        parser.error("Finite nonnegative renderer stall requires decoupled rendering")
    model, initial, goals, expected, hashes = LoadReplay(args.capture, args.expected_report, args.segment)
    report = {"robot_command": False, "mujoco_version": comparison.probe.mujoco.__version__, **hashes,
        "resolution": [args.width, args.height], "runs": [], "screenshots": [],
        "scope": "MuJoCo offscreen GPU render/readback every frame, fixed-step IK, real-time pacing without catch-up. No Unity/Quest/UDP/DDS, physical dynamics or hardware. Fresh initial pose between repeats; reset jumps are not control transitions. Initialization/warmup and PNG writes excluded. Per-frame diagnostics included."}
    if args.decoupled_render:
        report["scope"] = ("Separate spawned offline renderer; a single nonblocking locked latest-state slot. "
            "Renderer may skip intermediate display states; no IK input frames skipped. State age starts at "
            "publication after IK, not Quest capture. No network, Unity/Quest/DDS, dynamics or robot commands. "
            "Initialization/warmup/report/PNG writes excluded. Fresh initial pose between repeats.")
    report["decoupled_render"] = args.decoupled_render
    report["renderer_stall_ms"] = args.renderer_stall_ms
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    renderer = None
    try:
        for repeat in range(1, args.repeats + 1):
            if args.decoupled_render:
                from offline_render_worker import ProcessRenderer
                trace_path = args.expected_report.with_name(args.expected_report.stem + f"_s{args.segment}_limit_avoidance.jsonl")
                renderer = ProcessRenderer(comparison.probe.base.g1.DEMO_XML, initial,
                    args.width, args.height, trace_path,
                    args.result_json.with_name(f"{args.result_json.stem}_r{repeat}"), args.renderer_stall_ms)
            elif renderer is None:
                renderer = ReplayRenderer(model, args.width, args.height)
            result, snapshots = RunRenderedReplay(model, initial, goals, expected, renderer, repeat)
            report["runs"].append(result)
            if args.decoupled_render:
                report["screenshots"].extend(result["render_worker"]["screenshots"])
                renderer.Close()
                renderer = None
            for frame, pixels in snapshots.items():
                path = args.result_json.with_name(f"{args.result_json.stem}_r{repeat}_f{frame}.png")
                Image.fromarray(pixels).save(path)
                report["screenshots"].append(str(path.resolve()))
            print(json.dumps({"repeat": repeat, "parity": result["trajectory_parity"],
                "work": result["timings"]["work_ms"], "wall_duration_s": result["wall_duration_s"]}), flush=True)
            report["status"] = "IN_PROGRESS"
            args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    except BaseException as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print("Result saved to:", args.result_json.resolve(), flush=True)
        raise
    finally:
        if renderer is not None:
            renderer.Close()
    report["status"] = GetRunStatus(report["runs"])
    args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(report["status"], flush=True)
    print("Result saved to:", args.result_json.resolve(), flush=True)
    return 1 if report["status"] == "PARITY_OR_RENDER_FAILURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
