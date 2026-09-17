"""Build and validate a leak-free Mink command trajectory bank."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


SCHEMA = "g1.mjlab.mink_trajectory_bank.v1"
RIGHT_NAMES = (
    "right_shoulder_pitch_joint", "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint", "right_elbow_joint",
    "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_active_episode(path: Path, stride: int = 4) -> tuple[np.ndarray, np.ndarray]:
    times, joints = [], []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            packet = item.get("packet", item)
            if packet.get("event") != "active":
                continue
            q = packet.get("joints")
            t = packet.get("sample_time_s")
            if not isinstance(q, list) or len(q) != 7 or not isinstance(t, (int, float)):
                raise ValueError(f"Malformed active packet in {path}")
            times.append(float(t))
            joints.append([float(value) for value in q])
    if len(times) < 100:
        raise ValueError(f"Too few active samples in {path}: {len(times)}")
    time = np.asarray(times, dtype=np.float64)
    q = np.asarray(joints, dtype=np.float64)
    if not np.isfinite(time).all() or not np.isfinite(q).all():
        raise ValueError(f"Nonfinite sample in {path}")
    if np.any(np.diff(time) <= 0):
        raise ValueError(f"Non-monotonic active timestamps in {path}")
    # Preserve command motion as offsets from the session's first active pose.
    return time[::stride] - time[0], (q - q[0])[::stride]


def build_bank(assignments: dict[str, list[Path]], output: Path, manifest: Path) -> None:
    if set(assignments) != {"train", "validation"}:
        raise ValueError("Exactly train and validation splits are required")
    records = []
    seen_hashes: dict[str, str] = {}
    arrays: dict[str, np.ndarray] = {}
    for split, paths in assignments.items():
        if not paths:
            raise ValueError(f"Empty {split} split")
        for index, path in enumerate(paths):
            digest = sha256(path)
            if digest in seen_hashes:
                raise ValueError(f"Content overlap: {path} == {seen_hashes[digest]}")
            seen_hashes[digest] = str(path)
            time, offsets = read_active_episode(path)
            key = f"{split}_{index:03d}"
            arrays[f"{key}_time_s"] = time
            arrays[f"{key}_right_offset_rad"] = offsets
            records.append({
                "episode_id": key,
                "split": split,
                "source_path": str(path.resolve()),
                "source_sha256": digest,
                "source_kind": "recorded_pc_mink_command",
                "measured_g1_data": False,
                "sample_count": int(len(time)),
                "duration_s": float(time[-1]),
            })
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **arrays)
    body = {
        "schema": SCHEMA,
        "status": "prepared",
        "data_file": str(output.resolve()),
        "data_sha256": sha256(output),
        "right_joint_names": RIGHT_NAMES,
        "representation": "right joint command offset from first active sample, rad",
        "validation_frozen_before_training": True,
        "episodes": records,
    }
    manifest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def load_split(manifest: Path, split: str) -> list[dict]:
    body = json.loads(manifest.read_text(encoding="utf-8"))
    if body.get("schema") != SCHEMA or split not in {"train", "validation"}:
        raise ValueError("Invalid trajectory manifest or split")
    episodes = body.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Missing episodes")
    train_hashes = {e["source_sha256"] for e in episodes if e.get("split") == "train"}
    val_hashes = {e["source_sha256"] for e in episodes if e.get("split") == "validation"}
    if not train_hashes or not val_hashes or train_hashes & val_hashes:
        raise ValueError("Empty or overlapping train/validation split")
    selected = [e for e in episodes if e.get("split") == split]
    if not selected:
        raise ValueError(f"No episodes for {split}")
    return selected
