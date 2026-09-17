#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/c/Users/user/Desktop/G1_Teleop_Project
MJLAB=/home/user/g1-learning/mjlab-20260915
LOG_ROOT="$ROOT/logs/test_results"
STAGE1="$LOG_ROOT/mjlab_matched_stage1_20260915"
TRAIN="$ROOT/experiments/independent_locomotion/train_upper_body_conditioned.py"
SELECTOR="$ROOT/experiments/independent_locomotion/select_matched_resume.py"
MANIFEST="$ROOT/experiments/independent_locomotion/data/mink_command_trajectories_v1.json"
ITERATIONS=${1:-1000}
RAMP_ITERATIONS=${2:-800}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$LOG_ROOT/mjlab_recorded_curriculum_$STAMP"

if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ && "$RAMP_ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Iterations and ramp iterations must be positive integers." >&2
  exit 2
fi
if (( RAMP_ITERATIONS > ITERATIONS )); then
  echo "Ramp iterations cannot exceed total iterations." >&2
  exit 2
fi

FIXED_CKPT=$(. "$MJLAB/.venv/bin/activate" && python "$SELECTOR" \
  --log-root "$LOG_ROOT" --stage1 "$STAGE1" --mode fixed)
RECORDED_CKPT=$(. "$MJLAB/.venv/bin/activate" && python "$SELECTOR" \
  --log-root "$LOG_ROOT" --stage1 "$STAGE1" --mode recorded)
echo "[RESUME] fixed: $FIXED_CKPT"
echo "[RESUME] recorded curriculum: $RECORDED_CKPT"

mkdir -p "$OUT"
cat >"$OUT/curriculum_plan.json" <<EOF
{"schema":"g1.mjlab.recorded_curriculum.v1","simulation_only":true,"iterations_per_model":$ITERATIONS,"recorded_scale_start":0.25,"recorded_scale_end":1.0,"recorded_ramp_iterations":$RAMP_ITERATIONS,"full_scale_iterations":$((ITERATIONS-RAMP_ITERATIONS)),"validation_execution":false}
EOF
printf '%s\n' "$OUT" >"$LOG_ROOT/mjlab_matched_continuation_latest.txt"
cd "$MJLAB"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/fixed" --result "$OUT/fixed_result.json" --num-envs 256 \
  --iterations "$ITERATIONS" --seed 1509 --upper-mode fixed \
  --resume-checkpoint "$FIXED_CKPT" >"$OUT/fixed_console.log" 2>&1
printf '%s\n' FIXED_COMPLETE >"$OUT/FIXED_COMPLETE"

PYTHONPATH="$ROOT/experiments/independent_locomotion" .venv/bin/python "$TRAIN" \
  --log-root "$OUT/recorded" --result "$OUT/recorded_result.json" --num-envs 256 \
  --iterations "$ITERATIONS" --seed 1509 --upper-mode recorded \
  --trajectory-manifest "$MANIFEST" --trajectory-split train \
  --recorded-scale-start 0.25 --recorded-scale-end 1.0 \
  --recorded-ramp-iterations "$RAMP_ITERATIONS" \
  --resume-checkpoint "$RECORDED_CKPT" >"$OUT/recorded_console.log" 2>&1
printf '%s\n' RECORDED_COMPLETE >"$OUT/RECORDED_COMPLETE"
printf '%s\n' RECORDED_CURRICULUM_COMPLETE >"$OUT/COMPLETE"
