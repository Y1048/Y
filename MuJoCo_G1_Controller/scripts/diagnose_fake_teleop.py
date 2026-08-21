"""VR-free end-to-end diagnostics for the right-arm teleoperation backend.

Run the configured MuJoCo teleop runtime first, with Unity closed. This script
acts as the Quest sender on UDP 5005 and as the Unity state receiver on UDP 5006.
It separates backend/reference/IK faults from Unity/Quest tracking faults.
"""

from __future__ import annotations

import json
import math
import socket
import statistics
import time
import uuid
from dataclasses import dataclass


COMMAND_HOST = "127.0.0.1"
COMMAND_PORT = 5005
STATE_HOST = "127.0.0.1"
STATE_PORT = 5006
SEND_HZ = 60.0
BASE_POSITION = [0.42, -0.16, 1.05]
POSITION_STEP_M = 0.12
POSITION_SPEED_LIMIT_MPS = 0.08
# State packets carry wall-clock timestamps and are sampled by another Python
# process on Windows. Single adjacent-sample derivatives are therefore noisy.
# Judge the transport path using a 3-sample window while still reporting raw max.
ROBUST_POSITION_SPEED_TOLERANCE_MPS = 0.095
MIN_ROBUST_POSITION_SPEED_MPS = 0.060
MIN_EXPECTED_POSITION_MOTION_M = 0.085


@dataclass
class StateSample:
    timestamp: float
    joints: list[float]
    wrist_delta: list[float]
    target_delta: list[float]
    position_error: float
    workspace_limited: bool
    collision_limited: bool


def euler_xyz_to_quaternion(roll_deg: float, pitch_deg: float, yaw_deg: float) -> list[float]:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return [
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ]


def norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def vector_sub(first: list[float], second: list[float]) -> list[float]:
    return [a - b for a, b in zip(first, second)]


def receive_latest(sock: socket.socket) -> StateSample | None:
    latest = None
    while True:
        try:
            payload, _ = sock.recvfrom(8192)
        except BlockingIOError:
            break
        try:
            message = json.loads(payload.decode("utf-8"))
            arm = message["right_arm"]
            latest = StateSample(
                timestamp=float(message.get("timestamp", time.time())),
                joints=[float(value) for value in arm["joints"]],
                wrist_delta=[float(value) for value in arm["wrist_delta"]],
                target_delta=[float(value) for value in arm["target_delta"]],
                position_error=float(arm["position_error"]),
                workspace_limited=bool(arm["workspace_limited"]),
                collision_limited=bool(arm["collision_limited"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return latest


def send_phase(
    command_sock: socket.socket,
    state_sock: socket.socket,
    session_id: str,
    sequence: int,
    position: list[float],
    rotation: list[float],
    duration_s: float,
    label: str,
) -> tuple[int, list[StateSample]]:
    print(f"\n[{label}] {duration_s:.1f}s")
    samples: list[StateSample] = []
    period = 1.0 / SEND_HZ
    deadline = time.monotonic() + duration_s
    next_send = time.monotonic()
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_send:
            message = {
                "session_id": session_id,
                "sequence": sequence,
                "command_state": "active",
                "right": {
                    "pos": position,
                    "rot": rotation,
                    "valid": True,
                },
                "timestamp": time.time(),
                "source": "diagnostic_fake_vr",
            }
            command_sock.sendto(json.dumps(message).encode("utf-8"), (COMMAND_HOST, COMMAND_PORT))
            sequence += 1
            next_send += period

        sample = receive_latest(state_sock)
        if sample is not None:
            samples.append(sample)
        time.sleep(0.002)

    sample = receive_latest(state_sock)
    if sample is not None:
        samples.append(sample)
    print(f"  state samples: {len(samples)}")
    return sequence, samples


def unique_samples(samples: list[StateSample]) -> list[StateSample]:
    result: list[StateSample] = []
    last_timestamp = None
    for sample in samples:
        if last_timestamp is None or sample.timestamp > last_timestamp + 1e-6:
            result.append(sample)
            last_timestamp = sample.timestamp
    return result


def diagnose_position_speed(samples: list[StateSample]) -> tuple[bool, str]:
    values = unique_samples(samples)
    adjacent_speeds: list[float] = []
    for previous, current in zip(values, values[1:]):
        dt = current.timestamp - previous.timestamp
        if dt <= 1e-4:
            continue
        displacement = norm(vector_sub(current.target_delta, previous.target_delta))
        adjacent_speeds.append(displacement / dt)

    robust_speeds: list[float] = []
    for index in range(len(values) - 2):
        first = values[index]
        last = values[index + 2]
        dt = last.timestamp - first.timestamp
        if dt <= 1e-4:
            continue
        displacement = norm(vector_sub(last.target_delta, first.target_delta))
        robust_speeds.append(displacement / dt)

    if len(values) < 4 or not adjacent_speeds or not robust_speeds:
        return False, "insufficient state samples"

    total_motion = norm(vector_sub(values[-1].target_delta, values[0].target_delta))
    raw_maximum = max(adjacent_speeds)
    robust_maximum = max(robust_speeds)
    median_speed = statistics.median(robust_speeds)
    passed = (
        MIN_ROBUST_POSITION_SPEED_MPS <= robust_maximum <= ROBUST_POSITION_SPEED_TOLERANCE_MPS
        and total_motion >= MIN_EXPECTED_POSITION_MOTION_M
    )
    detail = (
        f"safe-reference motion={total_motion * 100:.1f} cm, "
        f"robust_max={robust_maximum:.3f} m/s, "
        f"raw_max={raw_maximum:.3f} m/s, median={median_speed:.3f} m/s "
        f"(configured={POSITION_SPEED_LIMIT_MPS:.2f} m/s, "
        f"expected robust>={MIN_ROBUST_POSITION_SPEED_MPS:.3f}, "
        f"motion>={MIN_EXPECTED_POSITION_MOTION_M*100:.1f} cm)"
    )
    return passed, detail


def diagnose_rotation_only(
    baseline: StateSample,
    rotated: StateSample,
) -> tuple[bool, str, bool]:
    joint_delta_deg = [
        math.degrees(after - before)
        for before, after in zip(baseline.joints, rotated.joints)
    ]
    proximal_change = norm(joint_delta_deg[:4])
    wrist_change = norm(joint_delta_deg[4:7])
    wrist_position_drift = norm(vector_sub(rotated.wrist_delta, baseline.wrist_delta))

    wrist_responded = wrist_change >= 3.0
    position_held = wrist_position_drift <= 0.03
    coupled_suspect = proximal_change > max(5.0, 0.75 * wrist_change)
    passed = wrist_responded and position_held
    detail = (
        f"wrist-joint change={wrist_change:.1f} deg, "
        f"shoulder/elbow change={proximal_change:.1f} deg, "
        f"wrist-position drift={wrist_position_drift * 100:.1f} cm"
    )
    return passed, detail, coupled_suspect


def release(command_sock: socket.socket, session_id: str, sequence: int) -> None:
    message = {
        "session_id": session_id,
        "sequence": sequence,
        "command_state": "idle",
        "right": {"valid": False},
        "timestamp": time.time(),
        "source": "diagnostic_fake_vr",
    }
    encoded = json.dumps(message).encode("utf-8")
    for _ in range(3):
        command_sock.sendto(encoded, (COMMAND_HOST, COMMAND_PORT))
        time.sleep(0.02)


def main() -> int:
    print("G1 VR-free teleoperation diagnostic")
    print("===================================")
    print("Prerequisite: configured MuJoCo runtime is running and Unity is CLOSED.")
    print("This test owns UDP state port 5006 while it runs.\n")

    command_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        state_sock.bind((STATE_HOST, STATE_PORT))
    except OSError as exc:
        print(f"FAIL: cannot bind {STATE_HOST}:{STATE_PORT}: {exc}")
        print("Close Unity or any other state receiver, then run this test again.")
        return 2
    state_sock.setblocking(False)

    session_id = f"diag-{uuid.uuid4().hex}"
    sequence = 0
    identity = euler_xyz_to_quaternion(0.0, 0.0, 0.0)

    try:
        sequence, engage_samples = send_phase(
            command_sock, state_sock, session_id, sequence,
            BASE_POSITION, identity, 1.8, "1/4 ENGAGE + HOLD",
        )
        if not engage_samples:
            print("\nFAIL: no state packets received from MuJoCo on UDP 5006.")
            print("Start START_VR_HAND_TO_MUJOCO.bat first, then rerun this diagnostic.")
            return 2

        stepped_position = [
            BASE_POSITION[0] + POSITION_STEP_M,
            BASE_POSITION[1],
            BASE_POSITION[2],
        ]
        sequence, position_samples = send_phase(
            command_sock, state_sock, session_id, sequence,
            stepped_position, identity, 2.2, "2/4 POSITION STEP (+12 cm X)",
        )
        position_pass, position_detail = diagnose_position_speed(position_samples)

        sequence, settle_samples = send_phase(
            command_sock, state_sock, session_id, sequence,
            stepped_position, identity, 1.2, "3/4 POSITION HOLD",
        )
        baseline_samples = settle_samples or position_samples or engage_samples
        rotation_baseline = baseline_samples[-1]

        rotated_quaternion = euler_xyz_to_quaternion(0.0, 0.0, 35.0)
        sequence, rotation_samples = send_phase(
            command_sock, state_sock, session_id, sequence,
            stepped_position, rotated_quaternion, 1.8, "4/4 ROTATION ONLY (+35 deg yaw)",
        )
        if rotation_samples:
            rotation_pass, rotation_detail, coupled_suspect = diagnose_rotation_only(
                rotation_baseline,
                rotation_samples[-1],
            )
        else:
            rotation_pass = False
            coupled_suspect = False
            rotation_detail = "no state samples during rotation phase"

        print("\n===================================")
        print("DIAGNOSTIC RESULT")
        print("===================================")
        print(f"POSITION: {'PASS' if position_pass else 'FAIL'} - {position_detail}")
        print(f"ROTATION: {'PASS' if rotation_pass else 'FAIL'} - {rotation_detail}")

        if coupled_suspect:
            print("WARNING: rotation-only command moved shoulder/elbow strongly; coupled IK fallback is suspect.")

        if position_pass and rotation_pass and not coupled_suspect:
            print("\nBACKEND/MUJOCO PATH: PASS")
            print("Position timing and wrist isolation are both within the configured diagnostic range.")
            return 0

        print("\nBACKEND/MUJOCO PATH: FAIL or SUSPECT")
        if not position_pass:
            print("- Position motion is either too fast OR materially under-speed; inspect runtime timing/reference integration.")
        if not rotation_pass:
            print("- Rotation failure points to backend rotation mapping or wrist IK.")
        if coupled_suspect:
            print("- Large proximal motion points to rotation-triggered coupled fallback / 7-DoF IK behavior.")
        return 1
    finally:
        release(command_sock, session_id, sequence)
        state_sock.close()
        command_sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
