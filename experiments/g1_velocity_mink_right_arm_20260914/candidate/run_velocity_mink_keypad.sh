#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9]{16,128}$ ]]; then
  echo "Usage: $0 RELAY_TOKEN" >&2
  exit 2
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
sha256sum -c SHA256SUMS
export G1_MINK_SPEED_PROFILE=today
export G1_VR_BIND_IPV4=192.168.123.164
export G1_VR_SOURCE_IPV4=192.168.123.99
export G1_VR_UDP_PORT=5014
export G1_VR_RELAY_TOKEN="$1"
export G1_VELOCITY_BIND_IPV4=192.168.123.164
export G1_VELOCITY_SOURCE_IPV4=192.168.123.99
export G1_VELOCITY_UDP_PORT=5017
export G1_VELOCITY_RELAY_TOKEN="$1"
exec "$script_dir/build/g1_velocity_mink_keypad_right_arm" \
  eth0 "$script_dir/g1_velocity_12dof_motion.pt" \
  --enable-actuation --policy-seconds 300 --udp-right-arm
