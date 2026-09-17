"""Select the newest fully completed matched-training checkpoint."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


MODEL_RE = re.compile(r"model_(\d+)\.pt$")
RUN_STAMP_RE = re.compile(r"(\d{8}T\d{6}Z)$")


def checkpoint_from_result(run: Path, mode: str) -> Path | None:
    result_path = run / f"{mode}_result.json"
    marker = run / f"{mode.upper()}_COMPLETE"
    if not (run.joinpath("COMPLETE").is_file() and marker.is_file() and result_path.is_file()):
        return None
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if result.get("status") != "passed" or result.get("upper_mode") != mode:
        return None
    candidates: list[tuple[int, Path]] = []
    for raw in result.get("checkpoints", []):
        path = Path(raw)
        match = MODEL_RE.search(path.name)
        if match and path.is_file() and path.is_relative_to(run):
            candidates.append((int(match.group(1)), path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def select_checkpoint(log_root: Path, stage1: Path, mode: str) -> Path:
    completed = sorted(
        list(log_root.glob("mjlab_matched_continuation_*"))
        + list(log_root.glob("mjlab_recorded_curriculum_*")),
        key=lambda path: (
            RUN_STAMP_RE.search(path.name).group(1)
            if RUN_STAMP_RE.search(path.name) else ""
        ),
        reverse=True,
    )
    for run in completed:
        checkpoint = checkpoint_from_result(run.resolve(), mode)
        if checkpoint is not None:
            return checkpoint.resolve()

    stage_candidates = []
    for path in stage1.joinpath(mode).rglob("model_499.pt"):
        if path.is_file():
            stage_candidates.append(path)
    if len(stage_candidates) != 1:
        raise FileNotFoundError(
            f"Expected exactly one stage-1 {mode} model_499.pt, found {len(stage_candidates)}"
        )
    return stage_candidates[0].resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--mode", choices=("fixed", "recorded"), required=True)
    args = parser.parse_args()
    print(select_checkpoint(args.log_root.resolve(), args.stage1.resolve(), args.mode))


if __name__ == "__main__":
    main()
