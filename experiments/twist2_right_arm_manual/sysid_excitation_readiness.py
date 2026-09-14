"""Offline comparison of an excitation plan with a read-only DDS capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from sysid_capture import decode
from sysid_excitation_plan import PLAN_SCHEMA, RIGHT_ARM
from sysid_readonly_parse import read


SCHEMA = "g1.sysid.excitation-readiness.v1"


def _load_plan(path):
    raw = Path(path).read_bytes()
    value = decode(raw)
    if value.get("schema") != PLAN_SCHEMA:
        raise ValueError("plan_schema")
    if value.get("command_capable") is not False or value.get("execution_authorized") is not False:
        raise ValueError("plan_must_be_command_incapable")
    if value.get("joint_indices") != list(RIGHT_ARM):
        raise ValueError("plan_joint_order")
    for key, length in (("start_q_rad", 29), ("kp_nm_rad", 29), ("kd_nm_s_rad", 29)):
        data = value.get(key)
        if not isinstance(data, list) or len(data) != length or not all(
                type(x) in (int, float) and math.isfinite(x) for x in data):
            raise ValueError(f"plan_{key}")
    owner = value.get("termination_owner_contract")
    if not isinstance(owner, dict) or owner.get("status") not in ("unresolved", "reviewed"):
        raise ValueError("plan_owner_contract")
    return value, hashlib.sha256(raw).hexdigest()


def inspect(plan_path, capture_path, *, pose_tolerance_rad, velocity_tolerance_rad_s,
            minimum_tail_s=0.5):
    for name, value in (("pose_tolerance_rad", pose_tolerance_rad),
                        ("velocity_tolerance_rad_s", velocity_tolerance_rad_s),
                        ("minimum_tail_s", minimum_tail_s)):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(name)
    plan, plan_sha = _load_plan(plan_path)
    rows = read(capture_path)
    end_ns = rows[-1]["state_receive_ns"]
    tail = [x for x in rows if (end_ns - x["state_receive_ns"]) * 1e-9 <= minimum_tail_s]
    if len(tail) < 2:
        raise ValueError("insufficient_tail_samples")
    tail_duration = (tail[-1]["state_receive_ns"] - tail[0]["state_receive_ns"]) * 1e-9
    pose_errors = [max(abs(x["measured_q"][j] - plan["start_q_rad"][j]) for j in RIGHT_ARM) for x in tail]
    velocities = [max(abs(x["measured_dq"][j]) for j in RIGHT_ARM) for x in tail]
    modes = sorted({(x["mode_pr"], x["mode_machine"]) for x in tail})
    commanded = [x for x in tail if x["has_command"]]
    gain_matches = None
    if commanded:
        gain_matches = all(
            x["kp"] == plan["kp_nm_rad"] and x["kd"] == plan["kd_nm_s_rad"]
            for x in commanded
        )
    blockers = []
    if tail_duration < minimum_tail_s * 0.9:
        blockers.append("tail_duration_too_short")
    if max(pose_errors) > pose_tolerance_rad:
        blockers.append("right_arm_start_pose_mismatch")
    if max(velocities) > velocity_tolerance_rad_s:
        blockers.append("right_arm_not_stationary")
    if len(modes) != 1:
        blockers.append("mode_not_stable")
    if gain_matches is False:
        blockers.append("observed_gain_contract_mismatch")
    if plan["termination_owner_contract"]["status"] != "reviewed":
        blockers.append("termination_owner_contract_unresolved")
    return {
        "schema": SCHEMA,
        "plan_sha256": plan_sha,
        "capture_sha256": hashlib.sha256(Path(capture_path).read_bytes()).hexdigest(),
        "capture_session": rows[0]["session"],
        "tail_samples": len(tail),
        "tail_duration_s": tail_duration,
        "observed_modes": [{"mode_pr": x[0], "mode_machine": x[1]} for x in modes],
        "right_arm_start_error_abs_max_rad": max(pose_errors),
        "right_arm_velocity_abs_max_rad_s": max(velocities),
        "observed_command_samples": len(commanded),
        "observed_gains_match_plan": gain_matches,
        "data_collection_preflight_passed": not blockers,
        "blockers": blockers,
        "physical_execution_authorized": False,
        "recommended_hardware_gains": None,
        "limitations": [
            "offline evidence only; this tool cannot observe current robot state",
            "mode numbers are recorded facts, not interpreted ownership proof",
            "missing LowCmd means gains are unobserved, not matched",
            "passing does not authorize or establish physical safety",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--pose-tolerance-rad", type=float, required=True)
    parser.add_argument("--velocity-tolerance-rad-s", type=float, required=True)
    parser.add_argument("--minimum-tail-s", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = inspect(args.plan, args.capture,
                     pose_tolerance_rad=args.pose_tolerance_rad,
                     velocity_tolerance_rad_s=args.velocity_tolerance_rad_s,
                     minimum_tail_s=args.minimum_tail_s)
    with args.output.open("xb") as stream:
        stream.write(json.dumps(result, sort_keys=True, separators=(",", ":")).encode())


if __name__ == "__main__":
    main()
