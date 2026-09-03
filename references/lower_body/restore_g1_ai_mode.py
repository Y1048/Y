#!/usr/bin/env python3

import sys
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
    MotionSwitcherClient,
)

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <network_interface>")
    raise SystemExit(2)

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
