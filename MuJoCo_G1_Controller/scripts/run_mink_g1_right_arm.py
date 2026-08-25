"""Production Mink right-arm teleoperation controller.

The controller keeps the 7-DoF right arm available for Cartesian translation,
but when the operator input is rotation-dominant it freezes shoulder/elbow DOFs
and lets the three wrist joints realize the rotation. This prevents large arm
reconfiguration when the operator only rotates their wrist.
"""

from __future__ import annotations

import math
import socket
import time

import mujoco
import mujoco.viewer
import numpy as np

import mink

import run_mink_g1_right_arm_prototype as base


ROTATION_ONLY_ENTER_TRANSLATION_SPEED_M_S = 0.025
ROTATION_ONLY_EXIT_TRANSLATION_SPEED_M_S = 0.050
ROTATION_ONLY_MIN_ANGULAR_SPEED_RAD_S = math.radians(2.0)


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
    proximal_dofs = right_dofs[:4]
    collision_pairs, collision_geom_ids = base._build_collision_pairs(model)

    wrist_task = mink.FrameTask(
        frame_name="right_wrist_yaw_link",
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=base.ORIENTATION_COST,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    wrist_task.set_target_from_configuration(configuration)

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

    base_constraints = [
        mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)
    ]
    proximal_freeze = mink.DofFreezingTask(
        model=model,
        dof_indices=proximal_dofs,
    )

    solver = base._select_solver()
    target_mocap_id = int(model.body("udp_target").mocapid[0])
    udp = base._open_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dry_run_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    raw_target = data.xpos[
        base.g1.get_body_id(model, "right_wrist_yaw_link")
    ].copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    raw_valid = False
    last_packet_time = float("-inf")
    clutch_reference = None
    last_active = False
    received_total = 0
    next_status = time.monotonic()
    next_state = time.monotonic()
    cycle_times: list[float] = []

    target_rotation = configuration.get_transform_frame_to_world(
        "right_wrist_yaw_link", "body"
    ).rotation().as_matrix().copy()

    previous_input_position = raw_target.copy()
    previous_input_rotation = base.g1.operator_rotation_to_robot_matrix(
        raw_rotation
    )
    translation_speed_m_s = 0.0
    angular_speed_rad_s = 0.0
    rotation_only_mode = False

    print("Mink G1 right-arm production controller")
    print("---------------------------------------")
    print(f"UDP input: {base.UDP_HOST}:{base.UDP_PORT}")
    print(f"QP solver: {solver}")
    print(f"Frozen non-right-arm DOFs: {len(frozen_dofs)}")
    print("Rotation-only policy: shoulder + elbow HARD-FROZEN")
    print(
        "  enter when translation <= "
        f"{ROTATION_ONLY_ENTER_TRANSLATION_SPEED_M_S*1000:.0f} mm/s "
        "and rotation >= "
        f"{math.degrees(ROTATION_ONLY_MIN_ANGULAR_SPEED_RAD_S):.1f} deg/s"
    )
    print(
        "  release when translation > "
        f"{ROTATION_ONLY_EXIT_TRANSLATION_SPEED_M_S*1000:.0f} mm/s"
    )
    print("Orientation mapping: clutch-relative Quest rotation -> G1 wrist-yaw frame.")
    print("Hardware output: disabled in this process.")

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                cycle_start = time.perf_counter()
                now = time.monotonic()

                raw_target, raw_rotation, raw_valid, received = base._receive_latest(
                    udp,
                    raw_target,
                    raw_rotation,
                    raw_valid,
                )

                if received:
                    received_total += received
                    last_packet_time = now

                    current_input_rotation = (
                        base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    )
                    translation_speed_m_s = float(
                        np.linalg.norm(raw_target - previous_input_position) / base.DT
                    )
                    angular_speed_rad_s = float(
                        base._rotation_error_radians(
                            current_input_rotation,
                            previous_input_rotation,
                        )
                        / base.DT
                    )
                    previous_input_position = raw_target.copy()
                    previous_input_rotation = current_input_rotation.copy()

                active = bool(
                    raw_valid
                    and now - last_packet_time < base.INPUT_TIMEOUT_S
                )

                wrist_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                if active and not last_active:
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(
                        raw_rotation
                    )
                    clutch_reference = {
                        "input_position": raw_target.copy(),
                        "input_rotation": input_rotation.copy(),
                        "robot_position": wrist_pose.translation().copy(),
                        "robot_rotation": wrist_pose.rotation().as_matrix().copy(),
                    }
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    posture_task.set_target(configuration.q.copy())
                    previous_input_position = raw_target.copy()
                    previous_input_rotation = input_rotation.copy()
                    translation_speed_m_s = 0.0
                    angular_speed_rad_s = 0.0
                    rotation_only_mode = False
                    print("\nMink clutch engaged without position or orientation jump.")

                if not active:
                    rotation_only_mode = False
                elif rotation_only_mode:
                    if (
                        translation_speed_m_s
                        > ROTATION_ONLY_EXIT_TRANSLATION_SPEED_M_S
                    ):
                        rotation_only_mode = False
                        print("[MODE] Full-arm translation mode")
                elif (
                    translation_speed_m_s
                    <= ROTATION_ONLY_ENTER_TRANSLATION_SPEED_M_S
                    and angular_speed_rad_s
                    >= ROTATION_ONLY_MIN_ANGULAR_SPEED_RAD_S
                ):
                    rotation_only_mode = True
                    print("[MODE] Wrist-only rotation mode; proximal DOFs frozen")

                if active and clutch_reference is not None:
                    target_position = (
                        clutch_reference["robot_position"]
                        + raw_target
                        - clutch_reference["input_position"]
                    )
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(
                        raw_rotation
                    )
                    rotation_delta = (
                        input_rotation
                        @ clutch_reference["input_rotation"].T
                    )
                    target_rotation = (
                        rotation_delta
                        @ clutch_reference["robot_rotation"]
                    )
                    wrist_task.set_target(
                        base._matrix_to_se3(target_rotation, target_position)
                    )

                    active_constraints = list(base_constraints)
                    if rotation_only_mode:
                        active_constraints.append(proximal_freeze)

                    velocity = mink.solve_ik(
                        configuration=configuration,
                        tasks=[wrist_task, posture_task, damping_task],
                        dt=base.DT,
                        solver=solver,
                        damping=base.QP_DAMPING,
                        limits=limits,
                        constraints=active_constraints,
                    )
                    configuration.integrate_inplace(velocity, base.DT)
                    data = configuration.data
                    data.mocap_pos[target_mocap_id] = target_position
                else:
                    target_position = wrist_pose.translation().copy()
                    target_rotation = wrist_pose.rotation().as_matrix().copy()
                    clutch_reference = None
                    wrist_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    data.mocap_pos[target_mocap_id] = target_position

                mujoco.mj_fwdPosition(model, data)
                min_clearance = base._min_pair_distance(
                    model,
                    data,
                    collision_geom_ids,
                )
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance
                    <= base.COLLISION_DETECTION_DISTANCE_M
                )

                if now >= next_state:
                    packet = base._state_packet(
                        configuration,
                        right_qpos_ids,
                        active,
                        target_position,
                        None
                        if clutch_reference is None
                        else clutch_reference["robot_position"],
                        collision_limited,
                    )
                    base._send_state(
                        state_sock,
                        packet,
                        base.UNITY_STATE_HOST,
                        base.UNITY_STATE_PORT,
                    )
                    base._send_state(
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
                    current_pose = configuration.get_transform_frame_to_world(
                        "right_wrist_yaw_link", "body"
                    )
                    current_rotation = current_pose.rotation().as_matrix()
                    position_error = float(
                        np.linalg.norm(
                            target_position - current_pose.translation()
                        )
                    )
                    orientation_error_deg = math.degrees(
                        base._rotation_error_radians(
                            target_rotation,
                            current_rotation,
                        )
                    )
                    stats = np.asarray(cycle_times, dtype=float)
                    base._write_status(
                        {
                            "updated_at": time.strftime(
                                "%Y-%m-%dT%H:%M:%S"
                            ),
                            "controller": "mink_right_arm_qp",
                            "input_active": active,
                            "received_packets": received_total,
                            "solver": solver,
                            "collision_pair_count": len(collision_pairs),
                            "collision_min_distance_m": base.COLLISION_MIN_DISTANCE_M,
                            "collision_detection_distance_m": base.COLLISION_DETECTION_DISTANCE_M,
                            "minimum_clearance_m": min_clearance,
                            "collision_limit_nearby": collision_limited,
                            "target_position": target_position.tolist(),
                            "wrist_position": current_pose.translation().tolist(),
                            "position_error_m": position_error,
                            "orientation_error_deg": orientation_error_deg,
                            "orientation_mapping": "clutch_relative",
                            "rotation_only_mode": rotation_only_mode,
                            "input_translation_speed_m_s": translation_speed_m_s,
                            "input_angular_speed_deg_s": math.degrees(
                                angular_speed_rad_s
                            ),
                            "proximal_hard_freeze": rotation_only_mode,
                            "proximal_damping_cost": base.PROXIMAL_DAMPING_COST,
                            "wrist_damping_cost": base.WRIST_DAMPING_COST,
                            "right_arm_q_deg": np.degrees(
                                configuration.q[right_qpos_ids]
                            ).tolist(),
                            "cycle_last_ms": cycle_ms,
                            "cycle_mean_ms": float(np.mean(stats)),
                            "cycle_p95_ms": float(
                                np.percentile(stats, 95)
                            ),
                            "cycle_p99_ms": float(
                                np.percentile(stats, 99)
                            ),
                            "cycle_worst_ms": float(np.max(stats)),
                        }
                    )
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
