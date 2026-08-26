#!/usr/bin/env python3
"""Static contract test for the G1 teleoperation wrist frame.

This test intentionally does not launch Unity, MuJoCo viewer, or hardware. It
prevents the operator/Unity/Mink wrist frame from silently drifting apart.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MINK_CONTROLLER = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts" / "run_mink_g1_right_arm_prototype.py"
UNITY_RIG = PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "G1Teleop" / "G1OfficialRig.cs"
UNITY_SENDER = PROJECT_ROOT / "Unity_G1_VR" / "Assets" / "G1Teleop" / "G1ExistingTargetUdpSender.cs"

MINK_FRAME = "right_wrist_yaw_link"
UNITY_JOINT = "right_wrist_yaw_joint"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: missing {needle!r}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"{label}: forbidden legacy reference {needle!r}")


def main() -> int:
    mink_text = MINK_CONTROLLER.read_text(encoding="utf-8")
    rig_text = UNITY_RIG.read_text(encoding="utf-8")
    sender_text = UNITY_SENDER.read_text(encoding="utf-8")

    require(
        mink_text,
        'FrameTask(frame_name="right_wrist_yaw_link"',
        "Mink 6D task frame",
    )
    require(
        mink_text,
        'g1.get_body_id(configuration.model, "right_wrist_yaw_link")',
        "MuJoCo state wrist frame",
    )
    require(
        mink_text,
        'g1.get_body_id(model, "right_wrist_yaw_link")',
        "MuJoCo startup wrist frame",
    )
    forbid(
        mink_text,
        'g1.get_body_id(configuration.model, "right_wrist_roll_link")',
        "MuJoCo state wrist frame",
    )
    forbid(
        mink_text,
        'g1.get_body_id(model, "right_wrist_roll_link")',
        "MuJoCo startup wrist frame",
    )

    require(
        rig_text,
        'node_value.joint_name == "right_wrist_yaw_joint"',
        "Unity G1 wrist reference",
    )
    require(
        rig_text,
        "right_wrist_position_reference = node_value.transform;",
        "Unity G1 position reference",
    )
    require(
        rig_text,
        "right_wrist_orientation_reference = node_value.transform;",
        "Unity G1 orientation reference",
    )

    require(
        sender_text,
        "public float operator_forward_scale = 1.00f;",
        "Quest translation scale",
    )

    print("[PASS] Quest/Unity/MuJoCo/Mink wrist frame contract is unified.")
    print(f"       Mink body : {MINK_FRAME}")
    print(f"       Unity joint: {UNITY_JOINT}")
    print("       XYZ scale  : 1.00 / 1.00 / 1.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
