"""Independent mjlab G1 velocity task with 12 leg actions and upper-body targets.

Simulation/training only. This module does not contain Unitree SDK, DDS, networking,
or deployment code.
"""

from __future__ import annotations

import math
import json
from pathlib import Path

import numpy as np
import torch

from mjlab.asset_zoo.robots import G1_ACTION_SCALE
from mjlab.envs import ManagerBasedRlEnvCfg
from mjlab.envs.mdp.actions import JointPositionActionCfg
from mjlab.managers.event_manager import EventTermCfg
from mjlab.managers.observation_manager import ObservationTermCfg
from mjlab.tasks.velocity.config.g1.env_cfgs import unitree_g1_flat_env_cfg


LEG_JOINT_PATTERNS = (
    r".*_hip_pitch_joint",
    r".*_hip_roll_joint",
    r".*_hip_yaw_joint",
    r".*_knee_joint",
    r".*_ankle_pitch_joint",
    r".*_ankle_roll_joint",
)

LEG_ACTION_SCALE = {
    pattern: G1_ACTION_SCALE[pattern] for pattern in LEG_JOINT_PATTERNS
}

UPPER_JOINT_PATTERNS = (
    r"waist_.*_joint",
    r".*_shoulder_pitch_joint",
    r".*_shoulder_roll_joint",
    r".*_shoulder_yaw_joint",
    r".*_elbow_joint",
    r".*_wrist_roll_joint",
    r".*_wrist_pitch_joint",
    r".*_wrist_yaw_joint",
)

# Conservative fixture amplitudes. They exercise changing inertial loads without
# claiming to reproduce the final Mink workspace or physical G1 limits.
UPPER_AMPLITUDE = {
    "waist_yaw_joint": 0.0,
    "waist_roll_joint": 0.0,
    "waist_pitch_joint": 0.0,
    "left_shoulder_pitch_joint": 0.35,
    "left_shoulder_roll_joint": 0.18,
    "left_shoulder_yaw_joint": 0.20,
    "left_elbow_joint": 0.40,
    "left_wrist_roll_joint": 0.15,
    "left_wrist_pitch_joint": 0.12,
    "left_wrist_yaw_joint": 0.12,
    "right_shoulder_pitch_joint": 0.35,
    "right_shoulder_roll_joint": 0.18,
    "right_shoulder_yaw_joint": 0.20,
    "right_elbow_joint": 0.40,
    "right_wrist_roll_joint": 0.15,
    "right_wrist_pitch_joint": 0.12,
    "right_wrist_yaw_joint": 0.12,
}


def _upper_state(env):
    """Resolve and cache ordered upper-body ids, defaults, phase and targets."""
    if not hasattr(env, "_g1_upper_joint_ids"):
        robot = env.scene["robot"]
        ids, names = robot.find_joints(UPPER_JOINT_PATTERNS, preserve_order=False)
        if len(ids) != 17:
            raise RuntimeError(f"Expected 17 upper joints, resolved {len(ids)}: {names}")
        env._g1_upper_joint_ids = torch.tensor(ids, device=env.device, dtype=torch.long)
        env._g1_upper_joint_names = tuple(names)
        env._g1_upper_default = robot.data.default_joint_pos[:, env._g1_upper_joint_ids].clone()
        env._g1_upper_amplitude = torch.tensor(
            [UPPER_AMPLITUDE[name] for name in names], device=env.device
        ).unsqueeze(0)
        env._g1_upper_phase = torch.linspace(
            0.0, math.pi, env.num_envs, device=env.device
        ).unsqueeze(1)
        env._g1_upper_target = env._g1_upper_default.clone()
    return (
        env._g1_upper_joint_ids,
        env._g1_upper_default,
        env._g1_upper_amplitude,
        env._g1_upper_phase,
    )


def apply_smooth_upper_target(env, env_ids, period_s: float = 6.0) -> None:
    """Write a deterministic, smooth upper target without adding policy actions."""
    del env_ids
    ids, default, amplitude, phase = _upper_state(env)
    time_s = env.common_step_counter * env.step_dt
    wave = torch.sin(torch.tensor(2.0 * math.pi * time_s / period_s, device=env.device) + phase)
    # Mirror the two arms through joint-specific signed amplitudes by alternating
    # environment phase, while keeping the target continuous and bounded.
    target = default + wave * amplitude
    env._g1_upper_target[:] = target
    env.scene["robot"].set_joint_position_target(target, joint_ids=ids)


def apply_fixed_upper_target(env, env_ids) -> None:
    """Hold the upper body at defaults while preserving the 17-value observation."""
    del env_ids
    ids, default, _amplitude, _phase = _upper_state(env)
    env._g1_upper_target[:] = default
    env.scene["robot"].set_joint_position_target(default, joint_ids=ids)


def recorded_scale_at_step(
    step: int, start: float, end: float, ramp_steps: int,
) -> float:
    """Return the bounded linear recorded-motion curriculum scale."""
    if not (0.0 <= start <= end <= 1.0) or ramp_steps < 0:
        raise ValueError("Invalid recorded trajectory curriculum")
    if ramp_steps == 0:
        return end
    fraction = min(max(step, 0) / ramp_steps, 1.0)
    return start + (end - start) * fraction


def apply_recorded_upper_target(
    env, env_ids, manifest_path: str, split: str,
    scale_start: float = 1.0, scale_end: float = 1.0, ramp_steps: int = 0,
) -> None:
    """Replay a frozen command-only trajectory split across vector environments."""
    del env_ids
    ids, default, _amplitude, _phase = _upper_state(env)
    cache_key = (manifest_path, split)
    if getattr(env, "_g1_trajectory_cache_key", None) != cache_key:
        from mink_trajectory_dataset import load_split, sha256

        manifest_file = Path(manifest_path)
        body = json.loads(manifest_file.read_text(encoding="utf-8"))
        episodes = load_split(manifest_file, split)
        data_file = Path(body["data_file"])
        if sha256(data_file) != body["data_sha256"]:
            raise ValueError("Trajectory data hash mismatch")
        archive = np.load(data_file, allow_pickle=False)
        loaded = []
        for episode in episodes:
            key = episode["episode_id"]
            time = torch.as_tensor(archive[f"{key}_time_s"], device=env.device)
            offset = torch.as_tensor(
                archive[f"{key}_right_offset_rad"], device=env.device
            )
            if time.ndim != 1 or offset.shape != (time.numel(), 7):
                raise ValueError(f"Invalid episode arrays: {key}")
            loaded.append((time, offset))
        env._g1_recorded_episodes = loaded
        env._g1_right_columns = torch.tensor(
            [env._g1_upper_joint_names.index(name) for name in body["right_joint_names"]],
            device=env.device,
            dtype=torch.long,
        )
        env._g1_trajectory_cache_key = cache_key

    target = default.clone()
    scale = recorded_scale_at_step(
        int(env.common_step_counter), scale_start, scale_end, ramp_steps
    )
    env._g1_recorded_scale = scale
    elapsed = torch.tensor(env.common_step_counter * env.step_dt, device=env.device)
    for episode_index, (time, offset) in enumerate(env._g1_recorded_episodes):
        env_mask = torch.arange(env.num_envs, device=env.device) % len(env._g1_recorded_episodes) == episode_index
        env_indices = torch.nonzero(env_mask, as_tuple=False).flatten()
        if env_indices.numel() == 0:
            continue
        episode_time = torch.remainder(elapsed, time[-1])
        sample = torch.searchsorted(time, episode_time).clamp(max=time.numel() - 1)
        target[env_indices[:, None], env._g1_right_columns[None, :]] += offset[sample] * scale
    env._g1_upper_target[:] = target
    env.scene["robot"].set_joint_position_target(target, joint_ids=ids)


def upper_target_relative(env) -> torch.Tensor:
    """Upper target relative to the robot default, ordered by the 17 upper joints."""
    _ids, default, _amplitude, _phase = _upper_state(env)
    return env._g1_upper_target - default


def make_upper_body_conditioned_g1_env_cfg(
    *, play: bool = False, trajectory_manifest: str | None = None,
    trajectory_split: str = "train", fixed_upper: bool = False,
    recorded_scale_start: float = 1.0, recorded_scale_end: float = 1.0,
    recorded_ramp_steps: int = 0,
) -> ManagerBasedRlEnvCfg:
    """Create the first independent 12-leg-action/17-upper-target training task."""
    cfg = unitree_g1_flat_env_cfg(play=play)

    cfg.actions["joint_pos"] = JointPositionActionCfg(
        entity_name="robot",
        actuator_names=LEG_JOINT_PATTERNS,
        scale=LEG_ACTION_SCALE,
        use_default_offset=True,
    )

    target_obs = ObservationTermCfg(func=upper_target_relative)
    cfg.observations["actor"].terms["upper_target"] = target_obs
    cfg.observations["critic"].terms["upper_target"] = target_obs

    if fixed_upper:
        cfg.events["upper_target"] = EventTermCfg(
            func=apply_fixed_upper_target, mode="step"
        )
    elif trajectory_manifest is None:
        cfg.events["upper_target"] = EventTermCfg(
            func=apply_smooth_upper_target, mode="step", params={"period_s": 6.0}
        )
    else:
        cfg.events["upper_target"] = EventTermCfg(
            func=apply_recorded_upper_target,
            mode="step",
            params={
                "manifest_path": trajectory_manifest,
                "split": trajectory_split,
                "scale_start": recorded_scale_start,
                "scale_end": recorded_scale_end,
                "ramp_steps": recorded_ramp_steps,
            },
        )
    return cfg
