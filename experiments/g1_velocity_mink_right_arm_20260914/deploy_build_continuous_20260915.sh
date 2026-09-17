#!/usr/bin/env bash
set -euo pipefail

project=/home/unitree/g1_velocity_mink_keypad_right_arm_20260914
package=/tmp/continuous_gait_keypad_update_20260915.tar.gz
expected=c06cb19378d8b0304a4f4879f5f69370aadea965f0a255e1ed912b459451151f

printf '%s  %s\n' "$expected" "$package" | sha256sum -c -
test -d "$project"
if pgrep -f '[g]1_velocity_mink_keypad_right_arm' >/dev/null; then
  echo 'Controller is running; refusing deployment.' >&2
  exit 1
fi

backup="$project/source_backups/pre_continuous_keypad_20260915"
mkdir -p "$backup"
for file in CMakeLists.txt g1_velocity_mink_keypad_right_arm.cpp \
  g1_velocity_policy.hpp README.md leg_policy_switch.hpp \
  native_velocity_udp.hpp velocity_keypad_contract.hpp; do
  test -f "$project/$file"
  cp -a "$project/$file" "$backup/$file"
done
if test -f "$project/build/g1_velocity_mink_keypad_right_arm"; then
  cp -a "$project/build/g1_velocity_mink_keypad_right_arm" \
    "$backup/g1_velocity_mink_keypad_right_arm.pre_continuous"
fi

tar -xzf "$package" -C "$project"
cmake -S "$project" -B "$project/build"
cmake --build "$project/build" -j2
ctest --test-dir "$project/build" --output-on-failure
file "$project/build/g1_velocity_mink_keypad_right_arm"
sha256sum "$project/build/g1_velocity_mink_keypad_right_arm"
grep -- '-DG1_VELOCITY_CONTINUOUS_GAIT=1' \
  "$project/build/CMakeFiles/g1_velocity_mink_keypad_right_arm.dir/flags.make"
if pgrep -f '[g]1_velocity_mink_keypad_right_arm' >/dev/null; then
  echo 'Unexpected controller process after build.' >&2
  exit 1
fi
echo 'DEPLOY_BUILD_TEST_COMPLETE'
