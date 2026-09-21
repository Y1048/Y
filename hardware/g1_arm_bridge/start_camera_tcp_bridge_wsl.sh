#!/usr/bin/env bash
set -euo pipefail
# Arguments come from G1_CAMERA_LAUNCH.py; no workstation-specific path.
project_root="${1:?project root required}"
mode="${2:---check-only}"
robot_host="${3:-192.168.123.164}"
base="${XDG_DATA_HOME:-$HOME/.local/share}/g1-teleop-camera"
python_path="${G1_CAMERA_PYTHON:-$base/venv-py311/bin/python}"
export CYCLONEDDS_HOME="$base/cyclonedds/install"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

if [[ "$mode" == --setup ]]; then
    for tool in git cc python3; do
        command -v "$tool" >/dev/null || { echo "Missing $tool. Install: sudo apt-get install python3-venv python3-dev build-essential cmake git"; exit 1; }
    done
    mkdir -p "$base"
    uv_path="$(command -v uv || true)"
    [[ -n "$uv_path" ]] || uv_path="$HOME/.local/bin/uv"
    [[ -x "$uv_path" ]] || uv_path="$base/bootstrap/uv"
    if [[ ! -x "$uv_path" ]]; then
        command -v curl >/dev/null || { echo 'Install curl and retry'; exit 1; }
        curl --max-time 60 --fail --location --silent --show-error https://astral.sh/uv/0.12.17/install.sh -o "$base/install-uv.sh"
        timeout 180 env UV_INSTALL_DIR="$base/bootstrap" UV_NO_MODIFY_PATH=1 sh "$base/install-uv.sh"
    fi
    if [[ ! -x "$python_path" ]]; then
        "$uv_path" venv --seed --python 3.11 "$base/venv-py311"
    fi
    "$uv_path" pip install --python "$python_path" cmake==3.31.6 numpy==2.2.6 opencv-python==4.12.0.88
    cmake_path="$(dirname "$python_path")/cmake"
    # Archives prepared from verified immutable revisions on Windows.
    for pair in "cyclonedds 9995905bce6c4cf9f740d6438bbf7fcfd1c83dfd" "sdk 9c519023d188bfe4643d326868474878ab515ed8"; do
        read -r name revision <<< "$pair"
        archive="$project_root/logs/setup/camera_sources/$name-$revision.tar"
        destination="$base/$name-$revision"
        [[ -f "$archive" ]] || { echo "Missing source archive: run SETUP_G1_VR_TELEOP.bat"; exit 1; }
        if [[ ! -d "$destination" ]]; then
            mkdir -p "$destination"
            tar -xf "$archive" -C "$destination"
        fi
        "$python_path" "$project_root/tools/g1_source_archive_check.py" "$archive" "$destination" || { echo "Modified/incomplete camera source; preserved: $destination"; exit 1; }
        if [[ "$name" == cyclonedds ]]; then cyclone_source="$destination"; else sdk_source="$destination"; fi
    done
    "$cmake_path" -S "$cyclone_source" -B "$base/cyclone-build" -DCMAKE_INSTALL_PREFIX="$CYCLONEDDS_HOME" -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF
    "$cmake_path" --build "$base/cyclone-build" --target install -j 2
    "$uv_path" pip install --python "$python_path" "$sdk_source"
    echo 'Camera SDK installed in user-local isolated environment. No DDS initialized.'
elif [[ "$mode" != --check-only && "$mode" != --run ]]; then
    echo 'Unknown camera mode'; exit 1
fi
[[ -x "$python_path" ]] || { echo 'Run tools/SETUP_G1_VR_TELEOP.bat to install camera dependencies.'; exit 1; }
# Imports only. Never instantiate VideoClient / ChannelFactory during setup/check.
"$python_path" -c 'from unitree_sdk2py.go2.video.video_client import VideoClient; print("PASS: camera SDK import only")'
if [[ "$mode" != --run ]]; then
    echo 'Camera dependencies ready; Ethernet, Unity listener and images not tested.'
    exit 0
fi
# Keep JPEG output loopback-only. NAT WSL cannot use Windows loopback this way.
if command -v wslinfo >/dev/null; then
    [[ "$(wslinfo --networking-mode)" == mirrored ]] || { echo 'Camera requires WSL mirrored networking. See docs/PORTABLE_TELEOP_SETUP.md. No SDK initialized.'; exit 1; }
fi
network_interface="${G1_CAMERA_INTERFACE:-}"
if [[ -z "$network_interface" ]]; then
    # Routing lookup only: does not send a probe to the robot.
    network_interface="$(ip -j route get "$robot_host" | "$python_path" -c 'import json,sys; r=json.load(sys.stdin)[0]; assert "gateway" not in r, "No direct G1 route: configure the robot Ethernet subnet"; print(r["dev"])')"
fi
[[ -n "$network_interface" && "$network_interface" != lo ]] || { echo 'No usable G1 Ethernet interface'; exit 1; }
echo "Camera interface=$network_interface; Unity=127.0.0.1:5011; project=$project_root"
cd "$project_root"
exec flock -n /tmp/g1_camera_to_unity_5011.lock "$python_path" hardware/g1_arm_bridge/g1_camera_tcp_bridge.py "$network_interface" --host 127.0.0.1 --port 5011
