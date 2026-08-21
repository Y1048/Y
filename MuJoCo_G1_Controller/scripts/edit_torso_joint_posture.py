"""Keyboard-controlled MuJoCo editor for a torso-front right-arm posture.

This mode intentionally runs no teleoperation, IK, workspace projection, fallback,
or UDP. The stock MuJoCo Joint panel can be read-only in passive viewers, so the
right arm is edited explicitly from the keyboard and written directly to qpos.
"""

from __future__ import annotations

import json
import math
import queue
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
SHORT_NAMES = [
    "shoulder_pitch",
    "shoulder_roll",
    "shoulder_yaw",
    "elbow",
    "wrist_roll",
    "wrist_pitch",
    "wrist_yaw",
]
READY_DEG = np.array([10.0, -22.0, 0.0, 55.0, 0.0, 0.0, 0.0], dtype=float)


def _joint_degrees(data, qpos_ids: np.ndarray) -> list[float]:
    return [float(math.degrees(v)) for v in data.qpos[qpos_ids]]


def _write_preview(values_deg: list[float], selected_index: int) -> None:
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "joint_names": JOINT_NAMES,
        "right_arm_deg": values_deg,
        "selected_joint": JOINT_NAMES[selected_index],
    }
    PREVIEW_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _save_profile(values_deg: list[float]) -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    payload["right_arm"]["torso_front_deg"] = values_deg
    PROFILE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _joint_limits_rad(model, qpos_ids: np.ndarray) -> list[tuple[float, float] | None]:
    limits: list[tuple[float, float] | None] = []
    qpos_to_joint: dict[int, int] = {}
    for joint_id in range(model.njnt):
        qadr = int(model.jnt_qposadr[joint_id])
        if int(model.jnt_type[joint_id]) == int(mujoco.mjtJoint.mjJNT_HINGE):
            qpos_to_joint[qadr] = joint_id

    for qid in qpos_ids:
        joint_id = qpos_to_joint.get(int(qid))
        if joint_id is None or not bool(model.jnt_limited[joint_id]):
            limits.append(None)
            continue
        low, high = (float(v) for v in model.jnt_range[joint_id])
        limits.append((low, high))
    return limits


def _apply_delta(
    model,
    data,
    qpos_ids: np.ndarray,
    limits: list[tuple[float, float] | None],
    index: int,
    delta_deg: float,
) -> None:
    qid = int(qpos_ids[index])
    value = float(data.qpos[qid]) + math.radians(delta_deg)
    limit = limits[index]
    if limit is not None:
        value = float(np.clip(value, limit[0], limit[1]))
    data.qpos[qid] = value
    mujoco.mj_forward(model, data)


def _set_ready(model, data, qpos_ids: np.ndarray, limits) -> None:
    for index, qid in enumerate(qpos_ids):
        value = math.radians(float(READY_DEG[index]))
        limit = limits[index]
        if limit is not None:
            value = float(np.clip(value, limit[0], limit[1]))
        data.qpos[int(qid)] = value
    mujoco.mj_forward(model, data)


def main() -> int:
    model, data, initial_qpos, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    if qpos_ids.size != 7:
        raise RuntimeError("expected exactly seven right-arm qpos ids")

    base.freeze_non_arm_joints(model, data, initial_qpos)
    base.set_left_arm_ready(model, data)
    mujoco.mj_forward(model, data)
    limits = _joint_limits_rad(model, qpos_ids)

    key_events: queue.SimpleQueue[int] = queue.SimpleQueue()

    def key_callback(keycode: int) -> None:
        key_events.put(int(keycode))

    selected = 0
    saved_once = False

    print("G1 TORSO-FRONT JOINT-SPACE POSTURE EDITOR")
    print("==========================================")
    print("The MuJoCo Joint panel may be read-only; use these keyboard controls instead.")
    print("  1..7 : select right-arm joint")
    print("  A / D: -1 deg / +1 deg")
    print("  Q / E: -5 deg / +5 deg")
    print("  R    : reset right arm to ready posture")
    print("  S    : save current posture to config/joint_postures.json")
    print("Close the viewer when finished. The final pose is also saved on exit.")
    print()

    last_preview = 0.0
    with mujoco.viewer.launch_passive(model, data, key_callback=key_callback) as viewer:
        try:
            base.configure_viewer_camera(viewer, model, "front")
        except Exception:
            pass

        while viewer.is_running():
            changed = False
            while True:
                try:
                    key = key_events.get_nowait()
                except queue.Empty:
                    break

                if ord("1") <= key <= ord("7"):
                    selected = key - ord("1")
                    changed = True
                elif key in (ord("A"), ord("a")):
                    _apply_delta(model, data, qpos_ids, limits, selected, -1.0)
                    changed = True
                elif key in (ord("D"), ord("d")):
                    _apply_delta(model, data, qpos_ids, limits, selected, +1.0)
                    changed = True
                elif key in (ord("Q"), ord("q")):
                    _apply_delta(model, data, qpos_ids, limits, selected, -5.0)
                    changed = True
                elif key in (ord("E"), ord("e")):
                    _apply_delta(model, data, qpos_ids, limits, selected, +5.0)
                    changed = True
                elif key in (ord("R"), ord("r")):
                    _set_ready(model, data, qpos_ids, limits)
                    changed = True
                elif key in (ord("S"), ord("s")):
                    values_deg = _joint_degrees(data, qpos_ids)
                    _save_profile(values_deg)
                    saved_once = True
                    print("\nSaved current torso-front posture.")
                    changed = True

            now = time.monotonic()
            if changed or now - last_preview >= 0.25:
                values_deg = _joint_degrees(data, qpos_ids)
                _write_preview(values_deg, selected)
                formatted = "  ".join(
                    ("[" if i == selected else " ")
                    + f"{i+1}:{SHORT_NAMES[i]}={value:7.2f}"
                    + ("]" if i == selected else " ")
                    for i, value in enumerate(values_deg)
                )
                print("\r" + formatted, end="", flush=True)
                last_preview = now

            viewer.sync()
            time.sleep(0.01)

    values_deg = _joint_degrees(data, qpos_ids)
    _write_preview(values_deg, selected)
    _save_profile(values_deg)

    print("\n\nSaved torso-front joint-space posture on exit")
    print("=============================================")
    for name, value in zip(JOINT_NAMES, values_deg):
        print(f"{name:28s} {value:8.3f} deg")
    print(f"\nsaved: {PROFILE_PATH}")
    if not saved_once:
        print("Tip: next time press S to save without closing the viewer.")
    print("Restart the configured runtime before the next live test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
