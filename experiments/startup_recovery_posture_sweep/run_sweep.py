#!/usr/bin/env python3
"""Map the sampled initial-pose region where Startup Recovery succeeds."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import html
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DIR = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
SCRIPTS_DIR = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
DEFAULT_STATE_PATH = PROJECT_ROOT / "logs" / "runtime" / "g1_hardware_initial_state.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "logs" / "experiments" / "startup_recovery_posture_sweep"
RUNNER = Path(__file__).with_name("single_pose_runner.py")

if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))
from safety_gate import JOINT_LIMITS_RAD, JOINT_NAMES, SafetyConfig  # noqa: E402


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    pitch_offset_deg: float
    roll_offset_deg: float
    elbow_offset_deg: float
    pose_rad: tuple[float, ...]


def ParseOffsets(value: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("offsets must be comma-separated numbers") from exc
    if not values or not all(math.isfinite(item) for item in values):
        raise argparse.ArgumentTypeError("offsets must contain finite numbers")
    return tuple(dict.fromkeys(values))


def ParseArguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline sampled map of G1 Startup Recovery initial poses"
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--pitch-offsets", type=ParseOffsets, default=(0.0,))
    parser.add_argument(
        "--roll-offsets", type=ParseOffsets, default=(-15.0, 0.0, 15.0)
    )
    parser.add_argument(
        "--elbow-offsets", type=ParseOffsets, default=(-15.0, 0.0, 15.0)
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--case-timeout", type=float, default=180.0)
    parser.add_argument("--run-name")
    parser.add_argument(
        "--resume-run",
        type=Path,
        help="Existing run directory; rerun only cases whose status is ERROR",
    )
    return parser.parse_args()


def LoadPose(path: Path) -> np.ndarray:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pose = np.asarray(payload.get("right_arm_q_rad"), dtype=float)
    if pose.shape != (7,) or not np.all(np.isfinite(pose)):
        raise RuntimeError("right_arm_q_rad must contain seven finite values")
    return pose


def GenerateCases(
    base_pose_rad: np.ndarray,
    pitch_offsets_deg: tuple[float, ...],
    roll_offsets_deg: tuple[float, ...],
    elbow_offsets_deg: tuple[float, ...],
) -> list[SweepCase]:
    cases: list[SweepCase] = []
    for pitch_index, pitch_offset in enumerate(pitch_offsets_deg):
        for elbow_index, elbow_offset in enumerate(elbow_offsets_deg):
            for roll_index, roll_offset in enumerate(roll_offsets_deg):
                pose = base_pose_rad.copy()
                pose[0] += math.radians(pitch_offset)
                pose[1] += math.radians(roll_offset)
                pose[3] += math.radians(elbow_offset)
                case_id = f"p{pitch_index:02d}_e{elbow_index:02d}_r{roll_index:02d}"
                cases.append(
                    SweepCase(
                        case_id=case_id,
                        pitch_offset_deg=pitch_offset,
                        roll_offset_deg=roll_offset,
                        elbow_offset_deg=elbow_offset,
                        pose_rad=tuple(float(item) for item in pose),
                    )
                )
    return cases


def JointLimitFailure(pose_rad: tuple[float, ...]) -> str | None:
    margin = SafetyConfig().joint_limit_margin_rad
    for name, value, (low, high) in zip(JOINT_NAMES, pose_rad, JOINT_LIMITS_RAD):
        if value < low + margin or value > high - margin:
            return (
                f"joint_limit:{name}:value={math.degrees(value):.2f}:"
                f"safe=[{math.degrees(low + margin):.2f},{math.degrees(high - margin):.2f}]"
            )
    return None


def PrepareModel() -> None:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import run_mink_g1_right_arm_prototype as controller

    controller._prepare_mink_xml()


def FailureReason(result: dict[str, Any], exit_code: int) -> str:
    failure = result.get("failure")
    if failure:
        return str(failure)
    collision = result.get("motion_profile", {}).get("collision_validation", {})
    if collision and collision.get("passed") is False:
        return str(collision.get("failure") or "swept_path_validation")
    gate = result.get("safety_gate", {})
    if gate and gate.get("passed") is False:
        return str(gate.get("failure") or "safety_gate")
    return f"recovery_exit_{exit_code}"


def RunCase(
    case: SweepCase,
    run_dir: Path,
    source_state: Path,
    timeout_s: float,
) -> dict[str, Any]:
    case_dir = run_dir / "cases" / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    state_path = case_dir / "initial_state.json"
    result_path = case_dir / "result.json"
    log_path = case_dir / "run.log"
    pose_deg = [math.degrees(value) for value in case.pose_rad]
    state_path.write_text(
        json.dumps(
            {
                "mode": "SYNTHETIC_OFFLINE_POSTURE_SWEEP",
                "source_state_path": str(source_state),
                "right_arm_q_rad": list(case.pose_rad),
                "right_arm_q_deg": pose_deg,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    common = {
        "case_id": case.case_id,
        "pitch_offset_deg": case.pitch_offset_deg,
        "roll_offset_deg": case.roll_offset_deg,
        "elbow_offset_deg": case.elbow_offset_deg,
        "initial_q_rad": list(case.pose_rad),
        "initial_q_deg": pose_deg,
        "state_path": str(state_path.resolve()),
        "result_path": str(result_path.resolve()),
        "log_path": str(log_path.resolve()),
    }
    limit_failure = JointLimitFailure(case.pose_rad)
    if limit_failure:
        return common | {
            "status": "SKIPPED",
            "passed": False,
            "failure": limit_failure,
            "wall_time_s": 0.0,
        }

    command = [
        sys.executable,
        str(RUNNER),
        "--state",
        str(state_path),
        "--result",
        str(result_path),
    ]
    environment = os.environ.copy()
    environment["G1_SWEEP_MODEL_PREPARED"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        wall_time_s = time.monotonic() - started
        log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    except subprocess.TimeoutExpired as exc:
        wall_time_s = time.monotonic() - started
        output = (exc.stdout or "") + (exc.stderr or "")
        log_path.write_text(str(output), encoding="utf-8")
        return common | {
            "status": "ERROR",
            "passed": False,
            "failure": f"case_timeout:{timeout_s:.1f}s",
            "wall_time_s": wall_time_s,
        }

    if not result_path.exists():
        return common | {
            "status": "ERROR",
            "passed": False,
            "failure": f"missing_result:exit={completed.returncode}",
            "process_exit_code": completed.returncode,
            "wall_time_s": wall_time_s,
        }

    result = json.loads(result_path.read_text(encoding="utf-8"))
    passed = result.get("passed") is True and completed.returncode == 0
    return common | {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "failure": None if passed else FailureReason(result, completed.returncode),
        "process_exit_code": completed.returncode,
        "wall_time_s": wall_time_s,
        "recovery_time_s": result.get("elapsed_s"),
        "initial_clearance_m": result.get("initial_minimum_clearance_m"),
        "minimum_clearance_after_escape_m": result.get(
            "minimum_clearance_after_escape_m"
        ),
        "maximum_velocity_deg_s": result.get("maximum_joint_velocity_deg_s"),
        "maximum_acceleration_deg_s2": result.get(
            "maximum_joint_acceleration_deg_s2"
        ),
        "maximum_jerk_deg_s3": result.get("maximum_joint_jerk_deg_s3"),
    }


def WriteCSV(path: Path, results: list[dict[str, Any]]) -> None:
    fields = [
        "case_id",
        "status",
        "passed",
        "pitch_offset_deg",
        "roll_offset_deg",
        "elbow_offset_deg",
        "recovery_time_s",
        "initial_clearance_m",
        "minimum_clearance_after_escape_m",
        "maximum_velocity_deg_s",
        "maximum_acceleration_deg_s2",
        "maximum_jerk_deg_s3",
        "wall_time_s",
        "failure",
        "result_path",
        "log_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def _number(value: object, scale: float = 1.0, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    try:
        number = float(value) * scale
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(number):
        return "n/a"
    return f"{number:.{digits}f}"


def BuildHTML(summary: dict[str, Any]) -> str:
    results = summary["cases"]
    by_key = {
        (
            float(item["pitch_offset_deg"]),
            float(item["elbow_offset_deg"]),
            float(item["roll_offset_deg"]),
        ): item
        for item in results
    }
    pitch_offsets = summary["axes"]["shoulder_pitch_offset_deg"]
    roll_offsets = summary["axes"]["shoulder_roll_offset_deg"]
    elbow_offsets = summary["axes"]["elbow_offset_deg"]
    base_deg = summary["base_q_deg"]
    sections: list[str] = []
    for pitch in pitch_offsets:
        header = "".join(
            f"<th>roll {roll:+.1f}<small>abs {base_deg[1] + roll:.1f}</small></th>"
            for roll in roll_offsets
        )
        rows: list[str] = []
        for elbow in reversed(elbow_offsets):
            cells: list[str] = []
            for roll in roll_offsets:
                item = by_key[(float(pitch), float(elbow), float(roll))]
                status = item["status"]
                css = status.lower()
                label = "BASE" if pitch == 0 and elbow == 0 and roll == 0 else status
                detail = (
                    f"{_number(item.get('recovery_time_s'))} s / "
                    f"{_number(item.get('minimum_clearance_after_escape_m'), 1000.0)} mm"
                    if status == "PASS"
                    else html.escape(str(item.get("failure") or "unknown"))
                )
                title = html.escape(
                    f"{item['case_id']} | {status} | {detail}", quote=True
                )
                result_uri = Path(item["result_path"]).as_uri()
                cells.append(
                    f'<td class="{css}" title="{title}"><a href="{result_uri}">'
                    f"<strong>{label}</strong><small>{detail}</small></a></td>"
                )
            rows.append(
                f"<tr><th>elbow {elbow:+.1f}<small>abs {base_deg[3] + elbow:.1f}</small></th>"
                + "".join(cells)
                + "</tr>"
            )
        sections.append(
            "<section><h2>Shoulder pitch offset "
            f"{pitch:+.1f} deg <span>(absolute {base_deg[0] + pitch:.1f} deg)</span></h2>"
            "<div class=table-wrap><table><thead><tr><th>Elbow / roll</th>"
            + header
            + "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div></section>"
        )

    counts = summary["status_counts"]
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G1 Startup Recovery posture sweep</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#17202a;letter-spacing:0}main{max-width:1180px;margin:auto;padding:28px}h1{font-size:28px;margin:0 0 8px}h2{font-size:18px;margin:0 0 14px}h2 span{font-weight:400;color:#5f6b76}.meta{color:#5f6b76;margin-bottom:20px}.summary{display:flex;gap:18px;flex-wrap:wrap;margin:18px 0 26px}.metric{border-left:4px solid #2f6f9f;padding:4px 16px}.metric strong{display:block;font-size:24px}.legend{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}.key:before{content:"";display:inline-block;width:13px;height:13px;margin-right:6px;vertical-align:-2px;border:1px solid #71808c}.key.pass:before{background:#b9e6c5}.key.fail:before{background:#f2b8b5}.key.skipped:before{background:#dde2e6}.key.error:before{background:#f5d58b}section{background:white;border:1px solid #d9e0e5;border-radius:6px;padding:18px;margin-bottom:20px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;table-layout:fixed;min-width:620px}th,td{border:1px solid #cbd4da;padding:10px;text-align:center;height:66px}th{background:#edf1f4;font-size:13px}small{display:block;font-weight:400;margin-top:5px;color:#48545e;overflow-wrap:anywhere}td a{color:inherit;text-decoration:none;display:block}td.pass{background:#b9e6c5}td.fail{background:#f2b8b5}td.skipped{background:#dde2e6}td.error{background:#f5d58b}.note{background:#fff8dd;border-left:4px solid #d9a514;padding:12px 14px;margin:22px 0}
</style></head><body><main>""" + f"""
<h1>G1 Startup Recovery posture sweep</h1>
<div class="meta">Run {html.escape(summary['run_name'])} | generated {html.escape(summary['generated_at_utc'])}</div>
<div class="summary"><div class="metric"><strong>{summary['case_count']}</strong>sampled poses</div><div class="metric"><strong>{summary['passed_count']}</strong>passed</div><div class="metric"><strong>{summary['success_rate_percent']:.1f}%</strong>sample success rate</div><div class="metric"><strong>{_number(summary.get('total_wall_time_s'), digits=1)} s</strong>wall time</div></div>
<div class="legend"><span class="key pass">Pass</span><span class="key fail">Recovery rejected</span><span class="key skipped">Outside safe joint limit</span><span class="key error">Infrastructure error</span></div>
<div class="note"><strong>Interpretation:</strong> This is a deterministic map of tested samples only. Green cells do not prove that every unsampled pose between them is safe, and no result is approved for hardware output.</div>
""" + "".join(sections) + f"""
<p>Status counts: {html.escape(json.dumps(counts, sort_keys=True))}</p>
</main></body></html>"""


def WriteOutputs(
    run_dir: Path,
    output_root: Path,
    run_name: str,
    source_state: Path,
    base_pose: np.ndarray,
    args: argparse.Namespace,
    results: list[dict[str, Any]],
    wall_time_s: float,
) -> dict[str, Any]:
    counts = Counter(item["status"] for item in results)
    evaluated = counts["PASS"] + counts["FAIL"]
    summary = {
        "schema": "g1.startup_recovery_posture_sweep.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_name": run_name,
        "experimental": True,
        "sampled_map_only": True,
        "production_files_modified": False,
        "hardware_ready": False,
        "command_output_enabled": False,
        "source_state_path": str(source_state.resolve()),
        "base_q_rad": base_pose.tolist(),
        "base_q_deg": np.degrees(base_pose).tolist(),
        "axes": {
            "shoulder_pitch_offset_deg": list(args.pitch_offsets),
            "shoulder_roll_offset_deg": list(args.roll_offsets),
            "elbow_offset_deg": list(args.elbow_offsets),
        },
        "fixed_joint_policy": "shoulder_yaw_and_all_wrist_joints_hold_base_pose",
        "case_count": len(results),
        "evaluated_count": evaluated,
        "passed_count": counts["PASS"],
        "failed_count": counts["FAIL"],
        "skipped_count": counts["SKIPPED"],
        "error_count": counts["ERROR"],
        "success_rate_percent": 0.0 if evaluated == 0 else 100.0 * counts["PASS"] / evaluated,
        "status_counts": dict(sorted(counts.items())),
        "workers": args.workers,
        "case_timeout_s": args.case_timeout,
        "total_wall_time_s": wall_time_s,
        "cases": sorted(
            results,
            key=lambda item: (
                item["pitch_offset_deg"],
                item["elbow_offset_deg"],
                item["roll_offset_deg"],
            ),
        ),
    }
    summary_path = run_dir / "summary.json"
    csv_path = run_dir / "results.csv"
    map_path = run_dir / "map.html"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    WriteCSV(csv_path, summary["cases"])
    map_path.write_text(BuildHTML(summary), encoding="utf-8")

    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(summary_path, output_root / "latest_summary.json")
    shutil.copy2(csv_path, output_root / "latest_results.csv")
    shutil.copy2(map_path, output_root / "latest_map.html")
    summary["summary_path"] = str(summary_path.resolve())
    summary["csv_path"] = str(csv_path.resolve())
    summary["map_path"] = str(map_path.resolve())
    return summary


def Main() -> int:
    args = ParseArguments()
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")
    if args.case_timeout <= 0.0:
        raise SystemExit("--case-timeout must be > 0")

    retained_results: list[dict[str, Any]] = []
    previous_wall_time_s = 0.0
    if args.resume_run is not None:
        run_dir = args.resume_run.resolve()
        previous_summary_path = run_dir / "summary.json"
        if not previous_summary_path.exists():
            raise SystemExit(f"resume summary is missing: {previous_summary_path}")
        previous = json.loads(previous_summary_path.read_text(encoding="utf-8"))
        source_state = Path(previous["source_state_path"]).resolve()
        output_root = run_dir.parents[1]
        run_name = str(previous["run_name"])
        base_pose = np.asarray(previous["base_q_rad"], dtype=float)
        args.pitch_offsets = tuple(previous["axes"]["shoulder_pitch_offset_deg"])
        args.roll_offsets = tuple(previous["axes"]["shoulder_roll_offset_deg"])
        args.elbow_offsets = tuple(previous["axes"]["elbow_offset_deg"])
        retained_results = [
            item for item in previous["cases"] if item.get("status") != "ERROR"
        ]
        pending_ids = {
            str(item["case_id"])
            for item in previous["cases"]
            if item.get("status") == "ERROR"
        }
        previous_wall_time_s = float(previous.get("total_wall_time_s", 0.0))
        all_cases = GenerateCases(
            base_pose,
            args.pitch_offsets,
            args.roll_offsets,
            args.elbow_offsets,
        )
        cases = [case for case in all_cases if case.case_id in pending_ids]
        if not cases:
            raise SystemExit("resume run has no ERROR cases")
    else:
        source_state = args.state.resolve()
        output_root = args.output_root.resolve()
        base_pose = LoadPose(source_state)
        cases = GenerateCases(
            base_pose,
            args.pitch_offsets,
            args.roll_offsets,
            args.elbow_offsets,
        )
        run_name = args.run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = output_root / "runs" / run_name
        if run_dir.exists():
            raise SystemExit(f"run directory already exists: {run_dir}")
        run_dir.mkdir(parents=True)

    print("G1 Startup Recovery posture sweep - OFFLINE")
    print("------------------------------------------------")
    print(f"Source pose: {source_state}")
    print(f"Cases this pass: {len(cases)}")
    if retained_results:
        print(f"Retained cases:  {len(retained_results)}")
    print(f"Workers:     {args.workers}")
    print("Map axes:    shoulder roll x elbow, sliced by shoulder pitch")
    print("DDS/network: NONE")
    print("Robot command: NONE")
    print("Preparing one immutable MuJoCo model for all workers...", flush=True)
    PrepareModel()

    started = time.monotonic()
    results: list[dict[str, Any]] = list(retained_results)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(
                RunCase,
                case,
                run_dir,
                source_state,
                args.case_timeout,
            ): case
            for case in cases
        }
        completed_count = 0
        for future in concurrent.futures.as_completed(future_map):
            item = future.result()
            results.append(item)
            completed_count += 1
            detail = item.get("failure") or (
                f"recovery={float(item['recovery_time_s']):.3f}s"
                if item.get("recovery_time_s") is not None
                else ""
            )
            print(
                f"[{completed_count:>3}/{len(cases)}] {item['status']:<7} "
                f"pitch={item['pitch_offset_deg']:+.1f} "
                f"roll={item['roll_offset_deg']:+.1f} "
                f"elbow={item['elbow_offset_deg']:+.1f} {detail}",
                flush=True,
            )

    summary = WriteOutputs(
        run_dir,
        output_root,
        run_name,
        source_state,
        base_pose,
        args,
        results,
        previous_wall_time_s + time.monotonic() - started,
    )
    print()
    print(
        f"[PASS] Sweep completed: {summary['passed_count']}/{summary['evaluated_count']} "
        "evaluated poses recovered."
    )
    print(f"Map saved to:     {summary['map_path']}")
    print(f"Summary saved to: {summary['summary_path']}")
    print(f"CSV saved to:     {summary['csv_path']}")
    print("This sampled offline map is not approved for hardware output.")
    if summary["error_count"]:
        print(f"[ERROR] {summary['error_count']} cases had infrastructure errors.")
        print("[ACTION] Inspect those case logs and rerun the sweep before using the map.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(Main())
