#!/usr/bin/env bash
set -euo pipefail

project_root="/mnt/c/Users/user/Desktop/G1_Teleop_Project"
python_path="/home/user/.venvs/g1-teleop/bin/python"
network_interface="$(ip -o -4 addr show | awk '$4 ~ /^192[.]168[.]123[.]99\// { print $2; exit }')"

if [[ -z "${network_interface}" ]]
then
    echo "G1 Ethernet interface with 192.168.123.99/24 was not found."
    exit 1
fi

if [[ ! -x "${python_path}" ]]
then
    echo "G1 WSL Python environment was not found: ${python_path}"
    exit 1
fi

cd "${project_root}"
exec "${python_path}" hardware/g1_arm_bridge/read_only_lowstate_entry.py \
    "${network_interface}" "$@"
