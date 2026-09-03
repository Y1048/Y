#!/usr/bin/env python3
"""실제 G1 29관절 LowState를 MuJoCo에 계속 표시하는 읽기 전용 Viewer.

Windows UDP telemetry만 수신하며 Unitree SDK, DDS publisher 및 로봇 명령 경로를
만들지 않는다. 첫 유효 패킷은 즉시 적용하고 이후 패킷은 짧게 보간한다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from gate5_lowstate_safety_monitor import (
    LowStatePacketError,
    LowStateTelemetry,
    parse_lowstate_telemetry,
)
from g1_base_state import MultiplyQuaternionWXYZ, NormalizeQuaternionWXYZ
from g1_joint_contract import G1_29_JOINT_NAMES
from g1_unity_state_bridge import (
    BuildUnityHardwareStatePacket,
    DEFAULT_UNITY_HARDWARE_HOST,
    DEFAULT_UNITY_HARDWARE_PORT,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5009
DEFAULT_STALE_TIMEOUT_S = 0.25
DEFAULT_SMOOTHING_TIME_S = 0.035
MAX_PACKET_BYTES = 8192
INSPECTION_SCENE_GEOM_NAMES = (
    "inspection_demo_target_marker",
    "inspection_panel",
    "inspection_tool_tip",
    "inspection_tool_grip",
    "inspection_tool_probe",
)


@dataclass
class StreamState:
    session_id: str | None = None
    sequence: int = -1
    packet: LowStateTelemetry | None = None
    received_monotonic: float = float("-inf")
    accepted_packets: int = 0
    rejected_packets: int = 0

    def Accept(self, packet: LowStateTelemetry, received_monotonic: float) -> bool:
        """새 bridge 세션은 허용하되 같은 세션의 역순 패킷은 버린다."""
        if packet.bridge_session_id != self.session_id:
            self.session_id = packet.bridge_session_id
            self.sequence = -1
        if packet.sequence <= self.sequence:
            self.rejected_packets += 1
            return False
        self.sequence = packet.sequence
        self.packet = packet
        self.received_monotonic = received_monotonic
        self.accepted_packets += 1
        return True


@dataclass(frozen=True)
class BaseBodyPose:
    body_id: int
    initial_position_m: np.ndarray
    initial_quaternion_wxyz: np.ndarray


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continuously mirror READ-ONLY G1 29-joint LowState in MuJoCo"
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--startup-timeout", type=float, default=8.0)
    parser.add_argument("--stale-timeout", type=float, default=DEFAULT_STALE_TIMEOUT_S)
    parser.add_argument(
        "--smoothing-time", type=float, default=DEFAULT_SMOOTHING_TIME_S
    )
    parser.add_argument(
        "--show-inspection-scene",
        action="store_true",
        help="Show the preserved inspection panel, marker, and hand tool",
    )
    parser.add_argument("--unity-host", default=DEFAULT_UNITY_HARDWARE_HOST)
    parser.add_argument(
        "--unity-port",
        type=int,
        default=0,
        help=(
            "Forward read-only 29-joint state to Unity hardware preview; "
            f"use {DEFAULT_UNITY_HARDWARE_PORT} to enable"
        ),
    )
    parser.add_argument(
        "--measurement-log",
        default="",
        help=(
            "Write source/MuJoCo/Unity mirror measurements as JSONL; "
            "use 'auto' for logs/runtime/g1_visual_mirror_<timestamp>.jsonl"
        ),
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def ResolveMeasurementLogPath(value: str) -> Path | None:
    normalized_value = value.strip()
    if not normalized_value:
        return None
    if normalized_value.lower() == "auto":
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return PROJECT_ROOT / "logs" / "runtime" / (
            f"g1_visual_mirror_{timestamp}.jsonl"
        )
    path_value = Path(normalized_value).expanduser()
    return path_value if path_value.is_absolute() else PROJECT_ROOT / path_value


def BuildMirrorMeasurement(
    unity_payload: dict[str, object],
    packet_age_s: float,
) -> dict[str, object] | None:
    diagnostics = unity_payload.get("mirror_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    return {
        "schema": "g1.visual_mirror.measurement.v1",
        "timestamp_unix": time.time(),
        "session_id": unity_payload["session_id"],
        "sequence": unity_payload["sequence"],
        "source_packet_age_s": packet_age_s,
        "source_base_position_m": diagnostics["source_base_position_m"],
        "mujoco_displayed_base_position_m": diagnostics[
            "displayed_base_position_m"
        ],
        "unity_commanded_base_position_m": diagnostics[
            "displayed_base_position_m"
        ],
        "source_base_quaternion_xyzw": diagnostics[
            "source_base_quaternion_xyzw"
        ],
        "mujoco_displayed_base_quaternion_xyzw": diagnostics[
            "displayed_base_quaternion_xyzw"
        ],
        "unity_commanded_base_quaternion_xyzw": diagnostics[
            "displayed_base_quaternion_xyzw"
        ],
        "source_to_mujoco_position_error_m": diagnostics[
            "base_position_error_m"
        ],
        "source_to_mujoco_orientation_error_deg": diagnostics[
            "base_orientation_error_deg"
        ],
        "source_to_mujoco_max_joint_error_rad": diagnostics[
            "max_joint_position_error_rad"
        ],
    }


def AdvancePose(
    current: np.ndarray,
    target: np.ndarray,
    dt_s: float,
    smoothing_time_s: float,
) -> np.ndarray:
    """오버슈트 없는 1차 보간으로 30 Hz 입력을 부드럽게 표시한다."""
    if smoothing_time_s <= 0.0:
        return target.copy()
    alpha = 1.0 - math.exp(-max(0.0, dt_s) / smoothing_time_s)
    return current + alpha * (target - current)


def AdvanceQuaternion(
    current_xyzw: np.ndarray,
    target_xyzw: np.ndarray,
    dt_s: float,
    smoothing_time_s: float,
) -> np.ndarray:
    """최단 quaternion 호를 정규화 보간해 부호 점프와 오버슈트를 막는다."""
    current = np.asarray(current_xyzw, dtype=float)
    target = np.asarray(target_xyzw, dtype=float)
    if current.shape != (4,) or target.shape != (4,):
        raise ValueError("base quaternion must contain four XYZW values")
    current /= np.linalg.norm(current)
    target /= np.linalg.norm(target)
    if float(np.dot(current, target)) < 0.0:
        target = -target
    if smoothing_time_s <= 0.0:
        return target.copy()
    alpha = 1.0 - math.exp(-max(0.0, dt_s) / smoothing_time_s)
    result = current + alpha * (target - current)
    return result / np.linalg.norm(result)


def FullBodyPose(packet: LowStateTelemetry) -> np.ndarray:
    """29관절 이름/위치/속도 계약이 완전한 패킷의 관절 위치를 반환한다."""
    if (
        packet.all_joint_names is None
        or packet.all_joint_q_rad is None
        or packet.all_joint_dq_rad_s is None
    ):
        raise LowStatePacketError(
            "full 29-joint names, positions, and velocities are required"
        )
    if packet.all_joint_names != G1_29_JOINT_NAMES:
        raise LowStatePacketError("full 29-joint name order does not match G1 contract")
    return np.asarray(packet.all_joint_q_rad, dtype=float)


def ReceiveAvailable(sock: socket.socket, state: StreamState) -> bool:
    """대기 중인 UDP datagram을 모두 비우고 가장 최신 유효 상태만 남긴다."""
    accepted = False
    while True:
        try:
            payload, _ = sock.recvfrom(MAX_PACKET_BYTES)
        except BlockingIOError:
            break
        received_monotonic = time.monotonic()
        try:
            packet = parse_lowstate_telemetry(payload)
            FullBodyPose(packet)
        except LowStatePacketError as exc:
            state.rejected_packets += 1
            print(f"[REJECTED] Invalid LowState telemetry: {exc}")
            continue
        accepted = state.Accept(packet, received_monotonic) or accepted
    return accepted


def ResolveFullBodyQposAddresses(model: mujoco.MjModel) -> np.ndarray:
    """29개 motor index 순서에 대응하는 MuJoCo qpos 주소를 한 번만 계산한다."""
    addresses: list[int] = []
    for joint_name in G1_29_JOINT_NAMES:
        mujoco_joint_name = joint_name + "_joint"
        joint_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_JOINT, mujoco_joint_name
        )
        if joint_id < 0:
            raise RuntimeError(f"MuJoCo joint missing: {mujoco_joint_name}")
        addresses.append(int(model.jnt_qposadr[joint_id]))
    return np.asarray(addresses, dtype=int)


def ResolveBaseBodyPose(model: mujoco.MjModel) -> BaseBodyPose:
    """고정-base 시각화 모델에서 움직일 pelvis body와 원래 pose를 찾는다."""
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "pelvis")
    if body_id < 0:
        raise RuntimeError("MuJoCo body missing: pelvis")
    return BaseBodyPose(
        body_id=body_id,
        initial_position_m=model.body_pos[body_id].copy(),
        initial_quaternion_wxyz=model.body_quat[body_id].copy(),
    )


def _RotateVectorWXYZ(
    quaternion_wxyz: np.ndarray,
    vector: np.ndarray,
) -> np.ndarray:
    w_value, x_value, y_value, z_value = NormalizeQuaternionWXYZ(
        quaternion_wxyz
    )
    rotation = np.asarray(
        [
            [
                1.0 - 2.0 * (y_value * y_value + z_value * z_value),
                2.0 * (x_value * y_value - z_value * w_value),
                2.0 * (x_value * z_value + y_value * w_value),
            ],
            [
                2.0 * (x_value * y_value + z_value * w_value),
                1.0 - 2.0 * (x_value * x_value + z_value * z_value),
                2.0 * (y_value * z_value - x_value * w_value),
            ],
            [
                2.0 * (x_value * z_value - y_value * w_value),
                2.0 * (y_value * z_value + x_value * w_value),
                1.0 - 2.0 * (x_value * x_value + y_value * y_value),
            ],
        ],
        dtype=float,
    )
    return rotation @ np.asarray(vector, dtype=float)


def ApplyBasePose(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    base_body: BaseBodyPose,
    relative_position_m: np.ndarray,
    relative_quaternion_xyzw: np.ndarray,
) -> None:
    """명령 없는 고정-base 모델의 pelvis transform만 시각적으로 이동한다."""
    position = np.asarray(relative_position_m, dtype=float)
    quaternion_xyzw = np.asarray(relative_quaternion_xyzw, dtype=float)
    if position.shape != (3,) or quaternion_xyzw.shape != (4,):
        raise ValueError("base pose must contain position[3] and quaternion[4]")
    relative_quaternion_wxyz = (
        quaternion_xyzw[3],
        quaternion_xyzw[0],
        quaternion_xyzw[1],
        quaternion_xyzw[2],
    )
    world_quaternion = NormalizeQuaternionWXYZ(
        MultiplyQuaternionWXYZ(
            base_body.initial_quaternion_wxyz,
            relative_quaternion_wxyz,
        )
    )
    world_position = base_body.initial_position_m + _RotateVectorWXYZ(
        base_body.initial_quaternion_wxyz,
        position,
    )
    model.body_pos[base_body.body_id] = world_position
    model.body_quat[base_body.body_id] = world_quaternion
    mujoco.mj_forward(model, data)


def BasePoseFromPacket(
    packet: LowStateTelemetry,
) -> tuple[np.ndarray, np.ndarray] | None:
    if packet.base_state is None or not packet.base_state.valid:
        return None
    return (
        np.asarray(packet.base_state.position_m, dtype=float),
        np.asarray(packet.base_state.quaternion_xyzw, dtype=float),
    )


def ApplyFullBodyPose(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos_addresses: np.ndarray,
    pose: np.ndarray,
) -> None:
    if qpos_addresses.shape != (29,) or pose.shape != (29,):
        raise ValueError("full-body pose and qpos addresses must contain 29 values")
    data.qpos[qpos_addresses] = pose
    mujoco.mj_forward(model, data)


def SetInspectionSceneEnabled(model: mujoco.MjModel, enabled: bool) -> None:
    """라이브 관절 미러에서만 점검 데모 오브젝트의 표시를 전환한다."""
    if enabled:
        return

    for geom_name in INSPECTION_SCENE_GEOM_NAMES:
        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, geom_name)
        if geom_id < 0:
            raise RuntimeError(f"inspection scene geom not found: {geom_name}")
        model.geom_rgba[geom_id, 3] = 0.0
        model.geom_contype[geom_id] = 0
        model.geom_conaffinity[geom_id] = 0


def LoadModel(show_inspection_scene: bool = False):
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller

    controller._prepare_mink_xml(
        show_inspection_scene=show_inspection_scene,
    )
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)
    SetInspectionSceneEnabled(model, show_inspection_scene)
    data = mujoco.MjData(model)
    data.qpos[:] = controller._initial_configuration(model)
    mujoco.mj_forward(model, data)
    return model, data, controller


def Run(args: argparse.Namespace) -> int:
    """검증된 실행 인자로 라이브 29관절 Viewer를 구동한다."""
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not 0 <= args.unity_port <= 65535:
        raise SystemExit("--unity-port must be 0 or between 1 and 65535")
    if args.startup_timeout <= 0.0 or args.stale_timeout <= 0.0:
        raise SystemExit("timeouts must be > 0")
    if args.smoothing_time < 0.0:
        raise SystemExit("--smoothing-time must be >= 0")

    model, data, controller = LoadModel(args.show_inspection_scene)
    full_body_qpos_addresses = ResolveFullBodyQposAddresses(model)
    base_body = ResolveBaseBodyPose(model)
    print("G1 29-joint live LowState - MuJoCo READ ONLY")
    print("---------------------------------------------")
    print(f"UDP input:       {args.host}:{args.port}")
    source_description = getattr(
        args,
        "source_description",
        "rt/lowstate subscriber in WSL",
    )
    print(f"State source:    {source_description}")
    print("Displayed joints: all 29 (legs, waist, both arms)")
    print("Displayed base:   rt/odommodestate relative to first valid sample")
    print(
        "Inspection scene: "
        + ("VISIBLE" if args.show_inspection_scene else "HIDDEN (preserved in model)")
    )
    print("DDS publisher:   NONE")
    print("Motor command:   NONE")
    print(
        "Unity preview:   "
        + (
            f"{args.unity_host}:{args.unity_port} (29-joint READ ONLY)"
            if args.unity_port > 0
            else "DISABLED"
        )
    )

    if args.validate_only:
        print("[PASS] Live LowState MuJoCo model and dependencies are valid.")
        return 0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.setblocking(False)
    unity_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    measurement_log_path = ResolveMeasurementLogPath(args.measurement_log)
    measurement_log = None
    if measurement_log_path is not None:
        measurement_log_path.parent.mkdir(parents=True, exist_ok=True)
        measurement_log = measurement_log_path.open("w", encoding="utf-8")
        print(f"Mirror log:      {measurement_log_path}")
    state = StreamState()
    displayed_pose: np.ndarray | None = None
    target_pose: np.ndarray | None = None
    displayed_base_position: np.ndarray | None = None
    displayed_base_quaternion: np.ndarray | None = None
    target_base_position: np.ndarray | None = None
    target_base_quaternion: np.ndarray | None = None
    startup_deadline = time.monotonic() + args.startup_timeout
    last_update = time.monotonic()
    last_report = float("-inf")
    last_measurement_flush = time.monotonic()
    stale_reported = False

    print("[WAITING] Waiting for the first valid G1 LowState packet...")
    print("Close the MuJoCo window to finish.")
    try:
        with mujoco.viewer.launch_passive(model, data) as viewer:
            viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
            viewer.cam.lookat[:] = np.asarray([0.0, 0.0, 0.9])
            viewer.cam.distance = 3.0
            viewer.cam.azimuth = 135.0
            viewer.cam.elevation = -12.0
            viewer.sync()

            while viewer.is_running():
                now = time.monotonic()
                dt_s = min(0.1, max(0.0, now - last_update))
                last_update = now
                previous_session_id = state.session_id
                received = ReceiveAvailable(sock, state)
                session_changed = received and state.session_id != previous_session_id

                if received and state.packet is not None:
                    target_pose = FullBodyPose(state.packet)
                    if session_changed:
                        displayed_base_position = None
                        displayed_base_quaternion = None
                        target_base_position = None
                        target_base_quaternion = None
                        ApplyBasePose(
                            model,
                            data,
                            base_body,
                            np.zeros(3, dtype=float),
                            np.asarray([0.0, 0.0, 0.0, 1.0], dtype=float),
                        )
                    base_pose = BasePoseFromPacket(state.packet)
                    if base_pose is not None:
                        target_base_position, target_base_quaternion = base_pose
                        if displayed_base_position is None or session_changed:
                            displayed_base_position = target_base_position.copy()
                            displayed_base_quaternion = target_base_quaternion.copy()
                    if displayed_pose is None or session_changed:
                        displayed_pose = target_pose.copy()
                        print(
                            "[LIVE] First measured 29-joint pose applied; "
                            + (
                                "normalized base pose is active."
                                if base_pose is not None
                                else "base pose is unavailable, so the model base is held."
                            )
                        )
                    stale_reported = False

                if displayed_pose is None:
                    if now >= startup_deadline:
                        print("[ERROR] No valid LowState packet arrived before timeout.")
                        timeout_action = getattr(
                            args,
                            "timeout_action",
                            "[ACTION] Check the WSL forwarder window, G1 Ethernet "
                            "192.168.123.99/24, and UDP port 5009.",
                        )
                        print(timeout_action)
                        return 2
                else:
                    age_s = now - state.received_monotonic
                    if age_s <= args.stale_timeout and target_pose is not None:
                        displayed_pose = AdvancePose(
                            displayed_pose,
                            target_pose,
                            dt_s,
                            args.smoothing_time,
                        )
                        if (
                            displayed_base_position is not None
                            and displayed_base_quaternion is not None
                            and target_base_position is not None
                            and target_base_quaternion is not None
                        ):
                            displayed_base_position = AdvancePose(
                                displayed_base_position,
                                target_base_position,
                                dt_s,
                                args.smoothing_time,
                            )
                            displayed_base_quaternion = AdvanceQuaternion(
                                displayed_base_quaternion,
                                target_base_quaternion,
                                dt_s,
                                args.smoothing_time,
                            )
                    elif not stale_reported:
                        print(
                            f"[STALE] No fresh packet for {age_s * 1000.0:.0f} ms; "
                            "holding the last displayed pose."
                        )
                        stale_reported = True
                    ApplyFullBodyPose(
                        model,
                        data,
                        full_body_qpos_addresses,
                        displayed_pose,
                    )
                    if (
                        displayed_base_position is not None
                        and displayed_base_quaternion is not None
                    ):
                        ApplyBasePose(
                            model,
                            data,
                            base_body,
                            displayed_base_position,
                            displayed_base_quaternion,
                        )

                    if (
                        args.unity_port > 0
                        and age_s <= args.stale_timeout
                        and state.packet is not None
                    ):
                        unity_payload = BuildUnityHardwareStatePacket(
                            state.packet,
                            displayed_all_joint_q_rad=displayed_pose,
                            displayed_base_position_m=displayed_base_position,
                            displayed_base_quaternion_xyzw=displayed_base_quaternion,
                        )
                        unity_sock.sendto(
                            json.dumps(
                                unity_payload,
                                separators=(",", ":"),
                            ).encode("utf-8"),
                            (args.unity_host, args.unity_port),
                        )
                        if measurement_log is not None:
                            measurement = BuildMirrorMeasurement(
                                unity_payload,
                                age_s,
                            )
                            if measurement is not None:
                                measurement_log.write(
                                    json.dumps(measurement, separators=(",", ":"))
                                    + "\n"
                                )
                                if now - last_measurement_flush >= 1.0:
                                    measurement_log.flush()
                                    last_measurement_flush = now

                    if now - last_report >= 1.0:
                        base_status = "fixed"
                        if (
                            displayed_base_position is not None
                            and target_base_position is not None
                        ):
                            source_move_cm = 100.0 * float(
                                np.linalg.norm(target_base_position)
                            )
                            display_move_cm = 100.0 * float(
                                np.linalg.norm(displayed_base_position)
                            )
                            base_lag_cm = 100.0 * float(
                                np.linalg.norm(
                                    target_base_position - displayed_base_position
                                )
                            )
                            base_status = (
                                f"source={source_move_cm:.1f} cm "
                                f"MuJoCo={display_move_cm:.1f} cm "
                                f"lag={base_lag_cm:.2f} cm"
                            )
                        print(
                            f"[STATUS] packets={state.accepted_packets} "
                            f"rejected={state.rejected_packets} "
                            f"age={age_s * 1000.0:.0f} ms "
                            f"base={base_status}"
                        )
                        last_report = now

                viewer.sync()
                time.sleep(1.0 / 60.0)
    finally:
        if measurement_log is not None:
            measurement_log.flush()
            measurement_log.close()
        unity_sock.close()
        sock.close()

    print("[DONE] Viewer closed. No robot command was sent.")
    if measurement_log_path is not None:
        print(f"[RESULT] Mirror measurement log: {measurement_log_path}")
    return 0


def Main() -> int:
    return Run(ParseArguments())


if __name__ == "__main__":
    raise SystemExit(Main())
