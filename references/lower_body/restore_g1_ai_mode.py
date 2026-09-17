#!/usr/bin/env python3

import os
from pathlib import Path
import sys
OWNER_MARKERS = (
    "g1_twist2",
    "twist2_static_stand",
    "twist2_mink_cycle_trial",
)


def active_command_owners(proc_root=Path("/proc")):
    owners = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(marker in command for marker in OWNER_MARKERS):
            owners.append((int(entry.name), command.strip()))
    return sorted(owners)


def main():
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
        MotionSwitcherClient,
    )

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <network_interface>")
        raise SystemExit(2)

    owners = active_command_owners()
    if owners:
        for pid, command in owners:
            print(f"REFUSE: active LowCmd candidate pid={pid}: {command}")
        print("Stop and verify the existing command owner before selecting AI mode.")
        raise SystemExit(3)

    ChannelFactoryInitialize(0, sys.argv[1])

    client = MotionSwitcherClient()
    client.SetTimeout(5.0)
    client.Init()

    before_code, before = client.CheckMode()
    print("before:", before_code, before)

    ret = client.SelectMode("ai")
    print("SelectMode('ai'):", ret)

    after_code, after = client.CheckMode()
    print("after:", after_code, after)


if __name__ == "__main__":
    main()
