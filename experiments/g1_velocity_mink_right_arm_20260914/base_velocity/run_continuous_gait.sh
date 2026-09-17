#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$script_dir/g1_velocity_keyboard_continuous_gait" \
  eth0 \
  "$script_dir/g1_velocity_12dof_motion.pt" \
  --enable-actuation \
  --policy-seconds 300 \
  --keyboard-left-arm

