"""Replay captured 6D targets offline at several speeds, without robot output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import verify_virtual_center_kinematics as probe


def GetActiveSegments(packets):
    segments = []
    active = []
    reference = None
    previous = None
    identity = None
    for packet in packets:
        sample = packet["sample"]
        current_identity = packet["value"].get("session_id")
        enabled = sample.active and sample.input_command_mode == "active"
        if active and (not enabled or current_identity != identity):
            segments.append((reference, active))
            active = []
        if enabled:
            if not active:
                reference = previous if previous is not None and current_identity == identity else packet
            active.append(packet)
        previous = packet
        identity = current_identity
    if active:
        segments.append((reference, active))
    return segments


def GetRecordedTargets(packets):
    times = np.array([p["offset_s"] - packets[0]["offset_s"] for p in packets])
    targets = []
    for packet in packets:
        arm = packet["value"]["right_arm"]
        rotation = np.asarray(arm.get("target_rotation_matrix_robot"), dtype=float)
        position = np.asarray(arm.get("target_position"), dtype=float)
        if rotation.shape != (3, 3) or position.shape != (3,):
            raise ValueError("Capture lacks recorded 6D targets; use a new Quest recording.")
        if not np.isfinite(rotation).all() or not np.isfinite(position).all():
            raise ValueError("Recorded 6D target contains non-finite values.")
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-6):
            raise ValueError("Recorded target rotation is not a proper rotation matrix.")
        targets.append(probe.base._matrix_to_se3(rotation, position))
    if np.any(np.diff(times) < 0):
        raise ValueError("Recorded target times are not monotonic.")
    return times, targets


def GetTargetIndex(times, seconds, speed):
    # 보간으로 입력을 개선하지 않고, 저장된 목표를 다음 표본까지 유지한다.
    return int(np.clip(np.searchsorted(times, seconds * speed, side="right") - 1, 0, len(times) - 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    manifest, packets = probe._decode_capture(args.capture)
    segments = GetActiveSegments(packets)
    if not segments:
        parser.error("capture contains no active segment")
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    qpos = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    result = {
        "capture_id": manifest["capture_id"],
        "capture_path": str(args.capture.resolve()),
        "robot_command": False,
        "interpretation": "Captured model-frame 6D goals replayed with zero-order hold, fixed solver dt, and per-segment pre-active measured-in-simulation pose. Not bit-exact runtime replay, hardware simulation, or physical authorization.",
        "hold_s": 5.0,
        "clearance_stride": 1,
        "segments": [],
    }
    for index, (reference, active) in enumerate(segments, 1):
        times, targets = GetRecordedTargets(active)
        initial_q = probe.base._initial_configuration(model)
        initial_q[qpos] = reference["value"]["all_joint_q_rad"]
        entry = {"segment": index, "packet_count": len(active), "duration_s": float(times[-1]), "speeds": {}}
        for speed in (1.0, 0.5, 0.25):
            motion_s = max(probe.base.DT, times[-1] / speed)

            def TargetAt(seconds):
                return targets[GetTargetIndex(times, seconds, speed)]

            metrics = probe.RunCase(model, initial_q, targets[0], "exact_posture", motion_s + 5.0,
                                    TargetAt, clearance_stride=1, trajectory_duration_s=motion_s)
            entry["speeds"][str(speed)] = metrics
            print(f"Segment {index}, {speed}x: " + json.dumps(metrics), flush=True)
        result["segments"].append(entry)
    result["review_reasons"] = []
    for entry in result["segments"]:
        for speed, metrics in entry["speeds"].items():
            label = f"segment {entry['segment']} speed {speed}"
            if metrics["settled_after_hold_s"] is None:
                result["review_reasons"].append(label + ": did not settle within 1 cm / 5 degrees during final hold")
            if metrics["sampled_minimum_clearance_mm"] < probe.live.TELEOP_COLLISION_TARGET_DISTANCE_M * 1000 - 0.5:
                result["review_reasons"].append(label + ": integrated trajectory fell below nominal IK clearance")
    result["quality_status"] = "REVIEW_REQUIRED" if result["review_reasons"] else "OFFLINE_CRITERIA_MET"
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())
    print("Quality:", result["quality_status"], "(never physical authorization)")


if __name__ == "__main__":
    main()
