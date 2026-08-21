"""Interactive MuJoCo editor for capturing a torso-front right-arm posture.

This intentionally does NOT run teleoperation, IK, workspace projection, fallback,
or UDP. The MuJoCo Joint panel therefore owns the right-arm qpos values while the
viewer is open. Closing the viewer saves the final seven right-arm joint angles to
config/joint_postures.json as right_arm.torso_front_deg.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import g1_right_arm_udp_ik_demo as base  # noqa: E402


PROFILE_PATH = PROJECT_ROOT / "config" / "joint_postures.json"
PREVIEW_PATH = PROJECT_ROOT / "logs" / "runtime" / "manual_torso_posture_preview.json"
JOINT_NAMES = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]


def _joint_degrees(data, qpos_ids: np.ndarray) -> list[float]:
    return [float(math.degrees(v)) for v in data.qpos[qpos_ids]]


def _write_preview(values_deg: list[float]) -> None:
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "joint_names": JOINT_NAMES,
        "right_arm_deg": values_deg,
    }
    PREVIEW_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _save_profile(values_deg: list[float]) -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["right_arm"]["torso_front_deg"] = values_deg
    PROFILE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    model, data, initial_qpos, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    if qpos_ids.size != 7:
        raise RuntimeError("expected exactly seven right-arm qpos ids")

    # Keep the left arm/non-arm configuration fixed once, but never touch the
    # right-arm qpos again. That leaves the viewer Joint sliders authoritative.
    base.freeze_non_arm_joints(model, data, initial_qpos)
    base.set_left_arm_ready(model, data)
    mujoco.mj_forward(model, data)

    print("G1 MANUAL TORSO-FRONT JOINT POSTURE EDITOR")
    print("==========================================")
    print("No IK / UDP / workspace / fallback is running in this mode.")
    print("Open the MuJoCo Joint panel and adjust the seven RIGHT-arm joints.")
    print("Make the exact L-shaped posture you want for torso-front reaching.")
    print("Close the MuJoCo window when finished; the final pose is saved automatically.")
    print(f"Preview while editing: {PREVIEW_PATH}")
    print()

    last_preview = 0.0
    with mujoco.viewer.launch_passive(model, data) as viewer:
        try:
            base.configure_viewer_camera(viewer, model, "front")
        except Exception:
            pass

        while viewer.is_running():
            # Important: do not call freeze_non_arm_joints/set_left_arm_ready here;
            # depending on the viewer implementation they may also trigger state
            # updates that make manual Joint-panel editing feel overridden.
            mujoco.mj_forward(model, data)
            now = time.monotonic()
            if now - last_preview >= 0.25:
                values_deg = _joint_degrees(data, qpos_ids)
                _write_preview(values_deg)
                print(
                    "\rRIGHT ARM deg: "
                    + "  ".join(f"{name.split('right_')[1].replace('_joint','')}={value:7.2f}" for name, value in zip(JOINT_NAMES, values_deg)),
                    end="",
                    flush=True,
                )
                last_preview = now
            viewer.sync()
            time.sleep(0.01)

    values_deg = _joint_degrees(data, qpos_ids)
    _write_preview(values_deg)
    _save_profile(values_deg)

    print("\n\nSaved torso-front joint-space posture")
    print("======================================")
    for name, value in zip(JOINT_NAMES, values_deg):
        print(f"{name:28s} {value:8.3f} deg")
    print(f"\nsaved: {PROFILE_PATH}")
    print("Restart the configured runtime before the next live test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
