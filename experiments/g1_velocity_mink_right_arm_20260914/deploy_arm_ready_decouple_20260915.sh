#!/usr/bin/env bash
set -euo pipefail
project=/home/unitree/g1_velocity_mink_keypad_right_arm_20260914
package=/tmp/keypad_arm_ready_decouple_20260915.tar.gz
printf '%s  %s\n' 81cfafa873baf29c994aa3c6fd016d9661aa694e577a28c459b385417f24f79d "$package" | sha256sum -c -
if pgrep -f '[g]1_velocity_mink_keypad_right_arm' >/dev/null; then
  echo 'Controller is running; refusing deployment.' >&2
  exit 1
fi
backup="$project/source_backups/pre_arm_ready_decouple_20260915"
mkdir -p "$backup"
cp -a "$project/g1_velocity_mink_keypad_right_arm.cpp" "$backup/"
cp -a "$project/README.md" "$backup/"
cp -a "$project/build/g1_velocity_mink_keypad_right_arm" "$backup/"
cp -a "$project/SHA256SUMS" "$backup/"
tar -xzf "$package" -C "$project"
cmake --build "$project/build" -j2
"$project/build/test_leg_policy_switch"
"$project/build/test_velocity_keypad_contract"
sha256sum "$project/build/g1_velocity_mink_keypad_right_arm" \
  "$project/g1_velocity_mink_keypad_right_arm.cpp" \
  "$project/g1_velocity_policy.hpp" "$project/leg_policy_switch.hpp" \
  "$project/CMakeLists.txt" "$project/g1_velocity_12dof_motion.pt" \
  /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt \
  "$project/run_velocity_mink_keypad.sh" \
  "$project/run_static_stand_handoff_probe.sh" > "$project/SHA256SUMS"
cd "$project"
sha256sum -c SHA256SUMS
sha256sum build/g1_velocity_mink_keypad_right_arm
echo DEPLOY_ARM_READY_DECOUPLE_COMPLETE
