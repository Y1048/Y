#!/usr/bin/env python3
"""Supported Jog permit generator with provenance binding (R42)."""

from __future__ import annotations

from pathlib import Path
import sys

import validate_right_arm_jog_collision_path as permit
from right_arm_jog_safety_guard import build_jog_permit_provenance


def _argument_path(name: str, default: Path) -> Path:
    argv = sys.argv[1:]
    for index, value in enumerate(argv):
        if value == name:
            if index + 1 >= len(argv):
                raise ValueError(f"{name} requires a path")
            return Path(argv[index + 1])
        prefix = name + "="
        if value.startswith(prefix):
            return Path(value[len(prefix) :])
    return default


def main() -> int:
    config_path = _argument_path("--config", permit.DEFAULT_CONFIG_PATH)
    original_write_json = permit.write_json

    def write_with_provenance(path: Path, payload: dict) -> None:
        if payload.get("passed") is True:
            payload["provenance"] = build_jog_permit_provenance(config_path)
        original_write_json(path, payload)

    permit.write_json = write_with_provenance
    return permit.main()


if __name__ == "__main__":
    raise SystemExit(main())
