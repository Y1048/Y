"""Offline-only low-order identification skeleton for g1.real-response.v1."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from real_response_log import JOINT_NAMES, parse_trace


def _matrix(trace, key):
    return np.asarray([r[key] for r in trace.records], dtype=np.float64)


def estimate(trace):
    """Estimate timing and dq=a*(command-q)-b*dq+c per joint.

    Results are descriptive model parameters. They are never hardware gains.
    """
    if trace.dropped_sequences:
        raise ValueError("sequence_gaps_require_episode_rejection")
    command = _matrix(trace, "command_q_rad")
    q = _matrix(trace, "measured_q_rad")
    dq = _matrix(trace, "measured_dq_rad_s")
    times = np.asarray([r["lowstate_monotonic_ns"] for r in trace.records], dtype=np.int64)
    if len(times) < 8:
        raise ValueError("insufficient_samples")
    dt = np.diff(times).astype(np.float64) * 1e-9
    if np.any(dt <= 0):
        raise ValueError("nonpositive_sample_period")
    derivative = np.diff(dq, axis=0) / dt[:, None]
    fits = []
    for joint in range(7):
        x = np.column_stack((command[:-1, joint] - q[:-1, joint], -dq[:-1, joint], np.ones(len(dt))))
        beta, _, rank, singular = np.linalg.lstsq(x, derivative[:, joint], rcond=None)
        prediction = x @ beta
        fits.append({
            "joint": JOINT_NAMES[joint], "command_error_gain_s2": float(beta[0]),
            "effective_damping_s1": float(beta[1]), "acceleration_bias_rad_s2": float(beta[2]),
            "acceleration_rmse_rad_s2": float(np.sqrt(np.mean((prediction-derivative[:, joint])**2))),
            "rank": int(rank), "identifiable": bool(rank == 3),
        })
    target_to_command = np.asarray([r["command_monotonic_ns"]-r["target_monotonic_ns"] for r in trace.records]) * 1e-6
    command_to_state = np.asarray([r["lowstate_monotonic_ns"]-r["command_monotonic_ns"] for r in trace.records]) * 1e-6
    return {
        "schema": "g1.real-response.identification.v1", "source_sha256": trace.sha256,
        "samples": len(trace.records), "measured_data": True,
        "timing_ms": {"target_to_command_median": float(np.median(target_to_command)),
                      "command_to_lowstate_median": float(np.median(command_to_state)),
                      "lowstate_period_median": float(np.median(dt)*1000)},
        "joint_models": fits, "recommended_hardware_gains": None,
        "limitations": ["single-episode descriptive fit", "no holdout validation", "clock timestamps do not prove command acceptance"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = estimate(parse_trace(args.trace))
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
