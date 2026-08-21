"""Replay a recorded live Quest trace against the configured voxel workspace."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop import VoxelWorkspaceMap, WorkspaceTargetProjector

CONFIG_PATH = PROJECT_ROOT / "config" / "teleop.json"
DEFAULT_TRACE = PROJECT_ROOT / "Unity_G1_Quest3S" / "Logs" / "live_quest_trace.csv"
DEFAULT_REPORT = PROJECT_ROOT / "logs" / "workspace" / "live_workspace_replay.csv"
_NEIGHBORS = [
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) != (0, 0, 0)
]


def load_workspace() -> tuple[VoxelWorkspaceMap, Path]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg = payload["workspace"]
    workspace_path = PROJECT_ROOT / cfg["workspace_file"]
    workspace = VoxelWorkspaceMap.from_npz(
        workspace_path,
        voxel_size_m=float(cfg["voxel_size_m"]),
        allowed_classes=tuple(int(v) for v in cfg["allowed_classes"]),
        dilation_voxels=int(cfg.get("dilation_voxels", 0)),
    )
    return workspace, workspace_path


def load_trace(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"sender_robot_x", "sender_robot_y", "sender_robot_z", "command_valid"}
    missing = required.difference(rows[0].keys() if rows else ())
    if missing:
        raise ValueError(f"trace missing columns: {sorted(missing)}")
    return [row for row in rows if row.get("command_valid") == "1"]


def connected_components(workspace: VoxelWorkspaceMap) -> dict[tuple[int, int, int], int]:
    safe = set(workspace._safe_keys)
    component: dict[tuple[int, int, int], int] = {}
    component_id = 0
    for start in safe:
        if start in component:
            continue
        queue = deque([start])
        component[start] = component_id
        while queue:
            key = queue.popleft()
            for offset in _NEIGHBORS:
                neighbor = (
                    key[0] + offset[0],
                    key[1] + offset[1],
                    key[2] + offset[2],
                )
                if neighbor in safe and neighbor not in component:
                    component[neighbor] = component_id
                    queue.append(neighbor)
        component_id += 1
    return component


def point_from_row(row: dict[str, str]) -> np.ndarray:
    return np.array([
        float(row["sender_robot_x"]),
        float(row["sender_robot_y"]),
        float(row["sender_robot_z"]),
    ])


def main() -> int:
    trace_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_TRACE
    if not trace_path.exists():
        print(f"FAIL: trace not found: {trace_path}")
        return 2

    workspace, workspace_path = load_workspace()
    rows = load_trace(trace_path)
    if not rows:
        print("FAIL: trace contains no command_valid=1 samples")
        return 2

    component_map = connected_components(workspace)
    component_sizes = Counter(component_map.values())
    first_point = point_from_row(rows[0])
    first_safe = workspace.nearest_safe_point(first_point)
    anchor_component = component_map[workspace.point_to_index(first_safe)]
    projector = WorkspaceTargetProjector(workspace)

    classified = []
    counts = Counter()
    replay_projected = 0
    recorded_workspace_limited = 0
    replay_distances = []

    for row in rows:
        point = point_from_row(row)
        nearest = workspace.nearest_safe_point(point)
        nearest_distance = float(np.linalg.norm(nearest - point))
        key = workspace.point_to_index(point)
        if workspace.contains_safe(point):
            point_component = component_map.get(key)
            category = "SAFE" if point_component == anchor_component else "DISCONNECTED"
        elif nearest_distance <= 2.0 * workspace.voxel_size_m:
            category = "PROJECTED"
        else:
            category = "OUTSIDE_MAP"

        projection = projector.update(point)
        if projection.projected:
            replay_projected += 1
        replay_distances.append(float(projection.distance_m))
        if row.get("workspace_limited") == "1":
            recorded_workspace_limited += 1
        counts[category] += 1
        classified.append((row, point, nearest_distance, category, projection))

    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_REPORT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "time_s", "sender_x", "sender_y", "sender_z", "category",
            "nearest_safe_distance_m", "replay_projected", "replay_projection_distance_m",
            "recorded_workspace_limited", "backend_position_error", "elbow_rad",
        ])
        for row, point, nearest_distance, category, projection in classified:
            writer.writerow([
                row.get("time_s", ""),
                f"{point[0]:.6f}", f"{point[1]:.6f}", f"{point[2]:.6f}",
                category,
                f"{nearest_distance:.6f}",
                int(projection.projected),
                f"{projection.distance_m:.6f}",
                row.get("workspace_limited", ""),
                row.get("backend_position_error", ""),
                row.get("elbow", ""),
            ])

    total = len(rows)
    distances = np.asarray(replay_distances, dtype=float)
    print("G1 LIVE WORKSPACE REPLAY")
    print("========================")
    print(f"trace: {trace_path}")
    print(f"workspace: {workspace_path}")
    print(f"safe voxels: {len(workspace.safe_voxel_indices):,}")
    print(f"connected components: {len(component_sizes)}")
    print(f"anchor component voxels: {component_sizes[anchor_component]:,}")
    print(f"valid samples: {total:,}")
    print()
    for name in ("SAFE", "PROJECTED", "OUTSIDE_MAP", "DISCONNECTED"):
        count = counts[name]
        print(f"{name:12s}: {count:5d} ({100.0*count/total:5.1f}%)")
    print()
    print(f"runtime-recorded workspace_limited: {recorded_workspace_limited}/{total} ({100.0*recorded_workspace_limited/total:.1f}%)")
    print(f"replay projected:                  {replay_projected}/{total} ({100.0*replay_projected/total:.1f}%)")
    print(
        "replay projection distance: "
        f"median={np.median(distances)*100:.1f} cm "
        f"p95={np.percentile(distances,95)*100:.1f} cm "
        f"max={np.max(distances)*100:.1f} cm"
    )

    worst = sorted(classified, key=lambda item: item[4].distance_m, reverse=True)[:8]
    print("\nLargest projection examples:")
    for row, point, _, category, projection in worst:
        elbow_deg = float(row.get("elbow", "nan")) * 180.0 / np.pi
        print(
            f"  t={float(row.get('time_s','0')):7.2f}s "
            f"target=({point[0]:+.3f},{point[1]:+.3f},{point[2]:+.3f}) "
            f"{category} projection={projection.distance_m*100:.1f} cm "
            f"elbow={elbow_deg:.1f} deg"
        )

    print(f"\nreport: {DEFAULT_REPORT}")
    print("\nInterpretation:")
    if counts["OUTSIDE_MAP"] + counts["DISCONNECTED"] > total * 0.25:
        print("- A large part of the live command path is absent from, or disconnected inside, the current voxel map.")
        print("- Rebuild/expand the workspace before further IK gain tuning.")
    elif replay_projected > total * 0.25:
        print("- The live path frequently rides the workspace boundary; projection jitter can dominate motion quality.")
    else:
        print("- Most live commands are represented by the workspace; investigate IK branch selection for remaining misses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
