"""Measure right-arm tracking in a recorded native-writer CSV.

This is read-only analysis.  It does not claim that untried PD gains can be
ranked from a single closed-loop trace.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


JOINTS = range(22, 29)


def _rms(values):
    return math.sqrt(sum(x * x for x in values) / len(values))


def _percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]


def _best_lag(target, measured, dt, max_lag_s=0.5):
    best = None
    for shift in range(0, min(len(target) // 3, int(max_lag_s / dt) + 1)):
        errors = [target[k] - measured[k + shift] for k in range(len(target) - shift)]
        score = _rms(errors)
        if best is None or score < best[0]:
            best = score, shift
    return best[1] * dt, best[0]


def analyze(path):
    path = Path(path)
    samples = []
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("writer_valid") != "1" or row.get("phase") != "arm_tracking":
                continue
            sequence = int(row["writer_sequence"])
            if sequence in seen:
                continue
            seen.add(sequence)
            samples.append(row)
    if len(samples) < 20:
        raise ValueError("insufficient unique arm_tracking samples")
    times = [float(r["writer_write_returned_s"]) for r in samples]
    gaps = [b - a for a, b in zip(times, times[1:])]
    if not gaps or min(gaps) <= 0:
        raise ValueError("writer time is not strictly increasing")
    dt = sorted(gaps)[len(gaps) // 2]
    results = []
    for joint in JOINTS:
        target = [float(r[f"writer_target_{joint}"]) for r in samples]
        q = [float(r[f"writer_q_{joint}"]) for r in samples]
        dq = [float(r[f"writer_dq_{joint}"]) for r in samples]
        error = [a - b for a, b in zip(target, q)]
        lag_s, aligned_rmse = _best_lag(target, q, dt)
        kp = {round(float(r[f"writer_kp_{joint}"]), 6) for r in samples}
        kd = {round(float(r[f"writer_kd_{joint}"]), 6) for r in samples}
        if len(kp) != 1 or len(kd) != 1:
            raise ValueError(f"gain changed during trace for joint {joint}")
        results.append({
            "joint": joint,
            "kp": next(iter(kp)),
            "kd": next(iter(kd)),
            "target_range_rad": max(target) - min(target),
            "rmse_rad": _rms(error),
            "mae_rad": sum(abs(x) for x in error) / len(error),
            "p95_abs_error_rad": _percentile([abs(x) for x in error], 0.95),
            "peak_abs_error_rad": max(abs(x) for x in error),
            "estimated_lag_s": lag_s,
            "lag_aligned_rmse_rad": aligned_rmse,
            "peak_abs_measured_speed_rad_s": max(abs(x) for x in dq),
        })
    return {
        "schema": "g1.vr_pd_replay_review.v1",
        "source": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "tracking_samples": len(samples),
        "duration_s": times[-1] - times[0],
        "median_sample_period_s": dt,
        "joints": results,
        "counterfactual_gain_ranking": False,
        "limitation": "One closed-loop recording at one gain setting measures that run, but cannot predict the motion produced by untried Kp/Kd values without a separately validated plant model or additional excitation runs.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = analyze(args.csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
