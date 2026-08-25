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

import mujoco
import mujoco.viewer
import numpy as np

import mink
from mink.tasks.task import Task

import run_mink_g1_right_arm_prototype as base


MAX_JOINT_VELOCITY_DEG_S = 50.0
base.RIGHT_ARM_MAX_VELOCITY_RAD_S = math.radians(MAX_JOINT_VELOCITY_DEG_S)
base.PROXIMAL_DAMPING_COST = 0.03
base.WRIST_DAMPING_COST = 0.015

ASSIST_ENTER_MARGIN_DEG = 10.0
ASSIST_RELEASE_MARGIN_DEG = 18.0
ASSIST_FULL_MARGIN_DEG = 3.0
ASSIST_LATCH_FLOOR = 0.03
ASSIST_MAX = 0.14


class VirtualCenterOrientationTask(Task):
    """Yaw-link orientation task with wrist-limit hysteretic proximal assistance."""

    last_assist_gain = 0.0
    last_min_wrist_margin_deg = float("inf")
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
        return self.inner.compute_error(configuration)

    def _assist_gain(self, configuration) -> float:
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

        if VirtualCenterOrientationTask.assist_latched:
            if min_margin >= ASSIST_RELEASE_MARGIN_DEG:
                VirtualCenterOrientationTask.assist_latched = False
        elif min_margin <= ASSIST_ENTER_MARGIN_DEG:
            VirtualCenterOrientationTask.assist_latched = True

        if not VirtualCenterOrientationTask.assist_latched:
            assist = 0.0
        elif min_margin <= ASSIST_FULL_MARGIN_DEG:
            assist = ASSIST_MAX
        elif min_margin >= ASSIST_ENTER_MARGIN_DEG:
            assist = ASSIST_LATCH_FLOOR
        else:
            span = ASSIST_ENTER_MARGIN_DEG - ASSIST_FULL_MARGIN_DEG
            fraction = (ASSIST_ENTER_MARGIN_DEG - min_margin) / span
            smooth = fraction * fraction * (3.0 - 2.0 * fraction)
            assist = ASSIST_LATCH_FLOOR + smooth * (ASSIST_MAX - ASSIST_LATCH_FLOOR)

        VirtualCenterOrientationTask.last_assist_gain = float(assist)
        return float(assist)

    def compute_jacobian(self, configuration) -> np.ndarray:
        jacobian = self.inner.compute_jacobian(configuration).copy()
        jacobian[3:6, self.proximal_dofs] *= self._assist_gain(configuration)
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

    orientation_task = VirtualCenterOrientationTask(model)
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
                roll_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_roll_link", "body"
                )
                yaw_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                if active and not last_active:
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
                    print("\nVirtual-center clutch engaged without position/orientation jump.")

                if active and clutch_reference is not None:
                    target_center_position = (
                        clutch_reference["center_position"]
                        + raw_target
                        - clutch_reference["input_position"]
                    )
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
                    target_rotation = rotation_delta @ clutch_reference["yaw_rotation"]

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
                    clutch_reference = None
                    position_task.set_target_from_configuration(configuration)
                    orientation_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    VirtualCenterOrientationTask.assist_latched = False
                    VirtualCenterOrientationTask.last_assist_gain = 0.0

                mujoco.mj_fwdPosition(model, configuration.data)
                roll_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_roll_link", "body"
                )
                yaw_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                # Keep the Unity-visible target in the existing yaw-link contract.
                # The vector from actual yaw wrist to displayed target equals the
                # internal virtual-center translation error. Pure wrist rotation
                # therefore produces zero visible position error.
                center_error = target_center_position - roll_pose.translation()
                external_target_position = yaw_pose.translation() + center_error
                configuration.data.mocap_pos[target_mocap_id] = external_target_position

                min_clearance = base._min_pair_distance(
                    model, configuration.data, collision_geom_ids
                )
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance <= base.COLLISION_DETECTION_DISTANCE_M
                )

                if now >= next_state:
                    packet = base._state_packet(
                        configuration,
                        right_qpos_ids,
                        active,
                        external_target_position,
                        None if clutch_reference is None else clutch_reference["yaw_position"],
                        collision_limited,
                    )
                    packet["right_arm"]["position_error"] = float(
                        np.linalg.norm(center_error)
                    )
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
                    current_rotation = yaw_pose.rotation().as_matrix()
                    orientation_error_deg = math.degrees(
                        base._rotation_error_radians(target_rotation, current_rotation)
                    )
                    stats = np.asarray(cycle_times, dtype=float)
                    base._write_status(
                        {
                            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "controller": "mink_right_arm_virtual_center_live",
                            "input_active": active,
                            "received_packets": received_total,
                            "solver": solver,
                            "collision_pair_count": len(collision_pairs),
                            "collision_min_distance_m": base.COLLISION_MIN_DISTANCE_M,
                            "collision_detection_distance_m": base.COLLISION_DETECTION_DISTANCE_M,
                            "minimum_clearance_m": min_clearance,
                            "collision_limit_nearby": collision_limited,
                            "position_task_frame": "right_wrist_roll_link",
                            "orientation_task_frame": "right_wrist_yaw_link",
                            "external_state_frame": "right_wrist_yaw_link",
                            "target_position": external_target_position.tolist(),
                            "wrist_position": yaw_pose.translation().tolist(),
                            "virtual_center_target_position": target_center_position.tolist(),
                            "virtual_center_position": roll_pose.translation().tolist(),
                            "position_error_m": float(np.linalg.norm(center_error)),
                            "orientation_error_deg": orientation_error_deg,
                            "orientation_mapping": "clutch_relative",
                            "proximal_orientation_assist_gain": (
                                VirtualCenterOrientationTask.last_assist_gain
                            ),
                            "min_wrist_limit_margin_deg": (
                                VirtualCenterOrientationTask.last_min_wrist_margin_deg
                            ),
                            "wrist_limit_assist_latched": (
                                VirtualCenterOrientationTask.assist_latched
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
