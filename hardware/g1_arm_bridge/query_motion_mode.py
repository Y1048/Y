#!/usr/bin/env python3
"""Query the active G1 motion service without changing robot state.

Only MotionSwitcherClient.CheckMode is called. SelectMode, ReleaseMode, arm
commands, and low-level commands are deliberately absent from this process.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


SCHEMA = "g1.motion_mode.query.v1"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="READ-ONLY G1 MotionSwitcher CheckMode query"
    )
    parser.add_argument("network_interface")
    parser.add_argument("--domain-id", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/runtime/g1_motion_mode_query.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0.0:
        raise SystemExit("--timeout must be > 0")

    # Import inside main so Windows-side unit tests can import this module
    # without requiring the Linux-only Unitree SDK2 package.
    from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import (
        MotionSwitcherClient,
    )
    from unitree_sdk2py.core.channel import ChannelFactoryInitialize

    started_ns = time.time_ns()
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "query_started_at_unix_ns": started_ns,
        "queried_at_unix_ns": started_ns,
        "network_interface": args.network_interface,
        "operation": "MotionSwitcherClient.CheckMode",
        "state_mutation_requested": False,
        "motor_command_publisher_present": False,
        "command_output_enabled": False,
        "result_code": None,
        "form": None,
        "name": None,
    }

    try:
        ChannelFactoryInitialize(args.domain_id, args.network_interface)
        client = MotionSwitcherClient()
        client.SetTimeout(args.timeout)
        client.Init()
        result_code, result = client.CheckMode()
        payload["result_code"] = int(result_code)
        if result_code == 0 and isinstance(result, dict):
            form = result.get("form")
            name = result.get("name")
            if not isinstance(form, str) or not isinstance(name, str):
                raise RuntimeError("CheckMode returned invalid form/name fields")
            payload["form"] = form
            payload["name"] = name
            payload["queried_at_unix_ns"] = time.time_ns()
        else:
            payload["error"] = "CheckMode request failed"
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(args.output, payload)
        print(f"[ERROR] Motion mode query failed: {exc}")
        print("[ACTION] Keep robot commands disabled and verify G1 Ethernet/DDS.")
        print(f"Result saved to: {args.output.resolve()}")
        return 2

    _write_json(args.output, payload)
    if payload["result_code"] != 0:
        print(f"[ERROR] CheckMode returned code {payload['result_code']}")
        print("[ACTION] Keep robot commands disabled and verify the motion service.")
        print(f"Result saved to: {args.output.resolve()}")
        return 3

    print("G1 motion service query -- READ ONLY")
    print(f"form={payload['form']} name={payload['name']}")
    print("State mutation: NONE")
    print("Robot command: NONE")
    print(f"Result saved to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
