"""Deterministic, weight-frozen validation for a trained mjlab checkpoint."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch
from mjlab.envs import ManagerBasedRlEnv
from mjlab.rl import RslRlVecEnvWrapper
from mjlab.tasks.velocity.config.g1.rl_cfg import unitree_g1_ppo_runner_cfg
from mjlab.tasks.velocity.rl import VelocityOnPolicyRunner
from mjlab.utils.lab_api.math import euler_xyz_from_quat

from upper_body_conditioned_env import make_upper_body_conditioned_g1_env_cfg


def _state_snapshot(runner) -> dict[str, torch.Tensor]:
    policy = runner.alg.get_policy()
    return {name: value.detach().cpu().clone() for name, value in policy.state_dict().items()}


def _unchanged(before, after) -> bool:
    return before.keys() == after.keys() and all(torch.equal(before[k], after[k]) for k in before)


def evaluate_seed(checkpoint: Path, manifest: Path, commands, seed: int, steps: int):
    cfg = make_upper_body_conditioned_g1_env_cfg(
        play=True, trajectory_manifest=str(manifest), trajectory_split="validation"
    )
    cfg.scene.num_envs = len(commands)
    cfg.seed = seed
    agent_cfg = unitree_g1_ppo_runner_cfg()
    agent_cfg.seed = seed
    wrapped = RslRlVecEnvWrapper(
        ManagerBasedRlEnv(cfg=cfg, device="cuda:0"), clip_actions=agent_cfg.clip_actions
    )
    try:
        runner = VelocityOnPolicyRunner(wrapped, asdict(agent_cfg), device="cuda:0")
        runner.load(str(checkpoint), load_cfg={"actor": True}, strict=True, map_location="cuda:0")
        policy = runner.get_inference_policy(device="cuda:0")
        before = _state_snapshot(runner)

        command = torch.tensor(commands, device="cuda:0", dtype=torch.float32)
        term = wrapped.unwrapped.command_manager.get_term("twist")
        term.is_heading_env[:] = False
        term.is_standing_env[:] = False
        term.is_world_env[:] = False
        term.is_forward_env[:] = False

        alive = torch.ones(len(commands), device="cuda:0", dtype=torch.bool)
        fell = torch.zeros_like(alive)
        linear_sq = torch.zeros(len(commands), device="cuda:0")
        yaw_sq = torch.zeros(len(commands), device="cuda:0")
        sample_count = torch.zeros(len(commands), device="cuda:0")
        attitude_max = torch.zeros(len(commands), device="cuda:0")
        slip_sum = torch.zeros(len(commands), device="cuda:0")
        slip_count = torch.zeros(len(commands), device="cuda:0")
        robot = wrapped.unwrapped.scene["robot"]
        foot_ids, _ = robot.find_sites(("left_foot", "right_foot"), preserve_order=True)
        contact = wrapped.unwrapped.scene["feet_ground_contact"]

        term.vel_command_b[:] = command
        obs = wrapped.get_observations()
        with torch.inference_mode():
            for _ in range(steps):
                term.vel_command_b[:] = command
                action = policy(obs)
                obs, _reward, dones, extras = wrapped.step(action)
                timeouts = extras.get("time_outs", torch.zeros_like(dones, dtype=torch.bool)).bool()
                new_fall = alive & dones.bool() & ~timeouts

                vel = robot.data.root_link_lin_vel_b[:, :2]
                yaw = robot.data.root_link_ang_vel_b[:, 2]
                roll, pitch, _ = euler_xyz_from_quat(robot.data.root_link_quat_w)
                attitude = torch.maximum(torch.abs(roll), torch.abs(pitch))
                valid = alive.float()
                linear_sq += torch.sum((vel - command[:, :2]) ** 2, dim=1) * valid
                yaw_sq += (yaw - command[:, 2]) ** 2 * valid
                sample_count += valid
                attitude_max = torch.maximum(attitude_max, attitude * valid)

                found = contact.data.found
                if found is not None:
                    foot_speed = torch.norm(robot.data.site_lin_vel_w[:, foot_ids, :2], dim=-1)
                    touching = found[:, : len(foot_ids)] > 0
                    slip_sum += torch.sum(foot_speed * touching * alive[:, None], dim=1)
                    slip_count += torch.sum(touching * alive[:, None], dim=1)

                fell |= new_fall
                alive &= ~new_fall
                term.vel_command_b[:] = command
                obs = wrapped.get_observations()

        after = _state_snapshot(runner)
        denom = torch.clamp(sample_count, min=1)
        return {
            "seed": seed,
            "weights_and_normalizers_unchanged": _unchanged(before, after),
            "episodes": [
                {
                    "command_m_s_rad_s": list(commands[i]),
                    "fell": bool(fell[i].item()),
                    "samples_before_fall": int(sample_count[i].item()),
                    "base_linear_velocity_rmse_m_s": float(torch.sqrt(linear_sq[i] / denom[i]).item()),
                    "base_yaw_velocity_rmse_rad_s": float(torch.sqrt(yaw_sq[i] / denom[i]).item()),
                    "base_roll_pitch_abs_max_rad": float(attitude_max[i].item()),
                    "foot_slip_velocity_mean_m_s": float((slip_sum[i] / torch.clamp(slip_count[i], min=1)).item()),
                }
                for i in range(len(commands))
            ],
        }
    finally:
        wrapped.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, help="Pipeline smoke override; makes result non-protocol-compliant")
    parser.add_argument("--max-seeds", type=int, help="Pipeline smoke override; makes result non-protocol-compliant")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("schema") != "g1.mjlab.locomotion_evaluation_protocol.v1":
        raise ValueError("Wrong evaluation protocol")
    manifest = (args.protocol.parent / protocol["validation_trajectory_manifest"]).resolve()
    seeds = protocol["seeds"][: args.max_seeds]
    steps = args.steps or round(protocol["episode_duration_s"] / 0.02)
    results = [evaluate_seed(args.checkpoint.resolve(), manifest, protocol["velocity_commands_m_s_rad_s"], seed, steps) for seed in seeds]
    episodes = [episode for result in results for episode in result["episodes"]]
    result = {
        "schema": "g1.mjlab.upper_conditioned.evaluation.v1",
        "status": "completed",
        "simulation_only": True,
        "hardware_validation": False,
        "checkpoint": str(args.checkpoint.resolve()),
        "protocol": str(args.protocol.resolve()),
        "protocol_compliant": args.steps is None and args.max_seeds is None,
        "weights_and_normalizers_unchanged": all(r["weights_and_normalizers_unchanged"] for r in results),
        "fall_rate": sum(e["fell"] for e in episodes) / len(episodes),
        "episode_count": len(episodes),
        "steps_requested": steps,
        "seed_results": results,
    }
    if not result["weights_and_normalizers_unchanged"]:
        raise RuntimeError("Evaluation mutated policy weights or observation normalizers")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "seed_results"}))


if __name__ == "__main__":
    main()
