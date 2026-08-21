"""Projected-workspace runtime for Quest-to-MuJoCo right-arm teleoperation.

This entry point keeps operator intent separate from the robot's feasible target.
It reuses the established MuJoCo model/IK helpers while making the offline
collision-free workspace map authoritative for position target projection.
"""

from __future__ import annotations

import math
import socket
import time

import mujoco
import mujoco.viewer
import numpy as np

import g1_right_arm_udp_ik_demo as base
from g1_teleop import VoxelWorkspaceMap, WorkspaceTargetProjector


WORKSPACE_PATH = base.PROJECT_ROOT / "logs" / "workspace" / "right_arm_workspace.npz"
WORKSPACE_VOXEL_SIZE_M = 0.01
WORKSPACE_ALLOWED_CLASSES = (1, 2)


def load_workspace_projector(anchor_point_m: np.ndarray) -> WorkspaceTargetProjector | None:
    if not WORKSPACE_PATH.exists():
        print("[workspace] right_arm_workspace.npz not found; using legacy box/torso workspace guards.")
        return None
    try:
        workspace = VoxelWorkspaceMap.from_npz(
            WORKSPACE_PATH,
            voxel_size_m=WORKSPACE_VOXEL_SIZE_M,
            allowed_classes=WORKSPACE_ALLOWED_CLASSES,
        )
        anchor = np.asarray(anchor_point_m, dtype=float).reshape(1, 3)
        workspace = VoxelWorkspaceMap(
            np.vstack([workspace.safe_voxel_centers_m, anchor]),
            voxel_size_m=WORKSPACE_VOXEL_SIZE_M,
        )
    except (KeyError, OSError, ValueError) as exc:
        print(f"[workspace] failed to load voxel map ({exc}); using legacy guards.")
        return None
    print(
        "[workspace] loaded collision-free voxel map: "
        f"{len(workspace.safe_voxel_indices):,} voxels, "
        f"{workspace.voxel_size_m * 1000.0:g} mm resolution"
    )
    return WorkspaceTargetProjector(workspace)


def main() -> None:
    args = base.parse_args()
    if args.camera_fps <= 0.0:
        raise ValueError("--camera-fps must be positive")
    if args.snapshot is not None:
        base.main()
        return

    model, data, initial_qpos, preferred = base.initialize_model(args.scene)
    scene_target = np.asarray(base.SCENES[args.scene]["target_pos"], dtype=float)
    ik_context = base.create_right_arm_ik_context(model)
    mujoco.mj_forward(model, data)
    position_body = ik_context["position_body"]
    orientation_body = ik_context["orientation_body"]
    workspace_projector = load_workspace_projector(data.xpos[position_body].copy())
    if workspace_projector is not None:
        base.is_right_wrist_target_safe = lambda target: True

    sock = base.setup_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    camera_source = None
    image_writer = None
    if args.publish_head_camera:
        camera_profile = base.load_camera_profile(base.CAMERA_PROFILE_PATH)
        camera_profile["active_source"] = "simulation"
        camera_source = base.create_head_camera_source(camera_profile, model=model, data=data)
        camera_source.start()
        image_writer = base.UnitreeSimImageWriter()

    raw_target = scene_target.copy()
    filtered_target = data.xpos[position_body].copy()
    operator_target = filtered_target.copy()
    feasible_target = filtered_target.copy()
    workspace_projection_distance_m = 0.0
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    filtered_rotation = raw_rotation.copy()
    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
    raw_valid = False
    clutch_active = False
    clutch_reference = None
    packet_watchdog = base.SessionSequenceWatchdog(takeover_after_s=base.INPUT_TIMEOUT_SECONDS)
    workspace_fault = base.WorkspaceFaultLatch()
    workspace_exit_debounce = base.WorkspaceExitDebounce(base.WORKSPACE_EXIT_CONFIRM_SECONDS)
    received_total = 0
    last_received_time = float("-inf")
    packet_was_fresh = False
    input_was_active = False
    next_camera_time = time.monotonic()
    camera_period = 1.0 / args.camera_fps
    next_state_time = time.monotonic()
    state_period = 1.0 / base.UNITY_STATE_HZ
    next_status_time = time.monotonic()
    status_period = 1.0 / base.RUNTIME_STATUS_HZ
    last_control_time = time.monotonic()

    print("G1 right-arm UDP IK demo - projected workspace runtime")
    print("----------------------------------------------------")
    print(f"Listening for UDP JSON on 127.0.0.1:{base.UDP_PORT} and local interfaces")
    print('Expected format: {"session_id": "...", "sequence": 0, "right": {"pos": [0.42, -0.16, 1.05], "rot": [0, 0, 0, 1], "valid": true}}')
    print("Run tools\\TEST_FAKE_VR_TO_MUJOCO.bat to test without VR.")
    print("Initial ready pose: both arms down; clutch motion is relative to this pose.")
    print(f"Publishing right-arm joint state to {base.UNITY_STATE_HOST}:{base.UNITY_STATE_PORT} at {base.UNITY_STATE_HZ:g} Hz.")
    if workspace_projector is not None:
        print("Workspace authority: backend collision-free voxel projection.")
    else:
        print("Workspace authority: legacy relative box + torso guard fallback.")
    print("Target marker: feasible target; G1 follows the lagged safe reference.")
    print("Safe reference path: fixed-speed interpolation to feasible target; runtime collision guard owns path safety.")
    if args.publish_head_camera:
        print(f"Head camera: 640x480 BGR at {args.camera_fps:g} FPS -> isaac_head_image_shm (TeleImager-compatible)")

    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            base.configure_viewer_camera(viewer, model, args.view)
            last_print = 0.0
            while viewer.is_running():
                t = time.monotonic()
                control_delta_time = float(np.clip(t - last_control_time, model.opt.timestep, 0.05))
                last_control_time = t
                base.freeze_non_arm_joints(model, data, initial_qpos)
                base.set_left_arm_ready(model, data)

                raw_target, raw_rotation, raw_valid, received_now, accepted_workspace_exit = base.receive_target(
                    sock, packet_watchdog, raw_target, raw_rotation, raw_valid
                )
                if received_now:
                    received_total += received_now
                    last_received_time = t

                if accepted_workspace_exit and workspace_projector is not None:
                    if clutch_active:
                        raw_valid = True
                    accepted_workspace_exit = False
                if accepted_workspace_exit:
                    if not workspace_fault.latched:
                        workspace_fault.trip()
                    workspace_fault.observe_workspace_exit()

                packet_fresh = (t - last_received_time) < base.INPUT_TIMEOUT_SECONDS
                valid_permitted = False
                if raw_valid and packet_fresh:
                    valid_permitted = workspace_fault.permit_valid()
                requested_active = raw_valid and packet_fresh and valid_permitted
                workspace_limited = workspace_fault.latched
                input_resumed = requested_active and not input_was_active

                if requested_active and not clutch_active:
                    mujoco.mj_forward(model, data)
                    clutch_reference = base.capture_clutch_reference(
                        data, position_body, orientation_body, raw_target, raw_rotation,
                        ik_context["shoulder_body"], ik_context["elbow_body"],
                    )
                    preferred[:] = data.qpos[ik_context["right_qpos_ids"]]
                    filtered_target = clutch_reference["robot_position"].copy()
                    operator_target = filtered_target.copy()
                    feasible_target = filtered_target.copy()
                    workspace_projection_distance_m = 0.0
                    filtered_rotation = raw_rotation.copy()
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    clutch_active = True
                    workspace_exit_debounce.reset()
                    print("\nRight-arm clutch engaged without a target jump.")
                elif input_resumed and clutch_active:
                    mujoco.mj_forward(model, data)
                    clutch_reference = base.capture_clutch_reference(
                        data, position_body, orientation_body, raw_target, raw_rotation,
                        ik_context["shoulder_body"], ik_context["elbow_body"],
                    )
                    preferred[:] = data.qpos[ik_context["right_qpos_ids"]]
                    filtered_target = clutch_reference["robot_position"].copy()
                    operator_target = filtered_target.copy()
                    feasible_target = filtered_target.copy()
                    workspace_projection_distance_m = 0.0
                    filtered_rotation = raw_rotation.copy()
                    target_rotation = clutch_reference["robot_rotation"].copy()
                    workspace_exit_debounce.reset()
                    print("\nInput resumed; clutch reference rebased without a jump.")

                if accepted_workspace_exit and clutch_active:
                    clutch_active = False
                    clutch_reference = None
                    raw_valid = False
                    workspace_limited = True
                    workspace_exit_debounce.reset()
                    mujoco.mj_forward(model, data)
                    filtered_target = data.xpos[position_body].copy()
                    operator_target = filtered_target.copy()
                    feasible_target = filtered_target.copy()
                    workspace_projection_distance_m = 0.0
                    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                    data.mocap_pos[0] = filtered_target
                    print("\nExplicit workspace exit received; clutch released and current pose held.")

                if not packet_fresh and packet_was_fresh and clutch_active:
                    print("\nUDP input temporarily stale; holding the current pose.")
                packet_was_fresh = packet_fresh

                if clutch_active and packet_fresh:
                    operator_target, desired_rotation = base.calculate_clutched_target(
                        clutch_reference, raw_target, raw_rotation
                    )
                    if workspace_projector is not None:
                        projection = workspace_projector.update(operator_target)
                        feasible_target = projection.feasible_target
                        workspace_projection_distance_m = projection.distance_m
                        workspace_limited = projection.projected
                        workspace_exit_debounce.reset()
                    else:
                        requested_delta = operator_target - clutch_reference["robot_position"]
                        feasible_target = base.clamp_to_clutch_workspace(
                            operator_target, clutch_reference["robot_position"]
                        )
                        workspace_projection_distance_m = float(np.linalg.norm(feasible_target - operator_target))
                        workspace_safe = (
                            base.is_clutch_delta_within_workspace(requested_delta)
                            and base.is_right_wrist_target_safe(feasible_target)
                        )
                        workspace_limited = not workspace_safe
                        workspace_exit_confirmed = workspace_exit_debounce.update(workspace_safe, control_delta_time)
                        if workspace_exit_confirmed:
                            workspace_fault.trip_and_arm_reset()
                            workspace_limited = True
                            clutch_active = False
                            clutch_reference = None
                            raw_valid = False
                            mujoco.mj_forward(model, data)
                            filtered_target = data.xpos[position_body].copy()
                            operator_target = filtered_target.copy()
                            feasible_target = filtered_target.copy()
                            workspace_projection_distance_m = 0.0
                            target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                            data.mocap_pos[0] = filtered_target
                            print("\nLegacy workspace exited; clutch released and current pose held.")

                    if clutch_active:
                        # Workspace projection decides the admissible destination.
                        # The lagged reference then advances toward that destination
                        # at the configured Cartesian speed. Do not re-project the
                        # post-speed-limit point through the voxel map: the ready-pose
                        # anchor may be an isolated injected voxel, which can trap the
                        # reference even though the feasible destination is valid.
                        # Runtime collision handling remains authoritative for the
                        # intermediate path and IK candidate acceptance.
                        filtered_target = base.update_safe_position_reference(
                            filtered_target, feasible_target, control_delta_time
                        )

                        filtered_rotation = base.update_safe_rotation_reference(
                            filtered_rotation, raw_rotation, control_delta_time
                        )
                        _, target_rotation = base.calculate_clutched_target(
                            clutch_reference, raw_target, filtered_rotation
                        )
                        data.mocap_pos[0] = feasible_target

                        base.solve_right_arm_target(
                            model, data, initial_qpos, preferred, filtered_target,
                            target_rotation=target_rotation,
                            context=ik_context,
                            elbow_pole_reference=clutch_reference["elbow_pole"],
                        )
                else:
                    mujoco.mj_forward(model, data)
                    filtered_target = data.xpos[position_body].copy()
                    operator_target = filtered_target.copy()
                    feasible_target = filtered_target.copy()
                    workspace_projection_distance_m = 0.0
                    target_rotation = data.xmat[orientation_body].reshape(3, 3).copy()
                    data.mocap_pos[0] = filtered_target

                input_was_active = requested_active and clutch_active
                monotonic_time = time.monotonic()
                if monotonic_time >= next_state_time:
                    base.send_robot_state(
                        state_sock, data, ik_context["right_qpos_ids"], requested_active,
                        position_body, filtered_target, clutch_reference, ik_context, workspace_limited,
                    )
                    next_state_time = monotonic_time + state_period

                if camera_source is not None and monotonic_time >= next_camera_time:
                    frame = camera_source.read()
                    image_writer.write_frame(frame, "head")
                    next_camera_time = monotonic_time + camera_period

                if monotonic_time >= next_status_time:
                    wrist_position = data.xpos[position_body].copy()
                    status_value = {
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "received_packets": received_total,
                        "packets_fresh": bool(packet_fresh),
                        "input_valid": bool(raw_valid),
                        "input_active": bool(requested_active),
                        "clutch_active": bool(clutch_active),
                        "raw_target": raw_target.tolist(),
                        "operator_target": operator_target.tolist(),
                        "feasible_target": feasible_target.tolist(),
                        "safe_target": filtered_target.tolist(),
                        "g1_wrist": wrist_position.tolist(),
                        "workspace_projection_distance_m": float(workspace_projection_distance_m),
                        "safe_reference_lag_m": float(np.linalg.norm(feasible_target - filtered_target)),
                        "tracking_error_m": float(np.linalg.norm(filtered_target - wrist_position)),
                        "workspace_limited": bool(workspace_limited),
                        "workspace_source": "collision_free_voxel_map" if workspace_projector is not None else "legacy_guards",
                        "workspace_exit_pending_s": float(workspace_exit_debounce.unsafe_duration_s),
                        "collision_limited": bool(ik_context["collision_limited"]),
                    }
                    base.write_runtime_status(status_value)
                    next_status_time = monotonic_time + status_period

                if t - last_print > 0.25:
                    last_print = t
                    wrist_pos = data.xpos[position_body].copy()
                    dist = np.linalg.norm(filtered_target - wrist_pos)
                    rotation_dist = np.linalg.norm(
                        base.calculate_rotation_error(
                            target_rotation,
                            data.xmat[orientation_body].reshape(3, 3),
                        )
                    )
                    if clutch_active and packet_fresh:
                        status = "ACTIVE"
                    elif clutch_active:
                        status = "STALE-HOLD"
                    elif packet_fresh:
                        status = "waiting"
                    else:
                        status = "NO UDP"
                    safety_flags = []
                    if workspace_limited:
                        safety_flags.append("workspace")
                    if ik_context["collision_limited"]:
                        safety_flags.append("collision")
                    safety_text = ",".join(safety_flags) if safety_flags else "clear"
                    print(
                        f"{status} packets={received_total} "
                        f"operator=({operator_target[0]: .2f}, {operator_target[1]: .2f}, {operator_target[2]: .2f}) "
                        f"target=({filtered_target[0]: .2f}, {filtered_target[1]: .2f}, {filtered_target[2]: .2f}) "
                        f"wrist=({wrist_pos[0]: .2f}, {wrist_pos[1]: .2f}, {wrist_pos[2]: .2f}) "
                        f"projection={workspace_projection_distance_m: .3f}m "
                        f"error={dist: .3f} rot_error={math.degrees(rotation_dist): .1f}deg "
                        f"safety={safety_text}",
                        end="\r",
                    )

                viewer.sync()
                time.sleep(model.opt.timestep)
    finally:
        sock.close()
        state_sock.close()
        if camera_source is not None:
            camera_source.close()
        if image_writer is not None:
            image_writer.close()


if __name__ == "__main__":
    main()
