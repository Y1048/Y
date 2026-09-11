"""Verify sweep artifacts and compare timestep sensitivity; no simulator or I/O to G1.

Example: python mujoco_pd_validate_results.py results/dt_1ms results/dt_0_5ms
Reads only existing run/summary/CSV files. Never changes gains or simulation data.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(folder: Path) -> dict:
    folder = folder.resolve()
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    require(run.get("schema") == "g1.mujoco.pd.run.v1", "wrong run schema")
    require(summary.get("schema") == "g1.mujoco.pd.sweep.v1", "wrong summary schema")
    require(run.get("simulation_only") is True and run.get("hardware_validated") is False,
            "not a simulation-only manifest")
    require(summary.get("simulation_only") is True and summary.get("hardware_config_modified") is False,
            "summary incorrectly claims hardware modification")
    require(summary.get("recommended_hardware_gains") is None, "must not recommend hardware gains")
    require(summary["run_sha256"] == digest(folder / "run.json"), "run hash mismatch")
    require(summary["sweep_complete"] is True, "sweep did not attempt the entire grid")
    expected = {tuple(pair) for pair in run["gain_pairs"]}
    actual = {(c["kp_proximal"], c["kd_proximal"]) for c in summary["candidates"]}
    require(len(summary["candidates"]) == len(expected) and actual == expected, "gain grid mismatch")
    compact = []
    for candidate in summary["candidates"]:
        name = candidate.get("csv")
        require(isinstance(name, str) and Path(name).name == name, "missing or unsafe CSV name")
        path = folder / name
        require(path.resolve().parent == folder, "CSV escapes results directory")
        require(candidate["csv_sha256"] == digest(path), "CSV hash mismatch: " + name)
        errors, command_errors, torques, velocities, contact, limited, clipped, cycles = [], [], [], [], [], [], [], set()
        segments = set()
        previous = None
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                t, trial = float(row["time_s"]), float(row["trial_time_s"])
                require(math.isfinite(t) and math.isfinite(trial), "invalid CSV clock")
                require(previous is None or math.isclose(t - previous, .002, rel_tol=0, abs_tol=1e-9),
                        "CSV is not contiguous at 500 Hz")
                previous = t
                require(float(row["kp_proximal"]) == candidate["kp_proximal"] and
                        float(row["kd_proximal"]) == candidate["kd_proximal"], "CSV gains differ from summary")
                if trial < 0:
                    continue
                ref, cmd, q, dq, torque = (float(row[field]) for field in
                                          ("ref_22", "cmd_22", "q_22", "dq_22", "actual_tau_22"))
                require(all(math.isfinite(x) for x in (ref, cmd, q, dq, torque)), "nonfinite CSV response")
                errors.append(ref - q)
                command_errors.append(cmd - q)
                torques.append(abs(torque))
                velocities.append(abs(dq))
                contact.append(int(row["contacts"]) > 0)
                limited.append(int(row["torque_target_limited_arm"]))
                clipped.append(int(row["hard_clipped_arm"]))
                cycles.add(int(row["cycle"]))
                segments.add((int(row["cycle"]), row["segment"]))
        require(len(errors) == candidate["samples"], "trial sample count differs")
        if candidate["completed"]:
            require(cycles == {0, 1, 2}, "completed trial lacks three cycles")
            require(all((cycle, segment) in segments for cycle in range(3) for segment in
                        ("out", "positive_hold", "cross", "negative_hold", "return", "ready_hold")),
                    "completed trial lacks round-trip segments")
        m = candidate["metrics"]
        if errors:
            calculated = {
                "reference_rmse_joint22_rad": math.sqrt(sum(x*x for x in errors) / len(errors)),
                "command_rmse_joint22_rad": math.sqrt(sum(x*x for x in command_errors) / len(errors)),
                "peak_reference_error_joint22_rad": max(map(abs, errors)),
                "peak_torque_joint22_nm": max(torques),
                "peak_speed_joint22_rad_s": max(velocities),
                "contact_sample_ratio": sum(contact) / len(errors),
                "torque_target_limit_arm_sample_ratio": sum(limited) / len(errors),
                "hard_clip_arm_sample_ratio": sum(clipped) / len(errors)}
            for field, value in calculated.items():
                require(m is not None and math.isclose(m[field], value, rel_tol=1e-10, abs_tol=1e-12),
                        f"metric differs from CSV: {name}: {field}")
        else:
            require(m is None and not candidate["completed"], "empty trial has results")
        eligible = bool(errors) and candidate["completed"] and not candidate["exclusion_reasons"]
        if m is not None:
            eligible = eligible and m["contact_sample_ratio"] == 0 and max(
                m["torque_target_limit_arm_sample_ratio"], m["hard_clip_arm_sample_ratio"]) <= run["max_limit_ratio"]
        require(candidate["eligible"] == eligible, "eligibility inconsistent with measurement")
        compact.append({"kp": candidate["kp_proximal"], "kd": candidate["kd_proximal"],
                        "completed": candidate["completed"], "eligible": eligible,
                        "samples": candidate["samples"], "reason": candidate["reason"],
                        "exclusion_reasons": candidate["exclusion_reasons"],
                        "metrics": None if m is None else {k: m[k] for k in calculated},
                        "csv_sha256": candidate["csv_sha256"]})
    ranked = sorted([c for c in compact if c["eligible"]],
                    key=lambda c: c["metrics"]["reference_rmse_joint22_rad"])
    require([(c["kp"], c["kd"]) for c in ranked] == [(c["kp"], c["kd"]) for c in summary["ranking"]],
            "ranking order differs from original reference RMSE")
    return {"folder": str(folder), "mujoco": run["mujoco"], "numpy": run["numpy"],
            "timestep_s": run["timestep_s"], "reference_hz": run["reference_hz"], "writer_hz": run["writer_hz"],
            "asset_sha256": run["asset_sha256"], "source_sha256": run["source_sha256"],
            "run_sha256": summary["run_sha256"], "summary_sha256": digest(folder / "summary.json"),
            "candidates": compact, "ranking": [(c["kp"], c["kd"]) for c in ranked]}


def compare(runs: list[dict]) -> dict:
    require(len(runs) == 2, "sensitivity comparison requires exactly two sweeps")
    first, second = runs
    for field in ("asset_sha256", "source_sha256", "reference_hz", "writer_hz", "mujoco"):
        require(first[field] == second[field], "incomparable sweeps: " + field)
    a = {(c["kp"], c["kd"]): c for c in first["candidates"]}
    b = {(c["kp"], c["kd"]): c for c in second["candidates"]}
    require(a.keys() == b.keys(), "incomparable candidate grids")
    deltas = []
    for pair in a:
        if a[pair]["metrics"] is None or b[pair]["metrics"] is None:
            continue
        x, y = (c[pair]["metrics"]["reference_rmse_joint22_rad"] for c in (a, b))
        deltas.append({"kp": pair[0], "kd": pair[1], "rmse_absolute_delta_rad": abs(x-y),
                       "rmse_relative_delta_percent": 100*abs(x-y)/abs(x) if x else None})
    return {"same_ranking": first["ranking"] == second["ranking"],
            "same_eligibility": all(a[p]["eligible"] == b[p]["eligible"] for p in a),
            "timestep_s": [r["timestep_s"] for r in runs], "candidate_deltas": deltas,
            "limitation": "Changing timestep also changes the ideal PD evaluation rate; not pure integrator convergence or hardware validation."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        runs = [validate(folder) for folder in args.folders]
        report = {"schema": "g1.mujoco.pd.artifact-validation.v1", "simulation_only": True,
                  "hardware_validated": False, "runs": runs,
                  "sensitivity": compare(runs) if len(runs) == 2 else None}
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        print(text)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ARTIFACT VALIDATION FAILED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
