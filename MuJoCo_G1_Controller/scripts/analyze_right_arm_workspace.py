"""Offline collision-aware reachable-workspace sampler for the G1 right arm."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import mujoco
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from g1_right_arm_udp_ik_demo import (  # noqa: E402
    RIGHT_ARM_JOINTS,
    RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES,
    create_right_arm_ik_context,
    freeze_non_arm_joints,
    initialize_model,
    set_left_arm_ready,
)


DEFAULT_OUTPUT = Path("logs/workspace/right_arm_workspace.npz")
DEFAULT_SUMMARY = Path("logs/workspace/right_arm_workspace_summary.json")
DEFAULT_SAMPLES = 200_000
SAFE_MIN_SINGULAR_VALUE = 0.035
SAFE_NORMALIZED_JOINT_MARGIN = 0.08


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample collision-free G1 right-arm joint configurations and save "
            "their reachable wrist workspace without launching a viewer."
        )
    )
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--seed", type=int, default=1048)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--progress-every", type=int, default=10_000)
    parser.add_argument(
        "--safe-min-singular-value",
        type=float,
        default=SAFE_MIN_SINGULAR_VALUE,
        help="minimum positional Jacobian singular value for SAFE classification",
    )
    parser.add_argument(
        "--safe-joint-margin",
        type=float,
        default=SAFE_NORMALIZED_JOINT_MARGIN,
        help="minimum normalized distance to every sampled joint limit",
    )
    return parser.parse_args()


def right_arm_joint_limits(model) -> tuple[np.ndarray, np.ndarray]:
    lower = []
    upper = []
    for joint_name in RIGHT_ARM_JOINTS:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        if joint_id < 0:
            raise RuntimeError(f"joint not found: {joint_name}")
        if not model.jnt_limited[joint_id]:
            raise RuntimeError(f"workspace sampler requires a limited joint: {joint_name}")

        low, high = map(float, model.jnt_range[joint_id])
        if joint_name in RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES:
            operational_low, operational_high = RIGHT_ARM_OPERATIONAL_LIMITS_DEGREES[joint_name]
            low = max(low, math.radians(operational_low))
            high = min(high, math.radians(operational_high))
        if not low < high:
            raise RuntimeError(f"invalid effective joint range for {joint_name}: {low}, {high}")
        lower.append(low)
        upper.append(high)
    return np.asarray(lower), np.asarray(upper)


def normalized_joint_margin(q: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    span = upper - lower
    distance_to_nearest_limit = np.minimum(q - lower, upper - q)
    return float(np.min(distance_to_nearest_limit / span))


def robot_body_ids(model) -> set[int]:
    ids: set[int] = set()
    for body_id in range(1, model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        if name is not None:
            ids.add(body_id)
    return ids


def has_right_arm_robot_contact(model, data, right_arm_body_ids: set[int], all_robot_body_ids: set[int]) -> bool:
    """Return True for any MuJoCo-enabled contact between the right arm and robot.

    The generated workspace scene disables the floor/panel collision masks, so
    contacts involving world body 0 are ignored. MuJoCo's model-level contact
    filtering remains authoritative for adjacent-link exclusions.
    """
    for contact_index in range(data.ncon):
        contact = data.contact[contact_index]
        first_body = int(model.geom_bodyid[contact.geom1])
        second_body = int(model.geom_bodyid[contact.geom2])
        if first_body == second_body:
            continue
        first_is_arm = first_body in right_arm_body_ids
        second_is_arm = second_body in right_arm_body_ids
        if not (first_is_arm or second_is_arm):
            continue
        other_body = second_body if first_is_arm else first_body
        if other_body in all_robot_body_ids:
            return True
    return False


def positional_quality(model, data, context) -> tuple[float, float]:
    jacp = np.zeros((3, model.nv), dtype=float)
    jacr = np.zeros((3, model.nv), dtype=float)
    mujoco.mj_jacBody(model, data, jacp, jacr, context["position_body"])
    jacobian = jacp[:, context["right_dof_ids"]]
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    min_singular_value = float(np.min(singular_values))
    gram = jacobian @ jacobian.T
    manipulability = float(math.sqrt(max(0.0, np.linalg.det(gram))))
    return min_singular_value, manipulability


def classify_sample(
    *,
    collision: bool,
    min_singular_value: float,
    joint_margin: float,
    safe_min_singular_value: float,
    safe_joint_margin: float,
) -> int:
    """0=collision, 1=reachable-but-poor, 2=safe."""
    if collision:
        return 0
    if min_singular_value < safe_min_singular_value or joint_margin < safe_joint_margin:
        return 1
    return 2


def percentile_bounds(points: np.ndarray, low_percentile: float = 0.5, high_percentile: float = 99.5) -> dict[str, list[float]]:
    if len(points) == 0:
        return {"low": [0.0, 0.0, 0.0], "high": [0.0, 0.0, 0.0]}
    return {
        "low": np.percentile(points, low_percentile, axis=0).tolist(),
        "high": np.percentile(points, high_percentile, axis=0).tolist(),
    }


def main() -> None:
    args = parse_args()
    if args.samples <= 0:
        raise ValueError("--samples must be positive")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be positive")
    if args.safe_min_singular_value < 0.0:
        raise ValueError("--safe-min-singular-value must be non-negative")
    if not 0.0 <= args.safe_joint_margin < 0.5:
        raise ValueError("--safe-joint-margin must be in [0, 0.5)")

    model, data, initial_qpos, _ = initialize_model("control")
    context = create_right_arm_ik_context(model)
    right_qpos_ids = context["right_qpos_ids"]
    lower, upper = right_arm_joint_limits(model)
    rng = np.random.default_rng(args.seed)

    right_arm_body_ids = set(context["right_arm_body_ids"])
    all_robot_body_ids = robot_body_ids(model)

    positions = np.empty((args.samples, 3), dtype=np.float32)
    joint_positions = np.empty((args.samples, len(RIGHT_ARM_JOINTS)), dtype=np.float32)
    min_singular_values = np.empty(args.samples, dtype=np.float32)
    manipulability = np.empty(args.samples, dtype=np.float32)
    joint_margins = np.empty(args.samples, dtype=np.float32)
    classes = np.empty(args.samples, dtype=np.uint8)

    start = time.perf_counter()
    for sample_index in range(args.samples):
        q = rng.uniform(lower, upper)
        freeze_non_arm_joints(model, data, initial_qpos)
        set_left_arm_ready(model, data)
        data.qpos[right_qpos_ids] = q
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)

        collision = has_right_arm_robot_contact(
            model,
            data,
            right_arm_body_ids,
            all_robot_body_ids,
        )
        min_sv, manip = positional_quality(model, data, context)
        margin = normalized_joint_margin(q, lower, upper)
        sample_class = classify_sample(
            collision=collision,
            min_singular_value=min_sv,
            joint_margin=margin,
            safe_min_singular_value=args.safe_min_singular_value,
            safe_joint_margin=args.safe_joint_margin,
        )

        positions[sample_index] = data.xpos[context["position_body"]]
        joint_positions[sample_index] = q
        min_singular_values[sample_index] = min_sv
        manipulability[sample_index] = manip
        joint_margins[sample_index] = margin
        classes[sample_index] = sample_class

        completed = sample_index + 1
        if completed % args.progress_every == 0 or completed == args.samples:
            elapsed = max(time.perf_counter() - start, 1e-9)
            rate = completed / elapsed
            print(
                f"{completed:,}/{args.samples:,} samples "
                f"({100.0 * completed / args.samples:5.1f}%) "
                f"{rate:,.0f} samples/s"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        positions_m=positions,
        right_arm_q_rad=joint_positions,
        min_singular_value=min_singular_values,
        manipulability=manipulability,
        normalized_joint_margin=joint_margins,
        classification=classes,
        joint_lower_rad=lower,
        joint_upper_rad=upper,
        joint_names=np.asarray(RIGHT_ARM_JOINTS),
    )

    collision_mask = classes == 0
    reachable_mask = classes >= 1
    safe_mask = classes == 2
    reachable_points = positions[reachable_mask]
    safe_points = positions[safe_mask]
    elapsed = time.perf_counter() - start

    summary = {
        "samples": int(args.samples),
        "seed": int(args.seed),
        "elapsed_s": elapsed,
        "sample_rate_hz": args.samples / max(elapsed, 1e-9),
        "classification": {
            "collision": int(np.count_nonzero(collision_mask)),
            "reachable_but_poor": int(np.count_nonzero(classes == 1)),
            "safe": int(np.count_nonzero(safe_mask)),
        },
        "fractions": {
            "collision": float(np.mean(collision_mask)),
            "reachable": float(np.mean(reachable_mask)),
            "safe": float(np.mean(safe_mask)),
        },
        "reachable_bounds_m": {
            "min": reachable_points.min(axis=0).tolist() if len(reachable_points) else None,
            "max": reachable_points.max(axis=0).tolist() if len(reachable_points) else None,
            "percentile_0_5_to_99_5": percentile_bounds(reachable_points),
        },
        "safe_bounds_m": {
            "min": safe_points.min(axis=0).tolist() if len(safe_points) else None,
            "max": safe_points.max(axis=0).tolist() if len(safe_points) else None,
            "percentile_0_5_to_99_5": percentile_bounds(safe_points),
        },
        "quality_thresholds": {
            "safe_min_singular_value": args.safe_min_singular_value,
            "safe_normalized_joint_margin": args.safe_joint_margin,
        },
        "output_npz": str(args.output),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Saved workspace samples: {args.output}")
    print(f"Saved summary: {args.summary}")
    print(json.dumps(summary["classification"], indent=2))


if __name__ == "__main__":
    main()
