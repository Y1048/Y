#!/usr/bin/env bash
# PC/WSL host only. No SSH, remote install or robot file mutation.
set -euo pipefail
mode=${1:---check}
case "$mode" in --check|--readiness|--vr) ;; *) echo "Usage: $0 --check|--readiness|--vr" >&2; exit 2;; esac
if [[ $# -gt 1 ]]; then echo "Unexpected arguments" >&2; exit 2; fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
binary=/home/user/twist2-vr-build-20260907/build/g1_twist2_vr_split_candidate
policy="$root/references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt"
[[ $(uname -m) == x86_64 ]] || { echo "This launcher is for the x86_64 PC only" >&2; exit 2; }
[[ -x "$binary" && -f "$policy" ]]
printf '%s  %s\n' 463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015 "$policy" | sha256sum -c -
route=$(ip -4 route get 192.168.123.164)
interface=$(awk '{for(i=1;i<=NF;i++)if($i=="dev"){print $(i+1);exit}}' <<< "$route")
source_ip=$(awk '{for(i=1;i<=NF;i++)if($i=="src"){print $(i+1);exit}}' <<< "$route")
[[ -n "$interface" && "$source_ip" == 192.168.123.* ]] || { echo "No direct G1 wired route" >&2; exit 2; }
echo "PC interface=$interface source=$source_ip"
file "$binary"
sha256sum "$binary"
if [[ "$mode" == --check ]]; then
 echo "CHECK ONLY: binary not executed; no DDS publisher. Network timing is not validated."
 exit 0
fi
if pgrep -x g1_twist2_vr_sp >/dev/null || pgrep -f '^/home/user/twist2-vr-build-20260907/build/g1_twist2_vr_' >/dev/null; then
 echo "Existing PC controller process; inspect it before continuing" >&2; exit 2
fi
if ss -H -lun | awk '{print $5}' | grep -Eq ':5013$'; then
 echo "UDP 5013 occupied; inspect its owner" >&2; exit 2
fi
export G1_VR_BIND_IPV4=127.0.0.1 G1_VR_SOURCE_IPV4=127.0.0.1 G1_VR_UDP_PORT=5013
if [[ "$mode" == --readiness ]]; then
 seconds=3
 export G1_VR_RELAY_TOKEN=PcReadinessNoVrSender20260908
else
 : "${G1_VR_RELAY_TOKEN:?Set the same fresh relay token in the Windows relay and this shell}"
 seconds=${G1_PC_POLICY_SECONDS:-10}
 [[ "$seconds" =~ ^([2-9]|1[0-9]|20)$ ]] || { echo "G1_PC_POLICY_SECONDS must be 2..20" >&2; exit 2; }
 export G1_VR_RELAY_TOKEN
fi
mkdir -p "$root/logs/test_results/pc_twist2_runs"
cd "$root/logs/test_results/pc_twist2_runs"
echo "Physical control: releases AI; hold R1; Select/B stops; ends in damping, no AI restore."
echo "The native program requires P before DDS initialization. Keep support in place."
exec "$binary" "$interface" "$policy" --enable-actuation --policy-seconds "$seconds" --vr-relative-candidate
