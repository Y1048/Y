"""Offline mesh-distance consistency audit. Never selects or executes robot commands."""

import argparse
import hashlib
import json
import time
from collections import Counter
from itertools import product
from pathlib import Path

import numpy as np

import compare_mink_step_acceptance as comparison


def GetSupportGap(first, second, direction):
    """Positive projection gap proves separation of both vertex convex hulls."""
    norm = np.linalg.norm(direction)
    if not np.isfinite(norm) or norm < 1e-12:
        return None
    axis = direction / norm
    a, b = first @ axis, second @ axis
    return float(max(np.min(b) - np.max(a), np.min(a) - np.max(b)))


def GetWorldVertices(model, data, geom):
    mujoco = comparison.probe.mujoco
    if model.geom_type[geom] != mujoco.mjtGeom.mjGEOM_MESH:
        raise ValueError("This audit requires mesh collision geometry")
    mesh = model.geom_dataid[geom]
    start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
    return model.mesh_vert[start:start + count] @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom]


def GetEnclosingVertices(model, data, geom):
    """Mesh hull or conservative outer box; never shrink collision geometry."""
    types = comparison.probe.mujoco.mjtGeom
    kind, size = model.geom_type[geom], model.geom_size[geom]
    if kind == types.mjGEOM_MESH:
        return GetWorldVertices(model, data, geom)
    if kind in (types.mjGEOM_BOX, types.mjGEOM_ELLIPSOID):
        extent = size.copy()
    elif kind == types.mjGEOM_SPHERE:
        extent = np.full(3, size[0])
    elif kind == types.mjGEOM_CAPSULE:
        extent = np.array([size[0], size[0], size[0] + size[1]])
    elif kind == types.mjGEOM_CYLINDER:
        extent = np.array([size[0], size[0], size[1]])
    else:
        return None
    vertices = np.array(list(product((-1., 1.), repeat=3))) * extent
    return vertices @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom]


def GetSeparationCertificate(first, second, directions, clearance_m=0.02):
    """OFFLINE lower bound only; an inconclusive result never authorizes motion."""
    arrays = [np.asarray(value, dtype=float) for value in (first, second, directions)]
    if (not np.isfinite(clearance_m) or clearance_m < 0 or
            any(a.ndim != 2 or a.shape[1] != 3 or not len(a) or
                not np.all(np.isfinite(a)) for a in arrays)):
        return {"status": "INVALID_INPUT", "lower_bound_m": None}
    first, second, directions = arrays
    scale = max(1., float(np.max(np.abs(first))), float(np.max(np.abs(second))))
    reserve = max(1e-6, 64 * np.finfo(float).eps * scale)
    # Shared recentering reduces cancellation without changing relative geometry.
    origin = first[0].copy()
    first, second = first - origin, second - origin
    lengths = np.linalg.norm(directions, axis=1)
    directions = directions[np.isfinite(lengths) & (lengths > 1e-12)]
    if not len(directions):
        return {"status": "INVALID_INPUT", "lower_bound_m": None}
    directions = directions / np.linalg.norm(directions, axis=1)[:, None]
    a, b = first @ directions.T, second @ directions.T
    gaps = np.maximum(np.min(b, axis=0) - np.max(a, axis=0),
                      np.min(a, axis=0) - np.max(b, axis=0))
    index = int(np.argmax(gaps))
    lower_bound = max(0., float(gaps[index]) - reserve)
    return {"status": "CLEARANCE_CERTIFIED" if gaps[index] >= clearance_m + reserve else "UNRESOLVED",
            "lower_bound_m": lower_bound, "projection_gap_m": float(gaps[index]),
            "roundoff_reserve_m": reserve, "axis": directions[index].tolist()}


def InspectTrace(model, reference_q, addresses, pairs, rows, stride):
    """Check canonical preview endpoints; not swept paths or an IK replacement."""
    probe = comparison.probe
    data = probe.mujoco.MjData(model)
    counts = Counter()
    examples = []
    minimum_bound = float("inf")
    elapsed = time.perf_counter()
    for frame in range(0, len(rows), stride):
        data.qpos[:] = reference_q
        data.qpos[addresses] = rows[frame]["decision"]["lookahead_target_right_q_rad"]
        probe.mujoco.mj_forward(model, data)
        vertices = {g: GetEnclosingVertices(model, data, g) for g in {g for pair in pairs for g in pair}}
        for pair in pairs:
            points = np.zeros(6)
            raw = float(probe.mujoco.mj_geomDistance(model, data, *pair, 0.2, points))
            a, b = [vertices[g] for g in pair]
            if a is None or b is None:
                counts["UNSUPPORTED_GEOMETRY"] += 1
                continue
            directions = np.vstack((np.eye(3), *(data.geom_xmat[g].reshape(3, 3).T for g in pair),
                                    np.mean(b, axis=0) - np.mean(a, axis=0), points[3:] - points[:3]))
            certificate = GetSeparationCertificate(a, b, directions)
            counts[certificate["status"]] += 1
            if certificate["lower_bound_m"] is not None:
                minimum_bound = min(minimum_bound, certificate["lower_bound_m"])
            contradiction = certificate["lower_bound_m"] is not None and raw < min(0.2, certificate["lower_bound_m"]) - 1e-6
            if contradiction:
                counts["raw_lower_bound_contradictions"] += 1
            if (contradiction or certificate["status"] != "CLEARANCE_CERTIFIED") and len(examples) < 30:
                examples.append({"frame": frame, "pair": [int(g) for g in pair],
                                 "raw_distance_m": raw, "certificate": certificate})
    return {"stride": stride, "frames": len(range(0, len(rows), stride)), "pairs_per_frame": len(pairs),
            "counts": dict(counts), "minimum_lower_bound_m": minimum_bound if np.isfinite(minimum_bound) else None,
            "examples": examples, "elapsed_s": time.perf_counter() - elapsed,
            "boundary": "Canonical preview endpoints only. Mesh vertices or enclosing primitive boxes. UNRESOLVED/UNSUPPORTED never mean safe. No path, velocity, or physical safety approval."}


def ClassifyRows(rows, tolerance_m=1e-6):
    raw = [r["raw_distance_m"] for r in rows]
    robust = [r["guard_distance_m"] for r in rows]
    spans = {"raw_span_m": max(raw) - min(raw), "guard_span_m": max(robust) - min(robust)}
    contradiction = any(r["support_gap_m"] is not None and r["support_gap_m"] > tolerance_m
                        and r["guard_distance_m"] < -tolerance_m for r in rows)
    inconsistent = contradiction or max(spans.values()) > tolerance_m
    return {"status": "DISTANCE_INCONSISTENT" if inconsistent else "NO_INCONSISTENCY_OBSERVED",
            "separation_sign_contradiction": contradiction, **spans}


def InspectPose(model, q, pair):
    probe = comparison.probe
    data = probe.mujoco.MjData(model)
    rows = []
    for offset in (0.0, 1e-12, -1e-12, 1e-9, -1e-9, 1e-6, -1e-6):
        data.qpos[:] = q
        data.qpos[0] += offset
        probe.mujoco.mj_forward(model, data)
        points = np.zeros(6)
        raw = float(probe.mujoco.mj_geomDistance(model, data, *pair, 0.2, points))
        a, b = [GetWorldVertices(model, data, geom) for geom in pair]
        gaps = [GetSupportGap(a, b, direction) for direction in
                (points[3:] - points[:3], np.mean(b, axis=0) - np.mean(a, axis=0))]
        gap = max((g for g in gaps if g is not None), default=None)
        guard = probe.base._robust_geom_distance(model, data, *pair, 0.2, np.zeros(6))
        certificate = GetSeparationCertificate(a, b, np.vstack((np.eye(3),
            np.mean(b, axis=0) - np.mean(a, axis=0), points[3:] - points[:3])))
        rows.append({"global_x_offset_m": offset, "raw_distance_m": raw,
                     "guard_distance_m": guard, "support_gap_m": gap, "certificate": certificate})
    return {**ClassifyRows(rows), "qpos": q.tolist(), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--frame", type=int, default=864, help="Zero-based trace frame")
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--scan-stride", type=int, default=0, help="Opt-in preview endpoint scan; 1 checks every frame, 0 disables")
    parser.add_argument("--geom-pair", nargs=2, help="Pin geom names for engine-version comparisons")
    args = parser.parse_args()
    if args.scan_stride < 0:
        parser.error("scan-stride must be non-negative")
    probe = comparison.probe
    _, packets = probe._decode_capture(args.capture)
    reference, _ = comparison.GetActiveSegments(packets)[args.segment - 1]
    rows = [json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines()]
    row = rows[args.frame]
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    q[addresses] = reference["value"]["all_joint_q_rad"]
    planner = comparison.BuildPlanner(model, q)
    q[planner.qpos_ids] = row["decision"]["lookahead_target_right_q_rad"]
    if args.geom_pair:
        pair = tuple(probe.mujoco.mj_name2id(model, probe.mujoco.mjtObj.mjOBJ_GEOM, name) for name in args.geom_pair)
        if min(pair) < 0:
            raise ValueError("Unknown geom name in geom-pair")
    else:
        planner.GetClearance(q)
        nearest = probe.base._nearest_pair_distance(model, planner.validation_data, planner.geom_pairs)
        if nearest is None:
            raise ValueError("No nearby pair to audit")
        pair = tuple(nearest[1:])
    cases = {"canonical_frozen_pose": InspectPose(model, q, pair)}
    if "lookahead_target_qpos" in row["decision"]:
        exact = np.array(row["decision"]["lookahead_target_qpos"])
        cases["exact_saved_pose"] = InspectPose(model, exact, pair)
        frozen_delta = float(np.max(np.abs(exact - q)))
    else:
        frozen_delta = None
    report = {"robot_command": False, "mujoco_version": probe.mujoco.__version__,
              "capture_sha256": hashlib.sha256(args.capture.read_bytes()).hexdigest(),
              "trace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(),
              "model_xml_sha256": hashlib.sha256(Path(probe.base.g1.DEMO_XML).read_bytes()).hexdigest(),
              "frame": args.frame, "time_s": row["time_s"],
              "geom_names": [probe.mujoco.mj_id2name(model, probe.mujoco.mjtObj.mjOBJ_GEOM, g) for g in pair],
              "maximum_frozen_q_difference": frozen_delta, "cases": cases,
              "boundary": "A support gap is a lower bound for vertex convex-hull separation, not a robot safety certificate. Never fix inconsistent signs by choosing the convenient positive value."}
    report["status"] = "BLOCK_DEPLOYMENT" if any(c["status"] == "DISTANCE_INCONSISTENT" for c in cases.values()) else "REVIEW_REQUIRED"
    if args.scan_stride:
        report["endpoint_scan"] = InspectTrace(model, q, planner.qpos_ids, planner.geom_pairs, rows, args.scan_stride)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(report["status"])
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
