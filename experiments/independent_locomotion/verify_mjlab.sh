#!/usr/bin/env bash
# Local WSL simulation only. No Unitree SDK/DDS or robot connection.
set -euo pipefail
project=/home/user/g1-learning/mjlab-20260915
workspace=/mnt/c/Users/user/Desktop/G1_Teleop_Project
uv=/home/user/.local/bin/uv
python="$project/.venv/bin/python"
train="$project/.venv/bin/train"
cd "$project"
test "$(git rev-parse HEAD)" = 8ee51fbcf806a7419189f706d9e394cbeb7790fa
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output="$workspace/logs/test_results/mjlab_setup_$stamp"
mkdir "$output"
exec > >(tee "$output/console.log") 2>&1
echo "Simulation setup check; output=$output"
# Verify/sync the pinned environment; uv serializes environment installation.
"$uv" sync --python 3.12 --extra cu128 --no-dev --locked
# list-envs prints a useful inventory but currently returns a non-zero status even
# after a successful listing. It is diagnostic and must not abort the smoke run.
"$project/.venv/bin/list-envs" || echo "[warning] list-envs returned non-zero after printing the registry"
"$python" "$workspace/experiments/independent_locomotion/smoke_mjlab.py" --output "$output/smoke.json"
# Two optimization iterations verify the training pipeline only, not locomotion.
WANDB_MODE=disabled "$train" Mjlab-Velocity-Flat-Unitree-G1 \
  --env.scene.num-envs 16 --agent.max-iterations 2 \
  --agent.logger tensorboard --log-root "$output/training"
echo "SETUP_CHECK_COMPLETE: synthetic smoke and two PPO iterations; no hardware validation"
