#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/c/Users/user/Desktop/G1_Teleop_Project
MJLAB=/home/user/g1-learning/mjlab-20260915
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$ROOT/logs/test_results/mjlab_upper_conditioned_$STAMP"

mkdir -p "$OUT"
cd "$MJLAB"

PYTHONPATH="$ROOT/experiments/independent_locomotion${PYTHONPATH:+:$PYTHONPATH}" \
  .venv/bin/python "$ROOT/experiments/independent_locomotion/smoke_upper_body_conditioned.py" \
  --output "$OUT/environment_smoke.json" \
  --trajectory-manifest "$ROOT/experiments/independent_locomotion/data/mink_command_trajectories_v1.json" \
  --trajectory-split validation | tee "$OUT/environment_console.log"

PYTHONPATH="$ROOT/experiments/independent_locomotion${PYTHONPATH:+:$PYTHONPATH}" \
  .venv/bin/python "$ROOT/experiments/independent_locomotion/train_upper_body_conditioned.py" \
  --log-root "$OUT/training" \
  --result "$OUT/training_smoke.json" \
  --num-envs 16 \
  --iterations 2 \
  --trajectory-manifest "$ROOT/experiments/independent_locomotion/data/mink_command_trajectories_v1.json" \
  --trajectory-split train | tee "$OUT/training_console.log"

printf '%s\n' UPPER_CONDITIONED_CHECK_COMPLETE | tee "$OUT/COMPLETE"
