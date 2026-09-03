#!/usr/bin/env bash
set -euo pipefail

project_root="/mnt/c/Users/user/Desktop/G1_Teleop_Project"
python_path="/home/user/.venvs/g1-teleop/bin/python"
network_interface="$(ip -o -4 addr show | awk '$4 ~ /^192[.]168[.]123[.]99\// { print $2; exit }')"

if [[ -z "${network_interface}" ]]
then
    echo "[ERROR] G1 Ethernet interface with 192.168.123.99/24 was not found."
    echo "[ACTION] Verify Ethernet and run tools/DETECT_G1_NETWORK.bat."
    exit 1
fi

if [[ ! -x "${python_path}" ]]
then
    echo "[ERROR] G1 WSL Python environment was not found: ${python_path}"
    echo "[ACTION] Restore /home/user/.venvs/g1-teleop before retrying."
    exit 1
fi

cd "${project_root}"
exec "${python_path}" hardware/g1_arm_bridge/g1_right_arm_jog_entry.py \
    "${network_interface}" "$@"
