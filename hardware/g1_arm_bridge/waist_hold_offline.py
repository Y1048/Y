#!/usr/bin/env python3
"""Saved-state waist HOLD study. No SDK, socket or hardware adapter integration."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

from arm_sdk_hold_contract import WAIST_INDICES, ArmSdkHoldConfig, build_measured_hold_frame

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def BuildStudyFrame(measured, target, initial_waist, *, weight, kp, kd, mode,
                    mode_pr=0, mode_machine=5):
    """Return a plain offline dict, not a publisher-ready ArmSdkCommandFrame."""
    if len(initial_waist) != 3 or not all(math.isfinite(float(q)) for q in initial_waist):
        raise ValueError("initial waist must contain three finite angles")
    if not math.isfinite(kp) or not math.isfinite(kd) or kp <= 0 or kd <= 0:
        raise ValueError("explicit positive finite study gains required")
    if type(mode) is not int or mode not in (0, 1):
        raise ValueError("explicit study mode must be 0 or 1")
    baseline = build_measured_hold_frame(measured, target, weight=weight,
        mode_pr=mode_pr, mode_machine=mode_machine, config=ArmSdkHoldConfig())
    fields = asdict(baseline)
    for name in ("motor_q_rad", "motor_mode", "motor_kp", "motor_kd"):
        fields[name] = list(fields[name])
    for index, q in zip(WAIST_INDICES, initial_waist):
        fields["motor_q_rad"][index] = float(q)
        fields["motor_mode"][index] = mode
        fields["motor_kp"][index] = kp
        fields["motor_kd"][index] = kd
    return {"offline_only": True, "hardware_authorized": False, "fields": fields}


def AnalyzeEvents(rows, *, kp, kd, mode):
    initial = next((row["details"] for row in rows
                    if row.get("details", {}).get("schedule_phase") == "READY"
                    and row["details"].get("measured_all_q_rad")), None)
    if initial is None:
        raise ValueError("READY baseline missing; do not infer initial waist from a later frame")
    initial_waist = tuple(initial["measured_all_q_rad"][12:15])
    records = []
    for row in rows:
        details = row.get("details", {})
        command = details.get("sampled_command")
        if not command:
            continue
        measured = details["measured_all_q_rad"]
        velocity = details["measured_all_dq_rad_s"]
        study = BuildStudyFrame(measured, command["q_rad"][15:29], initial_waist,
            weight=command["weight"], kp=kp, kd=kd, mode=mode,
            mode_pr=details["mode_pr"], mode_machine=details["mode_machine"])
        # Algebra evaluated on OLD measured motion, not simulated feedback or motor torque.
        pd_terms = [kp * (q - measured[j]) - kd * velocity[j]
                    for j, q in zip(WAIST_INDICES, initial_waist)]
        records.append({"phase": details["schedule_phase"],
            "write_return_unix_ns": details.get("last_successful_write_unix_ns"),
            "weight": command["weight"], "recorded_waist_q_rad": measured[12:15],
            "recorded_waist_command_q_rad": command["q_rad"][12:15],
            "recorded_waist_kp": command["waist_kp"],
            "candidate_fixed_waist_q_rad": study["fields"]["motor_q_rad"][12:15],
            "unblended_pd_algebra_nm": pd_terms})
    if not records:
        raise ValueError("no sampled commands in saved events")
    return {"schema": "g1.waist_hold.offline_study.v1", "offline_only": True,
        "hardware_authorized": False, "publisher_created": False,
        "study_kp": kp, "study_kd": kd, "study_mode": mode,
        "initial_waist_q_rad": initial_waist, "samples": records,
        "maximum_abs_unblended_pd_algebra_nm": [
            max(abs(row["unblended_pd_algebra_nm"][j]) for row in records) for j in range(3)],
        "limitations": ["No closed-loop simulation; old motion is not the candidate response.",
                        "Firmware weight blending, motor mode and control ownership are unverified.",
                        "Gains are study inputs, not approved physical gains.",
                        "No balance, collision, torque or joint-limit safety certification."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("--kp", type=float, required=True)
    parser.add_argument("--kd", type=float, required=True)
    parser.add_argument("--mode", type=int, choices=(0, 1), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = AnalyzeEvents(rows, kp=args.kp, kd=args.kd, mode=args.mode)
    result["source_events"] = str(args.events.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("OFFLINE only: no SDK / network / robot command")
    print(f"Samples: {len(result['samples'])}")
    print(f"Unblended PD algebra maximum: {result['maximum_abs_unblended_pd_algebra_nm']}")
    print("Not a prediction of actual torque or stability.")
    print(f"Result saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
