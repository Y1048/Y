"""Deterministic stress diagnostic for the final swept-path collision guard.

The diagnostic compares the production guard against a denser reference scan.
It never commands hardware. It only mutates MuJoCo qpos in-process.

Two populations are exercised:
  1) runtime-envelope updates: small joint steps representative of live control;
  2) adversarial updates: larger C-space jumps that stress adaptive sampling.

A false negative means the dense reference path crosses the 5 mm hard floor but
the production guard fails to clip it. Any false negative or unsafe accepted
final pose is a hard FAIL.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, asdict
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
    SWEPT_PATH_BOUNDARY_MARGIN_M,
    install_swept_path_collision_guard,
)


@dataclass
class TrialResult:
    population: str
    trial: int
    max_joint_delta_deg: float
    reference_samples: int
    reference_min_clearance_m: float | None
    reference_unsafe: bool
    endpoint_clearance_m: float | None
    endpoint_safe: bool
    intermediate_only_unsafe: bool
    guard_samples: int
    guard_clipped: bool
    guard_scale: float
    guard_min_clearance_m: float | None
    guard_after_m: float | None
    false_negative: bool
    false_positive: bool
    final_violation: bool
    start_q_deg: list[float]
    candidate_q_deg: list[float]


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


def _dense_reference_scan(
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    start_q: np.ndarray,
    candidate_q: np.ndarray,
    step_deg: float,
) -> tuple[float, int, bool]:
    delta = candidate_q - start_q
    max_delta_deg = float(np.max(np.abs(np.degrees(delta))))
    samples = max(2, int(math.ceil(max_delta_deg / step_deg)))
    min_clearance = math.inf
    unsafe = False

    for index in range(samples + 1):
        alpha = index / samples
        data.qpos[qpos_ids] = start_q + alpha * delta
        base.clamp_joint_angles(model, data, base.RIGHT_ARM_JOINTS)
        mujoco.mj_forward(model, data)
        clearance = _clearance(model, data, context)
        min_clearance = min(min_clearance, clearance)
        if (
            clearance < SWEPT_PATH_FLOOR_M
            or base.has_right_arm_core_contact(model, data, context)
        ):
            unsafe = True

    data.qpos[qpos_ids] = start_q
    mujoco.mj_forward(model, data)
    return min_clearance, samples + 1, unsafe


def _safe_start_pool(
    model: Any,
    data: Any,
    context: dict[str, Any],
    qpos_ids: np.ndarray,
    initial_qpos: np.ndarray,
    lows: np.ndarray,
    highs: np.ndarray,
    rng: np.random.Generator,
    desired: int,
) -> list[np.ndarray]:
    pool: list[np.ndarray] = []
    baseline = data.qpos[qpos_ids].copy()

    candidates = [baseline]
    for _ in range(desired * 80):
        anchor = candidates[int(rng.integers(0, len(candidates)))]
        perturb_deg = rng.normal(0.0, 18.0, size=7)
        q = np.clip(anchor + np.radians(perturb_deg), lows, highs)
        candidates.append(q)

    for q in candidates:
        data.qpos[:] = initial_qpos
        data.qpos[qpos_ids] = q
        base.freeze_non_arm_joints(model, data, initial_qpos)
        base.set_left_arm_ready(model, data)
        mujoco.mj_forward(model, data)
        clearance = _clearance(model, data, context)
        if (
            clearance >= 0.008
            and not base.has_right_arm_core_contact(model, data, context)
        ):
            pool.append(data.qpos[qpos_ids].copy())
            if len(pool) >= desired:
                break

    if not pool:
        raise RuntimeError("could not find any safe start configurations")
    return pool


def _candidate(
    start_q: np.ndarray,
    lows: np.ndarray,
    highs: np.ndarray,
    rng: np.random.Generator,
    max_step_deg: float,
) -> np.ndarray:
    direction = rng.normal(size=7)
    norm = float(np.linalg.norm(direction))
    if norm <= 1e-12:
        direction[0] = 1.0
        norm = 1.0
    direction /= norm

    # Mix whole-arm and sparse-joint moves to expose different swept geometries.
    if rng.random() < 0.35:
        mask = rng.random(7) < 0.45
        if not np.any(mask):
            mask[int(rng.integers(0, 7))] = True
        direction *= mask
        sparse_norm = float(np.linalg.norm(direction))
        if sparse_norm > 1e-12:
            direction /= sparse_norm

    magnitude_deg = float(rng.uniform(max(0.05, 0.08 * max_step_deg), max_step_deg))
    q = start_q + np.radians(magnitude_deg) * direction
    return np.clip(q, lows, highs)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-trials", type=int, default=2500)
    parser.add_argument("--adversarial-trials", type=int, default=750)
    parser.add_argument("--runtime-max-step-deg", type=float, default=1.0)
    parser.add_argument("--adversarial-max-step-deg", type=float, default=30.0)
    parser.add_argument("--reference-step-deg", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=1048)
    parser.add_argument("--safe-starts", type=int, default=48)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "logs" / "diagnostics" / "swept_path_stress.json",
    )
    args = parser.parse_args()

    if args.reference_step_deg <= 0.0:
        raise SystemExit("--reference-step-deg must be > 0")

    rng = np.random.default_rng(args.seed)

    # Ensure the generated model contains the transparent rubber-hand collision proxy.
    configured.install_right_hand_collision_proxy_generation()
    model, data, initial_qpos, _ = base.initialize_model("control")
    context = base.create_right_arm_ik_context(model)
    qpos_ids = np.asarray(context["right_qpos_ids"], dtype=int)
    lows, highs = _joint_ranges(model)

    starts = _safe_start_pool(
        model,
        data,
        context,
        qpos_ids,
        initial_qpos,
        lows,
        highs,
        rng,
        args.safe_starts,
    )

    candidate_holder: dict[str, np.ndarray] = {"q": starts[0].copy()}

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

    results: list[TrialResult] = []
    start_time = time.perf_counter()

    populations = [
        ("runtime", args.runtime_trials, args.runtime_max_step_deg),
        ("adversarial", args.adversarial_trials, args.adversarial_max_step_deg),
    ]

    trial_global = 0
    try:
        for population, count, max_step_deg in populations:
            for trial in range(count):
                trial_global += 1
                start_q = starts[int(rng.integers(0, len(starts)))].copy()
                candidate_q = _candidate(start_q, lows, highs, rng, max_step_deg)

                data.qpos[:] = initial_qpos
                data.qpos[qpos_ids] = start_q
                base.freeze_non_arm_joints(model, data, initial_qpos)
                base.set_left_arm_ready(model, data)
                mujoco.mj_forward(model, data)

                before = _clearance(model, data, context)
                if before < SWEPT_PATH_FLOOR_M:
                    continue

                reference_min, reference_samples, reference_unsafe = _dense_reference_scan(
                    model,
                    data,
                    context,
                    qpos_ids,
                    start_q,
                    candidate_q,
                    args.reference_step_deg,
                )

                data.qpos[qpos_ids] = candidate_q
                mujoco.mj_forward(model, data)
                endpoint_clearance = _clearance(model, data, context)
                endpoint_safe = (
                    endpoint_clearance >= SWEPT_PATH_FLOOR_M
                    and not base.has_right_arm_core_contact(model, data, context)
                )
                intermediate_only_unsafe = bool(reference_unsafe and endpoint_safe)

                data.qpos[:] = initial_qpos
                data.qpos[qpos_ids] = start_q
                base.freeze_non_arm_joints(model, data, initial_qpos)
                base.set_left_arm_ready(model, data)
                mujoco.mj_forward(model, data)
                candidate_holder["q"] = candidate_q.copy()
                guarded_solver(model=model, data=data, context=context)

                guard_clipped = bool(base.RUNTIME_SWEPT_PATH_CLIPPED)
                guard_scale = float(base.RUNTIME_SWEPT_PATH_SCALE)
                guard_after = base.RUNTIME_SWEPT_PATH_AFTER_M
                guard_min = base.RUNTIME_SWEPT_PATH_MIN_CLEARANCE_M
                final_clearance = _clearance(model, data, context)
                final_contact = base.has_right_arm_core_contact(model, data, context)

                false_negative = bool(reference_unsafe and not guard_clipped)
                false_positive = bool((not reference_unsafe) and guard_clipped)
                final_violation = bool(
                    final_contact
                    or final_clearance < SWEPT_PATH_FLOOR_M - 1e-8
                )

                results.append(
                    TrialResult(
                        population=population,
                        trial=trial,
                        max_joint_delta_deg=float(
                            np.max(np.abs(np.degrees(candidate_q - start_q)))
                        ),
                        reference_samples=reference_samples,
                        reference_min_clearance_m=_finite_or_none(reference_min),
                        reference_unsafe=bool(reference_unsafe),
                        endpoint_clearance_m=_finite_or_none(endpoint_clearance),
                        endpoint_safe=bool(endpoint_safe),
                        intermediate_only_unsafe=intermediate_only_unsafe,
                        guard_samples=int(base.RUNTIME_SWEPT_PATH_SAMPLES),
                        guard_clipped=guard_clipped,
                        guard_scale=guard_scale,
                        guard_min_clearance_m=guard_min,
                        guard_after_m=guard_after,
                        false_negative=false_negative,
                        false_positive=false_positive,
                        final_violation=final_violation,
                        start_q_deg=np.round(np.degrees(start_q), 5).tolist(),
                        candidate_q_deg=np.round(np.degrees(candidate_q), 5).tolist(),
                    )
                )

                if trial_global % 250 == 0:
                    print(f"checked {trial_global} generated paths...")
    finally:
        base.solve_right_arm_target = original_solver
        base._SWEPT_PATH_COLLISION_GUARD_INSTALLED = original_installed
        base._SWEPT_PATH_COLLISION_STATUS_INSTALLED = original_status_installed

    elapsed = time.perf_counter() - start_time

    def count(predicate) -> int:
        return sum(1 for item in results if predicate(item))

    summary = {
        "seed": args.seed,
        "generated_results": len(results),
        "runtime_trials_requested": args.runtime_trials,
        "adversarial_trials_requested": args.adversarial_trials,
        "reference_step_deg": args.reference_step_deg,
        "floor_m": SWEPT_PATH_FLOOR_M,
        "boundary_margin_m": SWEPT_PATH_BOUNDARY_MARGIN_M,
        "safe_start_pool": len(starts),
        "reference_unsafe_paths": count(lambda x: x.reference_unsafe),
        "intermediate_only_unsafe_paths": count(lambda x: x.intermediate_only_unsafe),
        "guard_clipped_paths": count(lambda x: x.guard_clipped),
        "false_negatives": count(lambda x: x.false_negative),
        "false_positives": count(lambda x: x.false_positive),
        "unsafe_final_poses": count(lambda x: x.final_violation),
        "elapsed_s": elapsed,
        "paths_per_s": (len(results) / elapsed) if elapsed > 0.0 else None,
    }

    failures = [
        item
        for item in results
        if item.false_negative or item.final_violation
    ]
    clipped_examples = [item for item in results if item.guard_clipped][:20]
    intermediate_examples = [
        item for item in results if item.intermediate_only_unsafe
    ][:20]

    payload = {
        "summary": summary,
        "failures": [asdict(item) for item in failures[:100]],
        "clipped_examples": [asdict(item) for item in clipped_examples],
        "intermediate_only_examples": [asdict(item) for item in intermediate_examples],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print("G1 SWEPT-PATH GUARD STRESS DIAGNOSTIC")
    print("====================================")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"report: {args.report}")

    passed = (
        summary["false_negatives"] == 0
        and summary["unsafe_final_poses"] == 0
        and summary["guard_clipped_paths"] > 0
    )
    if passed:
        print("RESULT: PASS - no dense-reference false negatives; clipping was exercised")
        return 0

    if summary["guard_clipped_paths"] == 0:
        print("RESULT: INCONCLUSIVE - no clipping case was generated; increase adversarial trials")
        return 2

    print("RESULT: FAIL - inspect failures in the JSON report")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
