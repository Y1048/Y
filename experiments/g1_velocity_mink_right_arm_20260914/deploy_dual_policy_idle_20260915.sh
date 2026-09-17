#!/usr/bin/env bash
set -euo pipefail
project=/home/unitree/g1_velocity_mink_keypad_right_arm_20260914
package=/tmp/dual_policy_idle_20260915.tar.gz
printf '%s  %s\n' 4cc41e629b7f3431102f9262ec5e82ee98015fa2bc91f04a1b2490694fe5dfde "$package" | sha256sum -c -
if pgrep -f '[g]1_velocity_mink_keypad_right_arm' >/dev/null; then echo 'Controller is running; refusing deployment.' >&2; exit 1; fi
backup="$project/source_backups/pre_dual_policy_idle_20260915"
mkdir -p "$backup"
cp -a "$project/CMakeLists.txt" "$project/README.md" "$project/build/g1_velocity_mink_keypad_right_arm" "$project/SHA256SUMS" "$backup/"
tar -xzf "$package" -C "$project"
cmake -S "$project" -B "$project/build"
cmake --build "$project/build" -j2
"$project/build/test_leg_policy_switch"
"$project/build/test_velocity_keypad_contract"
"$project/build/test_initial_ready_continuous_gait"
sha256sum "$project/build/g1_velocity_mink_keypad_right_arm" "$project/g1_velocity_mink_keypad_right_arm.cpp" "$project/g1_velocity_policy.hpp" "$project/velocity_keypad_contract.hpp" "$project/mink_live_cycle_contract.hpp" "$project/mink_live_cycle_target.hpp" "$project/leg_policy_switch.hpp" "$project/CMakeLists.txt" "$project/g1_velocity_12dof_motion.pt" /home/unitree/twist2_deploy/twist2_1017_20k_torchscript.pt "$project/run_velocity_mink_keypad.sh" "$project/run_static_stand_handoff_probe.sh" > "$project/SHA256SUMS"
cd "$project"; sha256sum -c SHA256SUMS
sha256sum build/g1_velocity_mink_keypad_right_arm
echo DEPLOY_DUAL_POLICY_IDLE_COMPLETE
