#!/bin/sh
# Feed over SSH stdin from Windows. Do not copy this file onto G1.
# Read existing metadata only. No control binary, Python/SDK import or build.
set -eu
printf '\n=== architecture ===\n'
uname -m
getconf GNU_LIBC_VERSION
cat /etc/os-release
printf '\n=== compiler ===\n'
command -v c++ || true
printf '\n=== existing trial binary ===\n'
trial=/home/unitree/g1_right_arm_trial/build/g1_twist2_cpp_right_arm_trial
if [ -f "$trial" ]; then
  file "$trial"
  sha256sum "$trial"
  readelf -d "$trial"
fi
printf '\n=== existing build dependency paths ===\n'
cache=/home/unitree/g1_right_arm_trial/build/CMakeCache.txt
if [ -f "$cache" ]; then
  grep -E '^(CMAKE_CXX_COMPILER|UNITREE_SDK2_ROOT|TORCH_PYTHON_ROOT|TORCH_CXX11_ABI|Torch_DIR|CMAKE_SYSTEM_PROCESSOR)[^=]*=' "$cache" || true
fi
printf '\n=== process names (not proof of DDS ownership) ===\n'
ps -eo pid,ppid,user,comm
printf '\n=== interface addresses ===\n'
ip -j -4 address show
