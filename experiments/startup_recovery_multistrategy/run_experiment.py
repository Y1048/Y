#!/usr/bin/env python3
"""여러 Startup Recovery 탈출 후보를 비교하는 오프라인 실험기."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = (
    PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "logs" / "experiments" / "startup_recovery_multistrategy"
)
CANDIDATE_RUNNER = Path(__file__).with_name("candidate_runner.py")
CLEARANCE_EQUIVALENCE_M = 0.0005


@dataclass(frozen=True)
class RecoveryCandidate:
    name: str
    escape_offset_robot_m: tuple[float, float, float]


CANDIDATES = (
    RecoveryCandidate("baseline", (0.0, -0.18, 0.08)),
    RecoveryCandidate("outward_up", (0.0, -0.16, 0.14)),
    RecoveryCandidate("outward_forward_up", (0.08, -0.16, 0.10)),
    RecoveryCandidate("outward_backward_up", (-0.08, -0.16, 0.10)),
    RecoveryCandidate("outward_wide", (0.0, -0.22, 0.05)),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare isolated Startup Recovery escape strategies"
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_initial_pose(state_path: Path) -> list[float]:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    values = payload.get("right_arm_q_rad")
    if not isinstance(values, list) or len(values) != 7:
        raise RuntimeError("right_arm_q_rad must contain seven values")
    pose = [float(value) for value in values]
    if not all(math.isfinite(value) for value in pose):
        raise RuntimeError("right_arm_q_rad contains a non-finite value")
    return pose


def candidate_score(result: dict[str, Any]) -> tuple[float, float, float]:
    if result.get("passed") is not True:
        return (-math.inf, -math.inf, -math.inf)

    clearance = result.get("minimum_clearance_after_escape_m")
    clearance_value = -math.inf if clearance is None else float(clearance)
    elapsed = float(result.get("elapsed_s", math.inf))
    metrics = result.get("motion_profile", {}).get("metrics", {})
    maximum_jerk = float(metrics.get("max_jerk_deg_s3", math.inf))
    return (clearance_value, -elapsed, -maximum_jerk)


def select_candidate(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    passed = [item for item in results if item.get("passed") is True]
    if not passed:
        return None

    maximum_clearance = max(
        float(item["result"]["minimum_clearance_after_escape_m"])
        for item in passed
    )
    comparable = [
        item
        for item in passed
        if float(item["result"]["minimum_clearance_after_escape_m"])
        >= maximum_clearance - CLEARANCE_EQUIVALENCE_M
    ]

    # 0.5 mm 이내의 차이는 수치 잡음과 모델 오차보다 작으므로 같은 안전 등급으로
    # 취급하고, 그 안에서는 더 짧고 jerk가 작은 경로를 선택한다.
    return min(
        comparable,
        key=lambda item: (
            float(item["result"].get("elapsed_s", math.inf)),
            float(
                item["result"]
                .get("motion_profile", {})
                .get("metrics", {})
                .get("max_jerk_deg_s3", math.inf)
            ),
            item["name"],
        ),
    )


def run_candidate(
    candidate: RecoveryCandidate,
    state_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    result_path = output_dir / f"{candidate.name}.json"
    log_path = output_dir / f"{candidate.name}.log"
    command = [
        sys.executable,
        str(CANDIDATE_RUNNER),
        "--state",
        str(state_path),
        "--result",
        str(result_path),
        "--escape",
        *(str(value) for value in candidate.escape_offset_robot_m),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_path.write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )

    result: dict[str, Any] = {}
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))

    return {
        "name": candidate.name,
        "escape_offset_robot_m": list(candidate.escape_offset_robot_m),
        "process_exit_code": completed.returncode,
        "passed": result.get("passed") is True and completed.returncode == 0,
        "result_path": str(result_path.resolve()),
        "log_path": str(log_path.resolve()),
        "result": result,
    }


def print_result(item: dict[str, Any]) -> None:
    result = item["result"]
    status = "PASS" if item["passed"] else "FAIL"
    clearance = result.get("minimum_clearance_after_escape_m")
    clearance_mm = "n/a" if clearance is None else f"{float(clearance) * 1000.0:.2f}"
    elapsed = result.get("elapsed_s")
    elapsed_text = "n/a" if elapsed is None else f"{float(elapsed):.3f}"
    failure = result.get("failure") or result.get("safety_gate", {}).get("failure")
    print(
        f"[{status}] {item['name']:<24} "
        f"clearance={clearance_mm:>6} mm elapsed={elapsed_text:>7} s "
        f"failure={failure or 'none'}"
    )


def main() -> int:
    args = parse_arguments()
    state_path = args.state.resolve()
    output_dir = args.output_dir.resolve()
    load_initial_pose(state_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("G1 Startup Recovery multi-strategy experiment")
    print(f"Initial state: {state_path}")
    print("Hardware connection: NONE")
    print("DDS publisher: NONE")
    print("Robot command: NONE")
    print()

    results: list[dict[str, Any]] = []
    for index, candidate in enumerate(CANDIDATES, start=1):
        print(f"[{index}/{len(CANDIDATES)}] Running {candidate.name}...", flush=True)
        item = run_candidate(candidate, state_path, output_dir)
        results.append(item)
        print_result(item)

    selected = select_candidate(results)
    summary_path = output_dir / "summary.json"
    summary = {
        "schema": "g1.startup_recovery_multistrategy.v1",
        "experimental": True,
        "production_files_modified": False,
        "hardware_ready": False,
        "command_output_enabled": False,
        "source_state_path": str(state_path),
        "candidate_count": len(results),
        "passed_count": sum(int(item["passed"]) for item in results),
        "clearance_equivalence_m": CLEARANCE_EQUIVALENCE_M,
        "selected": (
            None
            if selected is None
            else {
                "name": selected["name"],
                "escape_offset_robot_m": selected["escape_offset_robot_m"],
                "result_path": selected["result_path"],
                "log_path": selected["log_path"],
                "score": list(candidate_score(selected["result"])),
            }
        ),
        "candidates": [
            {
                key: value
                for key, value in item.items()
                if key != "result"
            }
            | {
                "elapsed_s": item["result"].get("elapsed_s"),
                "minimum_clearance_after_escape_m": item["result"].get(
                    "minimum_clearance_after_escape_m"
                ),
                "failure": item["result"].get("failure"),
            }
            for item in results
        ],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    if selected is None:
        print("[FAIL] No recovery strategy passed all existing safety checks.")
        print(f"[ACTION] Inspect candidate logs under {output_dir}")
        print(f"Summary saved to: {summary_path}")
        return 2

    print(f"[PASS] Selected strategy: {selected['name']}")
    print(f"Selected result: {selected['result_path']}")
    print(f"Summary saved to: {summary_path}")
    print("This is an offline experiment and is not approved for hardware output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
