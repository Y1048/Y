#!/usr/bin/env bash
set -euo pipefail

project_root="/mnt/c/Users/user/Desktop/G1_Teleop_Project"
python_path="/home/user/.venvs/g1-teleop/bin/python"
network_interface="$(ip -o -4 addr show | awk '$4 ~ /^192[.]168[.]123[.]99\// { print $2; exit }')"

if [[ -z "${network_interface}" ]]
then
    echo "[ERROR] G1 Ethernet interface with 192.168.123.99/24 was not found."
    echo "[ACTION] Run tools/DETECT_G1_NETWORK.bat, then tools/CONFIGURE_G1_ETHERNET.bat if needed."
    exit 1
fi

if [[ ! -x "${python_path}" ]]
then
    echo "[ERROR] G1 WSL Python environment was not found: ${python_path}"
    echo "[ACTION] Restore /home/user/.venvs/g1-teleop before starting the camera bridge."
    exit 1
fi

cd "${project_root}"
exec "${python_path}" hardware/g1_arm_bridge/g1_camera_tcp_bridge.py \
    "${network_interface}" \
    --host 127.0.0.1 \
    --port 5011 \
    --fps 20
