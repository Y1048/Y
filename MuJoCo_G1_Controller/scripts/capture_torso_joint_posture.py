"""Capture the current MuJoCo right-arm joint state as the torso-front posture."""

from __future__ import annotations

import json
import math
import socket
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = PROJECT_ROOT / "config" / "joint_postures.json"
STATE_HOST = "127.0.0.1"
STATE_PORT = 5006
TIMEOUT_S = 3.0
JOINT_NAMES = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]


def receive_joint_state() -> list[float]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((STATE_HOST, STATE_PORT))
        sock.settimeout(0.5)
        deadline = time.monotonic() + TIMEOUT_S
        latest = None
        while time.monotonic() < deadline:
            try:
                payload, _ = sock.recvfrom(8192)
            except socket.timeout:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
                joints = message["right_arm"]["joints"]
                values = [float(v) for v in joints]
                if len(values) == 7:
                    latest = values
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                continue
        if latest is None:
            raise RuntimeError(
                "No right-arm state received on UDP 5006. Start MuJoCo and close Unity before capture."
            )
        return latest
    finally:
        sock.close()


def main() -> int:
    joints_rad = receive_joint_state()
    joints_deg = [math.degrees(value) for value in joints_rad]

    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["right_arm"]["torso_front_deg"] = joints_deg
    PROFILE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("Captured torso-front joint-space posture")
    print("========================================")
    for name, value in zip(JOINT_NAMES, joints_deg):
        print(f"{name:28s} {value:8.3f} deg")
    print(f"\nsaved: {PROFILE_PATH}")
    print("Restart the configured MuJoCo runtime so it reloads this posture profile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
