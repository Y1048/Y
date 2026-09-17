"""Train the independent upper-body-conditioned G1 locomotion task.

Simulation/training only. This file has no Unitree SDK, DDS, networking, or
deployment dependency.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import replace
from pathlib import Path

import mjlab.tasks  # noqa: F401: register upstream task components
from mjlab.scripts.train import TrainConfig, launch_training
from mjlab.tasks.registry import register_mjlab_task
from mjlab.tasks.velocity.config.g1.rl_cfg import unitree_g1_ppo_runner_cfg
from mjlab.tasks.velocity.rl import VelocityOnPolicyRunner

from upper_body_conditioned_env import make_upper_body_conditioned_g1_env_cfg


TASK_ID = "Local-UpperConditioned-Velocity-Flat-Unitree-G1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--num-envs", type=int, default=16)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1509)
    parser.add_argument("--trajectory-manifest", type=Path)
    parser.add_argument("--trajectory-split", choices=("train", "validation"), default="train")
    parser.add_argument("--upper-mode", choices=("fixed", "recorded"), default="recorded")
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument("--recorded-scale-start", type=float, default=1.0)
    parser.add_argument("--recorded-scale-end", type=float, default=1.0)
    parser.add_argument("--recorded-ramp-iterations", type=int, default=0)
    args = parser.parse_args()

    if args.result.exists():
        raise FileExistsError(args.result)
    if args.num_envs < 1 or args.iterations < 1:
        raise ValueError("num-envs and iterations must be positive")
    if args.upper_mode == "recorded" and args.trajectory_manifest is None:
        raise ValueError("recorded mode requires --trajectory-manifest")
    if not (0.0 <= args.recorded_scale_start <= args.recorded_scale_end <= 1.0):
        raise ValueError("recorded scales must satisfy 0 <= start <= end <= 1")
    if args.recorded_ramp_iterations < 0:
        raise ValueError("recorded-ramp-iterations must be nonnegative")

    recorded_ramp_steps = args.recorded_ramp_iterations * 24

    manifest = str(args.trajectory_manifest.resolve()) if args.trajectory_manifest else None
    env_cfg = make_upper_body_conditioned_g1_env_cfg(
        trajectory_manifest=manifest, trajectory_split=args.trajectory_split,
        fixed_upper=args.upper_mode == "fixed",
        recorded_scale_start=args.recorded_scale_start,
        recorded_scale_end=args.recorded_scale_end,
        recorded_ramp_steps=recorded_ramp_steps,
    )
    play_cfg = make_upper_body_conditioned_g1_env_cfg(
        play=True, trajectory_manifest=manifest, trajectory_split=args.trajectory_split,
        fixed_upper=args.upper_mode == "fixed",
        recorded_scale_start=args.recorded_scale_start,
        recorded_scale_end=args.recorded_scale_end,
        recorded_ramp_steps=recorded_ramp_steps,
    )
    env_cfg.scene.num_envs = args.num_envs
    env_cfg.seed = args.seed

    rl_cfg = unitree_g1_ppo_runner_cfg()
    rl_cfg.seed = args.seed
    rl_cfg.max_iterations = args.iterations
    rl_cfg.save_interval = min(50, args.iterations)
    rl_cfg.experiment_name = "g1_upper_conditioned_training"
    rl_cfg.run_name = args.upper_mode
    rl_cfg.logger = "tensorboard"

    experiment_dir = args.log_root.resolve() / rl_cfg.experiment_name
    existing_runs = set(experiment_dir.iterdir()) if experiment_dir.exists() else set()
    if args.resume_checkpoint:
        checkpoint = args.resume_checkpoint.resolve()
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        resume_dir = experiment_dir / f"resume_{args.upper_mode}"
        resume_dir.mkdir(parents=True, exist_ok=True)
        copied_checkpoint = resume_dir / checkpoint.name
        shutil.copy2(checkpoint, copied_checkpoint)
        rl_cfg.resume = True
        rl_cfg.load_run = f"resume_{args.upper_mode}"
        rl_cfg.load_checkpoint = checkpoint.name.replace(".", r"\.")

    register_mjlab_task(
        task_id=TASK_ID,
        env_cfg=env_cfg,
        play_env_cfg=play_cfg,
        rl_cfg=rl_cfg,
        runner_cls=VelocityOnPolicyRunner,
    )

    train_cfg = replace(
        TrainConfig.from_task(TASK_ID),
        log_root=str(args.log_root),
        gpu_ids=[0],
    )
    launch_training(TASK_ID, train_cfg)

    run_dirs = sorted(
        path for path in experiment_dir.iterdir()
        if path.is_dir() and path not in existing_runs and not path.name.startswith("resume_")
    )
    if not run_dirs:
        raise RuntimeError(f"No training run directory under {experiment_dir}")
    run_dir = run_dirs[-1]
    checkpoints = sorted(run_dir.glob("model_*.pt"))
    required = (run_dir / "params" / "env.yaml", run_dir / "params" / "agent.yaml")
    if not checkpoints or not all(path.is_file() for path in required):
        raise RuntimeError(f"Incomplete training artifacts in {run_dir}")

    result = {
        "schema": "g1.mjlab.upper_conditioned.training.v1",
        "status": "passed",
        "simulation_only": True,
        "pipeline_smoke": args.iterations <= 2,
        "trained_walking_policy": False,
        "hardware_validation": False,
        "task_id": TASK_ID,
        "num_envs": args.num_envs,
        "iterations": args.iterations,
        "policy_action_dim": 12,
        "upper_target_observation_dim": 17,
        "trajectory_manifest": manifest,
        "trajectory_split": args.trajectory_split,
        "upper_mode": args.upper_mode,
        "recorded_scale_start": args.recorded_scale_start,
        "recorded_scale_end": args.recorded_scale_end,
        "recorded_ramp_iterations": args.recorded_ramp_iterations,
        "resume_checkpoint": str(args.resume_checkpoint.resolve()) if args.resume_checkpoint else None,
        "run_dir": str(run_dir),
        "checkpoints": [str(path) for path in checkpoints],
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
