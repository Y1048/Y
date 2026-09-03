"""Audit recorded target construction offline; never change calibration or commands."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

import compare_recorded_pose_speeds as replay
from diagnose_recorded_reach import GetReachUpperBound


def OperatorToRobotDelta(value):
    values = np.asarray(value, dtype=float)
    if values.shape[-1:] != (3,) or not np.isfinite(values).all():
        raise ValueError("Finite operator position vectors required")
    return np.stack((values[..., 2], -values[..., 0], values[..., 1]), axis=-1)


def GetNecessaryScale(anchor, shoulder, deltas, radius):
    """Largest scale <=1 satisfying only the chain sphere for these recorded goals."""
    relative = np.asarray(anchor, dtype=float) - np.asarray(shoulder, dtype=float)
    deltas = np.asarray(deltas, dtype=float)
    if relative.shape != (3,) or deltas.ndim != 2 or deltas.shape[1] != 3:
        raise ValueError("One anchor and an Nx3 delta array required")
    if not np.isfinite(relative).all() or not np.isfinite(deltas).all() or not np.isfinite(radius) or radius <= 0:
        raise ValueError("Finite vectors and positive radius required")
    constant = float(relative @ relative - radius ** 2)
    if constant > 1e-10:
        raise ValueError("Anchor is already outside the necessary reach bound")
    constant = min(0., constant)
    quadratic = np.einsum("ij,ij->i", deltas, deltas)
    linear = deltas @ relative
    moving = quadratic > 1e-20
    if not np.any(moving):
        return 1.
    a, b = quadratic[moving], linear[moving]
    upper = (-b + np.sqrt(b * b - a * constant)) / a
    return float(min(1., upper.min()))


def ReadUnitySegments(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    segments, active = [], []
    for row in rows:
        if row["command_valid"] == "1":
            active.append(row)
        elif active:
            segments.append(active)
            active = []
    if active:
        segments.append(active)
    return segments


def GetVectors(rows, prefix, suffixes=("x", "y", "z")):
    values = np.array([[float(row[prefix + axis]) for axis in suffixes] for row in rows])
    if not np.isfinite(values).all():
        raise ValueError("Non-finite position data in " + prefix)
    return values


def AuditSender(rows):
    operator = GetVectors(rows, "sender_delta_")
    robot = GetVectors(rows, "sender_robot_")
    offsets = robot - OperatorToRobotDelta(operator)
    center = np.median(offsets, axis=0)
    residual = np.linalg.norm(offsets - center, axis=1)
    if residual.max() > 5e-6:
        raise ValueError("Unity sender has a changing offset or inconsistent position mapping")
    return {"rows": len(rows), "inferred_constant_center_m": center.tolist(),
        "axis_mapping_residual_max_m": float(residual.max()),
        "offset_from_current_default_center_m": (center - [.42, -.16, 1.05]).tolist(),
        "basis": "sender_robot = constant_center + [sender_delta_z, -sender_delta_x, sender_delta_y]",
        "time_start_s": float(rows[0]["time_s"]), "time_end_s": float(rows[-1]["time_s"])}


def AuditSegment(model, packets, unity_rows):
    probe = replay.probe
    configuration = probe.mink.Configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, n)]) for n in probe.base.g1.G1_29_JOINTS]
    targets = np.array([p["value"]["right_arm"]["target_position"] for p in packets])
    deltas = np.array([p["value"]["right_arm"]["target_delta"] for p in packets])
    anchors = targets - deltas
    shoulders, fk_errors = [], []
    for packet in packets:
        q = probe.base._initial_configuration(model)
        q[addresses] = packet["value"]["all_joint_q_rad"]
        configuration.update(q)
        shoulders.append(configuration.get_transform_frame_to_world("right_shoulder_pitch_link", "body").translation())
        wrist = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
        fk_errors.append(float(np.linalg.norm(wrist - packet["value"]["right_arm"]["wrist_position"])))
    shoulders = np.array(shoulders)
    anchor_drift = float(np.linalg.norm(anchors - anchors[0], axis=1).max())
    shoulder_drift = float(np.linalg.norm(shoulders - shoulders[0], axis=1).max())
    if max(fk_errors) > 1e-5 or anchor_drift > 1e-6 or shoulder_drift > 1e-6:
        raise ValueError("Capture FK, fixed anchor or fixed shoulder premise did not verify")
    radius = GetReachUpperBound(model)
    distances = np.linalg.norm(targets - shoulders, axis=1)
    outside = distances > radius + 1e-6
    worst = int(np.argmax(distances))
    # CSV feedback can identify the same target, but not the exact send/receive time.
    feedback = OperatorToRobotDelta(GetVectors(unity_rows, "backend_target_d"))
    feedback_errors = np.linalg.norm(feedback - deltas[worst], axis=1)
    matched = int(np.argmin(feedback_errors))
    row = unity_rows[matched]
    result = {"packets": len(packets), "capture_offset_start_s": packets[0]["offset_s"],
        "capture_offset_end_s": packets[-1]["offset_s"], "unity_sender": AuditSender(unity_rows),
        "anchor_m": anchors[0].tolist(), "anchor_drift_max_m": anchor_drift,
        "shoulder_m": shoulders[0].tolist(), "shoulder_drift_max_m": shoulder_drift,
        "fk_reconstruction_error_max_m": max(fk_errors),
        "initial_target_delta_norm_m": float(np.linalg.norm(deltas[0])),
        "initial_target_to_measured_wrist_m": float(np.linalg.norm(targets[0] - packets[0]["value"]["right_arm"]["wrist_position"])),
        "chain_length_upper_bound_m": radius, "provably_outside_packets": int(outside.sum()),
        "provably_outside_percent": float(100 * outside.mean()),
        "worst": {"packet_index": worst, "capture_offset_s": packets[worst]["offset_s"],
            "target_m": targets[worst].tolist(), "delta_robot_m": deltas[worst].tolist(),
            "shoulder_target_distance_m": float(distances[worst]),
            "unavoidable_position_error_lower_bound_cm": float(max(0., distances[worst] - radius) * 100),
            "nearest_unity_feedback_error_m": float(feedback_errors[matched]),
            "matching_feedback_within_csv_precision": bool(feedback_errors[matched] < 2e-6),
            "unity_observation": {k: row[k] for k in row if k.startswith(("time_", "raw_wrist_", "binder_delta_", "sender_delta_", "backend_target_", "head_"))}},
        "counterfactual": {"applied": False,
            "boundary": "Position-only necessary bound on this recording, not an IK/collision/path permit or a recommended production scale.",
            "maximum_uniform_scale_le_one": GetNecessaryScale(anchors[0], shoulders[0], deltas, radius),
            "scales": []}}
    for scale in (1., .9, .8, .7):
        alternate = anchors[0] + scale * deltas
        distance = np.linalg.norm(alternate - shoulders, axis=1)
        result["counterfactual"]["scales"].append({"scale": scale,
            "provably_outside_packets": int(np.sum(distance > radius + 1e-6)),
            "maximum_target_distance_m": float(distance.max())})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("unity_trace", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    probe = replay.probe
    manifest, packets = probe._decode_capture(args.capture)
    segments = replay.GetActiveSegments(packets)
    unity_segments = ReadUnitySegments(args.unity_trace)
    if not segments or len(segments) != len(unity_segments):
        raise ValueError("Capture and Unity active segment counts differ; do not infer correspondence")
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    root = Path(__file__).resolve().parents[2]
    sources = [args.capture, args.unity_trace, Path(__file__), Path(probe.base.g1.DEMO_XML),
        root / "Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs",
        root / "Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs",
        root / "Unity_G1_VR/Assets/Scenes/SampleScene.unity",
        root / "MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py"]
    result = {"robot_command": False, "settings_modified": False, "capture_id": manifest["capture_id"],
        "mujoco_version": probe.mujoco.__version__,
        "sha256": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "limits_of_evidence": [
            "Current source/scene settings are not a snapshot of recording-time Inspector settings.",
            "CSV lacks session/packet sequence, exact engagement neutral, locked heading and accumulated body compensation. Raw-hand to binder cannot be reconstructed exactly.",
            "CSV feedback matching confirms a sampled target value, not exact input packet identity or latency.",
            "Position sphere exterior proves unreachable for this fixed model; interior proves neither 6D IK nor collision feasibility."],
        "segments": []}
    for index, ((_, active), rows) in enumerate(zip(segments, unity_segments), 1):
        entry = AuditSegment(model, active, rows)
        entry["segment"] = index
        result["segments"].append(entry)
        print(f"Segment {index}: outside={entry['provably_outside_packets']}/{len(active)}, "
              f"anchor drift={entry['anchor_drift_max_m']:.3g} m", flush=True)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
