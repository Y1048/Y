#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/c/Users/user/Desktop/G1_Teleop_Project
MJLAB=/home/user/g1-learning/mjlab-20260915
SOURCE="$ROOT/logs/test_results/mjlab_matched_stage1_20260915"
LOG_ROOT="$ROOT/logs/test_results"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$ROOT/logs/test_results/mjlab_matched_continuation_$STAMP"
TRAIN="$ROOT/experiments/independent_locomotion/train_upper_body_conditioned.py"
SELECTOR="$ROOT/experiments/independent_locomotion/select_matched_resume.py"
MANIFEST="$ROOT/experiments/independent_locomotion/data/mink_command_trajectories_v1.json"
ITERATIONS=${1:-500}

if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Iterations must be a positive integer." >&2
  exit 2
fi

FIXED_CKPT=$(/home/user/g1-learning/mjlab-20260915/.venv/bin/python "$SELECTOR" \
  --log-root "$LOG_ROOT" --stage1 "$SOURCE" --mode fixed)
RECORDED_CKPT=$(/home/user/g1-learning/mjlab-20260915/.venv/bin/python "$SELECTOR" \
  --log-root "$LOG_ROOT" --stage1 "$SOURCE" --mode recorded)
echo "[RESUME] fixed: $FIXED_CKPT"
echo "[RESUME] recorded: $RECORDED_CKPT"

mkdir -p "$OUT"
cat >"$OUT/continuation_plan.json" <<EOF
{"schema":"g1.mjlab.matched_continuation.v1","simulation_only":true,"additional_iterations_per_model":$ITERATIONS,"seed":1509,"num_envs":256,"validation_execution":false,"fixed_resume_checkpoint":"$FIXED_CKPT","recorded_resume_checkpoint":"$RECORDED_CKPT"}
EOF
printf '%s\n' "$OUT" >"$ROOT/logs/test_results/mjlab_matched_continuation_latest.txt"
cd "$MJLAB"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/fixed" --result "$OUT/fixed_result.json" \
  --num-envs 256 --iterations "$ITERATIONS" --seed 1509 --upper-mode fixed \
  --resume-checkpoint "$FIXED_CKPT" >"$OUT/fixed_console.log" 2>&1
printf '%s\n' FIXED_COMPLETE >"$OUT/FIXED_COMPLETE"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/recorded" --result "$OUT/recorded_result.json" \
  --num-envs 256 --iterations "$ITERATIONS" --seed 1509 --upper-mode recorded \
  --trajectory-manifest "$MANIFEST" --trajectory-split train \
  --resume-checkpoint "$RECORDED_CKPT" >"$OUT/recorded_console.log" 2>&1
printf '%s\n' RECORDED_COMPLETE >"$OUT/RECORDED_COMPLETE"
printf '%s\n' MATCHED_CONTINUATION_COMPLETE >"$OUT/COMPLETE"
