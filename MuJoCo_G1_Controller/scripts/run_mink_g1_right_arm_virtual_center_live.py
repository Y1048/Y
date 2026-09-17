"""가상 손목 중심을 사용하는 현재 G1 오른팔 Mink 실시간 제어기.

내부 IK 역할은 위치를 right_wrist_roll_link에, 회전을 right_wrist_yaw_link에
나누어 준다. 정확한 회전 Jacobian을 유지하고, 자세 비용으로 손목 관절을 우선
사용한다. 손목 제한에 가까워지면 히스테리시스로 회전 추종 비용을 낮춘다.

Unity에 돌려주는 외부 계약은 계속 right_wrist_yaw_link 기준이다. 따라서 내부
최적화 방식을 바꿔도 Unity의 손목/목표 위치 의미는 바뀌지 않는다. 속도 기반 모드
전환이나 hard freeze는 사용하지 않으며 충돌 회피는 항상 유지한다.

진입: START_VR_HAND_TO_MUJOCO.bat 또는 START_MUJOCO_ONLY.bat -> main.
연결: Unity UDP 5005 -> MinkCommandStream -> FeasibleTargetPlanner -> MuJoCo FK
      -> Unity UDP 5006 / Gate 7 후보 UDP 5008. 선택적 모의 복귀 입력은 UDP 5012.
이 프로세스는 로컬 모델/로그를 생성하지만 Unitree 모터 명령을 발행하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np
import mink
from mink.tasks.task import Task  # Backward-compatible public re-export.

import run_mink_g1_right_arm_prototype as base
from g1_mink_feasible_target import FeasibleTargetPlanner
from g1_standard_mink_planner import StandardMinkPlanner
from g1_mink_trajectory import StatefulMinkTrajectory
from g1_mink_collision_policy import (
    COLLISION_PROFILE_HARDWARE_GUARDED,
    COLLISION_PROFILE_MINK_DEFAULT,
    COLLISION_PROFILES,
    MINK_DEFAULT_QP_RESERVE_M,
    TELEOP_COLLISION_TARGET_DISTANCE_M,
    ResolveCollisionProfile,
)
from g1_virtual_center_tasks import (
    ASSIST_ENTER_MARGIN_DEG,
    ASSIST_RELEASE_MARGIN_DEG,
    ASSIST_FULL_MARGIN_DEG,
    ASSIST_LATCH_FLOOR,
    ASSIST_MAX,
    ORIENTATION_COST_MIN_SCALE,
    ORIENTATION_ERROR_NORMAL_MAX_DEG,
    ORIENTATION_ERROR_LIMIT_MAX_DEG,
    ORIENTATION_PROXIMAL_DAMPING_MAX,
    ORIENTATION_PROXIMAL_DAMPING_MIN,
    PROXIMAL_MAX_JOINT_VELOCITY_DEG_S,
    WRIST_MAX_JOINT_VELOCITY_DEG_S,
    JOINT_MAX_ACCELERATION_RAD_S2,
    JOINT_MAX_JERK_RAD_S3,
    VIRTUAL_CENTER_PROXIMAL_DAMPING_COST,
    VIRTUAL_CENTER_WRIST_DAMPING_COST,
    VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE,
    VirtualCenterOrientationTask,
    hierarchical_orientation_damping_costs,
    orientation_limit_policy,
    virtual_center_damping_costs,
    virtual_center_posture_costs,
    virtual_center_velocity_limits,
)
from g1_mink_diagnostics import orientation_diagnostics
from g1_gate7_feedback import (
    DUAL_ARM_JOINT_INDICES,
    GATE7_SIMULATION_FEEDBACK_HOST,
    GATE7_SIMULATION_FEEDBACK_PORT,
    GATE7_SIMULATION_FEEDBACK_TIMEOUT_S,
    MAX_GATE7_FEEDBACK_PACKET_BYTES,
    Gate7SimulationFeedback,
    Gate7SimulationFeedbackError,
    apply_gate7_simulation_feedback,
    drain_gate7_simulation_feedback,
    parse_gate7_feedback_packet,
    should_apply_gate7_feedback,
)
from g1_teleop.inspection_demo import (
    InspectionDemoTracker,
    append_inspection_result,
)


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


def cycle_velocity_limits(profile_name="today") -> dict[str, float]:
    from g1_mink_speed_profiles import speed_profile
    return dict(zip(base.g1.RIGHT_ARM_JOINTS, speed_profile(profile_name)["velocity_rad_s"]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the current G1 right-arm Mink virtual-center controller."
    )
    parser.add_argument(
        "--show-inspection-scene",
        action="store_true",
        help="Show the preserved inspection stick, panel, and target marker",
    )
    parser.add_argument(
        "--gate7-feedback-port",
        type=int,
        default=GATE7_SIMULATION_FEEDBACK_PORT,
    )
    parser.add_argument(
        "--disable-gate7-simulation-feedback",
        action="store_true",
    )
    parser.add_argument(
        "--collision-profile",
        choices=tuple(COLLISION_PROFILES),
        default=COLLISION_PROFILE_MINK_DEFAULT,
        help=(
            "mink-default uses upstream Mink 5/10 mm for local simulation; "
            "hardware-guarded is selected explicitly by the Gate 7 hardware path"
        ),
    )
    parser.add_argument("--ik-solver", choices=("hierarchical", "vanilla"), default="hierarchical")
    parser.add_argument("--initial-lowstate-seed", type=Path)
    parser.add_argument("--initial-lowstate-session")
    parser.add_argument("--initial-state-check-only", type=Path)
    parser.add_argument("--simulation-arm-cycle", action="store_true",
                        help="Local pinch return/re-engage; disables candidate UDP output")
    parser.add_argument("--upstream-mink-collision", action="store_true",
                        help="Simulation-only upstream G1 collision settings and direct IK integration")
    parser.add_argument("--speed-profile", choices=("yesterday", "today"), default=None,
                        help="Same current IK, named speed/acceleration preset; simulation arm cycle only")
    parser.add_argument("--live-cycle-candidate", action="store_true",
                        help="Explicit hardware cycle candidate; requires matching new receiver and relay")
    return parser.parse_args()


def main() -> None:
    """모델/task/통신을 준비하고 입력 -> 상대 목표 -> QP -> 상태 송신을 반복한다.

    qpos를 갱신하는 기구학 시뮬레이션이다. 실측 모터 응답은 별도 하드웨어 경로에서
    rt/lowstate로 확인하며, 이 함수의 계산 결과를 실측으로 취급하지 않는다.
    """
    args = parse_args()
    simulation_arm_cycle = getattr(args, "simulation_arm_cycle", False)
    live_cycle = getattr(args, "live_cycle_candidate", False)
    if live_cycle and simulation_arm_cycle:
        raise ValueError("live and simulation cycle modes are mutually exclusive")
    cycle_enabled = simulation_arm_cycle or live_cycle
    upstream_mink = getattr(args, "upstream_mink_collision", False)
    if live_cycle and (not upstream_mink or args.speed_profile is None):
        raise ValueError("live cycle requires upstream Mink and explicit speed profile")
    from g1_mink_speed_profiles import speed_profile
    if args.speed_profile is not None and not cycle_enabled:
        raise ValueError("speed comparison requires simulation-arm-cycle; no hardware profile deployment")
    comparison_profile = speed_profile(args.speed_profile or "today")
    if upstream_mink and (not cycle_enabled or args.ik_solver != "vanilla"):
        raise ValueError("upstream Mink flow requires simulation-arm-cycle and vanilla IK")
    if cycle_enabled:
        if getattr(args, "initial_lowstate_seed", None):
            raise ValueError("simulation arm cycle uses the model ready pose, not a LowState seed")
        args.disable_gate7_simulation_feedback = True
    ik_solver = getattr(args, "ik_solver", "hierarchical")
    position_frame = ("right_wrist_yaw_link" if ik_solver == "vanilla"
                      else "right_wrist_roll_link")
    if not 1 <= args.gate7_feedback_port <= 65535:
        raise ValueError("gate7-feedback-port must be within 1..65535")
    collision_profile = getattr(
        args, "collision_profile", COLLISION_PROFILE_MINK_DEFAULT
    )
    collision_min_distance_m, collision_detection_distance_m = (
        ResolveCollisionProfile(collision_profile)
    )
    local_tangent_steps_enabled = (
        collision_profile == COLLISION_PROFILE_MINK_DEFAULT
    )
    qp_collision_min_distance_m = collision_min_distance_m + (
        # Keep QP's linearized proposal outside the exact validation boundary.
        # Simulation-only fix; the physical candidate profile remains unchanged.
        MINK_DEFAULT_QP_RESERVE_M if local_tangent_steps_enabled or cycle_enabled else 0.0
    )
    model, model_metadata = base.LoadMinkModelWithMetadata(show_inspection_scene=args.show_inspection_scene)
    base._apply_operational_joint_limits(model)
    if live_cycle:
        from g1_mink_speed_profiles import live_joint_bounds
        live_lower, live_upper = live_joint_bounds()
        for axis, name in enumerate(base.g1.RIGHT_ARM_JOINTS):
            joint = base._joint_id(model, name)
            model.jnt_range[joint, 0] = max(model.jnt_range[joint, 0], live_lower[axis])
            model.jnt_range[joint, 1] = min(model.jnt_range[joint, 1], live_upper[axis])
            model.jnt_limited[joint] = 1
    model_metadata.update(base.GetJointLimitMetadata(model))
    configuration = mink.Configuration(model)
    initial_q = base._initial_configuration(model)
    seed_path = getattr(args, "initial_lowstate_seed", None)
    seed_session = getattr(args, "initial_lowstate_session", None)
    initial_seed = None
    if getattr(args, "initial_state_check_only", None) and not seed_path:
        raise ValueError("initial state check requires a fresh seed")
    if bool(seed_path) != bool(seed_session):
        raise ValueError("initial seed path and session must be supplied together")
    if seed_path:
        from g1_lowstate_seed import ReadSeed, ApplySeed
        initial_seed = ReadSeed(seed_path, seed_session, base.g1.G1_29_JOINT_NAMES)
        initial_q = ApplySeed(model, initial_q, initial_seed, base.g1.G1_29_JOINTS)
    configuration.update(initial_q)
    data = configuration.data
    collision_validation_data = mujoco.MjData(model)

    right_dofs = base._right_arm_dof_indices(model)
    right_qpos_ids = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.RIGHT_ARM_JOINTS
    ]
    all_qpos_ids = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.G1_29_JOINTS
    ]
    frozen_dofs = base._frozen_dof_indices(model, right_dofs)
    collision_pairs, collision_geom_ids = base._build_collision_pairs(model)

    position_task = mink.FrameTask(
        frame_name=position_frame,
        frame_type="body",
        position_cost=base.POSITION_COST,
        orientation_cost=0.0,
        gain=base.FRAME_GAIN,
        lm_damping=base.LM_DAMPING,
    )
    position_task.set_target_from_configuration(configuration)

    orientation_task = VirtualCenterOrientationTask(model)
    orientation_task.set_target_from_configuration(configuration)

    posture_task = mink.PostureTask(model, cost=virtual_center_posture_costs(model))
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(
        model,
        cost=virtual_center_damping_costs(model),
    )

    velocity_limits = cycle_velocity_limits(comparison_profile["name"]) if cycle_enabled else virtual_center_velocity_limits()
    limits = [
        mink.ConfigurationLimit(model=model),
        mink.VelocityLimit(model, velocity_limits),
        mink.CollisionAvoidanceLimit(
            model=model,
            geom_pairs=collision_pairs,
            minimum_distance_from_collisions=qp_collision_min_distance_m,
            collision_detection_distance=collision_detection_distance_m,
            gain=base.COLLISION_GAIN,
            broadphase=True,
        ),
    ]
    constraints = [mink.DofFreezingTask(model=model, dof_indices=frozen_dofs)]
    solver = base._select_solver()
    planner_type = StandardMinkPlanner if ik_solver == "vanilla" else FeasibleTargetPlanner
    feasible_planner = planner_type(
        model, position_task, orientation_task, posture_task, damping_task,
        limits, constraints, solver, collision_min_distance_m,
        velocity_limits,
        require_merit_decrease=not local_tangent_steps_enabled,
        allow_local_detour=local_tangent_steps_enabled,
    )
    feasible_target_policy = (
        "hierarchical_wrist_first_local_detour_v1"
        if local_tangent_steps_enabled
        else "hierarchical_wrist_first_checked_v1"
    )
    if ik_solver == "vanilla":
        feasible_target_policy = "standard_mink_6d_checked_v1"
    trajectory = StatefulMinkTrajectory(
        feasible_planner,
        right_qpos_ids,
        [velocity_limits[name] for name in base.g1.RIGHT_ARM_JOINTS],
        [JOINT_MAX_ACCELERATION_RAD_S2] * 7,
        [JOINT_MAX_JERK_RAD_S3] * 7,
        base.DT,
    )
    if upstream_mink:
        collision_min_distance_m = qp_collision_min_distance_m = .005
        collision_detection_distance_m = .15
        collision_profile = "upstream-g1-example"
        local_tangent_steps_enabled = False
    live_bridge = None
    if live_cycle:
        from g1_mink_live_cycle_bridge import LiveCycleBridge, live_tracking_active
        live_bridge = LiveCycleBridge(comparison_profile["name"], base.DT)
    selected_proximal_deg_s = math.degrees(comparison_profile["velocity_rad_s"][0]) if cycle_enabled else PROXIMAL_MAX_JOINT_VELOCITY_DEG_S
    selected_wrist_deg_s = math.degrees(comparison_profile["velocity_rad_s"][4]) if cycle_enabled else WRIST_MAX_JOINT_VELOCITY_DEG_S
    return_cycle = None
    if cycle_enabled:
        from g1_mink_return_cycle import SimulationReturnCycle
        # Same limiter for tracking and return: do not reset velocity on pinch.
        trajectory = StatefulMinkTrajectory(
            feasible_planner, right_qpos_ids,
            [velocity_limits[name] for name in base.g1.RIGHT_ARM_JOINTS],
            comparison_profile["acceleration_rad_s2"], [JOINT_MAX_JERK_RAD_S3]*7, base.DT)
        return_cycle = SimulationReturnCycle(initial_q, trajectory, live_bridge.can_ack if live_bridge else None)
        if upstream_mink:
            from g1_upstream_mink_tracking import UpstreamMinkTracking
            trajectory = UpstreamMinkTracking(feasible_planner, right_qpos_ids,
                [velocity_limits[name] for name in base.g1.RIGHT_ARM_JOINTS],
                comparison_profile["acceleration_rad_s2"], [JOINT_MAX_JERK_RAD_S3]*7, base.DT)
            return_cycle = SimulationReturnCycle(initial_q, trajectory, live_bridge.can_ack if live_bridge else None)

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
    if initial_seed is not None:
        if not 0 <= time.time() - initial_seed["received_at_unix_s"] <= .25:
            raise ValueError("initial seed expired during setup")
        if not feasible_planner.CheckConfiguration(configuration.q):
            raise ValueError("initial seed collision or configuration rejection")
        model_metadata["initial_state_source"] = "validated_lowstate_seed_simulation"
        model_metadata["initial_state_session"] = initial_seed["session_id"]
        model_metadata["initial_state_q29"] = initial_seed["q"]
        model_metadata["initial_state_received_at_unix_s"] = initial_seed["received_at_unix_s"]
        model_metadata["base_translation_measured"] = False
        model_metadata["base_pose_measured"] = False
    if getattr(args, "initial_state_check_only", None):
        report = dict(passed=True, robot_output=False, sockets_opened=False,
                      actual_vr_engage=False, engine=mujoco.__version__,
                      session_id=initial_seed["session_id"],
                      seed_age_s=time.time()-initial_seed["received_at_unix_s"],
                      clearance_m=feasible_planner.GetClearance(configuration.q),
                      q29=[float(configuration.q[i]) for i in all_qpos_ids],
                      base_pose_measured=False)
        with args.initial_state_check_only.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps(report), flush=True)
        return
    udp = base._open_udp_socket()
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dry_run_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gate7_feedback_sock = None
    if not args.disable_gate7_simulation_feedback:
        gate7_feedback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        gate7_feedback_sock.bind(
            (GATE7_SIMULATION_FEEDBACK_HOST, args.gate7_feedback_port)
        )
        gate7_feedback_sock.setblocking(False)

    roll_pose = configuration.get_transform_frame_to_world(position_frame, "body")
    yaw_pose = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
    raw_target = yaw_pose.translation().copy()
    raw_rotation = np.array([0.0, 0.0, 0.0, 1.0])
    command_stream = base.MinkCommandStream(
        raw_target,
        raw_rotation,
        input_timeout_s=base.INPUT_TIMEOUT_S,
        simulation_return_handshake=cycle_enabled,
    )
    clutch_reference = None
    last_return_state = None
    return_transitions = []
    received_total = 0
    rejected_total = 0
    next_status = time.monotonic()
    next_state = time.monotonic()
    state_sequence = 0
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
    gate7_feedback = None
    gate7_feedback_received_at = float("-inf")
    gate7_feedback_stream_id = None
    gate7_feedback_sequence = -1
    gate7_feedback_accepted = 0
    gate7_feedback_rejected = 0
    gate7_feedback_applied = False
    trajectory_active = False
    trajectory_status = "inactive"
    trajectory_velocity_rad_s = (0.0,) * 7
    trajectory_acceleration_rad_s2 = (0.0,) * 7

    print("============================================================")
    print("G1 Mink LIVE VIRTUAL-CENTER experiment")
    if cycle_enabled:
        print("LIVE CYCLE CANDIDATE: UDP 5008 enabled; wait for G1 udp_ready; Select/B requests checked return" if live_cycle else "SIMULATION ARM CYCLE: pinch -> ready pose -> new idle/engage; UDP 5008 DISABLED")
        print(f"Cycle speed profile: {comparison_profile}; return ACK: {'G1 measured ready' if live_cycle else 'local model only'}")
    print(f"IK solver         : {ik_solver}")
    print(f"Internal position : {position_frame}")
    print("Internal rotation : right_wrist_yaw_link")
    print(f"Position mapping  : Quest wrist -> {position_frame}")
    print("Rotation mapping  : Quest wrist -> right_wrist_yaw_link orientation")
    print("Normal wrist-first proximal damping : 100.0 (finite, not frozen)")
    print(
        "Continuous proximal assist : starts below wrist margin "
        f"{ASSIST_RELEASE_MARGIN_DEG:.0f} deg, full by {ASSIST_FULL_MARGIN_DEG:.0f} deg"
    )
    print("Collision avoidance: ENABLED")
    if upstream_mink:
        print("MINK: 5 mm minimum / 150 mm detection, reduced velocity QP with checked braking")
        print("Exact geometry guard retained; infeasible/collision steps hold the simulation model.")
        print("Tracking acceleration constrained inside QP; no Ruckig/jerk filter in tracking. Return uses Ruckig.")
    print("Green target: checked local IK look-ahead; raw hand goal stays unchanged")
    print("Speed modes : NONE")
    print("Hard freeze : NONE")
    print(
        "Joint speed : shoulder/elbow max "
        f"{math.degrees(velocity_limits[base.g1.RIGHT_ARM_JOINTS[0]]):.0f} deg/s, wrist max "
        f"{math.degrees(velocity_limits[base.g1.RIGHT_ARM_JOINTS[4]]):.0f} deg/s"
    )
    print(
        "Inspection demo : approach "
        f"{INSPECTION_APPROACH_RADIUS_M * 100:.0f} cm, contact "
        f"{INSPECTION_CONTACT_RADIUS_M * 100:.0f} cm, hold "
        f"{INSPECTION_HOLD_SECONDS:.2f} s"
    )
    print(
        "Inspection scene: "
        + ("VISIBLE" if args.show_inspection_scene else "HIDDEN (preserved in model)")
    )
    print(
        "Gate 7 MuJoCo feedback: "
        + (
            "DISABLED"
            if gate7_feedback_sock is None
            else f"udp://127.0.0.1:{args.gate7_feedback_port} (SIMULATION ONLY)"
        )
    )
    print("============================================================")

    tracking_diagnostic = None
    if cycle_enabled:
        from g1_tracking_diagnostic import TrackingDiagnostic
        diagnostic_dir = Path(__file__).resolve().parents[2] / "logs" / "test_results"
        diagnostic_dir.mkdir(parents=True, exist_ok=True)
        tracking_diagnostic = TrackingDiagnostic(diagnostic_dir / f"mink_blocked_{comparison_profile['name']}_{time.time_ns()}.jsonl")
        print(f"[DIAGNOSTIC] {tracking_diagnostic.path}", flush=True)
    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            while viewer.is_running():
                cycle_start = time.perf_counter()
                now = time.monotonic()

                if live_bridge:
                    live_bridge.poll(command_stream)
                command_update = command_stream.poll(udp)
                return_step = None
                if return_cycle is not None:
                    return_step = return_cycle.step(command_stream, configuration, now)
                    if command_stream.return_state != last_return_state:
                        last_return_state = command_stream.return_state
                        return_transitions.append({"time": time.strftime("%H:%M:%S"),
                            "state": last_return_state,
                            "mode": command_update.input_command_mode,
                            "reason": return_cycle.reason or command_stream.return_fault_reason})
                        return_transitions = return_transitions[-32:]
                        print(f"\n[{'PC LOCAL (not G1 readiness)' if live_cycle else 'SIM'} ARM CYCLE] {last_return_state} {return_cycle.reason or command_stream.return_fault_reason}", flush=True)
                raw_target = command_update.target_position_m
                raw_rotation = command_update.target_quaternion_xyzw
                received_total += command_update.accepted_count
                rejected_total += command_update.rejected_count
                active = (live_tracking_active(command_update)
                          if live_cycle else command_update.command_active)
                if gate7_feedback_sock is not None:
                    (
                        new_feedback,
                        gate7_feedback_stream_id,
                        gate7_feedback_sequence,
                        accepted_feedback,
                        rejected_feedback,
                    ) = drain_gate7_simulation_feedback(
                        gate7_feedback_sock,
                        gate7_feedback_stream_id,
                        gate7_feedback_sequence,
                    )
                    gate7_feedback_accepted += accepted_feedback
                    gate7_feedback_rejected += rejected_feedback
                    if new_feedback is not None:
                        gate7_feedback = new_feedback
                        gate7_feedback_received_at = now

                feedback_age_s = max(0.0, now - gate7_feedback_received_at)
                gate7_feedback_applied = should_apply_gate7_feedback(
                    gate7_feedback,
                    command_active=active,
                    packet_age_s=feedback_age_s,
                    timeout_s=GATE7_SIMULATION_FEEDBACK_TIMEOUT_S,
                )
                if gate7_feedback_applied and gate7_feedback is not None:
                    apply_gate7_simulation_feedback(
                        configuration,
                        all_qpos_ids,
                        gate7_feedback,
                    )
                    clutch_reference = None

                roll_pose = configuration.get_transform_frame_to_world(
                    position_frame, "body"
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
                        "yaw_rotation": yaw_pose.rotation().as_matrix().copy(),
                    }
                    target_rotation = clutch_reference["yaw_rotation"].copy()
                    posture_task.set_target(configuration.q.copy())
                    feasible_planner.ResetDetour()
                    trajectory.Reset(configuration.q.copy())
                    trajectory_active = True
                    VirtualCenterOrientationTask.assist_latched = False
                    operator_target_position = roll_pose.translation().copy()
                    feasible_target_position = roll_pose.translation().copy()
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
                        clutch_reference["center_position"] + input_position_delta
                    )
                    input_rotation = base.g1.operator_rotation_to_robot_matrix(raw_rotation)
                    rotation_delta = input_rotation @ clutch_reference["input_rotation"].T
                    desired_target_rotation = rotation_delta @ clutch_reference["yaw_rotation"]
                    target_center_position = operator_target_position.copy()
                    target_rotation = desired_target_rotation

                    tracking_start_q = configuration.q.copy()
                    if upstream_mink:
                        from g1_mink_feasible_target import FeasiblePlan
                        trajectory_step = trajectory.Track(tracking_start_q,
                            base._matrix_to_se3(target_rotation, target_center_position))
                        feasible_plan = FeasiblePlan(trajectory_step.q, trajectory_step.q,
                            feasible_planner.configuration.get_transform_frame_to_world(position_frame, "body").translation().copy(),
                            trajectory_step.applied,
                            "upstream_mink_following" if trajectory_step.applied else trajectory_step.status,
                            int(trajectory_step.applied))
                    else:
                        feasible_plan = feasible_planner.Plan(
                            configuration.q.copy(),
                            base._matrix_to_se3(target_rotation, target_center_position),
                            position_target=target_center_position,
                        )
                    if feasible_plan.accepted_steps > 0:
                        if not upstream_mink:
                            trajectory_step = trajectory.Step(
                                configuration.q.copy(),
                                feasible_plan.target_q,
                            )
                        configuration.update(trajectory_step.q)
                        trajectory_status = trajectory_step.status
                        trajectory_velocity_rad_s = trajectory_step.velocity_rad_s
                        trajectory_acceleration_rad_s2 = (
                            trajectory_step.acceleration_rad_s2
                        )
                    else:
                        trajectory.Reset(configuration.q.copy())
                        trajectory_status = trajectory_step.status if upstream_mink else "trajectory_planner_hold"
                        trajectory_velocity_rad_s = (0.0,) * 7
                        trajectory_acceleration_rad_s2 = (0.0,) * 7
                    feasible_target_position = feasible_plan.target_position
                    feasible_target_valid = feasible_plan.valid
                    feasible_target_status = feasible_plan.status
                    if tracking_diagnostic is not None:
                        tracking_diagnostic.record(now, feasible_plan.status,
                            feasible_plan.accepted_steps, trajectory_status,
                            tracking_start_q, target_center_position, target_rotation,
                            feasible_plan.target_q,
                            trajectory.rejected_sample if upstream_mink or feasible_plan.accepted_steps > 0 else None,
                            feasible_planner, trajectory)
                else:
                    if trajectory_active and return_step is None:
                        trajectory.Reset(configuration.q.copy())
                    trajectory_active = return_step is not None
                    trajectory_status = return_step.status if return_step else "inactive"
                    trajectory_velocity_rad_s = return_step.velocity_rad_s if return_step else (0.0,) * 7
                    trajectory_acceleration_rad_s2 = return_step.acceleration_rad_s2 if return_step else (0.0,) * 7
                    target_center_position = roll_pose.translation().copy()
                    target_rotation = yaw_pose.rotation().as_matrix().copy()
                    operator_target_position = roll_pose.translation().copy()
                    feasible_target_position = roll_pose.translation().copy()
                    feasible_target_valid = False
                    feasible_target_status = "inactive"
                    input_position_delta = np.zeros(3)
                    position_task.set_target_from_configuration(configuration)
                    orientation_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    feasible_planner.ResetDetour()
                    VirtualCenterOrientationTask.assist_latched = False
                    VirtualCenterOrientationTask.last_assist_gain = 0.0

                mujoco.mj_forward(model, configuration.data)
                roll_pose = configuration.get_transform_frame_to_world(
                    position_frame, "body"
                )
                yaw_pose = configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body"
                )

                center_error = target_center_position - roll_pose.translation()
                external_target_position = operator_target_position.copy()
                configuration.data.mocap_pos[target_mocap_id] = external_target_position
                current_rotation = yaw_pose.rotation().as_matrix()
                orientation_error_deg = math.degrees(
                    base._rotation_error_radians(target_rotation, current_rotation)
                )
                position_error = float(np.linalg.norm(center_error))

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
                collision_limited = bool(
                    min_clearance is not None
                    and min_clearance <= collision_detection_distance_m
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
                if args.show_inspection_scene:
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
                            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "session_id": command_update.session_id or "",
                            "elapsed_s": round(inspection_snapshot.elapsed_s, 4),
                            "final_distance_m": round(inspection_snapshot.distance_m, 6),
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

                # Live sample_time advances by one IK step per packet. Never decimate it
                # with the separate wall-clock display timer.
                if live_cycle or now >= next_state:
                    packet = base._state_packet(
                        configuration,
                        right_qpos_ids,
                        all_qpos_ids,
                        active,
                        external_target_position,
                            None if clutch_reference is None
                            else clutch_reference["center_position"],
                        collision_limited,
                        minimum_clearance_m=min_clearance,
                        workspace_limited=False,
                        control_state=command_update.control_state,
                        input_command_mode=command_update.input_command_mode,
                        state_sequence=state_sequence,
                        session_id=command_update.session_id,
                        input_packet_age_s=command_update.packet_age_s,
                    )
                    state_sequence += 1
                    packet["model_metadata"] = model_metadata
                    packet["right_arm"]["position_error"] = position_error
                    packet["right_arm"].update({
                        "ik_solver": ik_solver,
                        "position_task_frame": position_frame,
                        "collision_profile": collision_profile,
                        "collision_min_distance_m": collision_min_distance_m,
                        "collision_detection_distance_m": collision_detection_distance_m,
                        "feasible_target_position": feasible_target_position.tolist(),
                            "feasible_target_delta": (
                                feasible_target_position - (
                                    roll_pose.translation() if clutch_reference is None
                                    else clutch_reference["center_position"]
                                )
                            ).tolist(),
                        "feasible_target_valid": feasible_target_valid,
                        "feasible_target_status": feasible_target_status,
                        "feasible_target_policy": feasible_target_policy,
                        "trajectory_status": trajectory_status,
                        "trajectory_velocity_rad_s": list(
                            trajectory_velocity_rad_s
                        ),
                        "trajectory_acceleration_rad_s2": list(
                            trajectory_acceleration_rad_s2
                        ),
                    })
                    packet["right_arm"]["orientation_error_deg"] = orientation_error_deg
                    packet["right_arm"].update(
                        orientation_diagnostics(target_rotation, current_rotation)
                    )
                    packet["right_arm"]["orientation_assist_gain"] = (
                        VirtualCenterOrientationTask.last_assist_gain
                    )
                    packet["right_arm"]["orientation_cost_scale"] = (
                        VirtualCenterOrientationTask.last_orientation_cost_scale
                    )
                    packet["right_arm"]["min_wrist_limit_margin_deg"] = (
                        VirtualCenterOrientationTask.last_min_wrist_margin_deg
                    )
                    packet["right_arm"]["wrist_jacobian_sigma_min"] = (
                        VirtualCenterOrientationTask.last_wrist_jacobian_sigma_min
                    )
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
                        "minimum_distance_m": inspection_snapshot.minimum_distance_m,
                        "complete": inspection_snapshot.state.value == "complete",
                    }
                    _send_state = base._send_state
                    if simulation_arm_cycle:
                        from g1_mink_command_provenance import mark_simulation_cycle_packet
                        mark_simulation_cycle_packet(packet)
                        packet["simulation_arm_cycle"] = {
                            "state": command_stream.return_state,
                            "epoch": command_stream.return_epoch,
                            "reason": return_cycle.reason,
                            "candidate_output_disabled": True,
                        }
                    _send_state(
                        state_sock,
                        packet,
                        base.UNITY_STATE_HOST,
                        base.UNITY_STATE_PORT,
                    )
                    if live_bridge:
                        live_bridge.send(packet, command_stream)
                    if not cycle_enabled:
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
                            "tracking_diagnostic_path": str(tracking_diagnostic.path) if tracking_diagnostic else None,
                            "last_blocked_tracking": tracking_diagnostic.latest if tracking_diagnostic else None,
                            "simulation_arm_cycle": simulation_arm_cycle,
                            "live_cycle_candidate": live_cycle,
                            "speed_comparison_profile": comparison_profile if cycle_enabled else None,
                            "upstream_mink_collision": upstream_mink,
                            "tracking_collision_flow": "mink_position_priority_recovery_v5" if upstream_mink else "checked_planner_ruckig",
                            "position_priority_active": bool(getattr(trajectory, "position_priority_active", False)),
                            "orientation_priority_scale": float(getattr(trajectory, "orientation_priority_scale", 1.)),
                            "elbow_reconfiguration_active": bool(getattr(trajectory, "elbow_assist_active", False)),
                            "corrected_zero_distance_pairs": int(getattr(trajectory, "corrected_zero_distances", 0)),
                            "arm_cycle_state": command_stream.return_state if cycle_enabled else None,
                            "arm_cycle_reason": return_cycle.reason if return_cycle else None,
                            "arm_cycle_input_fault": command_stream.return_fault_reason if cycle_enabled else None,
                            "arm_cycle_transitions": return_transitions if cycle_enabled else None,
                            "arm_cycle_rejection": return_cycle.rejection if return_cycle else None,
                            "input_active": active,
                            "input_control_state": command_update.control_state,
                            "input_command_mode": command_update.input_command_mode,
                            "input_session_id": command_update.session_id,
                            "input_packet_age_s": command_update.packet_age_s,
                            "gate7_simulation_feedback_enabled": (
                                gate7_feedback_sock is not None
                            ),
                            "gate7_simulation_feedback_applied": (
                                gate7_feedback_applied
                            ),
                            "gate7_simulation_feedback_state": (
                                None if gate7_feedback is None else gate7_feedback.state
                            ),
                            "gate7_simulation_feedback_age_s": (
                                None if gate7_feedback is None else feedback_age_s
                            ),
                            "gate7_simulation_feedback_accepted": (
                                gate7_feedback_accepted
                            ),
                            "gate7_simulation_feedback_rejected": (
                                gate7_feedback_rejected
                            ),
                            "clutch_engaged": command_update.clutch_engaged,
                            "workspace_fault": command_update.workspace_fault,
                            "received_packets": received_total,
                            "rejected_packets": rejected_total,
                            "solver": solver,
                            "collision_profile": collision_profile,
                            "collision_pair_count": len(collision_pairs),
                            "collision_min_distance_m": collision_min_distance_m,
                            "qp_collision_min_distance_m": qp_collision_min_distance_m,
                            "gate7_hard_stop_distance_m": base.COLLISION_MIN_DISTANCE_M,
                            "collision_detection_distance_m": collision_detection_distance_m,
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
                            "position_task_frame": position_frame,
                            "ik_solver": ik_solver,
                            "orientation_task_frame": "right_wrist_yaw_link",
                            "external_state_frame": "right_wrist_yaw_link",
                            "target_position": external_target_position.tolist(),
                            **orientation_diagnostics(target_rotation, current_rotation),
                            "operator_target_position": operator_target_position.tolist(),
                            "feasible_target_position": feasible_target_position.tolist(),
                            "feasible_target_valid": feasible_target_valid,
                            "feasible_target_status": feasible_target_status,
                            "feasible_target_policy": feasible_target_policy,
                            "trajectory_policy": "upstream_qp_acceleration_bounded_exact_checked" if upstream_mink and active else "ruckig_checked_prototype_limits_v1",
                            "trajectory_status": trajectory_status,
                            "trajectory_velocity_rad_s": list(
                                trajectory_velocity_rad_s
                            ),
                            "trajectory_acceleration_rad_s2": list(
                                trajectory_acceleration_rad_s2
                            ),
                            "trajectory_max_acceleration_rad_s2": (
                                comparison_profile["acceleration_rad_s2"][0] if cycle_enabled else JOINT_MAX_ACCELERATION_RAD_S2
                            ),
                            "trajectory_max_velocity_rad_s": list(trajectory.velocity_limits),
                            "trajectory_max_jerk_rad_s3": None if upstream_mink and active else JOINT_MAX_JERK_RAD_S3,
                            "input_position_delta": input_position_delta.tolist(),
                            "external_target_delta": (
                                external_target_position
                                - (
                                    yaw_pose.translation()
                                    if clutch_reference is None
                                    else clutch_reference["center_position"]
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
                            "wrist_jacobian_sigma_min": (
                                VirtualCenterOrientationTask.last_wrist_jacobian_sigma_min
                            ),
                            "wrist_limit_assist_latched": (
                                VirtualCenterOrientationTask.assist_latched
                            ),
                            "inspection_state": inspection_snapshot.state.value,
                            "inspection_target_source": "static_demo",
                            "inspection_target_position": inspection_target_position.tolist(),
                            "inspection_tool_tip_position": inspection_tool_position.tolist(),
                            "inspection_distance_m": inspection_snapshot.distance_m,
                            "inspection_hold_progress": inspection_snapshot.hold_progress,
                            "inspection_elapsed_s": inspection_snapshot.elapsed_s,
                            "inspection_complete": inspection_snapshot.state.value == "complete",
                            "speed_based_mode_switch": False,
                            "proximal_hard_freeze": False,
                            "max_joint_velocity_deg_s": selected_wrist_deg_s,
                            "max_proximal_joint_velocity_deg_s": (
                                selected_proximal_deg_s
                            ),
                            "max_wrist_joint_velocity_deg_s": (
                                selected_wrist_deg_s
                            ),
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
        if live_bridge:
            live_bridge.close()
        if tracking_diagnostic is not None:
            tracking_diagnostic.close()
        udp.close()
        state_sock.close()
        dry_run_sock.close()
        if gate7_feedback_sock is not None:
            gate7_feedback_sock.close()


if __name__ == "__main__":
    main()
