"""Summarize train-only TensorBoard curves without reading validation episodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


WANTED = {
    "Train/mean_reward": "mean_reward",
    "Train/mean_episode_length": "mean_episode_length",
    "Metrics/twist/error_vel_xy": "velocity_xy_error",
    "Metrics/twist/error_vel_yaw": "velocity_yaw_error",
    "Episode_Termination/fell_over": "fell_over_log_value",
    "Metrics/slip_velocity_mean": "slip_velocity_mean",
}


def summarize(run_dir: Path, window: int) -> dict:
    event_files = list(run_dir.glob("events.out.tfevents.*"))
    if len(event_files) != 1:
        raise ValueError(f"Expected one event file in {run_dir}, got {len(event_files)}")
    acc = EventAccumulator(str(event_files[0]), size_guidance={"scalars": 0})
    acc.Reload()
    tags = set(acc.Tags()["scalars"])
    result = {"run_dir": str(run_dir.resolve()), "window_iterations": window, "metrics": {}}
    for tag, name in WANTED.items():
        if tag not in tags:
            continue
        events = acc.Scalars(tag)
        values = np.asarray([event.value for event in events[-window:]], dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f"Nonfinite TensorBoard values: {tag}")
        result["metrics"][name] = {
            "last": float(values[-1]),
            "window_mean": float(values.mean()),
            "window_min": float(values.min()),
            "window_max": float(values.max()),
            "sample_count": int(len(values)),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-run", type=Path, required=True)
    parser.add_argument("--recorded-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--window", type=int, default=50)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {
        "schema": "g1.mjlab.matched_training_summary.v1",
        "status": "completed",
        "simulation_only": True,
        "validation_data_read": False,
        "selection_decision": None,
        "fixed": summarize(args.fixed_run, args.window),
        "recorded": summarize(args.recorded_run, args.window),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
