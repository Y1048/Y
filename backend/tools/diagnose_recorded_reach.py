"""Prove impossible captured wrist targets using a model-derived reach upper bound."""

import argparse
import json
from pathlib import Path

import numpy as np

import compare_recorded_pose_speeds as replay

probe = replay.probe


def GetReachUpperBound(model, shoulder_name="right_shoulder_pitch_link", wrist_name="right_wrist_yaw_link"):
    """삼각부등식에 의한 상한. 구 내부가 도달 가능하다는 뜻은 아니다."""
    shoulder = probe.base.g1.get_body_id(model, shoulder_name)
    body = probe.base.g1.get_body_id(model, wrist_name)
    lengths = []
    while body != shoulder:
        if body == 0:
            raise ValueError("Wrist must descend from the selected shoulder.")
        for joint in range(int(model.body_jntadr[body]), int(model.body_jntadr[body] + model.body_jntnum[body])):
            if model.jnt_type[joint] != probe.mujoco.mjtJoint.mjJNT_HINGE or np.linalg.norm(model.jnt_pos[joint]) > 1e-10:
                raise ValueError("Reach proof requires origin-centered hinge joints along this chain.")
        lengths.append(float(np.linalg.norm(model.body_pos[body])))
        body = int(model.body_parentid[body])
    return sum(lengths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--result-json", type=Path, required=True)
    args = parser.parse_args()
    manifest, packets = probe._decode_capture(args.capture)
    model = probe.mujoco.MjModel.from_xml_path(str(probe.base.g1.DEMO_XML))
    probe.base._apply_operational_joint_limits(model)
    bound = GetReachUpperBound(model)
    configuration = probe.mink.Configuration(model)
    ids = [int(model.jnt_qposadr[probe.base._joint_id(model, name)]) for name in probe.base.g1.G1_29_JOINTS]
    result = {
        "capture_id": manifest["capture_id"], "robot_command": False,
        "interpretation": "Outside the chain-length sphere is provably unreachable for this model. Inside is NOT a collision-free or pose-feasible permit. Bound excludes palm/tool offsets and refers to yaw-wrist body origin.",
        "shoulder_to_yaw_wrist_upper_bound_m": bound,
        "segments": [],
    }
    for index, (reference, active) in enumerate(replay.GetActiveSegments(packets), 1):
        distances = []
        fk_errors = []
        for packet in active:
            q = probe.base._initial_configuration(model)
            q[ids] = packet["value"]["all_joint_q_rad"]
            configuration.update(q)
            arm = packet["value"]["right_arm"]
            shoulder = configuration.get_transform_frame_to_world("right_shoulder_pitch_link", "body").translation()
            wrist = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
            fk_errors.append(float(np.linalg.norm(wrist - arm["wrist_position"])))
            distances.append(float(np.linalg.norm(np.array(arm["target_position"]) - shoulder)))
        # 모델/기준 좌표가 일치하지 않으면 도달 불가 판정을 내리지 않는다.
        if max(fk_errors) > 1e-5:
            raise ValueError("Current model FK does not match recorded wrist positions; do not infer reachability.")
        entry = {
            "segment": index, "active_packets": len(active),
            "provably_outside_packets": sum(d > bound + 1e-6 for d in distances),
            "maximum_shoulder_target_distance_m": max(distances),
            "last_shoulder_target_distance_m": distances[-1],
            "maximum_reconstruction_error_m": max(fk_errors),
            "static_last_target_ablations": {},
        }
        q = probe.base._initial_configuration(model)
        q[ids] = reference["value"]["all_joint_q_rad"]
        _, targets = replay.GetRecordedTargets(active)
        if len(active) >= 10:
            for label, frame, cost_scale in (
                ("current", "right_wrist_roll_link", 1.0),
                ("yaw_position", "right_wrist_yaw_link", 1.0),
                ("no_posture_bias", "right_wrist_roll_link", 0.0),
            ):
                entry["static_last_target_ablations"][label] = probe.RunCase(
                    model, q, targets[-1], "exact_posture", 6.0, clearance_stride=1,
                    position_frame=frame, posture_scale=cost_scale,
                )
        result["segments"].append(entry)
        print(json.dumps(entry), flush=True)
    result["quality_status"] = "REVIEW_REQUIRED"
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print("Result saved to:", args.result_json.resolve())


if __name__ == "__main__":
    main()
