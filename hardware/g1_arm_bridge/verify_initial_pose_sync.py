#!/usr/bin/env python3
"""Verify the captured G1 pose through Mink and the Unity state contract.

This validator creates no DDS objects, opens no viewer, and sends no robot
command. It checks that the seven captured LowState right-arm values are
preserved when the current Mink model is initialized, and that the Unity state
packet preserves the complete 29-joint model state.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import mink
import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
RESULT_PATH = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_pose_sync_validation.json"
)


def _load_captured_pose() -> np.ndarray:
    payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    pose = np.asarray(payload.get("right_arm_q_rad"), dtype=float)
    if pose.shape != (7,) or not np.all(np.isfinite(pose)):
        raise RuntimeError(f"Invalid captured G1 pose: {STATE_PATH}")
    return pose


def main() -> int:
    os.environ["G1_USE_HARDWARE_INITIAL_STATE"] = "1"
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))

    import run_mink_g1_right_arm_prototype as controller

    expected = _load_captured_pose()
    controller._prepare_mink_xml()
    model = mujoco.MjModel.from_xml_path(str(controller.g1.DEMO_XML))
    controller._apply_operational_joint_limits(model)

    initial_qpos = controller._initial_configuration(model)
    qpos_ids = np.asarray(
        [
            int(model.jnt_qposadr[controller._joint_id(model, name)])
            for name in controller.g1.RIGHT_ARM_JOINTS
        ],
        dtype=int,
    )
    all_qpos_ids = np.asarray(
        [
            int(model.jnt_qposadr[controller._joint_id(model, name)])
            for name in controller.g1.G1_29_JOINTS
        ],
        dtype=int,
    )
    mink_pose = initial_qpos[qpos_ids]

    configuration = mink.Configuration(model)
    configuration.update(initial_qpos)
    wrist_position = configuration.data.xpos[
        controller.g1.get_body_id(model, "right_wrist_yaw_link")
    ].copy()
    state_packet = controller._state_packet(
        configuration,
        qpos_ids,
        all_qpos_ids,
        False,
        wrist_position,
        None,
        False,
    )
    unity_pose = np.asarray(state_packet["right_arm"]["joints"], dtype=float)
    unity_full_pose = np.asarray(state_packet["all_joint_q_rad"], dtype=float)
    expected_full_pose = configuration.q[all_qpos_ids]

    mink_error = float(np.max(np.abs(mink_pose - expected)))
    unity_error = float(np.max(np.abs(unity_pose - expected)))
    unity_full_error = float(np.max(np.abs(unity_full_pose - expected_full_pose)))
    tolerance = 1e-9
    passed = (
        mink_error <= tolerance
        and unity_error <= tolerance
        and unity_full_error <= tolerance
        and state_packet["all_joint_names"] == controller.g1.G1_29_JOINT_NAMES
    )
    result = {
        "passed": passed,
        "command_output_enabled": False,
        "captured_q_rad": expected.tolist(),
        "mink_q_rad": mink_pose.tolist(),
        "unity_packet_q_rad": unity_pose.tolist(),
        "unity_packet_all_joint_names": state_packet["all_joint_names"],
        "unity_packet_all_joint_q_rad": unity_full_pose.tolist(),
        "maximum_mink_error_rad": mink_error,
        "maximum_unity_packet_error_rad": unity_error,
        "maximum_unity_full_body_packet_error_rad": unity_full_error,
        "captured_q_deg": [math.degrees(value) for value in expected],
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(RESULT_PATH)

    print("G1 initial-pose synchronization validation -- READ ONLY")
    print(
        "Captured q[deg]: "
        + ", ".join(f"{value:.2f}" for value in result["captured_q_deg"])
    )
    print(f"Mink maximum error: {mink_error:.3e} rad")
    print(f"Unity packet maximum error: {unity_error:.3e} rad")
    print(f"Unity full-body packet maximum error: {unity_full_error:.3e} rad")
    print("Robot command: NONE")
    print("[PASS]" if passed else "[FAIL]")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
