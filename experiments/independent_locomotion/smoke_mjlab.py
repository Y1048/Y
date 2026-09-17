"""GPU environment smoke check only; zero actions are not a walking policy."""
import argparse
import json
import time
from pathlib import Path

import torch
import mjlab.tasks  # Register upstream tasks.
from mjlab.envs import ManagerBasedRlEnv
from mjlab.tasks.registry import load_env_cfg


def check_finite(value):
    if isinstance(value, torch.Tensor) and not torch.isfinite(value).all():
        raise RuntimeError("Nonfinite simulation data")
    if isinstance(value, dict):
        for child in value.values():
            check_finite(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    cfg = load_env_cfg("Mjlab-Velocity-Flat-Unitree-G1")
    cfg.scene.num_envs = 4
    cfg.seed = 15
    started = time.perf_counter()
    env = ManagerBasedRlEnv(cfg=cfg, device="cuda:0")
    try:
        observations, _ = env.reset()
        check_finite(observations)
        actions = torch.zeros(env.action_space.shape, device="cuda:0")
        resets = 0
        for _ in range(50):
            obs, reward, terminated, truncated, _ = env.step(actions)
            check_finite(obs)
            check_finite(reward)
            resets += int((terminated | truncated).sum().item())
        torch.cuda.synchronize()
        result = {
            "schema": "g1.mjlab.smoke.v1", "status": "passed",
            "simulation_only": True, "trained_policy": False,
            "hardware_validation": False, "num_envs": 4, "steps": 50,
            "action_shape": list(actions.shape), "reset_count": resets,
            "torch": torch.__version__, "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "torch_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "elapsed_seconds": time.perf_counter() - started,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        env.close()


if __name__ == "__main__":
    main()
