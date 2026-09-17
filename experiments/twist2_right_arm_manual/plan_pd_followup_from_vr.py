"""Create a small, explicit follow-up gain plan from a VR replay review."""
import argparse
import json
from pathlib import Path


def build(review):
    if review.get("schema") != "g1.vr_pd_replay_review.v1":
        raise ValueError("unsupported replay review")
    by_joint = {j["joint"]: j for j in review["joints"]}
    if set(by_joint) != set(range(22, 29)):
        raise ValueError("right-arm review must contain joints 22..28")
    baseline = {str(j): {"kp": by_joint[j]["kp"], "kd": by_joint[j]["kd"]} for j in by_joint}
    candidates = []
    for name, proximal_kp in (("baseline", 40.0), ("proximal_kp48", 48.0), ("proximal_kp56", 56.0)):
        gains = json.loads(json.dumps(baseline))
        for joint in range(22, 26):
            gains[str(joint)] = {"kp": proximal_kp, "kd": 5.0}
        candidates.append({"name": name, "gains": gains})
    return {
        "schema": "g1.pd.followup_plan.v1",
        "offline_only": True,
        "source_csv_sha256": review["sha256"],
        "fixed_trajectory": "three-cycle scripted forward reach/return",
        "candidate_order": "baseline, proximal_kp48, proximal_kp56",
        "candidates": candidates,
        "ranking_metrics": ["tracking_rmse_rad", "peak_abs_error_rad", "overshoot_rad", "settling_time_s", "peak_abs_tau_est_nm", "body_roll_pitch"],
        "stop_rule": "Do not advance after a fault, torque limiting, growing oscillation, or worse baseline repeatability.",
        "note": "This is a minimal data-collection plan, not predicted optimal gains or hardware approval. Kd remains 5 as requested; wrist gains remain 20/1.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("review", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    plan = build(json.loads(args.review.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
