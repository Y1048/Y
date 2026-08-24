"""Targeted intermediate-only collision stress test for the final swept-path guard.

This diagnostic searches specifically for C-space pairs whose endpoints are both
safe while the straight joint-space interpolation crosses the 5 mm hard floor.
Each discovered case is then replayed through the production swept-path guard.

No hardware is commanded. All motion is evaluated only by mutating MuJoCo qpos.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (SCRIPT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import g1_right_arm_udp_ik_demo as base  # noqa: E402
import run_configuration_aware_g1_teleop as configured  # noqa: E402
from g1_teleop.runtime_collision import dangerous_contact_clearance_m  # noqa: E402
from g1_teleop.swept_path_collision_guard import (  # noqa: E402
    SWEPT_PATH_FLOOR_M,
    install_swept_path_collision_guard,
)


@dataclass
class CaseResult:
    case_index: int
    pair_attempt: int
    start_clearance_m: float | None
    endpoint_clearance_m: float | None
    dense_min_clearance_m: float | None
    dense_min_fraction: float
    dense_samples: int
    max_joint_delta_deg: float
    guard_samples: int
    guard_clipped: bool
    guard_scale: float
    guard_min_clearance_m: float | None
    guard_after_m: float | None
    false_negative: bool
    final_violation: bool
    start_q_deg: list[float]
    end_q_deg: list[float]


def _clearance(model: Any, data: Any, context: dict[str, Any]) -> float:
    value = dangerous_contact_clearance_m(
        model,
        data,
        context,
        structural_neighbor_distance=int(
            getattr(base, "RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE", 1)
        ),
    )
    return math.inf if value is None else float(value)


def _finite_or_none(value: float) -> float | None:
    return None if math.isinf(value) else float(value)


def _joint_ranges(model: Any) -> tuple[np.ndarray, np.ndarray]:
    lows: list[float] = []
    highs: list[float] = []
    for name in base.RIGHT_ARM_JOINTS:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if joint_id < 0:
            raise RuntimeError(f"missing joint in MuJoCo model: {name}")
        if bool(model.jnt_limited[joint_id]):
            low, high = model.jnt_range[joint_id]
        else:
            low, high = -math.pi, math.pi
        lows.append(float(low))
        highs.append(float(high))
    return np.asarray(lows), np.asarray(highs)


def _set_pose(
    model: Any,
    data: Any,
    initial_qpos: np.ndarray,
    qpos_ids: np.ndarray,
    q: np.ndarray,
) -> None:
    data.qpos[:] = initial_qpos
    data.qpos[qpos_ids] = q
    base.freeze_non_arm_joints(model, data, initial_qpos)
    base.set_left_arm_ready(model, data)
    mujoco.mj_forward(model, data)


def _pose_safe(model: Any, data: Any, context: dict[str, Any], margin_m: float) -> bool:
    return (
        _clearance(model, data, context) >= margin_m
        and not base.has_right_arm_core_contact(model, data, context)
    )


def _build_safe_pool(
    model: Any,
    data: Any,
    context: dict[str, Any],
    initial_qpos: np.ndarray,
    qpos_ids: np.ndarray,
    lows: np.ndarray,
    highs: np.ndarray,
    rng: np.random.Generator,
    desired: int,
    endpoint_margin_m: float,
) -> list[np.ndarray]:
    pool: list[np.ndarray] = []
    baseline = data.qpos[qpos_ids].copy()
    attempts = 0
    max_attempts = desired * 600

    while len(pool) < desired and attempts < max_attempts:
        attempts += 1
        if pool and rng.random() < 0.72:
            anchor = pool[int(rng.integers(0, len(pool)))]
            perturb = np.radians(rng.normal(0.0, 24.0, size=7))
            q = np.clip(anchor + perturb, lows, highs)
        elif rng.random() < 0.35:
            q = np.clip(
                baseline + np.radians(rng.normal(0.0, 42.0, size=7)),
                lows,
                highs,
            )
        else:
            # Broad joint-space coverage; bias away from exact limits.
            u = rng.uniform(0.08, 0.92, size=7)
            q = lows + u * (highs - lows)

        _set_pose(model, data, initial_qpos, qpos_ids, q)
        if not _pose_safe(model, data, context, endpoint_margin_m):
            continue

        candidate = data.qpos[qpos_ids].copy()
        if pool:
            nearest = min(float(np.linalg.norm(candidate - item)) for item in pool)
            if nearest < math.radians(3.0):
                continue
        pool.append(candidate)

    if len(pool) < max(8, min(desired, 32)):
        raise RuntimeError(
            f"safe endpoint pool too small: found {len(pool)} / requested {desired}"
        )
    return pool


def _dense_path(
    model: Any,
    data: Any,
    context: dict[str, Any],
    initial_qpos: np.ndarray,
    qpos_ids: np.ndarray,
    start_q: np.ndarray,
    end_q: np.ndarray,
    step_deg: float,
) -> tuple[float, float, int, bool]:
    delta = end_q - start_q
    max_delta_deg = float(np.max(np.abs(np.degrees(delta))))
    segments = max(2, int(math.ceil(max_delta_deg / step_deg)))
    min_clearance = math.inf
    min_fraction = 0.0
    unsafe = False

    for index in range(segments + 1):
        fraction = index / segments
        q = start_q + fraction * delta
        _set_pose(model, data, initial_qpos, qpos_ids, q)
        clearance = _clearance(model, data, context)
        if clearance < min_clearance:
            min_clearance = clearance
            min_fraction = fraction
        if (
            clearance < SWEPT_PATH_FLOOR_M
            or base.has_right_arm_core_contact(model, data, context)
        ):
            unsafe = True

    return min_clearance, min_fraction, segments + 1, unsafe


def _pair_score(
    model: Any,
    data: Any,
    context: dict[str, Any],
    initial_qpos: np.ndarray,
    qpos_ids: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
) -> float:
    """Cheap midpoint/quarter-point score; lower clearance is more promising."""
    score = math.inf
    for fraction in (0.25, 0.5, 0.75):
        _set_pose(model, data, initial_qpos, qpos_ids, a + fraction * (b - a))
        clearance = _clearance(model, data, context)
        if base.has_right_arm_core_contact(model, data, context):
            return -1.0
        score = min(score, clearance)
    return score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-cases", type=int, default=100)
    parser.add_argument("--safe-endpoints", type=int, default=320)
    parser.add_argument("--pair-attempts", type=int, default=60000)
    parser.add_argument("--endpoint-margin-m", type=float, default=0.007)
    parser.add_argument("--reference-step-deg", type=float, default=0.03)
    parser.add_argument("--prefilter-clearance-m", type=float, default=0.009)
    parser.add_argument("--min-pair-delta-deg", type=float, default=12.0)
    parser.add_argument("--max-pair-delta-deg", type=float, default=150.0)
    parser.add_argument("--seed", type=int, default=2048)
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            PROJECT_ROOT
            / "logs"
            / "diagnostics"
            / "swept_path_intermediate_only_stress.json"
        ),
    )
    args = parser.parse_args()

    if args.reference_step_deg <= 0.0:
        raise SystemExit("--reference-step-deg must be > 0")
    if args.target_cases <= 0:
        raise SystemExit("--target-cases must be > 0")

    rng = np.random.default_rng(args.seed)
    configured.install_right_hand_collision_proxy_generation()
    model, data, initial_qpos, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    lows, highs = _joint_ranges(model)

    pool = _build_safe_pool(
        model,
        data,
        context,
        initial_qpos,
        qpos_ids,
        lows,
        highs,
        rng,
        args.safe_endpoints,
        args.endpoint_margin_m,
    )

    candidate_holder: dict[str, np.ndarray] = {"q": pool[0].copy()}

    def injected_candidate_solver(*solver_args: Any, **solver_kwargs: Any):
        solver_data = solver_args[1] if len(solver_args) > 1 else solver_kwargs["data"]
        solver_data.qpos[qpos_ids] = candidate_holder["q"]
        base.clamp_joint_angles(model, solver_data, base.RIGHT_ARM_JOINTS)
        mujoco.mj_forward(model, solver_data)
        return solver_data.xpos[int(context["position_body"])].copy()

    original_solver = base.solve_right_arm_target
    original_installed = getattr(base, "_SWEPT_PATH_COLLISION_GUARD_INSTALLED", False)
    original_status_installed = getattr(base, "_SWEPT_PATH_COLLISION_STATUS_INSTALLED", False)
    base.solve_right_arm_target = injected_candidate_solver
    base._SWEPT_PATH_COLLISION_GUARD_INSTALLED = False
    base._SWEPT_PATH_COLLISION_STATUS_INSTALLED = False
    install_swept_path_collision_guard(base)
    guarded_solver = base.solve_right_arm_target

    cases: list[CaseResult] = []
    dense_candidates_checked = 0
    prefilter_hits = 0
    start_time = time.perf_counter()

    try:
        for attempt in range(1, args.pair_attempts + 1):
            if len(cases) >= args.target_cases:
                break

            ia, ib = rng.choice(len(pool), size=2, replace=False)
            a = pool[int(ia)]
            b = pool[int(ib)]
            max_delta_deg = float(np.max(np.abs(np.degrees(b - a))))
            if (
                max_delta_deg < args.min_pair_delta_deg
                or max_delta_deg > args.max_pair_delta_deg
            ):
                continue

            _set_pose(model, data, initial_qpos, qpos_ids, a)
            start_clearance = _clearance(model, data, context)
            _set_pose(model, data, initial_qpos, qpos_ids, b)
            endpoint_clearance = _clearance(model, data, context)
            if (
                start_clearance < args.endpoint_margin_m
                or endpoint_clearance < args.endpoint_margin_m
                or base.has_right_arm_core_contact(model, data, context)
            ):
                continue

            cheap_min = _pair_score(
                model, data, context, initial_qpos, qpos_ids, a, b
            )
            if cheap_min >= args.prefilter_clearance_m:
                continue
            prefilter_hits += 1

            dense_candidates_checked += 1
            dense_min, dense_fraction, dense_samples, dense_unsafe = _dense_path(
                model,
                data,
                context,
                initial_qpos,
                qpos_ids,
                a,
                b,
                args.reference_step_deg,
            )
            if not dense_unsafe:
                continue

            # Endpoints are already known safe, therefore this is a true
            # intermediate-only unsafe path.
            _set_pose(model, data, initial_qpos, qpos_ids, a)
            candidate_holder["q"] = b.copy()
            guarded_solver(model=model, data=data, context=context)

            guard_clipped = bool(base.RUNTIME_SWEPT_PATH_CLIPPED)
            final_clearance = _clearance(model, data, context)
            final_contact = base.has_right_arm_core_contact(model, data, context)
            final_violation = bool(
                final_contact or final_clearance < SWEPT_PATH_FLOOR_M - 1e-8
            )
            false_negative = bool(not guard_clipped)

            cases.append(
                CaseResult(
                    case_index=len(cases),
                    pair_attempt=attempt,
                    start_clearance_m=_finite_or_none(start_clearance),
                    endpoint_clearance_m=_finite_or_none(endpoint_clearance),
                    dense_min_clearance_m=_finite_or_none(dense_min),
                    dense_min_fraction=float(dense_fraction),
                    dense_samples=int(dense_samples),
                    max_joint_delta_deg=max_delta_deg,
                    guard_samples=int(base.RUNTIME_SWEPT_PATH_SAMPLES),
                    guard_clipped=guard_clipped,
                    guard_scale=float(base.RUNTIME_SWEPT_PATH_SCALE),
                    guard_min_clearance_m=base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M,
                    guard_after_m=base.RUNTIME_SWEPT_PATH_AFTER_M,
                    false_negative=false_negative,
                    final_violation=final_violation,
                    start_q_deg=np.round(np.degrees(a), 5).tolist(),
                    end_q_deg=np.round(np.degrees(b), 5).tolist(),
                )
            )

            if len(cases) % 10 == 0:
                print(
                    f"found {len(cases)} intermediate-only cases "
                    f"after {attempt} pair attempts..."
                )

            if false_negative or final_violation:
                print("[FAIL-FAST] unsafe intermediate-only case escaped guard")
                break
    finally:
        base.solve_right_arm_target = original_solver
        base._SWEPT_PATH_COLLISION_GUARD_INSTALLED = original_installed
        base._SWEPT_PATH_COLLISION_STATUS_INSTALLED = original_status_installed

    elapsed = time.perf_counter() - start_time
    false_negatives = sum(1 for item in cases if item.false_negative)
    final_violations = sum(1 for item in cases if item.final_violation)
    clipped = sum(1 for item in cases if item.guard_clipped)

    summary = {
        "seed": args.seed,
        "target_cases": args.target_cases,
        "intermediate_only_cases_found": len(cases),
        "safe_endpoint_pool": len(pool),
        "pair_attempt_limit": args.pair_attempts,
        "prefilter_hits": prefilter_hits,
        "dense_candidates_checked": dense_candidates_checked,
        "reference_step_deg": args.reference_step_deg,
        "endpoint_margin_m": args.endpoint_margin_m,
        "floor_m": SWEPT_PATH_FLOOR_M,
        "guard_clipped_cases": clipped,
        "false_negatives": false_negatives,
        "unsafe_final_poses": final_violations,
        "elapsed_s": elapsed,
        "pair_attempts_per_s": (
            (cases[-1].pair_attempt if cases else args.pair_attempts) / elapsed
            if elapsed > 0.0
            else None
        ),
    }

    payload = {
        "summary": summary,
        "cases": [asdict(item) for item in cases],
        "failures": [
            asdict(item)
            for item in cases
            if item.false_negative or item.final_violation
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print("G1 INTERMEDIATE-ONLY SWEPT-PATH STRESS DIAGNOSTIC")
    print("================================================")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"report: {args.report}")

    passed = (
        len(cases) > 0
        and false_negatives == 0
        and final_violations == 0
        and clipped == len(cases)
    )
    complete = len(cases) >= args.target_cases
    if passed and complete:
        print(
            "RESULT: PASS - all targeted intermediate-only collision paths "
            "were clipped safely"
        )
        return 0
    if passed:
        print(
            "RESULT: PARTIAL PASS - no failures, but target case count was not reached"
        )
        return 2

    print(
        "RESULT: FAIL - intermediate-only coverage missing or at least one unsafe "
        "path escaped the guard"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
