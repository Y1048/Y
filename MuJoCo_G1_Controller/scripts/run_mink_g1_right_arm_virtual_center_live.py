"""Live experimental G1 right-arm Mink controller using a virtual wrist center.

Internal IK roles:
- translation: right_wrist_roll_link (upstream virtual wrist center),
- orientation: right_wrist_yaw_link,
- proximal orientation assistance: 0% normally, hysteretic near wrist limits.

External Unity/state contract remains right_wrist_yaw_link. This is deliberate:
Unity keeps receiving the same wrist_position / target_position semantics while
internal translation no longer forces shoulder/elbow compensation during wrist
pitch rotation.

No speed-based mode switching and no hard freeze are used. Collision avoidance
remains enabled; real hand/body collision may legitimately move the proximal arm.
"""

from __future__ import annotations

import math
import socket
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base
from g1_teleop.inspection_demo import (
    InspectionDemoTracker,
    append_inspection_result,
)


MAX_JOINT_VELOCITY_DEG_S = 42.0
VIRTUAL_CENTER_PROXIMAL_DAMPING_COST = 0.03
VIRTUAL_CENTER_WRIST_DAMPING_COST = 0.015

ASSIST_ENTER_MARGIN_DEG = 18.0
ASSIST_RELEASE_MARGIN_DEG = 28.0
ASSIST_FULL_MARGIN_DEG = 5.0
ASSIST_LATCH_FLOOR = 0.08
ASSIST_MAX = 1.0
ORIENTATION_COST_MIN_SCALE = 0.25
ORIENTATION_ERROR_NORMAL_MAX_DEG = 180.0
ORIENTATION_ERROR_LIMIT_MAX_DEG = 12.0

INSPECTION_APPROACH_RADIUS_M = 0.08
INSPECTION_CONTACT_RADIUS_M = 0.04
INSPECTION_HOLD_SECONDS = 0.75
INSPECTION_RESULTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "logs"
    / "inspection"
    / "inspection_runs.csv"
)
INSPECTION_MARKER_COLORS = {
    "waiting": (0.05, 0.65, 1.0, 0.75),
    "approach": (1.0, 0.82, 0.05, 0.90),
    "holding": (1.0, 0.35, 0.05, 0.95),
    "complete": (0.10, 1.0, 0.25, 1.0),
}


def virtual_center_damping_costs(model: mujoco.MjModel) -> np.ndarray:
    """Build controller-local damping without mutating the baseline module."""
    costs = np.zeros(int(model.nv), dtype=float)
    for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
        joint_id = base._joint_id(model, name)
        dof = int(model.jnt_dofadr[joint_id])
        costs[dof] = (
            VIRTUAL_CENTER_PROXIMAL_DAMPING_COST
            if index < 4
            else VIRTUAL_CENTER_WRIST_DAMPING_COST
        )
    return costs


def orientation_limit_policy(
    min_margin_deg: float,
    assist_latched: bool,
) -> tuple[bool, float, float, float]:
    """Return latch, proximal gain, orientation cost scale, and error cap."""
    if assist_latched:
        assist_latched = min_margin_deg < ASSIST_RELEASE_MARGIN_DEG
    elif min_margin_deg <= ASSIST_ENTER_MARGIN_DEG:
        assist_latched = True

    if not assist_latched:
        return False, 0.0, 1.0, ORIENTATION_ERROR_NORMAL_MAX_DEG

    span = ASSIST_ENTER_MARGIN_DEG - ASSIST_FULL_MARGIN_DEG
    normalized = np.clip(
        (ASSIST_ENTER_MARGIN_DEG - min_margin_deg) / span,
        0.0,
        1.0,
    )
    pressure = float(normalized * normalized * (3.0 - 2.0 * normalized))
    assist_gain = ASSIST_LATCH_FLOOR + pressure * (
        ASSIST_MAX - ASSIST_LATCH_FLOOR
    )
    orientation_cost_scale = 1.0 - pressure * (
        1.0 - ORIENTATION_COST_MIN_SCALE
    )
    orientation_error_max_deg = ORIENTATION_ERROR_NORMAL_MAX_DEG - pressure * (
        ORIENTATION_ERROR_NORMAL_MAX_DEG - ORIENTATION_ERROR_LIMIT_MAX_DEG
    )
    return (
        True,
        float(assist_gain),
        float(orientation_cost_scale),
        float(orientation_error_max_deg),
    )


class VirtualCenterOrientationTask(Task):
    """Yaw-link orientation task with wrist-limit hysteretic proximal assistance."""

    last_assist_gain = 0.0
    last_min_wrist_margin_deg = float("inf")
    last_orientation_cost_scale = 1.0
    last_orientation_error_cap_deg = ORIENTATION_ERROR_NORMAL_MAX_DEG
    last_unclipped_orientation_error_deg = 0.0
    assist_latched = False

    def __init__(self, model) -> None:
        self.inner = mink.FrameTask(
            frame_name="right_wrist_yaw_link",
            frame_type="body",
            position_cost=0.0,
            orientation_cost=1.0,
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )
        self.model = model
        self.proximal_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS[:4]
        ]
        self.wrist_joint_ids = [
            base._joint_id(model, name)
            for name in base.g1.RIGHT_ARM_JOINTS[4:]
        ]
        super().__init__(
            cost=np.array(
                [
                    0.0,
                    0.0,
                    0.0,
                    base.ORIENTATION_COST,
                    base.ORIENTATION_COST,
                    base.ORIENTATION_COST,
                ],
                dtype=float,
            ),
            gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )

    def set_target(self, target) -> None:
        self.inner.set_target(target)

    def set_target_from_configuration(self, configuration) -> None:
        self.inner.set_target_from_configuration(configuration)

    def compute_error(self, configuration) -> np.ndarray:
        error = self.inner.compute_error(configuration)
        rotation_error = error[3:6]
        rotation_norm = float(np.linalg.norm(rotation_error))
        VirtualCenterOrientationTask.last_unclipped_orientation_error_deg = (
            math.degrees(rotation_norm)
        )
        maximum = math.radians(
            VirtualCenterOrientationTask.last_orientation_error_cap_deg
        )
        if rotation_norm > maximum and rotation_norm > 1e-9:
            error = error.copy()
            error[3:6] *= maximum / rotation_norm
        return error

    def _update_limit_policy(self, configuration) -> None:
        model = configuration.model
        q = configuration.q
        margins: list[float] = []

        for joint_id in self.wrist_joint_ids:
            if not bool(model.jnt_limited[joint_id]):
                continue
            qpos = int(model.jnt_qposadr[joint_id])
            low, high = model.jnt_range[joint_id]
            value = float(q[qpos])
            margin = max(0.0, min(value - float(low), float(high) - value))
            margins.append(math.degrees(margin))

        min_margin = min(margins) if margins else float("inf")
        VirtualCenterOrientationTask.last_min_wrist_margin_deg = min_margin

        latched, assist, cost_scale, error_cap_deg = orientation_limit_policy(
            min_margin,
            VirtualCenterOrientationTask.assist_latched,
        )
        VirtualCenterOrientationTask.assist_latched = latched
        VirtualCenterOrientationTask.last_assist_gain = assist
        VirtualCenterOrientationTask.last_orientation_cost_scale = cost_scale
        VirtualCenterOrientationTask.last_orientation_error_cap_deg = error_cap_deg
        self.cost[3:6] = base.ORIENTATION_COST * cost_scale

    def compute_qp_objective(self, configuration):
        self._update_limit_policy(configuration)
        return super().compute_qp_objective(configuration)

    def compute_qp_residual(self, configuration):
        # Mink 0.0.13+ assembles low-rank tasks through this optimized path.
        # Keep the adaptive policy active for both old and new solver versions.
        self._update_limit_policy(configuration)
        return super().compute_qp_residual(configuration)

    def compute_jacobian(self, configuration) -> np.ndarray:
        jacobian = self.inner.compute_jacobian(configuration).copy()
        jacobian[3:6, self.proximal_dofs] *= (
            VirtualCenterOrientationTask.last_assist_gain
        )
        return jacobian


def main() -> None:
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    configuration.update(base._initial_configuration(model))
    data = configuration.data
    collision_validation_data = mujoco.MjData(model)

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos_ids = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.RIGHT_ARM_JOINTS
    ]
    frozen_dofs = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_ids = base._build_collision_pairs(model)

    position_task = mink.FrameTask(
        frame_name="right_wrist_roll_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=0.0,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    position_task.set_target_from_configuration(configuration)

    orientation_task = VirtualCenterOrientationTask(model)
    orientation_task.set_target_from_configuration(configuration)

    posture_task = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(
        model,
        cost=virtual_center_damping_costs(model),
    )

    velocity_limits = {
        name: math.radians(MAX_JOINT_VELOCITY_DEG_S)
        for name in base.g1.RIGHT_ARM_JOINTS
    }
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
        mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=base.COLLISION_MIN_DISTANCE_M,
            collision_detection_distance=base.COLLISION_DETECTION_DISTANCE_M,
            gain=base.COLLISION_GAIN,
            broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)]
    solver = base._select_solver()

    target_mocap_id = int(model.body("udp_target").mocapid[0])
    inspection_tool_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "inspection_tool_tip_body"
    )
    inspection_target_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "inspection_demo_target"
    )
    inspection_target_geom_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_GEOM, "inspection_demo_target_marker"
    )
    if min(
        inspection_tool_body_id,
        inspection_target_body_id,
        inspection_target_geom_id,
    ) < 0:
        raise RuntimeError("inspection demo bodies are missing from the generated model")

    inspection_tracker = InspectionDemoTracker(
        approach_radius_m=INSPECTION_APPROACH_RADIUS_M,
        contact_radius_m=INSPECTION_CONTACT_RADIUS_M,
        hold_seconds=INSPECTION_HOLD_SECONDS,
    )
    udp = base._open_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dry_run_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    roll_pose = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw_pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    raw_target = yaw_pose.translation().copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    command_stream = base.MinkCommandStream(
        raw_target,
        raw_rotation,
        input_timeout_s=base.INPUT_TIMEOUT_S,
    )
    clutch_reference = None
    received_total = 0
    rejected_total = 0
    next_status = time.monotonic()
    next_state = time.monotonic()
    cycle_times: list[float] = []
    target_rotation = yaw_pose.rotation().as_matrix().copy()
    operator_target_position = yaw_pose.translation().copy()
    feasible_target_position = yaw_pose.translation().copy()
    input_position_delta = np.zeros(3)
    inspection_snapshot = inspection_tracker.update(
        active=False,
        distance_m=float(
            np.linalg.norm(
                data.xpos[inspection_tool_body_id]
                - data.xpos[inspection_target_body_id]
            )
        ),
        now_s=time.monotonic(),
    )
    inspection_metric_samples = 0
    inspection_position_error_sum = 0.0
    inspection_collision_samples = 0
    inspection_minimum_wrist_margin_deg = float("inf")

    print("============================================================")
    print("G1 Mink LIVE VIRTUAL-CENTER experiment")
    print("Internal position : right_wrist_roll_link")
    print("Internal rotation : right_wrist_yaw_link")
    print("External contract : right_wrist_yaw_link (unchanged)")
    print("Normal proximal orientation assist : 0%")
    print(
        "Near-limit assist : enter <= "
        f"{ASSIST_ENTER_MARGIN_DEG:.0f} deg, release >= {ASSIST_RELEASE_MARGIN_DEG:.0f} deg"
    )
    print("Collision avoidance: ENABLED")
    print("Speed modes : NONE")
    print("Hard freeze : NONE")
    print(f"Joint speed : max {MAX_JOINT_VELOCITY_DEG_S:.0f} deg/s")
    print(
        "Inspection demo : approach "
        f"{INSPECTION_APPROACH_RADIUS_M * 100:.0f} cm, contact "
        f"{INSPECTION_CONTACT_RADIUS_M * 100:.0f} cm, hold "
        f"{INSPECTION_HOLD_SECONDS:.2f} s"
    )
    print("============================================================")

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                cycle_start = time.perf_counter()
                now = time.monotonic()

                command_update = command_stream.poll(udp)
                raw_target = command_update.target_position_m
                raw_rotation = command_update.target_quaternion_xyzw
                received_total += command_update.accepted_count
                rejected_total += command_update.rejected_count
                active = command_update.command_active
                roll_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_roll_link", "body"
                )
                yaw_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                if command_update.reset_clutch:
                    clutch_reference = None

                if command_update.engage_clutch:
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    clutch_reference = {
                        "input_position": raw_target.copy(),
                        "input_rotation": input_rotation.copy(),
                        "center_position": roll_pose.translation().copy(),
                        "yaw_position": yaw_pose.translation().copy(),
                        "yaw_rotation": yaw_pose.rotation().as_matrix().copy(),
                    }
                    target_rotation = clutch_reference["yaw_rotation"].copy()
                    posture_task.set_target(configuration.q.copy())
                    VirtualCenterOrientationTask.assist_latched = False
                    operator_target_position = yaw_pose.translation().copy()
                    feasible_target_position = yaw_pose.translation().copy()
                    inspection_tracker.reset()
                    inspection_metric_samples = 0
                    inspection_position_error_sum = 0.0
                    inspection_collision_samples = 0
                    inspection_minimum_wrist_margin_deg = float("inf")
                    print("\nVirtual-center clutch engaged without position/orientation jump.")

                if active and clutch_reference is not None:
                    input_position_delta = (
                        raw_target - clutch_reference["input_position"]
                    )
                    operator_target_position = (
                        clutch_reference["yaw_position"]
                        + input_position_delta
                    )
                    current_center_to_yaw = (
                        yaw_pose.translation() - roll_pose.translation()
                    )
                    desired_center_position = (
                        operator_target_position - current_center_to_yaw
                    )
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
                    desired_target_rotation = rotation_delta @ clutch_reference["yaw_rotation"]
                    target_center_position = desired_center_position
                    target_rotation = desired_target_rotation

                    position_task.set_target(
                        base._matrix_to_se3(
                            roll_pose.rotation().as_matrix(),
                            target_center_position,
                        )
                    )
                    orientation_task.set_target(
                        base._matrix_to_se3(
                            target_rotation,
                            yaw_pose.translation(),
                        )
                    )

#각 Task에서 Jacobian과 error를 받아 weighted least-squares 목적함수 H,c를 만들고
#joint/velocity/collision limit을 inequality GΔq≤h, DOF freeze를 equality AΔq=b로 구성한 뒤
#DAQP로 Δq를 풀고 이를 dt로 나눠 joint velocity를 반환한다.
                    velocity = mink.solve_ik(
                        configuration=configuration,
                        tasks=[position_task, orientation_task, posture_task, damping_task],
                        dt=base.DT,
                        solver=solver,
                        damping=base.QP_DAMPING,
                        limits=limits,
                        constraints=constraints,
                    )
                    configuration.integrate_inplace(velocity, base.DT)
                else:
                    target_center_position = roll_pose.translation().copy()
                    target_rotation = yaw_pose.rotation().as_matrix().copy()
                    operator_target_position = yaw_pose.translation().copy()
                    feasible_target_position = yaw_pose.translation().copy()
                    input_position_delta = np.zeros(3)
                    position_task.set_target_from_configuration(configuration)
                    orientation_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    VirtualCenterOrientationTask.assist_latched = False
                    VirtualCenterOrientationTask.last_assist_gain = 0.0

                # Keep collision geometry, constraints, and derived MuJoCo
                # state synchronized after Mink integrates the kinematic qpos.
                mujoco.mj_forward(model, configuration.data)
                roll_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_roll_link", "body"
                )
                yaw_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                # Keep the external yaw-wrist target identical to the Unity
                # command. The internal roll-center target compensates the
                # current roll-to-yaw offset before Mink solves the joint motion.
                center_error = target_center_position - roll_pose.translation()
                external_target_position = operator_target_position.copy()
                configuration.data.mocap_pos[target_mocap_id] = external_target_position
                current_rotation = yaw_pose.rotation().as_matrix()
                orientation_error_deg = math.degrees(
                    base._rotation_error_radians(target_rotation, current_rotation)
                )
                position_error = float(
                    np.linalg.norm(external_target_position - yaw_pose.translation())
                )

                nearest_collision = base._nearest_pair_distance(
                    model, configuration.data, collision_geom_ids
                )
                min_clearance = (
                    None if nearest_collision is None else nearest_collision[0]
                )
                nearest_collision_geoms = []
                nearest_collision_bodies = []
                if nearest_collision is not None:
                    for geom_id in nearest_collision[1:]:
                        nearest_collision_geoms.append(
                            mujoco.mj_id2name(
                                model, mujoco.mjtObj.mjOBJ_GEOM, geom_id
                            )
                        )
                        body_id = int(model.geom_bodyid[geom_id])
                        nearest_collision_bodies.append(
                            mujoco.mj_id2name(
                                model, mujoco.mjtObj.mjOBJ_BODY, body_id
                            )
                        )
                feasible_target_position = external_target_position.copy()
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance <= base.COLLISION_DETECTION_DISTANCE_M
                )

                inspection_tool_position = data.xpos[
                    inspection_tool_body_id
                ].copy()
                inspection_target_position = data.xpos[
                    inspection_target_body_id
                ].copy()
                inspection_distance = float(
                    np.linalg.norm(
                        inspection_tool_position - inspection_target_position
                    )
                )
                inspection_snapshot = inspection_tracker.update(
                    active=active and clutch_reference is not None,
                    distance_m=inspection_distance,
                    now_s=now,
                )
                model.geom_rgba[inspection_target_geom_id] = np.asarray(
                    INSPECTION_MARKER_COLORS[inspection_snapshot.state.value],
                    dtype=float,
                )

                if active and clutch_reference is not None:
                    inspection_metric_samples += 1
                    inspection_position_error_sum += position_error
                    inspection_collision_samples += int(collision_limited)
                    inspection_minimum_wrist_margin_deg = min(
                        inspection_minimum_wrist_margin_deg,
                        VirtualCenterOrientationTask.last_min_wrist_margin_deg,
                    )

                if inspection_snapshot.just_completed:
                    sample_count = max(1, inspection_metric_samples)
                    append_inspection_result(
                        INSPECTION_RESULTS_PATH,
                        {
                            "completed_at": time.strftime(
                                "%Y-%m-%dT%H:%M:%S"
                            ),
                            "session_id": command_update.session_id or "",
                            "elapsed_s": round(
                                inspection_snapshot.elapsed_s, 4
                            ),
                            "final_distance_m": round(
                                inspection_snapshot.distance_m, 6
                            ),
                            "minimum_distance_m": round(
                                inspection_snapshot.minimum_distance_m, 6
                            ),
                            "mean_ik_position_error_m": round(
                                inspection_position_error_sum / sample_count, 6
                            ),
                            "minimum_wrist_limit_margin_deg": round(
                                inspection_minimum_wrist_margin_deg, 3
                            ),
                            "collision_nearby_ratio": round(
                                inspection_collision_samples / sample_count, 4
                            ),
                        },
                    )
                    print(
                        "\nInspection target COMPLETE in "
                        f"{inspection_snapshot.elapsed_s:.2f} s; "
                        f"tip error {inspection_snapshot.distance_m * 1000:.1f} mm."
                    )

                if now >= next_state:
                    packet = base._state_packet(
                        configuration,
                        right_qpos_ids,
                        active,
                        external_target_position,
                        None if clutch_reference is None else clutch_reference["yaw_position"],
                        collision_limited,
                        workspace_limited=False,
                        control_state=command_update.control_state,
                        session_id=command_update.session_id,
                        input_packet_age_s=command_update.packet_age_s,
                    )
                    packet["right_arm"]["position_error"] = position_error
                    packet["right_arm"]["orientation_error_deg"] = orientation_error_deg
                    packet["right_arm"]["orientation_assist_gain"] = (
                        VirtualCenterOrientationTask.last_assist_gain
                    )
                    packet["right_arm"]["orientation_cost_scale"] = (
                        VirtualCenterOrientationTask.last_orientation_cost_scale
                    )
                    packet["right_arm"]["min_wrist_limit_margin_deg"] = (
                        VirtualCenterOrientationTask.last_min_wrist_margin_deg
                    )
                    packet["right_arm"]["minimum_clearance_m"] = min_clearance
                    packet["right_arm"]["nearest_collision_geoms"] = (
                        nearest_collision_geoms
                    )
                    packet["right_arm"]["nearest_collision_bodies"] = (
                        nearest_collision_bodies
                    )
                    panel_scene = base.g1.SCENES["control"]
                    packet["inspection"] = {
                        "state": inspection_snapshot.state.value,
                        "target_source": "static_demo",
                        "target_position": inspection_target_position.tolist(),
                        "tool_tip_position": inspection_tool_position.tolist(),
                        "panel_position": list(panel_scene["panel_pos"]),
                        "panel_half_size": list(panel_scene["panel_size"]),
                        "distance_m": inspection_snapshot.distance_m,
                        "hold_progress": inspection_snapshot.hold_progress,
                        "elapsed_s": inspection_snapshot.elapsed_s,
                        "minimum_distance_m": (
                            inspection_snapshot.minimum_distance_m
                        ),
                        "complete": (
                            inspection_snapshot.state.value == "complete"
                        ),
                    }
                    _send_state = base._send_state
                    _send_state(
                        state_sock,
                        packet,
                        base.UNITY_STATE_HOST,
                        base.UNITY_STATE_PORT,
                    )
                    _send_state(
                        dry_run_sock,
                        packet,
                        base.SAFETY_DRY_RUN_HOST,
                        base.SAFETY_DRY_RUN_PORT,
                    )
                    next_state = now + base.DT

                cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
                cycle_times.append(cycle_ms)
                if len(cycle_times) > 600:
                    del cycle_times[:-600]

                if now >= next_status:
                    stats = np.asarray(cycle_times, dtype=float)
                    collision_validation_data.qpos[:] = configuration.q
                    mujoco.mj_forward(model, collision_validation_data)
                    validation_nearest_collision = base._nearest_pair_distance(
                        model,
                        collision_validation_data,
                        collision_geom_ids,
                    )
                    validation_min_clearance = (
                        None
                        if validation_nearest_collision is None
                        else validation_nearest_collision[0]
                    )
                    validation_collision_geoms = []
                    validation_collision_bodies = []
                    if validation_nearest_collision is not None:
                        for geom_id in validation_nearest_collision[1:]:
                            validation_collision_geoms.append(
                                mujoco.mj_id2name(
                                    model,
                                    mujoco.mjtObj.mjOBJ_GEOM,
                                    geom_id,
                                )
                            )
                            body_id = int(model.geom_bodyid[geom_id])
                            validation_collision_bodies.append(
                                mujoco.mj_id2name(
                                    model,
                                    mujoco.mjtObj.mjOBJ_BODY,
                                    body_id,
                                )
                            )
                    base._write_status(
                        {
                            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "controller": "mink_right_arm_virtual_center_live",
                            "input_active": active,
                            "input_control_state": command_update.control_state,
                            "input_session_id": command_update.session_id,
                            "input_packet_age_s": command_update.packet_age_s,
                            "clutch_engaged": command_update.clutch_engaged,
                            "workspace_fault": command_update.workspace_fault,
                            "received_packets": received_total,
                            "rejected_packets": rejected_total,
                            "solver": solver,
                            "collision_pair_count": len(collision_pairs),
                            "collision_min_distance_m": base.COLLISION_MIN_DISTANCE_M,
                            "collision_detection_distance_m": base.COLLISION_DETECTION_DISTANCE_M,
                            "minimum_clearance_m": min_clearance,
                            "nearest_collision_geoms": nearest_collision_geoms,
                            "nearest_collision_bodies": nearest_collision_bodies,
                            "validation_minimum_clearance_m": (
                                validation_min_clearance
                            ),
                            "validation_nearest_collision_geoms": (
                                validation_collision_geoms
                            ),
                            "validation_nearest_collision_bodies": (
                                validation_collision_bodies
                            ),
                            "validation_qpos_delta_max": float(
                                np.max(
                                    np.abs(
                                        collision_validation_data.qpos
                                        - configuration.data.qpos
                                    )
                                )
                            ),
                            "collision_limit_nearby": collision_limited,
                            "position_task_frame": "right_wrist_roll_link",
                            "orientation_task_frame": "right_wrist_yaw_link",
                            "external_state_frame": "right_wrist_yaw_link",
                            "target_position": external_target_position.tolist(),
                            "operator_target_position": operator_target_position.tolist(),
                            "feasible_target_position": feasible_target_position.tolist(),
                            "input_position_delta": input_position_delta.tolist(),
                            "external_target_delta": (
                                external_target_position
                                - (
                                    yaw_pose.translation()
                                    if clutch_reference is None
                                    else clutch_reference["yaw_position"]
                                )
                            ).tolist(),
                            "wrist_position": yaw_pose.translation().tolist(),
                            "virtual_center_target_position": target_center_position.tolist(),
                            "virtual_center_position": roll_pose.translation().tolist(),
                            "virtual_center_position_error_m": float(
                                np.linalg.norm(center_error)
                            ),
                            "position_error_m": position_error,
                            "orientation_error_deg": orientation_error_deg,
                            "orientation_mapping": "clutch_relative",
                            "proximal_orientation_assist_gain": (
                                VirtualCenterOrientationTask.last_assist_gain
                            ),
                            "orientation_cost_scale": (
                                VirtualCenterOrientationTask.last_orientation_cost_scale
                            ),
                            "orientation_error_cap_deg": (
                                VirtualCenterOrientationTask.last_orientation_error_cap_deg
                            ),
                            "unclipped_orientation_error_deg": (
                                VirtualCenterOrientationTask.last_unclipped_orientation_error_deg
                            ),
                            "min_wrist_limit_margin_deg": (
                                VirtualCenterOrientationTask.last_min_wrist_margin_deg
                            ),
                            "wrist_limit_assist_latched": (
                                VirtualCenterOrientationTask.assist_latched
                            ),
                            "inspection_state": inspection_snapshot.state.value,
                            "inspection_target_source": "static_demo",
                            "inspection_target_position": (
                                inspection_target_position.tolist()
                            ),
                            "inspection_tool_tip_position": (
                                inspection_tool_position.tolist()
                            ),
                            "inspection_distance_m": inspection_snapshot.distance_m,
                            "inspection_hold_progress": (
                                inspection_snapshot.hold_progress
                            ),
                            "inspection_elapsed_s": inspection_snapshot.elapsed_s,
                            "inspection_complete": (
                                inspection_snapshot.state.value == "complete"
                            ),
                            "speed_based_mode_switch": False,
                            "proximal_hard_freeze": False,
                            "max_joint_velocity_deg_s": MAX_JOINT_VELOCITY_DEG_S,
                            "right_arm_q_deg": np.degrees(
                                configuration.q[right_qpos_ids]
                            ).tolist(),
                            "cycle_last_ms": cycle_ms,
                            "cycle_mean_ms": float(np.mean(stats)),
                            "cycle_p95_ms": float(np.percentile(stats, 95)),
                            "cycle_p99_ms": float(np.percentile(stats, 99)),
                            "cycle_worst_ms": float(np.max(stats)),
                        }
                    )
                    next_status = now + 0.5

                viewer.sync()
                elapsed = time.perf_counter() - cycle_start
                if elapsed < base.DT:
                    time.sleep(base.DT - elapsed)
    finally:
        udp.close()
        state_sock.close()
        dry_run_sock.close()


if __name__ == "__main__":
    main()
