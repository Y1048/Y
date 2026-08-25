"""Experimental Mink G1 right-arm controller with physically decoupled wrist roles.

Position is controlled at right_wrist_roll_link, whose origin is upstream of the
three wrist rotations, so wrist roll/pitch/yaw do not cause artificial position
compensation. Orientation is controlled at right_wrist_yaw_link.

No speed-classification mode and no hard freeze are used. Slow translation stays
fully available. Mink joint/velocity/collision limits remain active.
"""

from __future__ import annotations

import math
import socket
import time

import mujoco
import mujoco.viewer
import numpy as np

import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base


ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S = 50.0
base.RIGHT_ARM_MAX_VELOCITY_RAD_S = math.radians(ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S)
base.PROXIMAL_DAMPING_COST = 0.03
base.WRIST_DAMPING_COST = 0.015

# Keep orientation almost entirely in the wrist. The small proximal contribution
# is retained only as a feasibility escape path near limits/collision.
PROXIMAL_ORIENTATION_ASSIST_GAIN = 0.02


class WristOrientationTask(Task):
    """Yaw-link orientation task with proximal Jacobian columns strongly suppressed."""

    def __init__(self, model, gain: float = 0.35, lm_damping: float = 1e-5) -> None:
        self._task = mink.FrameTask(
            frame_name="right_wrist_yaw_link",
            frame_type="body",
            position_cost=0.0,
            orientation_cost=1.0,
            gain=gain,
            lm_damping=lm_damping,
        )
        self._proximal_dofs = [
            int(model.jnt_dofadr[base._joint_id(model, name)])
            for name in base.g1.RIGHT_ARM_JOINTS[:4]
        ]
        super().__init__(
            cost=np.array([0.0, 0.0, 0.0, base.ORIENTATION_COST, base.ORIENTATION_COST, base.ORIENTATION_COST]),
            gain=gain,
            lm_damping=lm_damping,
        )

    def set_target(self, target) -> None:
        self._task.set_target(target)

    def set_target_from_configuration(self, configuration) -> None:
        self._task.set_target_from_configuration(configuration)

    def compute_error(self, configuration) -> np.ndarray:
        return self._task.compute_error(configuration)

    def compute_jacobian(self, configuration) -> np.ndarray:
        jacobian = self._task.compute_jacobian(configuration).copy()
        jacobian[3:6, self._proximal_dofs] *= PROXIMAL_ORIENTATION_ASSIST_GAIN
        return jacobian


def main() -> None:
    base._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
    base._apply_operational_joint_limits(model)
    configuration = mink.Configuration(model)
    configuration.update(base._initial_configuration(model))
    data = configuration.data

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

    orientation_task = WristOrientationTask(
        model,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    orientation_task.set_target_from_configuration(configuration)

    posture_task = mink.PostureTask(model, cost=base.POSTURE_COST)
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(model, cost=base._damping_costs(model))

    velocity_limits = {
        name: base.RIGHT_ARM_MAX_VELOCITY_RAD_S
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
    udp = base._open_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dry_run_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    roll_pose = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
    yaw_pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    raw_target = yaw_pose.translation().copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    raw_valid = False
    last_packet_time = float("-inf")
    clutch_reference = None
    last_active = False
    received_total = 0
    next_status = time.monotonic()
    next_state = time.monotonic()
    cycle_times: list[float] = []
    target_rotation = yaw_pose.rotation().as_matrix().copy()

    print("============================================================")
    print("G1 Mink ROLE-SPLIT V2")
    print("Position    : right_wrist_roll_link translation")
    print("Orientation : right_wrist_yaw_link rotation")
    print("Proximal orientation assist: 2%")
    print("Speed modes : NONE")
    print("Hard freeze : NONE")
    print(f"Joint speed : max {ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S:.0f} deg/s")
    print("============================================================")

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                cycle_start = time.perf_counter()
                now = time.monotonic()

                raw_target, raw_rotation, raw_valid, received = base._receive_latest(
                    udp, raw_target, raw_rotation, raw_valid
                )
                if received:
                    received_total += received
                    last_packet_time = now

                active = bool(raw_valid and now - last_packet_time < base.INPUT_TIMEOUT_S)
                roll_pose = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
                yaw_pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

                if active and not last_active:
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    clutch_reference = {
                        "input_position": raw_target.copy(),
                        "input_rotation": input_rotation.copy(),
                        "roll_position": roll_pose.translation().copy(),
                        "yaw_rotation": yaw_pose.rotation().as_matrix().copy(),
                    }
                    target_rotation = clutch_reference["yaw_rotation"].copy()
                    posture_task.set_target(configuration.q.copy())
                    print("\nMink V2 clutch engaged without position/orientation jump.")

                if active and clutch_reference is not None:
                    target_roll_position = (
                        clutch_reference["roll_position"]
                        + raw_target
                        - clutch_reference["input_position"]
                    )
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
                    target_rotation = rotation_delta @ clutch_reference["yaw_rotation"]

                    current_roll_rotation = roll_pose.rotation().as_matrix()
                    position_task.set_target(base._matrix_to_se3(current_roll_rotation, target_roll_position))
                    orientation_task.set_target(base._matrix_to_se3(target_rotation, yaw_pose.translation()))

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
                    data = configuration.data
                else:
                    target_roll_position = roll_pose.translation().copy()
                    target_rotation = yaw_pose.rotation().as_matrix().copy()
                    clutch_reference = None
                    position_task.set_target_from_configuration(configuration)
                    orientation_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())

                mujoco.mj_fwdPosition(model, data)
                roll_pose = configuration.get_transform_frame_to_world("right_wrist_roll_link", "body")
                yaw_pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")

                # Viewer target stays on actual yaw-link translation so the green
                # sphere continues to indicate the end-wrist frame visually.
                data.mocap_pos[target_mocap_id] = yaw_pose.translation()

                min_clearance = base._min_pair_distance(model, data, collision_geom_ids)
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance <= base.COLLISION_DETECTION_DISTANCE_M
                )

                if now >= next_state:
                    # Preserve the existing Unity state packet contract. Position
                    # error here is roll-link task error; joints remain authoritative.
                    packet = base._state_packet(
                        configuration,
                        right_qpos_ids,
                        active,
                        yaw_pose.translation(),
                        None,
                        collision_limited,
                    )
                    packet["right_arm"]["position_error"] = float(
                        np.linalg.norm(target_roll_position - roll_pose.translation())
                    )
                    base._send_state(state_sock, packet, base.UNITY_STATE_HOST, base.UNITY_STATE_PORT)
                    base._send_state(dry_run_sock, packet, base.SAFETY_DRY_RUN_HOST, base.SAFETY_DRY_RUN_PORT)
                    next_state = now + base.DT

                cycle_ms = (time.perf_counter() - cycle_start) * 1000.0
                cycle_times.append(cycle_ms)
                if len(cycle_times) > 600:
                    del cycle_times[:-600]

                if now >= next_status:
                    orientation_error_deg = math.degrees(
                        base._rotation_error_radians(
                            target_rotation,
                            yaw_pose.rotation().as_matrix(),
                        )
                    )
                    position_error = float(
                        np.linalg.norm(target_roll_position - roll_pose.translation())
                    )
                    stats = np.asarray(cycle_times, dtype=float)
                    base._write_status({
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "controller": "mink_right_arm_role_split_v2",
                        "input_active": active,
                        "received_packets": received_total,
                        "solver": solver,
                        "collision_pair_count": len(collision_pairs),
                        "minimum_clearance_m": min_clearance,
                        "collision_limit_nearby": collision_limited,
                        "position_task_frame": "right_wrist_roll_link",
                        "orientation_task_frame": "right_wrist_yaw_link",
                        "position_error_m": position_error,
                        "orientation_error_deg": orientation_error_deg,
                        "proximal_orientation_assist_gain": PROXIMAL_ORIENTATION_ASSIST_GAIN,
                        "max_joint_velocity_deg_s": ROLE_SPLIT_MAX_JOINT_VELOCITY_DEG_S,
                        "right_arm_q_deg": np.degrees(configuration.q[right_qpos_ids]).tolist(),
                        "cycle_last_ms": cycle_ms,
                        "cycle_mean_ms": float(np.mean(stats)),
                        "cycle_p95_ms": float(np.percentile(stats, 95)),
                        "cycle_p99_ms": float(np.percentile(stats, 99)),
                        "cycle_worst_ms": float(np.max(stats)),
                    })
                    next_status = now + 0.5

                last_active = active
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
