#!/usr/bin/env python3
"""기존 Startup Recovery를 격리된 입력과 출력으로 한 번 실행한다."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DIR = PROJECT_ROOT / "hardware" / "g1_arm_bridge"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--escape", type=float, nargs=3, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    sys.path.insert(0, str(BRIDGE_DIR))

    import simulate_startup_recovery as recovery

    # 기존 파일을 바꾸지 않고 이 프로세스 안의 입력, 출력, 탈출 목표만 교체한다.
    recovery.STATE_PATH = args.state.resolve()
    recovery.RESULT_PATH = args.result.resolve()
    recovery.ESCAPE_OFFSET_ROBOT_M = np.asarray(args.escape, dtype=float)
    return int(recovery.main())


if __name__ == "__main__":
    raise SystemExit(main())
