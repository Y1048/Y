#!/usr/bin/env python3
"""Plan and dry-run a collision-aware G1 rest-to-ready transition.

The planner has no Unitree SDK dependency, creates no DDS publisher, and sends
no robot command. It searches deterministic staged joint motions in MuJoCo and
passes the selected 50 Hz trajectory through the hardware Safety Gate.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import sys
from pathlib import Path

import mujoco
import numpy as np

import diagnose_initial_pose_collision as collision_diag
from safety_gate import SafetyConfig, evaluate_target


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
RESULT_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_startup_transition_plan.json"

TRANSITION_SPEED_DEG_S = 8.0
CONTROL_HZ = 50.0
COLLISION_SAMPLE_STEP_DEG = 0.25
FINAL_VALIDATION_STEP_DEG = 0.03
START_HOLD_S = 1.0
END_HOLD_S = 1.0
RRT_SEED = 20260826
RRT_MAX_ITERATIONS = 12000
RRT_STEP_DEG = 3.0
RRT_GOAL_CONNECT_DEG = 12.0
RECOVERY_REGRESSION_TOLERANCE_M = 1e-7

JOINT_GROUPS = (
    ("shoulder_pitch", (0,)),
    ("shoulder_roll", (1,)),
    ("shoulder_yaw", (2,)),
    ("elbow", (3,)),
    ("wrist", (4, 5, 6)),
)


def _inside_pairs(nearby, minimum_distance_m: float):
    inside = [
        item for item in nearby if float(item["distance_m"]) < minimum_distance_m
    ]
    body_pairs = {
        tuple(sorted((str(item["first_body"]), str(item["second_body"]))))
        for item in inside
    }
    return inside, body_pairs


def _waypoints_for_order(start, goal, order):
    current = start.copy()
    waypoints = [current.copy()]
    labels = ["rest_hold"]
    group_indices = dict(JOINT_GROUPS)
    for group_name in order:
        indices = group_indices[group_name]
        current = current.copy()
        current[list(indices)] = goal[list(indices)]
        waypoints.append(current)
        labels.append(group_name)
    return waypoints, labels


def _dense_segment(first, second, step_deg=COLLISION_SAMPLE_STEP_DEG):
    maximum_delta_deg = float(
        np.max(np.abs(np.degrees(np.asarray(second) - np.asarray(first))))
    )
    intervals = max(1, int(math.ceil(maximum_delta_deg / step_deg)))
    return [
        np.asarray(first) + fraction * (np.asarray(second) - np.asarray(first))
        for fraction in np.linspace(0.0, 1.0, intervals + 1)
    ]


def _evaluate_order(model, data, controller, geom_pairs, start, goal, order):
    collision_diag._joint_pose(model, data, controller, start)
    initial_nearby = collision_diag._nearby_pairs(
        model, data, controller, geom_pairs
    )
    initial_inside, initial_body_pairs = _inside_pairs(
        initial_nearby, controller.COLLISION_MIN_DISTANCE_M
    )

    waypoints, labels = _waypoints_for_order(start, goal, order)
    escaped = not initial_inside
    first_clear_sample = 0 if escaped else None
    samples_checked = 0
    elapsed_s = 0.0
    first_clear_time_s = 0.0 if escaped else None
    minimum_clearance_after_escape = math.inf
    failure = None

    for segment_index in range(len(waypoints) - 1):
        first = waypoints[segment_index]
        second = waypoints[segment_index + 1]
        segment_delta_deg = float(
            np.max(np.abs(np.degrees(second - first)))
        )
        segment_duration_s = segment_delta_deg / TRANSITION_SPEED_DEG_S
        dense = _dense_segment(first, second)
        for local_index, pose in enumerate(dense):
            if segment_index > 0 and local_index == 0:
                continue
            fraction = local_index / max(1, len(dense) - 1)
            sample_time_s = elapsed_s + fraction * segment_duration_s
            collision_diag._joint_pose(model, data, controller, pose)
            nearby = collision_diag._nearby_pairs(
                model, data, controller, geom_pairs
            )
            inside, body_pairs = _inside_pairs(
                nearby, controller.COLLISION_MIN_DISTANCE_M
            )
            samples_checked += 1

            if not escaped:
                if not body_pairs.issubset(initial_body_pairs):
                    failure = {
                        "reason": "new_collision_pair_during_escape",
                        "stage": labels[segment_index + 1],
                        "time_s": sample_time_s,
                        "body_pairs": [list(pair) for pair in sorted(body_pairs)],
                    }
                    break
                if len(inside) > len(initial_inside):
                    failure = {
                        "reason": "initial_collision_count_increased",
                        "stage": labels[segment_index + 1],
                        "time_s": sample_time_s,
                        "inside_count": len(inside),
                    }
                    break
                if not inside:
                    escaped = True
                    first_clear_sample = samples_checked
                    first_clear_time_s = sample_time_s
            elif inside:
                failure = {
                    "reason": "collision_after_clearance",
                    "stage": labels[segment_index + 1],
                    "time_s": sample_time_s,
                    "body_pairs": [list(pair) for pair in sorted(body_pairs)],
                }
                break

            if escaped:
                nearest = (
                    math.inf
                    if not nearby
                    else float(nearby[0]["distance_m"])
                )
                minimum_clearance_after_escape = min(
                    minimum_clearance_after_escape, nearest
                )
        if failure is not None:
            break
        elapsed_s += segment_duration_s

    valid = failure is None and escaped
    return {
        "valid": valid,
        "order": list(order),
        "waypoints": [item.tolist() for item in waypoints],
        "waypoint_labels": labels,
        "duration_s": elapsed_s,
        "samples_checked": samples_checked,
        "initial_inside_count": len(initial_inside),
        "initial_inside_body_pairs": [
            list(pair) for pair in sorted(initial_body_pairs)
        ],
        "first_clear_sample": first_clear_sample,
        "first_clear_time_s": first_clear_time_s,
        "minimum_clearance_after_escape_m": (
            None
            if math.isinf(minimum_clearance_after_escape)
            else minimum_clearance_after_escape
        ),
        "failure": failure,
    }


def _joint_limits(model, controller):
    lower = []
    upper = []
    margin = SafetyConfig().joint_limit_margin_rad
    for name in controller.g1.RIGHT_ARM_JOINTS:
        joint_id = controller._joint_id(model, name)
        lower.append(float(model.jnt_range[joint_id, 0]) + margin)
        upper.append(float(model.jnt_range[joint_id, 1]) - margin)
    return np.asarray(lower), np.asarray(upper)


def _edge_is_valid(
    model,
    data,
    controller,
    geom_pairs,
    first,
    second,
    escaped_before,
    initial_minimum_clearance_m,
    initial_body_pairs,
    sample_step_deg=COLLISION_SAMPLE_STEP_DEG,
):
    escaped = bool(escaped_before)
    minimum_clearance = math.inf
    for local_index, pose in enumerate(
        _dense_segment(first, second, step_deg=sample_step_deg)
    ):
        if local_index == 0:
            continue
        collision_diag._joint_pose(model, data, controller, pose)
        nearby = collision_diag._nearby_pairs(model, data, controller, geom_pairs)
        inside, body_pairs = _inside_pairs(
            nearby, controller.COLLISION_MIN_DISTANCE_M
        )
        nearest = math.inf if not nearby else float(nearby[0]["distance_m"])

        if escaped:
            if inside:
                return False, escaped, minimum_clearance
            minimum_clearance = min(minimum_clearance, nearest)
            continue

        if not body_pairs.issubset(initial_body_pairs):
            return False, escaped, minimum_clearance
        if nearest < (
            initial_minimum_clearance_m - RECOVERY_REGRESSION_TOLERANCE_M
        ):
            return False, escaped, minimum_clearance
        if not inside:
            escaped = True
            minimum_clearance = min(minimum_clearance, nearest)

    return True, escaped, minimum_clearance


def _simplify_and_validate_path(
    model,
    data,
    controller,
    geom_pairs,
    path,
    initial_minimum_clearance_m,
    initially_clear,
    initial_body_pairs,
):
    simplified = [np.asarray(path[0], dtype=float)]
    source_index = 0
    escaped = initially_clear

    while source_index < len(path) - 1:
        accepted_index = None
        accepted_escaped = escaped
        for candidate_index in range(len(path) - 1, source_index, -1):
            valid, edge_escaped, _ = _edge_is_valid(
                model,
                data,
                controller,
                geom_pairs,
                path[source_index],
                path[candidate_index],
                escaped,
                initial_minimum_clearance_m,
                initial_body_pairs,
                sample_step_deg=FINAL_VALIDATION_STEP_DEG,
            )
            if valid:
                accepted_index = candidate_index
                accepted_escaped = edge_escaped
                break
        if accepted_index is None:
            raise RuntimeError("RRT path could not retain its next valid edge")
        simplified.append(np.asarray(path[accepted_index], dtype=float))
        source_index = accepted_index
        escaped = accepted_escaped

    strict_escaped = initially_clear
    post_clear_minimum = math.inf
    for first, second in zip(simplified, simplified[1:]):
        valid, strict_escaped, clearance = _edge_is_valid(
            model,
            data,
            controller,
            geom_pairs,
            first,
            second,
            strict_escaped,
            initial_minimum_clearance_m,
            initial_body_pairs,
            sample_step_deg=FINAL_VALIDATION_STEP_DEG,
        )
        if not valid:
            return simplified, False, None
        if strict_escaped:
            post_clear_minimum = min(post_clear_minimum, clearance)

    return (
        simplified,
        strict_escaped,
        None if math.isinf(post_clear_minimum) else post_clear_minimum,
    )


def _search_coordinated_path(model, data, controller, geom_pairs, start, goal):
    collision_diag._joint_pose(model, data, controller, start)
    initial_nearby = collision_diag._nearby_pairs(
        model, data, controller, geom_pairs
    )
    initial_inside, initial_body_pairs = _inside_pairs(
        initial_nearby, controller.COLLISION_MIN_DISTANCE_M
    )
    initial_minimum_clearance_m = (
        math.inf if not initial_nearby else float(initial_nearby[0]["distance_m"])
    )
    lower, upper = _joint_limits(model, controller)
    rng = np.random.default_rng(RRT_SEED)
    nodes = [np.asarray(start, dtype=float).copy()]
    parents = [-1]
    escaped_states = [not initial_inside]
    edge_clearances = [math.inf]
    start_deg = np.degrees(start)
    goal_deg = np.degrees(goal)
    spread_deg = np.asarray([25.0, 18.0, 30.0, 25.0, 25.0, 20.0, 20.0])

    for iteration in range(RRT_MAX_ITERATIONS):
        selector = rng.random()
        if selector < 0.18:
            sample = goal.copy()
        elif selector < 0.88:
            fraction = rng.random()
            center_deg = start_deg + fraction * (goal_deg - start_deg)
            sample = np.radians(center_deg + rng.normal(0.0, spread_deg))
        else:
            sample = rng.uniform(lower, upper)
        sample = np.clip(sample, lower, upper)

        node_matrix = np.asarray(nodes)
        distance_deg = np.max(
            np.abs(np.degrees(node_matrix - sample)), axis=1
        )
        nearest_index = int(np.argmin(distance_deg))
        nearest = nodes[nearest_index]
        delta_deg = np.degrees(sample - nearest)
        maximum_delta_deg = float(np.max(np.abs(delta_deg)))
        if maximum_delta_deg < 1e-9:
            continue
        scale = min(1.0, RRT_STEP_DEG / maximum_delta_deg)
        candidate = nearest + scale * (sample - nearest)

        valid, escaped, clearance = _edge_is_valid(
            model,
            data,
            controller,
            geom_pairs,
            nearest,
            candidate,
            escaped_states[nearest_index],
            initial_minimum_clearance_m,
            initial_body_pairs,
            sample_step_deg=FINAL_VALIDATION_STEP_DEG,
        )
        if not valid:
            continue

        nodes.append(candidate)
        parents.append(nearest_index)
        escaped_states.append(escaped)
        edge_clearances.append(clearance)
        new_index = len(nodes) - 1

        goal_distance_deg = float(
            np.max(np.abs(np.degrees(goal - candidate)))
        )
        if not escaped or goal_distance_deg > RRT_GOAL_CONNECT_DEG:
            continue
        goal_valid, goal_escaped, goal_clearance = _edge_is_valid(
            model,
            data,
            controller,
            geom_pairs,
            candidate,
            goal,
            escaped,
            initial_minimum_clearance_m,
            initial_body_pairs,
            sample_step_deg=FINAL_VALIDATION_STEP_DEG,
        )
        if not goal_valid or not goal_escaped:
            continue

        nodes.append(goal.copy())
        parents.append(new_index)
        escaped_states.append(True)
        edge_clearances.append(goal_clearance)
        path_indices = []
        cursor = len(nodes) - 1
        while cursor >= 0:
            path_indices.append(cursor)
            cursor = parents[cursor]
        path_indices.reverse()
        path = [nodes[index] for index in path_indices]
        simplified, strictly_valid, post_clear_minimum = _simplify_and_validate_path(
            model,
            data,
            controller,
            geom_pairs,
            path,
            initial_minimum_clearance_m,
            not initial_inside,
            initial_body_pairs,
        )
        if not strictly_valid:
            continue
        return {
            "valid": True,
            "planner": "deterministic_collision_aware_rrt",
            "seed": RRT_SEED,
            "iterations": iteration + 1,
            "tree_nodes": len(nodes),
            "initial_inside_count": len(initial_inside),
            "initial_inside_body_pairs": [
                list(pair) for pair in sorted(initial_body_pairs)
            ],
            "raw_waypoint_count": len(path),
            "waypoints": [pose.tolist() for pose in simplified],
            "waypoint_labels": ["rest_hold"]
            + [
                f"coordinated_{index}"
                for index in range(1, len(simplified) - 1)
            ]
            + ["teleop_ready"],
            "final_validation_step_deg": FINAL_VALIDATION_STEP_DEG,
            "minimum_clearance_after_escape_m": post_clear_minimum,
        }

    return {
        "valid": False,
        "planner": "deterministic_collision_aware_rrt",
        "seed": RRT_SEED,
        "iterations": RRT_MAX_ITERATIONS,
        "tree_nodes": len(nodes),
        "initial_inside_count": len(initial_inside),
        "initial_inside_body_pairs": [
            list(pair) for pair in sorted(initial_body_pairs)
        ],
    }


def _trajectory(waypoints, labels):
    dt = 1.0 / CONTROL_HZ
    samples = []
    sequence = 0

    def append_sample(time_s, stage, pose):
        nonlocal sequence
        samples.append(
            {
                "sequence": sequence,
                "time_s": float(time_s),
                "stage": stage,
                "q_rad": np.asarray(pose, dtype=float).tolist(),
            }
        )
        sequence += 1

    start = np.asarray(waypoints[0], dtype=float)
    for index in range(int(round(START_HOLD_S * CONTROL_HZ))):
        append_sample(index * dt, "rest_hold", start)

    elapsed_s = START_HOLD_S
    for segment_index in range(len(waypoints) - 1):
        first = np.asarray(waypoints[segment_index], dtype=float)
        second = np.asarray(waypoints[segment_index + 1], dtype=float)
        maximum_delta_deg = float(
            np.max(np.abs(np.degrees(second - first)))
        )
        segment_duration_s = maximum_delta_deg / TRANSITION_SPEED_DEG_S
        intervals = max(1, int(math.ceil(segment_duration_s * CONTROL_HZ)))
        for local_index in range(1, intervals + 1):
            fraction = local_index / intervals
            pose = first + fraction * (second - first)
            append_sample(
                elapsed_s + local_index * dt,
                labels[segment_index + 1],
                pose,
            )
        elapsed_s += intervals * dt

    goal = np.asarray(waypoints[-1], dtype=float)
    for _ in range(int(round(END_HOLD_S * CONTROL_HZ))):
        elapsed_s += dt
        append_sample(elapsed_s, "teleop_ready_hold", goal)
    return samples


def _safety_gate_dry_run(samples):
    config = SafetyConfig()
    dt = 1.0 / CONTROL_HZ
    measured = tuple(float(value) for value in samples[0]["q_rad"])
    previous = None
    rate_limited = 0
    for sample in samples:
        requested = tuple(float(value) for value in sample["q_rad"])
        decision = evaluate_target(
            measured_q_rad=measured,
            requested_q_rad=requested,
            previous_command_q_rad=previous,
            lowstate_age_s=0.0,
            dt_s=dt,
            config=config,
        )
        if not decision.allowed or decision.command_q_rad is None:
            return {
                "passed": False,
                "failed_sequence": sample["sequence"],
                "reason": decision.reason,
                "rate_limited_samples": rate_limited,
            }
        if decision.rate_limited:
            rate_limited += 1
        previous = decision.command_q_rad
        measured = decision.command_q_rad

    stale = evaluate_target(
        measured_q_rad=measured,
        requested_q_rad=measured,
        previous_command_q_rad=previous,
        lowstate_age_s=config.lowstate_timeout_s + 0.001,
        dt_s=dt,
        config=config,
    )
    stale_blocked = stale.command_q_rad is None and not stale.allowed
    return {
        "passed": stale_blocked,
        "accepted_samples": len(samples),
        "rate_limited_samples": rate_limited,
        "stale_lowstate_blocked": stale_blocked,
    }


def main() -> int:
    os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller

    start = np.asarray(
        json.loads(STATE_PATH.read_text(encoding="utf-8"))["right_arm_q_rad"],
        dtype=float,
    )
    goal = np.radians(controller.g1.DEFAULT_RIGHT_ARM_READY_DEGREES)

    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    data = mujoco.MjData(model)
    _, geom_pairs = controller._build_collision_pairs(model)

    candidates = []
    group_names = [name for name, _ in JOINT_GROUPS]
    for order in itertools.permutations(group_names):
        candidates.append(
            _evaluate_order(
                model, data, controller, geom_pairs, start, goal, order
            )
        )

    valid = [item for item in candidates if item["valid"]]
    if not valid:
        coordinated = _search_coordinated_path(
            model, data, controller, geom_pairs, start, goal
        )
        if coordinated["valid"]:
            trajectory = _trajectory(
                [np.asarray(item, dtype=float) for item in coordinated["waypoints"]],
                coordinated["waypoint_labels"],
            )
            gate = _safety_gate_dry_run(trajectory)
            passed = bool(gate["passed"])
            result = {
                "passed": passed,
                "command_output_enabled": False,
                "planner": coordinated["planner"],
                "staged_candidate_count": len(candidates),
                "staged_valid_candidate_count": 0,
                "transition_speed_deg_s": TRANSITION_SPEED_DEG_S,
                "control_hz": CONTROL_HZ,
                "collision_sample_step_deg": COLLISION_SAMPLE_STEP_DEG,
                "selected": coordinated,
                "safety_gate": gate,
                "trajectory": trajectory,
            }
            temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
            temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
            temporary.replace(RESULT_PATH)
            print("G1 rest-to-ready startup transition -- OFFLINE DRY RUN")
            print("Staged search: 120 total, 0 valid")
            print(
                f"Coordinated search: {coordinated['iterations']} iterations, "
                f"{coordinated['tree_nodes']} nodes"
            )
            print(f"Waypoints: {len(coordinated['waypoints'])}")
            print(f"Transition duration: {trajectory[-1]['time_s']:.3f} s")
            print(f"Trajectory samples: {len(trajectory)} at {CONTROL_HZ:.1f} Hz")
            print(
                "Safety Gate rate-limited samples: "
                f"{gate.get('rate_limited_samples', 0)}"
            )
            print("DDS publisher: NONE")
            print("Robot command: NONE")
            print("[PASS]" if passed else "[FAIL]")
            return 0 if passed else 3

        result = {
            "passed": False,
            "command_output_enabled": False,
            "reason": "no_valid_staged_transition",
            "candidate_count": len(candidates),
            "coordinated_search": coordinated,
            "candidates": candidates,
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("[FAIL] No collision-valid staged startup transition was found.")
        print("Robot command: NONE")
        return 2

    valid.sort(
        key=lambda item: (
            float(item["first_clear_time_s"]),
            -float(item["minimum_clearance_after_escape_m"]),
            float(item["duration_s"]),
        )
    )
    selected = valid[0]
    trajectory = _trajectory(
        [np.asarray(item, dtype=float) for item in selected["waypoints"]],
        selected["waypoint_labels"],
    )
    gate = _safety_gate_dry_run(trajectory)
    passed = bool(gate["passed"])
    result = {
        "passed": passed,
        "command_output_enabled": False,
        "planner": "deterministic_staged_joint_search",
        "candidate_count": len(candidates),
        "valid_candidate_count": len(valid),
        "transition_speed_deg_s": TRANSITION_SPEED_DEG_S,
        "control_hz": CONTROL_HZ,
        "collision_sample_step_deg": COLLISION_SAMPLE_STEP_DEG,
        "selected": selected,
        "safety_gate": gate,
        "trajectory": trajectory,
    }
    temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(RESULT_PATH)

    print("G1 rest-to-ready startup transition -- OFFLINE DRY RUN")
    print(f"Candidates: {len(candidates)} total, {len(valid)} valid")
    print("Selected order: " + " -> ".join(selected["order"]))
    print(f"First clear: {selected['first_clear_time_s']:.3f} s")
    print(f"Transition duration: {trajectory[-1]['time_s']:.3f} s")
    print(f"Trajectory samples: {len(trajectory)} at {CONTROL_HZ:.1f} Hz")
    print(f"Safety Gate rate-limited samples: {gate.get('rate_limited_samples', 0)}")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    print("[PASS]" if passed else "[FAIL]")
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
