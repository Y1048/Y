#!/usr/bin/env python3
"""저장된 G1 29관절 상태를 UDP 5009 경로로 재생해 MuJoCo에 표시한다.

Unitree SDK와 DDS를 사용하지 않으며 publisher 및 로봇 명령을 만들지 않는다.
다음 실제 연결에서 생성되는 완전한 LowState 스냅샷을 우선 사용하고, 현재처럼
구형 스냅샷에 29관절 필드가 없으면 검증용 전체 자세 자료로 대체한다.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from g1_joint_contract import G1_29_JOINT_NAMES
from gate5_lowstate_safety_monitor import (
    LOWSTATE_MODE,
    LOWSTATE_TELEMETRY_SCHEMA,
    LOWSTATE_TOPIC,
    LowStatePacketError,
    parse_lowstate_telemetry,
)
from g1_unity_state_bridge import (
    DEFAULT_UNITY_HARDWARE_HOST,
    DEFAULT_UNITY_HARDWARE_PORT,
    BuildUnityHardwareStatePacket,
)
import live_lowstate_mujoco


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HARDWARE_SNAPSHOT = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_lowstate.json"
)
DEFAULT_VALIDATION_SNAPSHOT = (
    PROJECT_ROOT
    / "logs"
    / "runtime"
    / "g1_hardware_pose_sync_validation.json"
)
DEFAULT_PORT = 5009
DEFAULT_HZ = 30.0


@dataclass(frozen=True)
class SavedLowState:
    path: Path
    source_kind: str
    joint_names: tuple[str, ...]
    q_rad: tuple[float, ...]
    dq_rad_s: tuple[float, ...]
    mode_pr: int | None
    mode_machine: int | None
    actual_full_body_capture: bool


def _FiniteVector(value: object, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != 29:
        raise ValueError(f"{field_name} must contain exactly 29 values")
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} contains a non-numeric value") from exc
    if not all(math.isfinite(item) for item in vector):
        raise ValueError(f"{field_name} contains a non-finite value")
    return vector


def _JointNames(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must contain the canonical 29 joint names")
    names = tuple(value)
    if names != G1_29_JOINT_NAMES:
        raise ValueError(f"{field_name} does not match the canonical G1 motor order")
    return names


def _OptionalMode(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError(f"{field_name} must be a uint8 value or null")
    return value


def LoadSnapshot(path: Path) -> SavedLowState:
    """LowState 상태 파일 또는 pose-sync 검증 파일에서 29관절을 읽는다."""
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"snapshot not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"snapshot is not valid JSON: {path}") from exc
    if not isinstance(root, Mapping):
        raise ValueError("snapshot root must be an object")

    details = root.get("details")
    if isinstance(details, Mapping) and "all_joint_q_rad" in details:
        names = _JointNames(details.get("all_joint_names"), "details.all_joint_names")
        q_rad = _FiniteVector(details.get("all_joint_q_rad"), "details.all_joint_q_rad")
        dq_rad_s = _FiniteVector(
            details.get("all_joint_dq_rad_s"),
            "details.all_joint_dq_rad_s",
        )
        return SavedLowState(
            path=path,
            source_kind="read_only_lowstate_status",
            joint_names=names,
            q_rad=q_rad,
            dq_rad_s=dq_rad_s,
            mode_pr=_OptionalMode(details.get("mode_pr"), "details.mode_pr"),
            mode_machine=_OptionalMode(
                details.get("mode_machine"),
                "details.mode_machine",
            ),
            actual_full_body_capture=True,
        )

    if "all_joint_q_rad" in root:
        names = _JointNames(root.get("all_joint_names"), "all_joint_names")
        q_rad = _FiniteVector(root.get("all_joint_q_rad"), "all_joint_q_rad")
        dq_value = root.get("all_joint_dq_rad_s")
        dq_rad_s = (
            _FiniteVector(dq_value, "all_joint_dq_rad_s")
            if dq_value is not None
            else (0.0,) * 29
        )
        return SavedLowState(
            path=path,
            source_kind="lowstate_telemetry",
            joint_names=names,
            q_rad=q_rad,
            dq_rad_s=dq_rad_s,
            mode_pr=_OptionalMode(root.get("mode_pr"), "mode_pr"),
            mode_machine=_OptionalMode(root.get("mode_machine"), "mode_machine"),
            actual_full_body_capture=True,
        )

    if "unity_packet_all_joint_q_rad" in root:
        names = _JointNames(
            root.get("unity_packet_all_joint_names"),
            "unity_packet_all_joint_names",
        )
        q_rad = _FiniteVector(
            root.get("unity_packet_all_joint_q_rad"),
            "unity_packet_all_joint_q_rad",
        )
        return SavedLowState(
            path=path,
            source_kind="pose_sync_validation",
            joint_names=names,
            q_rad=q_rad,
            dq_rad_s=(0.0,) * 29,
            mode_pr=None,
            mode_machine=None,
            actual_full_body_capture=False,
        )

    raise ValueError(
        "snapshot has no complete 29-joint fields; reconnect once and run "
        "START_G1_READ_ONLY.bat to create a new full-body capture"
    )


def ResolveSnapshot(explicit_path: Path | None) -> SavedLowState:
    if explicit_path is not None:
        return LoadSnapshot(explicit_path.resolve())

    errors: list[str] = []
    for candidate in (DEFAULT_HARDWARE_SNAPSHOT, DEFAULT_VALIDATION_SNAPSHOT):
        try:
            return LoadSnapshot(candidate)
        except ValueError as exc:
            errors.append(str(exc))
    raise ValueError("no replayable snapshot found: " + " | ".join(errors))


def BuildPacket(
    snapshot: SavedLowState,
    *,
    session_id: str,
    sequence: int,
    sent_at_unix_ns: int | None = None,
) -> bytes:
    """라이브 Viewer와 같은 엄격한 LowState UDP 문서를 만든다."""
    payload = {
        "schema": LOWSTATE_TELEMETRY_SCHEMA,
        "mode": LOWSTATE_MODE,
        "topic": LOWSTATE_TOPIC,
        "bridge_session_id": session_id,
        "sequence": sequence,
        "received_packets": sequence,
        "mode_pr": snapshot.mode_pr,
        "mode_machine": snapshot.mode_machine,
        "sent_at_unix_ns": sent_at_unix_ns or time.time_ns(),
        "right_arm_q_rad": list(snapshot.q_rad[22:29]),
        "right_arm_dq_rad_s": list(snapshot.dq_rad_s[22:29]),
        "all_joint_names": list(snapshot.joint_names),
        "all_joint_q_rad": list(snapshot.q_rad),
        "all_joint_dq_rad_s": list(snapshot.dq_rad_s),
        "publisher_present": False,
        "command_output_enabled": False,
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    parse_lowstate_telemetry(encoded)
    return encoded


def _SendLoop(
    snapshot: SavedLowState,
    *,
    host: str,
    port: int,
    hz: float,
    stop_event: threading.Event,
) -> None:
    session_id = "saved-" + uuid.uuid4().hex
    sequence = 0
    period_s = 1.0 / hz
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        while not stop_event.is_set():
            sequence += 1
            sock.sendto(
                BuildPacket(
                    snapshot,
                    session_id=session_id,
                    sequence=sequence,
                ),
                (host, port),
            )
            stop_event.wait(period_s)
    finally:
        sock.close()


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay saved G1 29-joint state through UDP 5009 into MuJoCo"
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--hz", type=float, default=DEFAULT_HZ)
    parser.add_argument("--unity-host", default=DEFAULT_UNITY_HARDWARE_HOST)
    parser.add_argument(
        "--unity-port",
        type=int,
        default=DEFAULT_UNITY_HARDWARE_PORT,
    )
    parser.add_argument("--show-inspection-scene", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def Main() -> int:
    args = ParseArguments()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    if not 0 <= args.unity_port <= 65535:
        raise SystemExit("--unity-port must be 0 or between 1 and 65535")
    if not math.isfinite(args.hz) or args.hz <= 0.0:
        raise SystemExit("--hz must be a finite value > 0")

    try:
        snapshot = ResolveSnapshot(args.source)
        packet = BuildPacket(snapshot, session_id="saved-validation", sequence=1)
        parsed = parse_lowstate_telemetry(packet)
        live_lowstate_mujoco.FullBodyPose(parsed)
        BuildUnityHardwareStatePacket(parsed)
    except (ValueError, LowStatePacketError) as exc:
        print(f"[ERROR] Saved LowState replay is unavailable: {exc}")
        print(
            "[ACTION] Reconnect G1 later, run START_G1_READ_ONLY.bat once, "
            "then retry this offline viewer."
        )
        return 2

    print("G1 saved 29-joint state - OFFLINE MuJoCo replay")
    print("--------------------------------------------------")
    print(f"Snapshot:         {snapshot.path}")
    print(f"Snapshot kind:    {snapshot.source_kind}")
    print(f"Actual full body: {'YES' if snapshot.actual_full_body_capture else 'NO'}")
    print("DDS connection:   NONE")
    print("DDS publisher:    NONE")
    print("Motor command:    NONE")
    print(
        "Unity preview:    "
        + (
            f"{args.unity_host}:{args.unity_port} (29-joint READ ONLY)"
            if args.unity_port > 0
            else "DISABLED"
        )
    )
    if not snapshot.actual_full_body_capture:
        print(
            "[WARNING] The current hardware file predates 29-joint logging; "
            "showing the validated fallback pose."
        )
        print(
            "[ACTION] On the next G1 connection, run START_G1_READ_ONLY.bat "
            "once to replace it with an actual 29-joint capture."
        )

    if args.validate_only:
        print("[PASS] Saved 29-joint replay packet is valid.")
        return 0

    stop_event = threading.Event()
    sender = threading.Thread(
        target=_SendLoop,
        kwargs={
            "snapshot": snapshot,
            "host": "127.0.0.1",
            "port": args.port,
            "hz": args.hz,
            "stop_event": stop_event,
        },
        name="saved-lowstate-replay",
        daemon=True,
    )
    sender.start()

    viewer_args = argparse.Namespace(
        host="127.0.0.1",
        port=args.port,
        startup_timeout=4.0,
        stale_timeout=live_lowstate_mujoco.DEFAULT_STALE_TIMEOUT_S,
        smoothing_time=0.0,
        show_inspection_scene=args.show_inspection_scene,
        validate_only=False,
        source_description=f"saved snapshot ({snapshot.source_kind})",
        unity_host=args.unity_host,
        unity_port=args.unity_port,
        timeout_action=(
            "[ACTION] Check whether another process is using UDP 5009, then "
            "run the saved-state viewer again."
        ),
    )
    try:
        return live_lowstate_mujoco.Run(viewer_args)
    finally:
        stop_event.set()
        sender.join(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(Main())
