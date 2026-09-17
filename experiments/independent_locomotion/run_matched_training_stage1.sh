#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/c/Users/user/Desktop/G1_Teleop_Project
MJLAB=/home/user/g1-learning/mjlab-20260915
OUT="$ROOT/logs/test_results/mjlab_matched_stage1_20260915"
TRAIN="$ROOT/experiments/independent_locomotion/train_upper_body_conditioned.py"
MANIFEST="$ROOT/experiments/independent_locomotion/data/mink_command_trajectories_v1.json"

mkdir -p "$OUT"
cp "$ROOT/experiments/independent_locomotion/matched_training_stage1.json" "$OUT/training_plan.json"
cd "$MJLAB"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/fixed" --result "$OUT/fixed_result.json" \
  --num-envs 256 --iterations 500 --seed 1509 --upper-mode fixed \
  >"$OUT/fixed_console.log" 2>&1
printf '%s\n' FIXED_COMPLETE >"$OUT/FIXED_COMPLETE"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/recorded" --result "$OUT/recorded_result.json" \
  --num-envs 256 --iterations 500 --seed 1509 --upper-mode recorded \
  --trajectory-manifest "$MANIFEST" --trajectory-split train \
  >"$OUT/recorded_console.log" 2>&1
printf '%s\n' RECORDED_COMPLETE >"$OUT/RECORDED_COMPLETE"
printf '%s\n' MATCHED_STAGE1_COMPLETE >"$OUT/COMPLETE"
