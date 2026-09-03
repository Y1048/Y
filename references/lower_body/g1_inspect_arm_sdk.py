#!/usr/bin/env python3

import threading
import time

from unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelSubscriber,
)
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_


INTERFACE = "eth0"

count = 0
latest = None
lock = threading.Lock()


def callback(msg: LowCmd_):
    global count, latest

    with lock:
        count += 1
        latest = msg


def main():
    global count

    ChannelFactoryInitialize(0, INTERFACE)

    subscriber = ChannelSubscriber("rt/arm_sdk", LowCmd_)
    subscriber.Init(callback, 10)

    print("[INFO] Listening to rt/arm_sdk for 3 seconds...")
    start = time.monotonic()
    time.sleep(3.0)
    elapsed = time.monotonic() - start

    with lock:
        msg = latest
        received = count

    print(f"[RESULT] messages = {received}")
    print(f"[RESULT] approximate rate = {received / elapsed:.1f} Hz")

    if msg is None:
        print("[RESULT] No arm_sdk command received.")
        return 0

    print(f"[RESULT] mode_machine = {msg.mode_machine}")
    print(f"[RESULT] mode_pr      = {msg.mode_pr}")
    print()

    indices = [
        0, 1, 2, 3, 4, 5,
        6, 7, 8, 9, 10, 11,
        12, 13, 14,
        22, 23, 24, 25, 26, 27, 28,
        29,
    ]

    names = {
        0: "L_HIP_PITCH",
        1: "L_HIP_ROLL",
        2: "L_HIP_YAW",
        3: "L_KNEE",
        4: "L_ANKLE_PITCH",
        5: "L_ANKLE_ROLL",
        6: "R_HIP_PITCH",
        7: "R_HIP_ROLL",
        8: "R_HIP_YAW",
        9: "R_KNEE",
        10: "R_ANKLE_PITCH",
        11: "R_ANKLE_ROLL",
        12: "WAIST_YAW",
        13: "WAIST_ROLL",
        14: "WAIST_PITCH",
        22: "R_SHOULDER_PITCH",
        23: "R_SHOULDER_ROLL",
        24: "R_SHOULDER_YAW",
        25: "R_ELBOW",
        26: "R_WRIST_ROLL",
        27: "R_WRIST_PITCH",
        28: "R_WRIST_YAW",
        29: "ARM_SDK_WEIGHT",
    }

    for index in indices:
        motor = msg.motor_cmd[index]

        print(
            f"{index:2d} {names[index]:18s} "
            f"mode={motor.mode:3d} "
            f"q={motor.q:+.5f} "
            f"dq={motor.dq:+.5f} "
            f"kp={motor.kp:+.2f} "
            f"kd={motor.kd:+.2f} "
            f"tau={motor.tau:+.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
