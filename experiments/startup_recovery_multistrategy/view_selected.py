#!/usr/bin/env python3
"""다중 전략 실험에서 선택된 경로를 기존 MuJoCo Viewer로 재생한다."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = (
    PROJECT_ROOT
    / "logs"
    / "experiments"
    / "startup_recovery_multistrategy"
    / "summary.json"
)
REPLAY_SCRIPT = (
    PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "replay_startup_recovery.py"
)


def main() -> int:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    selected = summary.get("selected")
    if not isinstance(selected, dict):
        raise RuntimeError("No passed strategy is selected; run the experiment first")

    result_path = Path(selected["result_path"])
    command = [sys.executable, str(REPLAY_SCRIPT), "--result", str(result_path)]
    return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
