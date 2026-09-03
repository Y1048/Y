"""Offline constrained endpoint search and sampled direct-path inspection."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from compare_mink_step_acceptance import BuildPlanner, probe


class EndpointProblem:
    def __init__(self, planner, start_q, goal):
        self.planner = planner
        self.start_q = start_q.copy()
        self.goal = goal
        self.configuration = probe.mink.Configuration(planner.model)
        self.orientation = probe.mink.FrameTask("right_wrist_yaw_link", "body", 0, 1)
        self.orientation.set_target(goal)

    def GetConfiguration(self, joints):
        q = self.start_q.copy()
        q[self.planner.qpos_ids] = joints
        return q

    def GetResidual(self, joints):
        self.configuration.update(self.GetConfiguration(joints))
        pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        return np.concatenate((self.goal.translation() - pose.translation(),
            self.orientation.compute_error(self.configuration)[3:]))

    def GetJacobian(self, joints):
        self.configuration.update(self.GetConfiguration(joints))
        pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        jacobian = self.configuration.get_frame_jacobian("right_wrist_yaw_link", "body")
        return np.vstack((-pose.rotation().as_matrix() @ jacobian[:3],
            self.orientation.compute_jacobian(self.configuration)[3:]))[:, self.planner.right_dofs]

    def GetNegativeClearance(self, joints):
        return -self.planner.GetClearance(self.GetConfiguration(joints))

    def GetJointDistance(self, joints):
        delta = joints - self.start_q[self.planner.qpos_ids]
        return float(delta @ delta)

    def GetJointDistanceJacobian(self, joints):
        return 2 * (joints - self.start_q[self.planner.qpos_ids])

    def GetClearanceResidual(self, joints):
        return -self.GetNegativeClearance(joints) - self.planner.clearance_m

    def InspectEndpoint(self, joints):
        residual = self.GetResidual(joints)
        q = self.GetConfiguration(joints)
        position_cm = float(np.linalg.norm(residual[:3]) * 100)
        rotation_deg = float(np.rad2deg(np.linalg.norm(residual[3:])))
        valid = self.planner.CheckConfiguration(q)
        return {"q": q.tolist(), "position_cm": position_cm, "rotation_deg": rotation_deg,
            "clearance_mm": self.planner.GetClearance(q) * 1000,
            "configuration_valid": bool(valid),
            "pose_match": bool(valid and position_cm < 0.1 and rotation_deg < 1.0)}


def InspectDirectPath(planner, start_q, end_q, spacing_deg=0.25, goal=None, orientation_scale=0.5):
    """Joint-space samples only, not a continuous or dynamic safety proof."""
    if not np.isfinite(spacing_deg) or spacing_deg <= 0:
        raise ValueError("Positive finite path spacing required")
    start_q, end_q = np.asarray(start_q), np.asarray(end_q)
    if start_q.shape != (planner.model.nq,) or end_q.shape != start_q.shape:
        raise ValueError("Invalid configuration shape")
    if not np.isfinite(start_q).all() or not np.isfinite(end_q).all():
        raise ValueError("Non-finite configuration")
    frozen = np.ones(planner.model.nq, dtype=bool)
    frozen[planner.qpos_ids] = False
    if not np.array_equal(start_q[frozen], end_q[frozen]):
        raise ValueError("Endpoint changed a frozen coordinate")
    delta = end_q - start_q
    intervals = max(1, math.ceil(np.max(np.abs(delta[planner.qpos_ids])) / math.radians(spacing_deg)))
    minimum = float("inf")
    metrics = []
    configuration = probe.mink.Configuration(planner.model)
    for index in range(intervals + 1):
        q = start_q + delta * (index / intervals)
        clearance = planner.GetClearance(q)
        minimum = min(minimum, clearance)
        if goal is not None:
            configuration.update(q)
            pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
            position_error = float(np.linalg.norm(goal.translation() - pose.translation()))
            rotation_error = probe.base._rotation_error_radians(goal.rotation().as_matrix(), pose.rotation().as_matrix())
            merit = probe.base.POSITION_COST ** 2 * position_error ** 2 + orientation_scale ** 2 * rotation_error ** 2
            metrics.append((position_error * 100, math.degrees(rotation_error), merit))
        if not planner.CheckConfiguration(q):
            return {"sampled_valid": False, "checked_samples": index + 1,
                "planned_samples": intervals + 1, "first_invalid_fraction": index / intervals,
                "minimum_checked_clearance_mm": minimum * 1000, "spacing_deg": spacing_deg}
    result = {"sampled_valid": True, "checked_samples": intervals + 1,
        "minimum_checked_clearance_mm": minimum * 1000, "spacing_deg": spacing_deg,
        "joint_delta_deg": np.rad2deg(delta[planner.qpos_ids]).tolist(),
        "velocity_only_minimum_duration_s": float(np.max(
            np.abs(delta[planner.qpos_ids]) / planner.velocity_caps)),
        "boundary": "Geometry samples only; no acceleration, jerk, torque, dynamics or continuous-collision proof."}
    if metrics:
        result["goal_error"] = {"start_position_cm": metrics[0][0],
            "maximum_position_cm": max(m[0] for m in metrics),
            "maximum_rotation_deg": max(m[1] for m in metrics),
            "start_merit": metrics[0][2], "maximum_merit": max(m[2] for m in metrics),
            "merit_increasing_intervals": int(np.count_nonzero(np.diff([m[2] for m in metrics]) > 1e-10)),
            "final_position_cm": metrics[-1][0], "final_rotation_deg": metrics[-1][1]}
    return result


def InspectWaypointRoute(planner, nodes, goal, spacing_deg, orientation_scale):
    legs = []
    for start, end in zip(nodes, nodes[1:]):
        leg = InspectDirectPath(planner, start, end, spacing_deg, goal, orientation_scale)
        legs.append(leg)
        if not leg["sampled_valid"]:
            return {"sampled_valid": False, "legs": legs}
    if not legs:
        raise ValueError("At least two route nodes required")
    joints = np.array(nodes)[:, planner.qpos_ids]
    return {"sampled_valid": True, "legs": legs,
        "q_nodes": [np.asarray(q).tolist() for q in nodes],
        "joint_path_length_deg": float(np.sum(np.linalg.norm(np.rad2deg(np.diff(joints, axis=0)), axis=1))),
        "maximum_joint_excursion_deg": float(np.max(np.abs(np.rad2deg(joints - joints[0])))),
        "minimum_checked_clearance_mm": min(l["minimum_checked_clearance_mm"] for l in legs),
        "maximum_position_error_cm": max(l["goal_error"]["maximum_position_cm"] for l in legs),
        "maximum_rotation_error_deg": max(l["goal_error"]["maximum_rotation_deg"] for l in legs),
        "velocity_only_minimum_duration_s": sum(l["velocity_only_minimum_duration_s"] for l in legs),
        "boundary": "Sampled geometry only; no dynamics or executable controller trajectory."}


def InspectShortcuts(planner, start_q, goal, baseline, endpoints, orientation_scale):
    known = next(r for r in baseline["results"] if r.get("direct_path", {}).get("sampled_valid"))
    problem = EndpointProblem(planner, start_q, goal)
    verified = []
    for result in endpoints["results"]:
        candidate = np.array(result["q"])
        if candidate.shape != start_q.shape or not np.isfinite(candidate).all():
            raise ValueError("Invalid saved endpoint")
        inspection = problem.InspectEndpoint(candidate[planner.qpos_ids])
        if not np.array_equal(candidate, np.array(inspection["q"])):
            raise ValueError("Saved endpoint changed frozen coordinates")
        if inspection["pose_match"]:
            verified.append(inspection)
    if not verified:
        raise ValueError("No endpoint passes current FK pose and clearance checks")
    endpoint = min(verified,
        key=lambda r: np.linalg.norm(np.array(r["q"])[planner.qpos_ids] - start_q[planner.qpos_ids]))
    safe_end = np.array(known["q"])
    end_q = np.array(endpoint["q"])
    # 기존에 검사한 경로 위의 경유점만 사용한다. 각 새 연결 구간도 독립 검사한다.
    trials = []
    for fraction in (0.0, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        via = start_q + fraction * (safe_end - start_q)
        nodes = [start_q, via, end_q]
        route = InspectWaypointRoute(planner, nodes, goal, 0.25, orientation_scale)
        if route["sampled_valid"]:
            route = InspectWaypointRoute(planner, nodes, goal, 0.05, orientation_scale)
        trials.append({"baseline_fraction": fraction, **route})
        print("Shortcut fraction", fraction, "sampled_valid", route["sampled_valid"], flush=True)
    valid = [r for r in trials if r["sampled_valid"]]
    return {"robot_command": False, "trials": trials,
        "selected": min(valid, key=lambda r: r["joint_path_length_deg"]) if valid else None,
        "status": "SAMPLED_SHORTCUT_FOUND" if valid else "NO_SHORTCUT_FOUND_NOT_A_PROOF",
        "boundary": "Finite waypoint candidates, not a global shortest-path proof or physical authorization."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("held_audit", type=Path)
    parser.add_argument("endpoint_audit", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--segment", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=100)
    parser.add_argument("--path-spacing-deg", type=float, default=0.25)
    parser.add_argument("--objective", choices=("clearance", "joint-distance"), default="clearance")
    parser.add_argument("--seed-result", type=Path, help="Previously validated endpoint result for extra seeds")
    parser.add_argument("--shortcut-endpoints", type=Path,
                        help="Search waypoint routes to these endpoints using --seed-result as baseline")
    args = parser.parse_args()
    if not 1 <= args.maxiter <= 1000:
        parser.error("maxiter must be between 1 and 1000")
    if not np.isfinite(args.path_spacing_deg) or args.path_spacing_deg <= 0:
        parser.error("path-spacing-deg must be positive and finite")
    if args.shortcut_endpoints is not None and args.seed_result is None:
        parser.error("shortcut-endpoints requires seed-result")
    held = json.loads(args.held_audit.read_text(encoding="utf-8"))
    endpoint = json.loads(args.endpoint_audit.read_text(encoding="utf-8"))
    if held["capture_sha256"] != endpoint["capture_sha256"]:
        raise ValueError("Capture hashes differ")
    if endpoint.get("endpoint_source_sha256") != hashlib.sha256(args.held_audit.read_bytes()).hexdigest():
        raise ValueError("Endpoint audit was generated from a different held audit")
    segment = next(s for s in endpoint["segments"] if s["segment"] == args.segment)
    variant = segment["source_variant"]
    audit = next(s for s in held["segments"] if s["segment"] == args.segment)["variants"][variant]["held_goal_audit"]
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    q = np.array(audit["q"])
    matrix = np.array(audit["goal_matrix"])
    goal = probe.base._matrix_to_se3(matrix[:3, :3], matrix[:3, 3])
    planner = BuildPlanner(model, q)
    if not planner.CheckConfiguration(q):
        raise ValueError("Held start is invalid under current model")
    planner.configuration.update(q)
    if not np.isclose(planner.GetMerit(goal, audit["orientation_scale"]), audit["merit"], rtol=1e-8, atol=1e-10):
        raise ValueError("Current FK merit does not match the saved held audit")
    problem = EndpointProblem(planner, q, goal)
    lower, upper = model.jnt_range[planner.joint_ids].T
    seeds = sorted(segment["endpoint_audit"]["endpoints"], key=lambda s: -s["clearance_mm"])
    seeds = [{"seed": "held", "q": q.tolist()}] + seeds
    seed_result_hash = None
    if args.seed_result is not None:
        previous = json.loads(args.seed_result.read_text(encoding="utf-8"))
        seed_result_hash = hashlib.sha256(args.seed_result.read_bytes()).hexdigest()
        if (previous["capture_sha256"] != held["capture_sha256"]
                or previous["held_audit_sha256"] != hashlib.sha256(args.held_audit.read_bytes()).hexdigest()
                or previous["segment"] != args.segment):
            raise ValueError("Extra seeds do not belong to this held goal")
        seeds.extend({"seed": f"previous_{s['seed']}", "q": s["q"]}
            for s in previous["results"] if s["pose_match"])
    report = {"robot_command": False, "capture_sha256": held["capture_sha256"],
        "held_audit_sha256": hashlib.sha256(args.held_audit.read_bytes()).hexdigest(),
        "endpoint_audit_sha256": hashlib.sha256(args.endpoint_audit.read_bytes()).hexdigest(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "segment": args.segment, "objective": args.objective, "seed_result_sha256": seed_result_hash,
        "method": "SLSQP with exact 6D pose equality and joint bounds; joint-distance also constrains minimum clearance",
        "boundary": "Offline finite local search; failure is not proof of unreachability. No networking, publisher, robot output or production IK changes.",
        "clearance_required_mm": planner.clearance_m * 1000, "results": []}
    if args.shortcut_endpoints is not None:
        candidates = json.loads(args.shortcut_endpoints.read_text(encoding="utf-8"))
        for key in ("capture_sha256", "held_audit_sha256", "segment"):
            if candidates[key] != report[key]:
                raise ValueError("Shortcut endpoints do not belong to this held goal")
        report["shortcut_endpoint_sha256"] = hashlib.sha256(args.shortcut_endpoints.read_bytes()).hexdigest()
        report["route_search"] = InspectShortcuts(planner, q, goal, previous, candidates, audit["orientation_scale"])
        report["method"] = "Finite baseline-waypoint shortcut search with independent fine validation"
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(report["route_search"]["status"])
        print("Result saved to:", args.result_json.resolve())
        return
    for seed in seeds:
        joints = np.array(seed["q"])[planner.qpos_ids]
        started = time.perf_counter()
        constraints = [{"type": "eq", "fun": problem.GetResidual, "jac": problem.GetJacobian}]
        if args.objective == "joint-distance":
            constraints.append({"type": "ineq", "fun": problem.GetClearanceResidual})
        solution = minimize(problem.GetJointDistance if args.objective == "joint-distance" else problem.GetNegativeClearance,
            np.clip(joints, lower, upper), method="SLSQP",
            jac=problem.GetJointDistanceJacobian if args.objective == "joint-distance" else None,
            bounds=list(zip(lower, upper)),
            constraints=constraints,
            options={"maxiter": args.maxiter, "ftol": 1e-10})
        result = {"seed": seed["seed"], "optimizer_success": bool(solution.success),
            "optimizer_message": str(solution.message), "iterations": int(solution.nit),
            "elapsed_s": time.perf_counter() - started, **problem.InspectEndpoint(solution.x)}
        delta_deg = np.rad2deg(solution.x - q[planner.qpos_ids])
        result["joint_distance_norm_deg"] = float(np.linalg.norm(delta_deg))
        result["maximum_joint_change_deg"] = float(np.max(np.abs(delta_deg)))
        if result["pose_match"]:
            result["direct_path"] = InspectDirectPath(planner, q, np.array(result["q"]),
                spacing_deg=args.path_spacing_deg, goal=goal, orientation_scale=audit["orientation_scale"])
        report["results"].append(result)
        report["status"] = ("SAMPLED_DIRECT_PATH_FOUND" if any(
            r.get("direct_path", {}).get("sampled_valid") for r in report["results"])
            else "ENDPOINT_FOUND_PATH_UNRESOLVED" if any(r["pose_match"] for r in report["results"])
            else "NO_FEASIBLE_ENDPOINT_FOUND_NOT_A_PROOF")
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "q"}), flush=True)
    print(report["status"])
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
