#!/usr/bin/env bash
set -euo pipefail

project_root="/mnt/c/Users/user/Desktop/G1_Teleop_Project"
python_path="/home/user/.venvs/g1-teleop/bin/python"
network_interface="$(ip -o -4 addr show | awk '$4 ~ /^192[.]168[.]123[.]99\// { print $2; exit }')"

if [[ -n "${G1_GATE7_ADAPTER_LOG:-}" ]]
then
    exec > >(tee "${G1_GATE7_ADAPTER_LOG}") 2>&1
fi

if [[ -z "${network_interface}" ]]
then
    echo "G1 Ethernet interface with 192.168.123.99/24 was not found."
    echo "ACTION: Verify the Ethernet cable and run tools/DETECT_G1_NETWORK.bat."
    exit 1
fi

if [[ ! -x "${python_path}" ]]
then
    echo "G1 WSL Python environment was not found: ${python_path}"
    echo "ACTION: Restore the g1-teleop virtual environment before retrying."
    exit 1
fi

cd "${project_root}"
exec "${python_path}" -u hardware/g1_arm_bridge/gate7_live_arm_sdk_entry.py \
    "${network_interface}" "$@"
