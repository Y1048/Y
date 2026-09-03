#!/usr/bin/env python3

import sys
import time
import threading

from unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelSubscriber,
)
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_


INTERFACE = "eth0"

JOINT_NAMES = {
    22: "R_SHOULDER_PITCH",
    23: "R_SHOULDER_ROLL",
    24: "R_SHOULDER_YAW",
    25: "R_ELBOW",
    26: "R_WRIST_ROLL",
    27: "R_WRIST_PITCH",
    28: "R_WRIST_YAW",
}

received = threading.Event()
latest = None


def callback(msg: LowState_):
    global latest
    latest = msg
    received.set()


def main():
    ChannelFactoryInitialize(0, INTERFACE)

    subscriber = ChannelSubscriber("rt/lowstate", LowState_)
    subscriber.Init(callback, 10)

    print("[INFO] Waiting for rt/lowstate...")

    if not received.wait(timeout=5.0):
        print("[ABORT] No lowstate received.")
        return 1

    msg = latest

    print(f"[RESULT] mode_machine = {msg.mode_machine}")
    print(f"[RESULT] mode_pr      = {msg.mode_pr}")
    print()

    for index, name in JOINT_NAMES.items():
        motor = msg.motor_state[index]
        print(
            f"{index:2d} {name:18s} "
            f"q={motor.q:+.5f}, dq={motor.dq:+.5f}"
        )

    print()

    if msg.mode_machine == 9:
        print("[OK] Robot reports the 14-DoF arm mapping.")
    elif msg.mode_machine == 2:
        print("[STOP] Robot reports the 29-DoF whole-body mapping.")
        print("[STOP] Do not run a wrist command yet.")
    else:
        print("[STOP] Unexpected mode_machine value.")
        print("[STOP] Do not send arm commands.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
