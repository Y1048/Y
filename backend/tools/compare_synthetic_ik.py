"""Identical synthetic target suite for project single-QP and hierarchical IK."""

import argparse
import json
import math
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np

from compare_recorded_ik_hierarchy import RunComparison, probe, UseOfflineProximalCost, task_policy
import compare_recorded_ik_hierarchy as comparison
from g1_mink_feasible_target import PositionProgressConstraint


@contextmanager
def ObservePathChecks(enabled):
    """Record rejected samples without changing the original guard decision."""
    rows = []
    if not enabled:
        yield rows
        return
    factory = comparison.BuildPlanner

    def Build(*args, **kwargs):
        planner = factory(*args, **kwargs)
        check = planner.CheckConfiguration
        path = planner._PathClear
        data = probe.mujoco.MjData(planner.model)
        state = {"active": False, "call": 0, "sample": 0}

        def Check(q):
            valid = check(q)
            if state["active"]:
                state["sample"] += 1
                if not valid:
                    joints = []
                    for joint, address in zip(planner.joint_ids, planner.qpos_ids):
                        low, high = planner.model.jnt_range[joint]
                        if planner.model.jnt_limited[joint] and not low - 1e-9 <= q[address] <= high + 1e-9:
                            joints.append(planner.model.joint(joint).name)
                    nearest = None
                    if np.isfinite(q).all():
                        data.qpos[:] = q
                        probe.mujoco.mj_forward(planner.model, data)
                        nearest = probe.base._nearest_pair_distance(planner.model, data, planner.geom_pairs)
                    rows.append({"path_call": state["call"], "sample_fraction": state["sample"] / 4,
                                 "nonfinite": not bool(np.isfinite(q).all()), "joint_violations": joints,
                                 "required_mm": planner.clearance_m * 1000,
                                 "distance_mm": None if nearest is None else nearest[0] * 1000,
                                 "pair": None if nearest is None else [planner.model.geom(i).name for i in nearest[1:]]})
            return valid

        def Path(*args, **kwargs):
            state.update(active=True, call=state["call"] + 1, sample=0)
            try:
                return path(*args, **kwargs)
            finally:
                state["active"] = False

        planner.CheckConfiguration = Check
        planner._PathClear = Path
        return planner

    with patch.object(comparison, "BuildPlanner", side_effect=Build):
        yield rows


@contextmanager
def UseSingleQPCost(value):
    """Override only the single-QP damping task on newly created offline planners."""
    if value is None:
        yield
        return
    if not math.isfinite(value) or value < 0:
        raise ValueError("single-QP proximal cost must be finite and nonnegative")
    factory = comparison.BuildPlanner

    def Build(*args, **kwargs):
        planner = factory(*args, **kwargs)
        planner.tasks[3].cost[planner.proximal_dofs] = value
        return planner

    with patch.object(comparison, "BuildPlanner", side_effect=Build):
        yield


@contextmanager
def UseMeritAblation(enabled, tolerance_mm=0.):
    """Disable only merit acceptance on newly built offline planners."""
    if not math.isfinite(tolerance_mm) or tolerance_mm < 0 or (enabled and tolerance_mm):
        raise ValueError("merit tolerance must be nonnegative and separate from disabling merit")
    if not enabled and tolerance_mm == 0:
        yield
        return
    factory = comparison.BuildPlanner

    def Build(*args, **kwargs):
        planner = factory(*args, **kwargs)
        if enabled:
            planner.require_merit_decrease = False
        else:
            original_merit = planner.GetPositionMerit
            cost = abs(probe.base.POSITION_COST)

            def GetPositionMerit(goal, position_target=None):
                # Euclidean dead zone in the existing weighted squared-error merit.
                residual = math.sqrt(max(0., original_merit(goal, position_target)))
                return max(0., residual - cost * tolerance_mm / 1000) ** 2

            planner.GetPositionMerit = GetPositionMerit
        return planner

    with patch.object(comparison, "BuildPlanner", side_effect=Build):
        yield


class ProgressBand(probe.mink.Limit):
    """Offline per-axis linear displacement band; not absolute position tolerance."""

    def __init__(self, progress, budget_m):
        self.jacobian = progress.jacobian.copy()
        self.center = -progress.error.copy()
        self.budget = budget_m

    def compute_qp_inequalities(self, configuration, dt):
        return probe.mink.Constraint(
            G=np.vstack([self.jacobian, -self.jacobian]),
            h=np.concatenate([self.center + self.budget, -self.center + self.budget]))


class TargetErrorBand(probe.mink.Limit):
    """Linear task-frame residual bound, with primary recovery outside the budget."""

    def __init__(self, progress, error, budget_m):
        self.jacobian = progress.jacobian.copy()
        self.error = np.asarray(error).copy()
        primary_residual = self.error - progress.error
        self.bound = np.maximum(budget_m, np.abs(primary_residual))

    def compute_qp_inequalities(self, configuration, dt):
        return probe.mink.Constraint(
            G=np.vstack([self.jacobian, -self.jacobian]),
            h=np.concatenate([self.bound - self.error, self.bound + self.error]))


@contextmanager
def UseProgressBand(budget_mm, target_error=False, remove_progress=False):
    if not math.isfinite(budget_mm) or budget_mm < 0:
        raise ValueError("progress band must be finite and nonnegative")
    if remove_progress and (budget_mm or target_error):
        raise ValueError("progress removal and bands are mutually exclusive")
    if budget_mm == 0 and not remove_progress:
        yield
        return
    solve = probe.mink.solve_ik

    def Solve(configuration, tasks, *args, **kwargs):
        constraints = kwargs.get("constraints", ())
        progress = [c for c in constraints if isinstance(c, PositionProgressConstraint)]
        if progress:
            kwargs = dict(kwargs)
            kwargs["constraints"] = [c for c in constraints if not isinstance(c, PositionProgressConstraint)]
            if remove_progress:
                bands = []
            elif target_error:
                error = tasks[0].compute_error(configuration)[:3]
                bands = [TargetErrorBand(c, error, budget_mm / 1000) for c in progress]
            else:
                bands = [ProgressBand(c, budget_mm / 1000) for c in progress]
            kwargs["limits"] = [*kwargs["limits"], *bands]
        return solve(configuration, tasks, *args, **kwargs)

    with patch.object(probe.mink, "solve_ik", side_effect=Solve):
        yield


def BuildCases(axis="x"):
    """Return deterministic robot-frame deltas; near-body goal is not proven reachable."""
    if axis not in ("x", "y", "z"):
        raise ValueError("axis must be x, y or z")
    rotation_factory = getattr(probe.mink.SO3, f"from_{axis}_radians")
    times = np.linspace(0., 8., 481)
    cases = {}
    for name in ("wrist_only", "combined", "toward_body", "reversal_step"):
        goals = []
        for seconds in times:
            wave = np.sin(np.pi * seconds / 8) ** 2
            offset = np.zeros(3)
            angle = .35 * wave
            if name == "combined":
                offset = np.array([.04, .02, .03]) * wave
            elif name == "toward_body":
                offset = np.array([-.10, .20, -.06]) * wave
                angle = .15 * wave
            elif name == "reversal_step":
                sign = 0 if seconds < 1 or seconds >= 6 else (1 if seconds < 3 else -1)
                offset = np.array([.04, .02, .02]) * sign
                angle = .35 * sign
            goals.append(probe.base._matrix_to_se3(
                rotation_factory(float(angle)).as_matrix(), offset))
        cases[name] = (times.copy(), goals)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", choices=tuple(BuildCases()), default=None)
    parser.add_argument("--axis", choices=("x", "y", "z"), default="x")
    parser.add_argument("--profile", choices=("mink-default", "hardware-guarded"), default=None)
    parser.add_argument("--mode", choices=("both", "hierarchy", "single_weighted_qp"), default="both")
    parser.add_argument("--initial-arm-deg", type=float, nargs=7, default=[10, -22, 0, 55, 0, 0, 0])
    parser.add_argument("--diagnose-qp", action="store_true")
    parser.add_argument("--diagnose-path", action="store_true")
    parser.add_argument("--single-qp-backtrack", action="store_true")
    parser.add_argument("--progress-band-mm", type=float, default=0.)
    parser.add_argument("--target-error-band", action="store_true")
    parser.add_argument("--disable-merit-offline", action="store_true")
    parser.add_argument("--merit-position-tolerance-mm", type=float, default=0.)
    parser.add_argument("--remove-progress-offline", action="store_true")
    parser.add_argument("--proximal-cost", type=float, default=task_policy.ORIENTATION_PROXIMAL_DAMPING_MAX)
    parser.add_argument("--single-qp-proximal-cost", type=float, default=None)
    args = parser.parse_args()
    if args.single_qp_backtrack and args.mode != "single_weighted_qp":
        parser.error("single-qp-backtrack requires single_weighted_qp")
    if args.single_qp_proximal_cost is not None:
        if args.mode != "single_weighted_qp" or not math.isfinite(args.single_qp_proximal_cost) or args.single_qp_proximal_cost < 0:
            parser.error("single-qp-proximal-cost requires single_weighted_qp and finite nonnegative cost")
    if not math.isfinite(args.merit_position_tolerance_mm) or args.merit_position_tolerance_mm < 0 or (args.disable_merit_offline and args.merit_position_tolerance_mm):
        parser.error("merit tolerance must be nonnegative and separate from disabling merit")
    if not all(math.isfinite(value) for value in args.initial_arm_deg):
        parser.error("initial arm angles must be finite")
    if args.remove_progress_offline and (args.progress_band_mm or args.target_error_band or args.diagnose_qp):
        parser.error("progress removal must run separately from bands and shadow diagnosis")
    if not math.isfinite(args.proximal_cost) or args.proximal_cost < task_policy.ORIENTATION_PROXIMAL_DAMPING_MIN:
        parser.error("proximal-cost must be finite and at least the assist minimum")
    if not math.isfinite(args.progress_band_mm) or args.progress_band_mm < 0:
        parser.error("progress-band-mm must be finite and nonnegative")
    if args.diagnose_qp and args.progress_band_mm:
        parser.error("run shadow diagnostics separately from progress-band trials")
    model = probe.base.LoadMinkModel()
    probe.base._apply_operational_joint_limits(model)
    initial = probe.base._initial_configuration(model)
    addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                 for name in probe.base.g1.RIGHT_ARM_JOINTS]
    initial[addresses] = np.deg2rad(args.initial_arm_deg)
    for name, value in zip(probe.base.g1.RIGHT_ARM_JOINTS, initial[addresses]):
        joint = probe.base._joint_id(model, name)
        if model.jnt_limited[joint] and not model.jnt_range[joint, 0] <= value <= model.jnt_range[joint, 1]:
            parser.error(f"initial angle outside limits: {name}")
    report = {"robot_command": False, "speed_rad_s": probe.live.virtual_center_velocity_limits(),
              "rotation_axis_robot_world": args.axis,
              "per_axis_per_step_progress_band_mm": args.progress_band_mm,
              "target_error_band": args.target_error_band,
              "merit_acceptance_disabled_offline": args.disable_merit_offline,
              "merit_position_tolerance_mm": args.merit_position_tolerance_mm,
              "orientation_proximal_cost_max": args.proximal_cost,
              "single_qp_proximal_cost": args.single_qp_proximal_cost,
              "single_qp_backtrack": args.single_qp_backtrack,
              "progress_equality_removed_offline": args.remove_progress_offline,
              "initial_arm_deg": args.initial_arm_deg, "hold_s": 5., "results": [],
              "limitations": "Project single weighted QP, not upstream vanilla defaults. "
              "Same targets and limits, different planner/acceptance layers. "
              "Sampled kinematics only, no Ruckig/PD or physical safety proof. "
              "Return convergence does not prove intermediate goals reachable."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for profile in ("mink-default", "hardware-guarded"):
        if args.profile is not None and args.profile != profile:
            continue
        initial_planner = comparison.BuildPlanner(model, initial, collision_profile=profile)
        initial_clearance = initial_planner.GetClearance(initial)
        if initial_clearance < initial_planner.clearance_m:
            parser.error(f"initial clearance {initial_clearance * 1000:.3f}mm below profile minimum")
        for name, (times, goals) in BuildCases(args.axis).items():
            if args.case is not None and args.case != name:
                continue
            for mode in (("single_weighted_qp", "hierarchy") if args.mode == "both" else (args.mode,)):
                with UseProgressBand(args.progress_band_mm, args.target_error_band, args.remove_progress_offline), UseMeritAblation(args.disable_merit_offline, args.merit_position_tolerance_mm), UseOfflineProximalCost(args.proximal_cost), UseSingleQPCost(args.single_qp_proximal_cost), ObservePathChecks(args.diagnose_path) as path_rows:
                    metrics = RunComparison(model, initial.copy(), goals, times, mode, 5., profile,
                                            diagnose_qp=args.diagnose_qp, single_qp_backtrack=args.single_qp_backtrack)
                if args.diagnose_path:
                    metrics["rejected_path_samples"] = path_rows
                metrics["maximum_position_error_mm"] = max(row["position_error_mm"] for row in metrics["trace"])
                metrics.pop("trace")
                report["results"].append(dict(profile=profile, case=name, mode=mode,
                                             initial_clearance_mm=initial_clearance * 1000, **metrics))
                args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
                print(f"{profile} {name} {mode}: position_p95={metrics['motion_position_p95_mm']:.2f}mm "
                      f"rotation_p95={metrics['motion_rotation_p95_deg']:.2f}deg "
                      f"proximal_travel={metrics['proximal_total_travel_deg']:.2f}deg "
                      f"clearance_violations={metrics['clearance_violating_frames']}", flush=True)
    print(f"Result saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
