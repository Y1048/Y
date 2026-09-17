"""Smoke-test the independent 12-leg-action, upper-conditioned G1 task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import mjlab.tasks  # noqa: F401: register upstream components
from mjlab.envs import ManagerBasedRlEnv

from upper_body_conditioned_env import make_upper_body_conditioned_g1_env_cfg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trajectory-manifest", type=Path)
    parser.add_argument("--trajectory-split", choices=("train", "validation"), default="train")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    cfg = make_upper_body_conditioned_g1_env_cfg(
        trajectory_manifest=(
            str(args.trajectory_manifest.resolve()) if args.trajectory_manifest else None
        ),
        trajectory_split=args.trajectory_split,
    )
    cfg.scene.num_envs = 4
    cfg.seed = 1509
    env = ManagerBasedRlEnv(cfg=cfg, device="cuda:0")
    try:
        obs, _ = env.reset()
        action_names = tuple(env.action_manager.get_term("joint_pos").target_names)
        if env.action_manager.total_action_dim != 12:
            raise RuntimeError(f"Expected 12 actions, got {env.action_manager.total_action_dim}")
        if any("waist" in name or "shoulder" in name or "elbow" in name or "wrist" in name for name in action_names):
            raise RuntimeError(f"Upper joint leaked into policy action: {action_names}")
        if len(action_names) != 12:
            raise RuntimeError(f"Expected 12 leg targets, got {action_names}")

        actions = torch.zeros((env.num_envs, 12), device=env.device)
        initial_target = env._g1_upper_target.clone()
        resets = 0
        for _ in range(100):
            obs, reward, terminated, truncated, _ = env.step(actions)
            for value in (*obs.values(), reward):
                if isinstance(value, torch.Tensor) and not torch.isfinite(value).all():
                    raise RuntimeError("Nonfinite observation/reward")
            resets += int((terminated | truncated).sum().item())

        target_delta = torch.max(torch.abs(env._g1_upper_target - initial_target)).item()
        if target_delta <= 1e-4:
            raise RuntimeError("Upper target did not change")

        result = {
            "schema": "g1.mjlab.upper_conditioned.smoke.v1",
            "status": "passed",
            "simulation_only": True,
            "trained_policy": False,
            "hardware_validation": False,
            "num_envs": env.num_envs,
            "steps": 100,
            "policy_action_dim": env.action_manager.total_action_dim,
            "policy_action_joint_names": action_names,
            "upper_target_dim": env._g1_upper_target.shape[1],
            "upper_target_joint_names": env._g1_upper_joint_names,
            "upper_target_delta_abs_max_rad": target_delta,
            "trajectory_split": args.trajectory_split if args.trajectory_manifest else "generated_sine",
            "reset_count": resets,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        env.close()


if __name__ == "__main__":
    main()
