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
from g1_mink_feasible_target import FeasibleTargetPlanner
from g1_teleop.inspection_demo import (
    InspectionDemoTracker,
    append_inspection_result,
)
from g1_teleop.gate7_simulation_feedback import (
    DUAL_ARM_JOINT_INDICES,
    Gate7SimulationFeedback,
    Gate7SimulationFeedbackError,
    parse_packet as parse_gate7_feedback_packet,
    should_apply as should_apply_gate7_feedback,
)


# static stand 키보드 기본 1배 속도: 모든 팔 관절에 0.08 rad/s.
PROXIMAL_MAX_JOINT_VELOCITY_DEG_S = math.degrees(0.08)
WRIST_MAX_JOINT_VELOCITY_DEG_S = math.degrees(0.08)
# 관절 이동 비용과 자세 복원 비용을 구분한다. 모터 감쇠 게인과는 별개다.
VIRTUAL_CENTER_PROXIMAL_DAMPING_COST = 0.03
VIRTUAL_CENTER_WRIST_DAMPING_COST = 0.015
VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE = 0.05

# MuJoCo-only operation can reproduce upstream Mink's CollisionAvoidanceLimit
# defaults.  Physical Gate 7 keeps a separate, explicit margin above its
# independent 12 mm command stop.
COLLISION_PROFILE_MINK_DEFAULT = "mink-default"
COLLISION_PROFILE_HARDWARE_GUARDED = "hardware-guarded"
COLLISION_PROFILES = {
    COLLISION_PROFILE_MINK_DEFAULT: (0.005, 0.010),
    COLLISION_PROFILE_HARDWARE_GUARDED: (0.020, 0.040),
}
MINK_DEFAULT_QP_RESERVE_M = 0.0005

# Compatibility name for offline tools that intentionally audit the guarded
# physical-output candidate policy. New runtime code resolves a named profile.
TELEOP_COLLISION_TARGET_DISTANCE_M = COLLISION_PROFILES[
    COLLISION_PROFILE_HARDWARE_GUARDED
][0]


def ResolveCollisionProfile(name: str) -> tuple[float, float]:
    """Return (minimum, detection) distances for one named runtime profile."""
    try:
        return COLLISION_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown collision profile: {name}") from exc

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
GATE7_SIMULATION_FEEDBACK_HOST = "127.0.0.1"
GATE7_SIMULATION_FEEDBACK_PORT = 5012
GATE7_SIMULATION_FEEDBACK_TIMEOUT_S = 0.25
MAX_GATE7_FEEDBACK_PACKET_BYTES = 16384


def virtual_center_damping_costs(model: mujoco.MjModel) -> np.ndarray:
    """기준 제어기 상수를 바꾸지 않고 이 제어기 전용 관절 감쇠를 만든다."""
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


def virtual_center_posture_costs(model: mujoco.MjModel) -> np.ndarray:
    """회전식을 변형하지 않고 손목의 중립 자세 복원 비용만 낮춘다."""
    costs = np.full(int(model.nv), base.POSTURE_COST, dtype=float)
    for name in base.g1.RIGHT_ARM_JOINTS[4:]:
        dof = int(model.jnt_dofadr[base._joint_id(model, name)])
        costs[dof] *= VIRTUAL_CENTER_WRIST_POSTURE_COST_SCALE
    return costs


def orientation_diagnostics(target_rotation, wrist_rotation) -> dict:
    """오차 크기만이 아닌 목표/실제 회전도 기록해 오프라인 재현에 사용한다."""
    return {
        "target_rotation_matrix_robot": target_rotation.tolist(),
        "wrist_rotation_matrix_robot": wrist_rotation.tolist(),
        "orientation_solver_policy": "exact_jacobian_weighted_posture_v1",
    }


def virtual_center_velocity_limits() -> dict[str, float]:
    """어깨/팔꿈치는 안정적으로, 손목 3축은 더 빠르게 제한한다."""
    return {
        name: math.radians(
            PROXIMAL_MAX_JOINT_VELOCITY_DEG_S
            if index < 4
            else WRIST_MAX_JOINT_VELOCITY_DEG_S
        )
        for index, name in enumerate(base.g1.RIGHT_ARM_JOINTS)
    }


def orientation_limit_policy(
    min_margin_deg: float,
    assist_latched: bool,
) -> tuple[bool, float, float, float]:
    """손목 한계 여유로 보조 상태 표시값과 회전 비용/오차 상한을 정한다."""
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
    """정확한 yaw-link 회전식과 손목 한계 근처의 추종 완화를 사용한다."""

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
        # 어깨/팔꿈치 열을 줄이면 실제 회전 변화와 QP의 예측이 달라진다.
        # 손목 우선 선택은 별도의 자세 비용에서 처리한다.
        return self.inner.compute_jacobian(configuration)


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
    return parser.parse_args()


def drain_gate7_simulation_feedback(
    sock: socket.socket,
    last_stream_id: str | None,
    last_sequence: int,
) -> tuple[Gate7SimulationFeedback | None, str | None, int, int, int]:
    """Drain localhost feedback and retain only the newest ordered packet."""
    latest = None
    accepted = 0
    rejected = 0
    stream_id = last_stream_id
    sequence = last_sequence
    while True:
        try:
            payload, source = sock.recvfrom(MAX_GATE7_FEEDBACK_PACKET_BYTES)
        except BlockingIOError:
            break
        if source[0] != GATE7_SIMULATION_FEEDBACK_HOST:
            rejected += 1
            continue
        try:
            packet = parse_gate7_feedback_packet(payload)
        except (Gate7SimulationFeedbackError, TypeError, ValueError):
            rejected += 1
            continue
        if packet.stream_id != stream_id:
            stream_id = packet.stream_id
            sequence = -1
        if packet.sequence <= sequence:
            rejected += 1
            continue
        sequence = packet.sequence
        latest = packet
        accepted += 1
    return latest, stream_id, sequence, accepted, rejected


def apply_gate7_simulation_feedback(
    configuration: mink.Configuration,
    all_qpos_ids: list[int],
    feedback: Gate7SimulationFeedback,
) -> None:
    """Apply only the 14 arm joints to the in-memory MuJoCo configuration."""
    if len(all_qpos_ids) != 29:
        raise ValueError("all_qpos_ids must contain all 29 G1 joints")
    feedback_q = configuration.q.copy()
    for joint_index, value in zip(
        DUAL_ARM_JOINT_INDICES,
        feedback.dual_arm_q_rad,
    ):
        feedback_q[all_qpos_ids[joint_index]] = value
    configuration.update(feedback_q)


def main() -> None:
    """모델/task/통신을 준비하고 입력 -> 상대 목표 -> QP -> 상태 송신을 반복한다.

    qpos를 갱신하는 기구학 시뮬레이션이다. 실측 모터 응답은 별도 하드웨어 경로에서
    rt/lowstate로 확인하며, 이 함수의 계산 결과를 실측으로 취급하지 않는다.
    """
    args = parse_args()
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
        MINK_DEFAULT_QP_RESERVE_M if local_tangent_steps_enabled else 0.0
    )
    base._prepare_mink_xml(show_inspection_scene=args.show_inspection_scene)
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
    all_qpos_ids = [
        int(model.jnt_qposadr[base._joint_id(model, name)])
        for name in base.g1.G1_29_JOINTS
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

    posture_task = mink.PostureTask(model, cost=virtual_center_posture_costs(model))
    posture_task.set_target(configuration.q.copy())
    damping_task = mink.DampingTask(
        model,
        cost=virtual_center_damping_costs(model),
    )

    velocity_limits = virtual_center_velocity_limits()
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
    feasible_planner = FeasibleTargetPlanner(
        model, position_task, orientation_task, posture_task, damping_task,
        limits, constraints, solver, collision_min_distance_m,
        velocity_limits,
        require_merit_decrease=not local_tangent_steps_enabled,
        allow_local_detour=local_tangent_steps_enabled,
    )
    feasible_target_policy = (
        "mink_local_detour_checked_v1"
        if local_tangent_steps_enabled
        else "checked_local_lookahead_v1"
    )

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
    gate7_feedback_sock = None
    if not args.disable_gate7_simulation_feedback:
        gate7_feedback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        gate7_feedback_sock.bind(
            (GATE7_SIMULATION_FEEDBACK_HOST, args.gate7_feedback_port)
        )
        gate7_feedback_sock.setblocking(False)

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
    print("Green target: checked local IK look-ahead; raw hand goal stays unchanged")
    print("Speed modes : NONE")
    print("Hard freeze : NONE")
    print(
        "Joint speed : shoulder/elbow max "
        f"{PROXIMAL_MAX_JOINT_VELOCITY_DEG_S:.0f} deg/s, wrist max "
        f"{WRIST_MAX_JOINT_VELOCITY_DEG_S:.0f} deg/s"
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
                    # A completed safety return invalidates the old operator
                    # offset. Require the normal explicit alignment before the
                    # next active hand-tracking session.
                    clutch_reference = None
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
                    feasible_planner.ResetDetour()
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

                    # 원래 손 목표는 보존한다. 별도 QP 예측 경로의 첫 단계만
                    # 적용하고, 검증된 앞쪽 자세의 FK를 초록 목표로 보낸다.
                    feasible_plan = feasible_planner.Plan(
                        configuration.q.copy(),
                        base._matrix_to_se3(target_rotation, operator_target_position),
                    )
                    configuration.update(feasible_plan.next_q)
                    feasible_target_position = feasible_plan.target_position
                    feasible_target_valid = feasible_plan.valid
                    feasible_target_status = feasible_plan.status
                else:
                    target_center_position = roll_pose.translation().copy()
                    target_rotation = yaw_pose.rotation().as_matrix().copy()
                    operator_target_position = yaw_pose.translation().copy()
                    feasible_target_position = yaw_pose.translation().copy()
                    feasible_target_valid = False
                    feasible_target_status = "inactive"
                    input_position_delta = np.zeros(3)
                    position_task.set_target_from_configuration(configuration)
                    orientation_task.set_target_from_configuration(configuration)
                    posture_task.set_target(configuration.q.copy())
                    feasible_planner.ResetDetour()
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
                        all_qpos_ids,
                        active,
                        external_target_position,
                        None if clutch_reference is None else clutch_reference["yaw_position"],
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
                    packet["right_arm"]["position_error"] = position_error
                    packet["right_arm"].update({
                        "collision_profile": collision_profile,
                        "collision_min_distance_m": collision_min_distance_m,
                        "collision_detection_distance_m": (
                            collision_detection_distance_m
                        ),
                        "feasible_target_position": feasible_target_position.tolist(),
                        "feasible_target_delta": (
                            feasible_target_position - (
                                yaw_pose.translation() if clutch_reference is None
                                else clutch_reference["yaw_position"]
                            )
                        ).tolist(),
                        "feasible_target_valid": feasible_target_valid,
                        "feasible_target_status": feasible_target_status,
                        "feasible_target_policy": feasible_target_policy,
                    })
                    packet["right_arm"]["orientation_error_deg"] = orientation_error_deg
                    packet["right_arm"].update(orientation_diagnostics(target_rotation, current_rotation))
                    packet["right_arm"]["orientation_assist_gain"] = (
                        VirtualCenterOrientationTask.last_assist_gain
                    )
                    packet["right_arm"]["orientation_cost_scale"] = (
                        VirtualCenterOrientationTask.last_orientation_cost_scale
                    )
                    packet["right_arm"]["min_wrist_limit_margin_deg"] = (
                        VirtualCenterOrientationTask.last_min_wrist_margin_deg
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
                                None
                                if gate7_feedback is None
                                else feedback_age_s
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
                            "qp_collision_min_distance_m": (
                                qp_collision_min_distance_m
                            ),
                            "gate7_hard_stop_distance_m": (
                                base.COLLISION_MIN_DISTANCE_M
                            ),
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
                            "position_task_frame": "right_wrist_roll_link",
                            "orientation_task_frame": "right_wrist_yaw_link",
                            "external_state_frame": "right_wrist_yaw_link",
                            "target_position": external_target_position.tolist(),
                            **orientation_diagnostics(target_rotation, current_rotation),
                            "operator_target_position": operator_target_position.tolist(),
                            "feasible_target_position": feasible_target_position.tolist(),
                            "feasible_target_valid": feasible_target_valid,
                            "feasible_target_status": feasible_target_status,
                            "feasible_target_policy": feasible_target_policy,
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
                            "max_joint_velocity_deg_s": WRIST_MAX_JOINT_VELOCITY_DEG_S,
                            "max_proximal_joint_velocity_deg_s": (
                                PROXIMAL_MAX_JOINT_VELOCITY_DEG_S
                            ),
                            "max_wrist_joint_velocity_deg_s": (
                                WRIST_MAX_JOINT_VELOCITY_DEG_S
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
        udp.close()
        state_sock.close()
        dry_run_sock.close()
        if gate7_feedback_sock is not None:
            gate7_feedback_sock.close()


if __name__ == "__main__":
    main()
