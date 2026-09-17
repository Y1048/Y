#!/usr/bin/env bash
set -euo pipefail
project=/home/unitree/g1_velocity_mink_keypad_right_arm_20260914
package=/tmp/continuous_gait_arm_ready_20260915.tar.gz
printf '%s  %s\n' a4346886b79283848403137d93000356080dd1e790694576ba76ab68c7c97dbe "$package" | sha256sum -c -
if pgrep -f '[g]1_velocity_mink_keypad_right_arm' >/dev/null; then
  echo 'Controller is running; refusing deployment.' >&2
  exit 1
fi
backup="$project/source_backups/pre_continuous_gait_arm_ready_20260915"
mkdir -p "$backup"
for f in mink_live_cycle_contract.hpp mink_live_cycle_target.hpp CMakeLists.txt README.md SHA256SUMS; do cp -a "$project/$f" "$backup/"; done
cp -a "$project/build/g1_velocity_mink_keypad_right_arm" "$backup/"
tar -xzf "$package" -C "$project"
cmake -S "$project" -B "$project/build"
cmake --build "$project/build" -j2
"$project/build/test_leg_policy_switch"
"$project/build/test_velocity_keypad_contract"
"$project/build/test_initial_ready_continuous_gait"
sha256sum "$project/build/g1_velocity_mink_keypad_right_arm" \
  "$project/g1_velocity_mink_keypad_right_arm.cpp" \
  "$project/g1_velocity_policy.hpp" "$project/velocity_keypad_contract.hpp" \
  "$project/mink_live_cycle_contract.hpp" "$project/mink_live_cycle_target.hpp" \
  "$project/leg_policy_switch.hpp" "$project/CMakeLists.txt" \
  "$project/g1_velocity_12dof_motion.pt" \
  /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt \
  "$project/run_velocity_mink_keypad.sh" \
  "$project/run_static_stand_handoff_probe.sh" > "$project/SHA256SUMS"
cd "$project"
sha256sum -c SHA256SUMS
sha256sum build/g1_velocity_mink_keypad_right_arm
echo DEPLOY_CONTINUOUS_GAIT_ARM_READY_COMPLETE
