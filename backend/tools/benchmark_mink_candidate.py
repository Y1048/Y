"""Offline planner-only timing and trajectory parity; no network or robot output."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

import compare_mink_step_acceptance as comparison


class CachedClearance:
    """One exact-q cache for an immutable benchmark model, never a time-based cache."""

    def __init__(self, query):
        self.query = query
        self.q = None
        self.distance = None
        self.hits = 0
        self.misses = 0

    def __call__(self, q):
        if self.q is not None and np.array_equal(q, self.q):
            self.hits += 1
            return self.distance
        self.q = None
        self.misses += 1
        distance = self.query(q)
        if not np.isnan(distance):
            self.q = np.array(q, copy=True)
            self.distance = distance
        return distance


class BoundedClearance:
    """Offline immutable-model sphere prefilter; uncertain pairs stay in order."""

    def __init__(self, planner):
        self.model = planner.model
        self.data = planner.validation_data
        self.pairs = np.asarray(planner.geom_pairs, dtype=int).reshape(-1, 2)
        self.distmax = .20
        self.pair_queries = 0
        self.skipped_pairs = 0
        self.queries = 0
        geom = comparison.probe.mujoco.mjtGeom
        supported = [geom.mjGEOM_SPHERE, geom.mjGEOM_CAPSULE, geom.mjGEOM_ELLIPSOID,
                     geom.mjGEOM_CYLINDER, geom.mjGEOM_BOX, geom.mjGEOM_MESH]
        radii = self.model.geom_rbound[self.pairs]
        self.bounded = (np.isin(self.model.geom_type[self.pairs], supported).all(axis=1)
                        & np.isfinite(radii).all(axis=1) & (radii > 0).all(axis=1))
        self.radius_sum = radii.sum(axis=1)

    def __call__(self, q):
        probe = comparison.probe
        self.data.qpos[:] = q
        probe.mujoco.mj_forward(self.model, self.data)
        difference = self.data.geom_xpos[self.pairs[:, 0]] - self.data.geom_xpos[self.pairs[:, 1]]
        distance_sq = np.einsum("ij,ij->i", difference, difference)
        # Extra margin keeps roundoff and exact-cutoff pairs in the narrow phase.
        bound = self.radius_sum + self.distmax + 1e-9
        discard = self.bounded & np.isfinite(distance_sq) & (distance_sq > bound * bound)
        pairs = self.pairs[~discard]
        self.queries += 1
        self.skipped_pairs += int(np.count_nonzero(discard))
        self.pair_queries += len(pairs)
        nearest = probe.base._nearest_pair_distance(self.model, self.data, pairs, self.distmax)
        return float("inf") if nearest is None else nearest[0]


class CachedCollisionLimit(comparison.ResolvedCollisionLimit):
    """Offline exact-state reuse, assuming immutable model and collision pairs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_key = None
        self.cache_configuration = None
        self.cache_constraint = None
        self.hits = 0
        self.misses = 0

    def compute_qp_inequalities(self, configuration, dt):
        if configuration.model is not self.model or not np.isfinite(dt) or dt <= 0:
            self.cache_key = None
            raise ValueError("Same model and positive finite dt required")
        key = (configuration.q.tobytes(), configuration.data.mocap_pos.tobytes(),
               configuration.data.mocap_quat.tobytes(), float(dt), self.gain,
               self.minimum_distance_from_collisions, self.collision_detection_distance,
               self.bound_relaxation, self.broadphase, self.broadphase_min_pairs,
               self.recover_reserve)
        if configuration is self.cache_configuration and key == self.cache_key:
            self.hits += 1
            # Neither the solver nor a test caller may mutate the retained result.
            return comparison.probe.mink.limits.Constraint(
                G=self.cache_constraint.G.copy(), h=self.cache_constraint.h.copy())
        self.cache_key = None
        self.misses += 1
        result = super().compute_qp_inequalities(configuration, dt)
        if (result.G is not None and result.h is not None and np.isfinite(result.G).all()
                and not np.isnan(result.h).any() and not np.isneginf(result.h).any()):
            self.cache_constraint = comparison.probe.mink.limits.Constraint(
                G=result.G.copy(), h=result.h.copy())
            self.cache_configuration = configuration
            self.cache_key = key
        return result


def BuildCandidate(model, initial_q, cache_enabled, broadphase=False, constraint_cache=False):
    probe = comparison.probe
    planner = comparison.BuildPlanner(model, initial_q)
    planner.position_task = comparison.WristPositionTask()
    planner.orientation_task = comparison.FullOrientationErrorTask(model)
    planner.tasks[:2] = [planner.position_task, planner.orientation_task]
    for index, limit in enumerate(planner.limits):
        if isinstance(limit, probe.mink.CollisionAvoidanceLimit):
            limit_class = CachedCollisionLimit if constraint_cache else comparison.ResolvedCollisionLimit
            planner.limits[index] = limit_class(
                model, geom_pairs=probe.base._build_collision_pairs(model)[0],
                gain=limit.gain, minimum_distance_from_collisions=limit.minimum_distance_from_collisions + .0005,
                collision_detection_distance=limit.collision_detection_distance,
                bound_relaxation=limit.bound_relaxation, broadphase=limit.broadphase, recover_reserve=False)
    if broadphase:
        planner.benchmark_clearance = BoundedClearance(planner)
        planner.GetClearance = planner.benchmark_clearance
    if cache_enabled:
        planner.GetClearance = CachedClearance(planner.GetClearance)
    return planner


def SummarizeTiming(values, budget_ms):
    values = np.asarray(values, dtype=float)
    if not len(values) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("Non-empty finite non-negative timing samples required")
    if not np.isfinite(budget_ms) or budget_ms <= 0:
        raise ValueError("Positive finite budget required")
    misses = int(np.count_nonzero(values > budget_ms))
    return {"frames": len(values), "ms_p50_p95_p99_max": np.percentile(values, [50, 95, 99, 100]).tolist(),
            "mean_ms": float(values.mean()), "deadline_ms": budget_ms,
            "deadline_misses": misses, "deadline_miss_percent": 100 * misses / len(values)}


def RunBenchmark(model, initial_q, goals, expected, repeat, cache_enabled, broadphase=False, constraint_cache=False):
    probe = comparison.probe
    dt = probe.base.DT
    times, targets = comparison.GetRecordedTargets(goals)
    duration = max(dt, float(times[-1]))
    count = math.ceil((duration + 12.) / dt)
    if len(expected) != count:
        raise ValueError("Expected trace does not match the full replay length")

    def Step(planner, q, goal):
        return comparison.EvaluateLookahead(planner, q, goal, consistent_position=True,
            center_redundancy=True, limit_margin_rad=math.radians(probe.live.ASSIST_ENTER_MARGIN_DEG),
            horizon_steps=3, diagnostic_geometry=False)

    warmup = BuildCandidate(model, initial_q, cache_enabled, broadphase, constraint_cache)
    q = initial_q.copy()
    for _ in range(30):
        q, _ = Step(warmup, q, targets[0])
    planner = BuildCandidate(model, initial_q, cache_enabled, broadphase, constraint_cache)
    planner.configuration.update(initial_q)
    return_goal = planner.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    q = initial_q.copy()
    measurements = []
    samples = []
    for index in range(count):
        start = time.perf_counter_ns()
        seconds = index * dt
        phase = "recorded" if seconds < duration else "hold" if seconds < duration + 6. else "return"
        goal = targets[comparison.GetTargetIndex(times, seconds, 1.)] if phase != "return" else return_goal
        q, decision = Step(planner, q, goal)
        elapsed_ms = (time.perf_counter_ns() - start) / 1e6
        measurements.append(elapsed_ms)
        samples.append({"time_s": seconds, "phase": phase, "qpos": q.tolist(), "decision": decision})
    actual_error = max(float(np.max(np.abs(np.array(a["qpos"]) - b["qpos"]))) for a, b in zip(samples, expected))
    preview_error = max(float(np.max(np.abs(np.array(a["decision"]["lookahead_target_qpos"]) -
                                              b["decision"]["lookahead_target_qpos"]))) for a, b in zip(samples, expected))
    step_mismatches = sum(a["decision"]["lookahead_steps"] != b["decision"]["lookahead_steps"] for a, b in zip(samples, expected))
    result = {"repeat": repeat, "timing": SummarizeTiming(measurements, dt * 1000),
              "phase_timing": {phase: SummarizeTiming([ms for s, ms in zip(samples, measurements) if s["phase"] == phase], dt * 1000)
                               for phase in ("recorded", "hold", "return")},
              "maximum_qpos_error": actual_error, "maximum_preview_qpos_error": preview_error,
              "accepted_step_mismatches": step_mismatches,
              "trajectory_parity": actual_error <= 1e-6 and preview_error <= 1e-6 and step_mismatches == 0}
    if cache_enabled:
        result["clearance_cache"] = {"hits": planner.GetClearance.hits, "misses": planner.GetClearance.misses}
    if broadphase:
        query = planner.benchmark_clearance
        result["clearance_broadphase"] = {"queries": query.queries,
            "pair_queries": query.pair_queries, "skipped_pairs": query.skipped_pairs}
    if constraint_cache:
        result["collision_constraint_cache"] = [
            {"hits": limit.hits, "misses": limit.misses}
            for limit in planner.limits if isinstance(limit, CachedCollisionLimit)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("expected_report", type=Path)
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--broadphase", action="store_true", help="Offline conservative sphere prefilter")
    parser.add_argument("--constraint-cache", action="store_true", help="Offline exact-state collision-QP reuse")
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.segment < 1:
        parser.error("Positive repeats and segment required")
    probe = comparison.probe
    reference_report = json.loads(args.expected_report.read_text(encoding="utf-8"))
    model_path = Path(probe.base.g1.DEMO_XML)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if reference_report["capture_sha256"] != digest(args.capture) or reference_report["model_xml_sha256"] != digest(model_path):
        raise ValueError("Capture or model does not match reference")
    if reference_report["mujoco_version"] != probe.mujoco.__version__ or reference_report["horizon_steps"] != 3:
        raise ValueError("Engine version or horizon does not match reference")
    trace_path = args.expected_report.with_name(args.expected_report.stem + f"_s{args.segment}_limit_avoidance.jsonl")
    expected = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    _, packets = probe._decode_capture(args.capture)
    reference, goals = comparison.GetActiveSegments(packets)[args.segment - 1]
    model = probe.mujoco.MjModel.from_xml_path(str(model_path))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    q[addresses] = reference["value"]["all_joint_q_rad"]
    report = {"robot_command": False, "mujoco_version": probe.mujoco.__version__, "cache_enabled": not args.no_cache,
              "broadphase_enabled": args.broadphase,
              "constraint_cache_enabled": args.constraint_cache,
              "capture_sha256": digest(args.capture), "model_xml_sha256": digest(model_path),
              "expected_trace_sha256": digest(trace_path), "tool_sha256": digest(Path(__file__)), "runs": [],
              "scope": "Planner-only sequential replay with 30 untimed warmup steps per repeat; no rendering, networking, pacing or physical dynamics. Geometry on accepted candidates and all four path samples remains enabled. Flags select exact-state caches and conservative broadphase; rejected-merit diagnostic checks are omitted. Model geometry and collision pairs must remain immutable."}
    for repeat in range(args.repeats):
        result = RunBenchmark(model, q, goals, expected, repeat + 1, not args.no_cache,
                              args.broadphase, args.constraint_cache)
        report["runs"].append(result)
        print(json.dumps(result), flush=True)
    parity = all(r["trajectory_parity"] for r in report["runs"])
    report["status"] = "PARITY_FAILURE" if not parity else "DEADLINE_MISSES" if any(r["timing"]["deadline_misses"] for r in report["runs"]) else "PLANNER_ONLY_BUDGET_MET"
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(report["status"])
    print("Result saved to:", args.result_json.resolve())
    return 0 if parity else 1


if __name__ == "__main__":
    raise SystemExit(main())
