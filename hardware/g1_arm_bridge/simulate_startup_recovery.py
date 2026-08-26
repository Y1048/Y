#!/usr/bin/env python3
"""Offline Mink QP recovery from measured G1 rest pose to teleop-ready pose.

This process has no Unitree SDK dependency, creates no DDS publisher, opens no
network socket, and sends no robot command. It exists only to validate the
kinematic startup state-machine transition before hardware output is written.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import mink
import mujoco
import numpy as np

import diagnose_initial_pose_collision as collision_diag
import plan_startup_transition as startup_plan
from safety_gate import SafetyConfig, evaluate_target


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
RESULT_PATH = Path(
    os.environ.get(
        "G1_STARTUP_RESULT_PATH",
        str(PROJECT_ROOT / "logs" / "runtime" / "g1_startup_mink_recovery.json"),
    )
)

CONTROL_HZ = 500.0
DT_S = 1.0 / CONTROL_HZ
MAX_DURATION_S = 30.0
MAX_JOINT_VELOCITY_RAD_S = math.radians(8.0)
QP_MAX_JOINT_VELOCITY_RAD_S = math.radians(6.0)
FINE_QP_MAX_JOINT_VELOCITY_RAD_S = math.radians(0.5)
MAX_JOINT_ACCELERATION_RAD_S2 = math.radians(30.0)
MAX_JOINT_JERK_RAD_S3 = math.radians(300.0)
READY_TOLERANCE_RAD = math.radians(0.5)
POSTURE_COST = 1.0
DAMPING_COST = 1e-3
TRACE_DECIMATION = 10
ESCAPE_OFFSET_ROBOT_M = np.asarray(
    [float(value) for value in os.environ.get(
        "G1_STARTUP_ESCAPE_OFFSET", "0,-0.18,0.08"
    ).split(",")],
    dtype=float,
)
RECOVERY_VALIDATION_STEP_DEG = 0.001
ESCAPE_TARGET_TOLERANCE_M = 0.015
ESCAPE_LATCH_DISTANCE_M = 0.040
STARTUP_COLLISION_DETECTION_DISTANCE_M = 0.080
STARTUP_QP_MINIMUM_COLLISION_DISTANCE_M = 0.040
STARTUP_SAFE_READY_DEGREES = np.asarray(
    [10.0, -30.0, 0.0, 55.0, 0.0, 0.0, 0.0], dtype=float
)


def _right_qpos_ids(model, controller):
    return np.asarray(
        [
            int(model.jnt_qposadr[controller._joint_id(model, name)])
            for name in controller.g1.RIGHT_ARM_JOINTS
        ],
        dtype=int,
    )


def _minimum_clearance(model, data, controller, geom_pairs):
    nearby = collision_diag._nearby_pairs(model, data, controller, geom_pairs)
    return math.inf if not nearby else float(nearby[0]["distance_m"])


def _minimum_clearance_extended(model, data, geom_pairs, max_distance_m=0.2):
    fromto = np.empty(6, dtype=float)
    minimum = math.inf
    for first_geom, second_geom in geom_pairs:
        distance = float(
            mujoco.mj_geomDistance(
                model,
                data,
                int(first_geom),
                int(second_geom),
                max_distance_m,
                fromto,
            )
        )
        minimum = min(minimum, distance)
    return minimum


def _recovery_edge_is_valid(
    model,
    data,
    controller,
    geom_pairs,
    first,
    second,
    escaped_before,
    initial_body_pairs,
):
    escaped = bool(escaped_before)
    minimum_after_escape = math.inf
    for local_index, pose in enumerate(
        startup_plan._dense_segment(
            first,
            second,
            step_deg=RECOVERY_VALIDATION_STEP_DEG,
        )
    ):
        if local_index == 0:
            continue
        collision_diag._joint_pose(model, data, controller, pose)
        nearby = collision_diag._nearby_pairs(model, data, controller, geom_pairs)
        inside, body_pairs = startup_plan._inside_pairs(
            nearby, controller.COLLISION_MIN_DISTANCE_M
        )
        nearest = math.inf if not nearby else float(nearby[0]["distance_m"])
        if escaped:
            if inside:
                return False, escaped, minimum_after_escape
            minimum_after_escape = min(minimum_after_escape, nearest)
            continue
        if not body_pairs.issubset(initial_body_pairs):
            return False, escaped, minimum_after_escape
        initial_pair_still_near = any(
            tuple(
                sorted((str(item["first_body"]), str(item["second_body"])))
            )
            in initial_body_pairs
            and float(item["distance_m"]) < ESCAPE_LATCH_DISTANCE_M
            for item in nearby
        )
        if not initial_pair_still_near:
            escaped = True
            minimum_after_escape = min(minimum_after_escape, nearest)
    return True, escaped, minimum_after_escape


def _motion_metrics(q_history):
    values = np.asarray(q_history, dtype=float)
    if len(values) < 2:
        return {
            "max_velocity_deg_s": 0.0,
            "max_acceleration_deg_s2": 0.0,
            "max_jerk_deg_s3": 0.0,
        }
    velocity = np.diff(values, axis=0) / DT_S
    acceleration = (
        np.diff(velocity, axis=0) / DT_S
        if len(velocity) > 1
        else np.zeros((0, values.shape[1]))
    )
    jerk = (
        np.diff(acceleration, axis=0) / DT_S
        if len(acceleration) > 1
        else np.zeros((0, values.shape[1]))
    )

    def maximum(array):
        return 0.0 if array.size == 0 else float(np.max(np.abs(np.degrees(array))))

    return {
        "max_velocity_deg_s": maximum(velocity),
        "max_acceleration_deg_s2": maximum(acceleration),
        "max_jerk_deg_s3": maximum(jerk),
    }


def _simplify_recovery_path(
    model, data, controller, geom_pairs, q_history, initial_body_pairs
):
    path = [np.asarray(item, dtype=float) for item in q_history]
    if len(path) <= 2:
        return path

    # Preserve the first accepted escape step. The measured pose starts at
    # zero mesh clearance, so this establishes a positive recovery floor before
    # any long shortcut is considered.
    simplified = [path[0], path[1]]
    source_index = 1
    while source_index < len(path) - 1:
        collision_diag._joint_pose(
            model, data, controller, path[source_index]
        )
        nearby = collision_diag._nearby_pairs(
            model, data, controller, geom_pairs
        )
        initial_pair_still_near = any(
            tuple(
                sorted((str(item["first_body"]), str(item["second_body"])))
            )
            in initial_body_pairs
            and float(item["distance_m"]) < ESCAPE_LATCH_DISTANCE_M
            for item in nearby
        )
        clearance = math.inf if not nearby else float(nearby[0]["distance_m"])
        escaped = not initial_pair_still_near
        def edge_valid(candidate_index):
            valid, _, _ = _recovery_edge_is_valid(
                model,
                data,
                controller,
                geom_pairs,
                path[source_index],
                path[candidate_index],
                escaped,
                initial_body_pairs,
            )
            return valid

        last_valid = source_index
        first_invalid = None
        stride = min(64, len(path) - 1 - source_index)
        while stride > 0:
            candidate_index = min(len(path) - 1, source_index + stride)
            if edge_valid(candidate_index):
                last_valid = candidate_index
                if candidate_index == len(path) - 1:
                    break
                stride = min(
                    stride * 2,
                    len(path) - 1 - source_index,
                )
                continue
            first_invalid = candidate_index
            break

        if last_valid == source_index:
            low = source_index + 1
            high = (first_invalid or source_index + 1) - 1
            if high < low:
                high = low
        elif first_invalid is not None:
            low = last_valid + 1
            high = first_invalid - 1
        else:
            low = last_valid
            high = last_valid

        while low <= high:
            middle = (low + high) // 2
            if edge_valid(middle):
                last_valid = middle
                low = middle + 1
            else:
                high = middle - 1

        accepted_index = max(source_index + 1, last_valid)
        if not edge_valid(accepted_index):
            collision_diag._joint_pose(
                model, data, controller, path[accepted_index]
            )
            candidate_clearance = _minimum_clearance(
                model, data, controller, geom_pairs
            )
            raise RuntimeError(
                "Original QP recovery edge failed during simplification: "
                f"source={source_index} candidate={accepted_index} "
                f"escaped={escaped} before={clearance:.9f} "
                f"candidate_clearance={candidate_clearance:.9f}"
            )
        simplified.append(path[accepted_index])
        source_index = accepted_index
    return simplified


def _minimum_jerk_profile(waypoints):
    samples = [np.asarray(waypoints[0], dtype=float).copy()]
    segment_metadata = []
    for segment_index, (first, second) in enumerate(
        zip(waypoints, waypoints[1:])
    ):
        first = np.asarray(first, dtype=float)
        second = np.asarray(second, dtype=float)
        maximum_delta = float(np.max(np.abs(second - first)))
        duration = max(
            1.875 * maximum_delta / MAX_JOINT_VELOCITY_RAD_S,
            math.sqrt(
                5.7735026919
                * maximum_delta
                / MAX_JOINT_ACCELERATION_RAD_S2
            ),
            (
                60.0 * maximum_delta / MAX_JOINT_JERK_RAD_S3
            )
            ** (1.0 / 3.0),
            DT_S,
        )
        intervals = max(1, int(math.ceil(duration * CONTROL_HZ)))
        duration = intervals * DT_S
        for local_index in range(1, intervals + 1):
            u = local_index / intervals
            blend = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
            samples.append(first + blend * (second - first))
        segment_metadata.append(
            {
                "segment": segment_index,
                "duration_s": duration,
                "maximum_joint_delta_deg": math.degrees(maximum_delta),
            }
        )
    return samples, segment_metadata


def _minimum_jerk_path_profile(path, duration_scale=1.0):
    poses = [np.asarray(item, dtype=float) for item in path]
    filtered = [poses[0]]
    cumulative = [0.0]
    for pose in poses[1:]:
        distance = float(np.max(np.abs(pose - filtered[-1])))
        if distance <= 1e-12:
            continue
        filtered.append(pose)
        cumulative.append(cumulative[-1] + distance)
    total_distance = cumulative[-1]
    if total_distance <= 1e-12:
        return [filtered[0]], 0.0

    duration = max(
        1.875 * total_distance / MAX_JOINT_VELOCITY_RAD_S,
        math.sqrt(
            5.7735026919
            * total_distance
            / MAX_JOINT_ACCELERATION_RAD_S2
        ),
        (60.0 * total_distance / MAX_JOINT_JERK_RAD_S3) ** (1.0 / 3.0),
        DT_S,
    ) * duration_scale
    intervals = max(1, int(math.ceil(duration * CONTROL_HZ)))
    duration = intervals * DT_S
    cumulative_array = np.asarray(cumulative, dtype=float)
    samples = []
    for sample_index in range(intervals + 1):
        u = sample_index / intervals
        blend = 10.0 * u**3 - 15.0 * u**4 + 6.0 * u**5
        path_distance = blend * total_distance
        segment = int(
            np.clip(
                np.searchsorted(cumulative_array, path_distance, side="right") - 1,
                0,
                len(filtered) - 2,
            )
        )
        segment_length = cumulative[segment + 1] - cumulative[segment]
        fraction = (
            0.0
            if segment_length <= 1e-12
            else (path_distance - cumulative[segment]) / segment_length
        )
        samples.append(
            filtered[segment]
            + float(np.clip(fraction, 0.0, 1.0))
            * (filtered[segment + 1] - filtered[segment])
        )
    samples[-1] = filtered[-1].copy()
    return samples, duration


def _validate_profile(
    model, data, controller, geom_pairs, samples, initial_body_pairs
):
    collision_diag._joint_pose(model, data, controller, samples[0])
    nearby = collision_diag._nearby_pairs(model, data, controller, geom_pairs)
    inside, _ = startup_plan._inside_pairs(
        nearby, controller.COLLISION_MIN_DISTANCE_M
    )
    escaped = not inside
    minimum_after_escape = math.inf
    for sample_index in range(1, len(samples)):
        collision_diag._joint_pose(
            model, data, controller, samples[sample_index - 1]
        )
        clearance_before = _minimum_clearance(
            model, data, controller, geom_pairs
        )
        valid, escaped, edge_clearance = _recovery_edge_is_valid(
            model,
            data,
            controller,
            geom_pairs,
            samples[sample_index - 1],
            samples[sample_index],
            escaped,
            initial_body_pairs,
        )
        if not valid:
            collision_diag._joint_pose(
                model, data, controller, samples[sample_index]
            )
            rejected_nearby = collision_diag._nearby_pairs(
                model, data, controller, geom_pairs
            )
            return {
                "passed": False,
                "failed_sample": sample_index,
                "escaped_initial_contact": escaped,
                "clearance_before_m": clearance_before,
                "candidate_minimum_clearance_m": (
                    None
                    if not rejected_nearby
                    else float(rejected_nearby[0]["distance_m"])
                ),
                "candidate_nearest_pair": (
                    None if not rejected_nearby else rejected_nearby[0]
                ),
            }
        if escaped:
            minimum_after_escape = min(minimum_after_escape, edge_clearance)
    return {
        "passed": escaped,
        "failed_sample": None,
        "escaped_initial_contact": escaped,
        "minimum_clearance_after_escape_m": (
            None if math.isinf(minimum_after_escape) else minimum_after_escape
        ),
    }


def _write_result(payload):
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(RESULT_PATH)


def main() -> int:
    os.environ.pop("G1_USE_HARDWARE_INITIAL_STATE", None)
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller

    measured = np.asarray(
        json.loads(STATE_PATH.read_text(encoding="utf-8"))["right_arm_q_rad"],
        dtype=float,
    )
    ready = np.radians(STARTUP_SAFE_READY_DEGREES)

    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    initial_q = controller._initial_configuration(model)
    right_qpos_ids = _right_qpos_ids(model, controller)
    initial_q[right_qpos_ids] = measured
    configuration.update(initial_q)
    data = configuration.data

    right_dofs = controller._right_arm_dof_indices(model)
    frozen_dofs = controller._frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_pairs = controller._build_collision_pairs(model)
    initial_nearby = collision_diag._nearby_pairs(
        model, data, controller, collision_geom_pairs
    )
    initial_inside, initial_body_pairs = startup_plan._inside_pairs(
        initial_nearby, controller.COLLISION_MIN_DISTANCE_M
    )
    initial_recovery_body_pairs = {
        tuple(
            sorted((str(item["first_body"]), str(item["second_body"])))
        )
        for item in initial_nearby
    }
    initial_minimum = (
        math.inf if not initial_nearby else float(initial_nearby[0]["distance_m"])
    )

    target_q = configuration.q.copy()
    target_q[right_qpos_ids] = ready
    posture_task = mink.PostureTask(model, cost=POSTURE_COST)
    posture_task.set_target(target_q)
    damping_task = mink.DampingTask(model, cost=DAMPING_COST)
    wrist_pose = configuration.get_transform_frame_to_world(
        "right_wrist_yaw_link", "body"
    )
    escape_task = mink.FrameTask(
        frame_name="right_wrist_yaw_link",
        frame_type="body",
        position_cost=5.0,
        orientation_cost=0.0,
        gain=0.35,
        lm_damping=1e-3,
    )
    escape_task.set_target(
        mink.SE3.from_rotation_and_translation(
            wrist_pose.rotation(),
            wrist_pose.translation() + ESCAPE_OFFSET_ROBOT_M,
        )
    )
    escape_target_position = wrist_pose.translation() + ESCAPE_OFFSET_ROBOT_M
    velocity_limits = {
        name: QP_MAX_JOINT_VELOCITY_RAD_S
        for name in controller.g1.RIGHT_ARM_JOINTS
    }
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
        mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=(
                STARTUP_QP_MINIMUM_COLLISION_DISTANCE_M
            ),
            collision_detection_distance=STARTUP_COLLISION_DETECTION_DISTANCE_M,
            gain=controller.COLLISION_GAIN,
            broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)]
    solver = controller._select_solver()

    q_history = [measured.copy()]
    trace = []
    escaped = not initial_inside
    escape_target_reached = False
    escape_complete = False
    ready_braking = False
    ready_fine_mode = False
    minimum_after_escape = math.inf
    failure = None
    failure_details = None
    reached = False
    clipped_steps = 0
    minimum_accepted_scale = 1.0
    applied_velocity = np.zeros(model.nv, dtype=float)
    applied_acceleration = np.zeros(model.nv, dtype=float)
    maximum_steps = int(round(MAX_DURATION_S * CONTROL_HZ))

    for step in range(maximum_steps):
        before_full = configuration.q.copy()
        before = before_full[right_qpos_ids].copy()
        if (escape_target_reached and not escape_complete) or ready_braking:
            velocity = np.zeros(model.nv, dtype=float)
        else:
            try:
                active_tasks = (
                    [posture_task, damping_task]
                    if escape_complete
                    else [escape_task, damping_task]
                )
                velocity = mink.solve_ik(
                    configuration,
                    active_tasks,
                    DT_S,
                    solver,
                    damping=1e-6,
                    safety_break=False,
                    limits=limits,
                    constraints=constraints,
                )
                if ready_fine_mode:
                    velocity = np.clip(
                        velocity,
                        -FINE_QP_MAX_JOINT_VELOCITY_RAD_S,
                        FINE_QP_MAX_JOINT_VELOCITY_RAD_S,
                    )
            except Exception as exc:
                failure = f"qp_solver:{type(exc).__name__}:{exc}"
                break

        desired_acceleration = np.clip(
            (velocity - applied_velocity) / DT_S,
            -MAX_JOINT_ACCELERATION_RAD_S2,
            MAX_JOINT_ACCELERATION_RAD_S2,
        )
        acceleration_delta = np.clip(
            desired_acceleration - applied_acceleration,
            -MAX_JOINT_JERK_RAD_S3 * DT_S,
            MAX_JOINT_JERK_RAD_S3 * DT_S,
        )
        candidate_acceleration = np.clip(
            applied_acceleration + acceleration_delta,
            -MAX_JOINT_ACCELERATION_RAD_S2,
            MAX_JOINT_ACCELERATION_RAD_S2,
        )
        candidate_velocity = np.clip(
            applied_velocity + candidate_acceleration * DT_S,
            -MAX_JOINT_VELOCITY_RAD_S,
            MAX_JOINT_VELOCITY_RAD_S,
        )
        clearance_before = _minimum_clearance(
            model, data, controller, collision_geom_pairs
        )
        candidate_full = before_full.copy()
        mujoco.mj_integratePos(
            model, candidate_full, candidate_velocity, DT_S
        )
        candidate = candidate_full[right_qpos_ids].copy()
        configuration.update(before_full)
        valid, edge_escaped, edge_clearance = _recovery_edge_is_valid(
            model,
            data,
            controller,
            collision_geom_pairs,
            before,
            candidate,
            escaped,
            initial_recovery_body_pairs,
        )
        if not valid:
            failure = f"swept_path_rejected_at_step:{step}"
            rejected_samples = []
            for sample_index, sample_pose in enumerate(
                startup_plan._dense_segment(
                    before,
                    candidate,
                    step_deg=RECOVERY_VALIDATION_STEP_DEG,
                )
            ):
                collision_diag._joint_pose(
                    model, data, controller, sample_pose
                )
                sample_nearby = collision_diag._nearby_pairs(
                    model, data, controller, collision_geom_pairs
                )
                rejected_samples.append(
                    {
                        "sample": sample_index,
                        "minimum_clearance_m": (
                            None
                            if not sample_nearby
                            else float(sample_nearby[0]["distance_m"])
                        ),
                        "nearest_pair": (
                            None if not sample_nearby else sample_nearby[0]
                        ),
                    }
                )
            collision_diag._joint_pose(model, data, controller, candidate)
            rejected_nearby = collision_diag._nearby_pairs(
                model, data, controller, collision_geom_pairs
            )
            failure_details = {
                "clearance_before_m": clearance_before,
                "candidate_minimum_clearance_m": (
                    None
                    if not rejected_nearby
                    else float(rejected_nearby[0]["distance_m"])
                ),
                "candidate_nearest_pairs": rejected_nearby[:5],
                "swept_samples": rejected_samples,
                "before_q_rad": before.tolist(),
                "candidate_q_rad": candidate.tolist(),
            }
            configuration.update(before_full)
            break

        configuration.update(candidate_full)
        applied_velocity = candidate_velocity
        applied_acceleration = candidate_acceleration
        escaped = edge_escaped
        if escaped:
            minimum_after_escape = min(minimum_after_escape, edge_clearance)
        current = configuration.q[right_qpos_ids].copy()
        q_history.append(current)
        wrist_position = data.xpos[
            controller.g1.get_body_id(model, "right_wrist_yaw_link")
        ].copy()
        escape_position_error = float(
            np.linalg.norm(wrist_position - escape_target_position)
        )
        if escaped and escape_position_error <= ESCAPE_TARGET_TOLERANCE_M:
            escape_target_reached = True
        if (
            escape_target_reached
            and float(np.max(np.abs(applied_velocity[right_dofs])))
            <= math.radians(0.1)
            and float(np.max(np.abs(applied_acceleration[right_dofs])))
            <= math.radians(1.0)
        ):
            escape_complete = True
        ready_error = float(np.max(np.abs(ready - current)))
        if escape_complete and not ready_braking:
            if not ready_fine_mode and ready_error <= math.radians(2.0):
                ready_braking = True
            elif ready_fine_mode and ready_error <= math.radians(0.3):
                ready_braking = True
        motion_stopped = bool(
            float(np.max(np.abs(applied_velocity[right_dofs])))
            <= math.radians(0.1)
            and float(np.max(np.abs(applied_acceleration[right_dofs])))
            <= math.radians(1.0)
        )
        if ready_braking and motion_stopped:
            if ready_error <= READY_TOLERANCE_RAD:
                reached = True
            else:
                ready_fine_mode = True
                ready_braking = False

        if step % TRACE_DECIMATION == 0:
            trace.append(
                {
                    "time_s": (step + 1) * DT_S,
                    "q_rad": current.tolist(),
                    "maximum_ready_error_deg": float(
                        np.max(np.abs(np.degrees(ready - current)))
                    ),
                    "minimum_clearance_m": _minimum_clearance(
                        model, data, controller, collision_geom_pairs
                    ),
                    "escaped_initial_contact": escaped,
                    "escape_complete": escape_complete,
                    "escape_target_reached": escape_target_reached,
                    "ready_braking": ready_braking,
                    "ready_fine_mode": ready_fine_mode,
                    "escape_position_error_m": escape_position_error,
                    "phase": (
                        (
                            "ready_brake_hold"
                            if ready_braking
                            else (
                                "ready_fine_positioning"
                                if ready_fine_mode
                                else "transition_to_ready"
                            )
                        )
                        if escape_complete
                        else (
                            "escape_brake_hold"
                            if escape_target_reached
                            else "escape_body"
                        )
                    ),
                }
            )

        if reached:
            break

    final_q = q_history[-1]
    final_error = float(np.max(np.abs(ready - final_q)))
    final_clearance = _minimum_clearance(
        model, data, controller, collision_geom_pairs
    )
    final_clearance_extended = _minimum_clearance_extended(
        model, data, collision_geom_pairs
    )

    if reached and failure is None:
        profile_waypoints = q_history
        profile_samples = [np.asarray(item, dtype=float) for item in q_history]
        profile_duration = (len(profile_samples) - 1) * DT_S
        profile_validation = _validate_profile(
            model,
            data,
            controller,
            collision_geom_pairs,
            profile_samples,
                initial_recovery_body_pairs,
        )
        profile_segments = [
            {
                "segment": 0,
                "duration_s": profile_duration,
                "raw_path_points": len(profile_waypoints),
                "duration_scale": 1.0,
            }
        ]
    else:
        profile_waypoints = [q_history[0], q_history[-1]]
        profile_samples = [np.asarray(item, dtype=float) for item in q_history]
        profile_segments = []
        profile_validation = {
            "passed": False,
            "failed_sample": None,
            "escaped_initial_contact": escaped,
            "reason": "raw_qp_recovery_failed",
        }
    profile_metrics = _motion_metrics(profile_samples)
    profile_limits_passed = bool(
        profile_metrics["max_velocity_deg_s"] <= 8.0 * 1.001
        and profile_metrics["max_acceleration_deg_s2"] <= 30.0 * 1.001
        and profile_metrics["max_jerk_deg_s3"] <= 300.0 * 1.001
    )

    safety_config = SafetyConfig()
    previous_command = None
    measured_for_gate = tuple(float(value) for value in profile_samples[0])
    gate_failure = None
    gate_rate_limited = 0
    for index, requested_values in enumerate(profile_samples):
        requested = tuple(float(value) for value in requested_values)
        decision = evaluate_target(
            measured_q_rad=measured_for_gate,
            requested_q_rad=requested,
            previous_command_q_rad=previous_command,
            lowstate_age_s=0.0,
            dt_s=DT_S,
            config=safety_config,
        )
        if not decision.allowed or decision.command_q_rad is None:
            gate_failure = {"sample": index, "reason": decision.reason}
            break
        gate_rate_limited += int(decision.rate_limited)
        previous_command = decision.command_q_rad
        measured_for_gate = decision.command_q_rad

    stale = evaluate_target(
        measured_q_rad=measured_for_gate,
        requested_q_rad=measured_for_gate,
        previous_command_q_rad=previous_command,
        lowstate_age_s=safety_config.lowstate_timeout_s + 0.001,
        dt_s=DT_S,
        config=safety_config,
    )
    stale_blocked = not stale.allowed and stale.command_q_rad is None
    passed = bool(
        reached
        and failure is None
        and profile_validation["passed"]
        and profile_limits_passed
        and gate_failure is None
        and stale_blocked
    )
    result = {
        "passed": passed,
        "hardware_ready": False,
        "command_output_enabled": False,
        "mode": "offline_mink_qp_startup_recovery",
        "solver": solver,
        "control_hz": CONTROL_HZ,
        "recovery_validation_step_deg": RECOVERY_VALIDATION_STEP_DEG,
        "maximum_joint_velocity_deg_s": math.degrees(MAX_JOINT_VELOCITY_RAD_S),
        "qp_maximum_joint_velocity_deg_s": math.degrees(
            QP_MAX_JOINT_VELOCITY_RAD_S
        ),
        "fine_qp_maximum_joint_velocity_deg_s": math.degrees(
            FINE_QP_MAX_JOINT_VELOCITY_RAD_S
        ),
        "maximum_joint_acceleration_deg_s2": math.degrees(
            MAX_JOINT_ACCELERATION_RAD_S2
        ),
        "maximum_joint_jerk_deg_s3": math.degrees(MAX_JOINT_JERK_RAD_S3),
        "escape_offset_robot_m": ESCAPE_OFFSET_ROBOT_M.tolist(),
        "elapsed_s": (len(q_history) - 1) * DT_S,
        "steps": len(q_history) - 1,
        "swept_path_clipped_steps": clipped_steps,
        "minimum_accepted_step_scale": minimum_accepted_scale,
        "reached_ready_pose": reached,
        "escaped_initial_contact": escaped,
        "escape_complete": escape_complete,
        "escape_target_reached": escape_target_reached,
        "ready_braking": ready_braking,
        "ready_fine_mode": ready_fine_mode,
        "escape_target_tolerance_m": ESCAPE_TARGET_TOLERANCE_M,
        "escape_latch_distance_m": ESCAPE_LATCH_DISTANCE_M,
        "startup_collision_detection_distance_m": (
            STARTUP_COLLISION_DETECTION_DISTANCE_M
        ),
        "startup_qp_minimum_collision_distance_m": (
            STARTUP_QP_MINIMUM_COLLISION_DISTANCE_M
        ),
        "initial_inside_count": len(initial_inside),
        "initial_recovery_body_pairs": [
            list(pair) for pair in sorted(initial_recovery_body_pairs)
        ],
        "initial_minimum_clearance_m": initial_minimum,
        "minimum_clearance_after_escape_m": (
            None if math.isinf(minimum_after_escape) else minimum_after_escape
        ),
        "final_clearance_m": final_clearance,
        "final_clearance_extended_m": final_clearance_extended,
        "final_maximum_ready_error_deg": math.degrees(final_error),
        "failure": failure,
        "failure_details": failure_details,
        "safety_gate": {
            "failure": gate_failure,
            "rate_limited_samples": gate_rate_limited,
            "stale_lowstate_blocked": stale_blocked,
        },
        "raw_qp_motion_metrics": _motion_metrics(q_history),
        "motion_profile": {
            "type": "online_velocity_acceleration_jerk_limited_qp",
            "limits_passed": profile_limits_passed,
            "waypoint_count": len(profile_waypoints),
            "sample_count": len(profile_samples),
            "duration_s": (len(profile_samples) - 1) * DT_S,
            "metrics": profile_metrics,
            "collision_validation": profile_validation,
            "segments": profile_segments,
            "samples_decimated": [
                {
                    "time_s": index * DT_S,
                    "q_rad": np.asarray(values, dtype=float).tolist(),
                }
                for index, values in enumerate(profile_samples)
                if index % TRACE_DECIMATION == 0
                or index == len(profile_samples) - 1
            ],
        },
        "initial_q_rad": measured.tolist(),
        "ready_q_rad": ready.tolist(),
        "startup_safe_ready_deg": STARTUP_SAFE_READY_DEGREES.tolist(),
        "final_q_rad": final_q.tolist(),
        "trace_decimation": TRACE_DECIMATION,
        "trace": trace,
    }
    _write_result(result)

    print("G1 Mink startup recovery -- OFFLINE DRY RUN")
    print(f"Solver: {solver}")
    print(f"Elapsed: {result['elapsed_s']:.3f} s ({result['steps']} steps)")
    print(f"Escaped initial contact: {escaped}")
    print(f"Ready error: {math.degrees(final_error):.3f} deg")
    print(
        f"Final clearance: {final_clearance_extended * 1000.0:.3f} mm "
        "(200 mm diagnostic range)"
    )
    print(
        "Motion profile: "
        f"{len(profile_waypoints)} waypoints, "
        f"{(len(profile_samples) - 1) * DT_S:.3f} s"
    )
    print(
        "Profile maxima: "
        f"v={profile_metrics['max_velocity_deg_s']:.3f} deg/s, "
        f"a={profile_metrics['max_acceleration_deg_s2']:.3f} deg/s^2, "
        f"j={profile_metrics['max_jerk_deg_s3']:.3f} deg/s^3"
    )
    print(f"Profile swept-path validation: {profile_validation['passed']}")
    print(f"Failure: {failure or gate_failure or 'none'}")
    print("Motion limits pass offline but are NOT hardware-approved.")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    print("[PASS]" if passed else "[FAIL]")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
