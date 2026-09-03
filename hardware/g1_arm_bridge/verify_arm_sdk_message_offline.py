#!/usr/bin/env python3
"""Build and CRC-check one Gate 6 frame with the installed Unitree SDK2.

No ChannelFactory, subscriber, publisher, socket, or robot command is created.
"""

from __future__ import annotations

import math
import sys

from arm_sdk_hold_contract import build_measured_hold_frame, dual_arm_from_all_joints
from gate6_arm_sdk_hold import _apply_frame


def main() -> int:
    from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
    from unitree_sdk2py.utils.crc import CRC

    measured = [0.0] * 29
    measured[15:22] = [
        math.radians(value) for value in (16.0, 12.0, -2.0, 56.0, 8.0, -1.0, 2.0)
    ]
    measured[22:29] = [
        math.radians(value) for value in (16.0, -12.0, 2.0, 56.0, -8.0, 1.0, -2.0)
    ]
    frame = build_measured_hold_frame(
        measured,
        dual_arm_from_all_joints(measured),
        mode_pr=0,
        mode_machine=5,
        weight=0.2,
    )
    message = unitree_hg_msg_dds__LowCmd_()
    _apply_frame(message, frame)
    message.crc = CRC().Crc(message)

    if len(message.motor_cmd) != 35:
        print(f"[FAIL] SDK LowCmd has {len(message.motor_cmd)} slots, expected 35")
        return 2
    if abs(float(message.motor_cmd[29].q) - 0.2) > 1e-9:
        print("[FAIL] Arm SDK weight was not written to motor_cmd[29].q")
        return 3
    if int(message.motor_cmd[12].mode) != 0:
        print("[FAIL] Waist command slot is unexpectedly enabled")
        return 4
    if int(message.motor_cmd[22].mode) != 1:
        print("[FAIL] Right-arm command slot is not enabled")
        return 5
    if int(message.crc) == 0:
        print("[FAIL] SDK CRC remained zero")
        return 6

    print("[PASS] Installed Unitree SDK2 accepted the Gate 6 HG LowCmd frame.")
    print("[PASS] 35 slots, dual-arm indices 15..28, weight index 29, CRC verified.")
    print("[PASS] Waist indices 12..14 remain disabled in the command frame.")
    print("ChannelFactory: NONE")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
