"""Local bilateral geometric IK for a display target, never a motor command.

The caller must supply a private simulation/configuration. Numerical iterations
have no physical duration and do not use the live velocity or stopping tail.
Both arms share one constrained solve; every accepted configuration and the
sampled segment leading to it are checked. A partial result is a checked local
witness, not a global workspace projection or continuous collision proof.
"""
import math
import time

import mink
import mujoco
import numpy as np
import qpsolvers
from qpsolvers.exceptions import SolverError

import g1_mink_shared as base

MAX_ITERATIONS = 48
TRUST_REGION_RAD = .10
POSITION_TOLERANCE_M = .001
ORIENTATION_TOLERANCE_RAD = math.radians(1.)
_SIDES = ('left', 'right')


def _poses(sim):
    return {side: sim.config.get_transform_frame_to_world(
        side + '_wrist_yaw_link', 'body') for side in _SIDES}


def _errors(poses, goals):
    position = {side: float(np.linalg.norm(
        poses[side].translation() - goals[side].translation())) for side in _SIDES}
    orientation = {side: float(np.linalg.norm((
        poses[side].rotation().inverse() @ goals[side].rotation()).log()))
        for side in _SIDES}
    return position, orientation


def _ranges(sim):
    lower, upper = sim.ranges[:, 0].copy(), sim.ranges[:, 1].copy()
    for arm, side in enumerate(_SIDES):
        policy = sim.motion[side]
        reference = policy.posture_reference[policy.qpos_ids[2]]
        index = arm * 7 + 2
        lower[index] = max(lower[index], reference - policy.priority_shoulder_yaw_envelope_rad)
        upper[index] = min(upper[index], reference + policy.priority_shoulder_yaw_envelope_rad)
    return lower, upper


def _bounds(sim, trust_region):
    """Joint displacement inequalities, including coupled-arm collision."""
    rows, values = [], []
    # Same authored configuration and collision limit as the live model. The
    # live VelocityLimit is deliberately not a geometric feasibility condition.
    for limit in (sim.limits[0], sim.limits[2]):
        bound = limit.compute_qp_inequalities(sim.config, 1.)
        if bound.G is not None:
            rows.append(bound.G[:, sim.dofs])
            values.append(bound.h)
    eye = np.eye(len(sim.dofs))
    lower, upper = _ranges(sim)
    q = sim.config.q[sim.qids]
    rows.extend((eye, -eye))
    values.extend((np.minimum(upper - q, trust_region),
                   np.minimum(q - lower, trust_region)))
    g, h = np.vstack(rows), np.concatenate(values)
    if not np.isfinite(g).all() or np.isnan(h).any() or np.isneginf(h).any():
        return None
    norms = np.linalg.norm(g, axis=1)
    finite = np.isfinite(h)
    if np.any(finite & (norms < 1e-12) & (h < -1e-10)):
        return None
    keep = finite & (norms >= 1e-12)
    return g[keep] / norms[keep, None], h[keep] / norms[keep]


def _solve(tasks, sim, bounds, *, equality=None):
    objective = mink.build_ik(sim.config, tasks, 1., damping=1e-7,
                              limits=[], constraints=[])
    hessian = objective.P[np.ix_(sim.dofs, sim.dofs)]
    linear = objective.q[sim.dofs]
    scale = max(float(np.max(np.abs(hessian))), 1e-12)
    a, b = (None, None) if equality is None else equality
    problem = qpsolvers.Problem(hessian / scale, linear / scale,
                               *bounds, A=a, b=b)
    try:
        result = qpsolvers.solve_problem(problem, solver=base._select_solver())
    except SolverError:
        return None
    if result is None or not result.found or result.x is None:
        return None
    step = np.asarray(result.x)
    if step.shape != (len(sim.dofs),) or not np.isfinite(step).all():
        return None
    # Solver status is not sufficient when an ill-conditioned equality or
    # tiny collision row leaves a numerical constraint violation.
    if np.any(bounds[0] @ step > bounds[1] + 1e-7):
        return None
    if a is not None and np.max(np.abs(a @ step - b)) > 1e-7:
        return None
    return step


def _checked_segment(sim, origin, displacement, minimum_clearance=.2,
                     deadline=None):
    velocity = np.zeros(sim.model.nv)
    velocity[sim.dofs] = displacement
    # Use the same authored + operational bounds as seed validation and the
    # QP. Its numeric residual tolerance is not permission to cross an active
    # shoulder-yaw envelope when accepting an exact geometry witness.
    lower, upper = _ranges(sim)
    steps = max(2, int(np.ceil(np.max(np.abs(displacement)) /
                              sim.profile.checked_stop_substep_rad)))
    minimum = minimum_clearance
    candidate = origin.copy()
    for fraction in np.linspace(0., 1., steps + 1)[1:]:
        if deadline is not None and time.perf_counter() >= deadline:
            return None, None
        candidate = origin.copy()
        mujoco.mj_integratePos(sim.model, candidate, velocity, float(fraction))
        if (not np.isfinite(candidate).all()
                or np.any(candidate[sim.qids] < lower - 1e-9)
                or np.any(candidate[sim.qids] > upper + 1e-9)):
            return None, None
        # Prune only geometry pairs whose conservative bounding-box lower
        # bound exceeds the smallest clearance already observed. Such pairs
        # cannot change the reported minimum or hide a hard-clearance failure.
        clearance = sim.clearance(candidate, threshold=minimum)
        if not np.isfinite(clearance) or clearance < sim.clearance_m:
            return None, None
        minimum = min(minimum, clearance)
    return candidate, minimum


def solve_geometric_goal(sim, goals, *, max_iterations=MAX_ITERATIONS,
                         initial_q=None, max_duration_s=None):
    """Return FK of one checked 14-joint witness on a private worker model.

    Position is the first QP objective. The second QP optimizes orientation
    while preserving the first QP's linearized position progress. The latter
    is optional: solver failure retains the checked position-first candidate.
    Nonlinear line search prioritizes position residual and then orientation.
    All returned poses use MuJoCo world coordinates. Inputs are not modified.
    An optional prior geometric witness can maintain the local branch while
    the live command approaches it. The caller owns session/context resets;
    all frozen body coordinates must match the current private snapshot.
    Invalid cached seeds return invalid_warm_start without modifying config;
    the caller can discard that cache and retry from the current snapshot.
    A display worker may set a positive time budget. Expiration returns only
    the last fully checked witness, never an unfinished sampled segment.
    This is a cooperative deadline, not a preemption guarantee for one native
    solver/geometry call; deterministic offline tests may leave it unset.
    """
    if (not isinstance(goals, dict) or set(goals) != set(_SIDES)
            or any(not isinstance(goals[side], mink.SE3)
                   or not np.isfinite(goals[side].as_matrix()).all()
                   or abs(np.linalg.norm(goals[side].rotation().wxyz) - 1.) > 1e-6
                   for side in _SIDES)
            or type(max_iterations) is not int or not 1 <= max_iterations <= 256):
        raise ValueError('Invalid geometric goal or iteration bound')
    if max_duration_s is not None and (
            isinstance(max_duration_s, bool)
            or not isinstance(max_duration_s, (int, float))
            or not np.isfinite(max_duration_s) or max_duration_s <= 0.):
        raise ValueError('Geometric time budget must be finite and positive')
    deadline = (None if max_duration_s is None
                else time.perf_counter() + max_duration_s)
    expired = lambda: deadline is not None and time.perf_counter() >= deadline
    start = sim.config.q.copy()
    lower, upper = _ranges(sim)
    if (start.shape != (sim.model.nq,) or not np.isfinite(start).all()
            or np.any(start[sim.qids] < lower - 1e-9)
            or np.any(start[sim.qids] > upper + 1e-9)):
        return dict(valid=False, status='invalid_start', iterations=0)
    initial_clearance = sim.clearance(start)
    if not np.isfinite(initial_clearance) or initial_clearance < sim.clearance_m:
        return dict(valid=False, status='invalid_start', iterations=0)
    if initial_q is not None:
        warm = np.asarray(initial_q, dtype=float)
        frozen = np.ones(sim.model.nq, dtype=bool)
        frozen[sim.qids] = False
        if (warm.shape != start.shape or not np.isfinite(warm).all()
                or not np.array_equal(warm[frozen], start[frozen])
                or np.any(warm[sim.qids] < lower - 1e-9)
                or np.any(warm[sim.qids] > upper + 1e-9)):
            return dict(valid=False, status='invalid_warm_start', iterations=0)
        warm_clearance = sim.clearance(warm)
        if not np.isfinite(warm_clearance) or warm_clearance < sim.clearance_m:
            return dict(valid=False, status='invalid_warm_start', iterations=0)
        sim.config.update(warm)
        initial_clearance = warm_clearance

    position_tasks, orientation_tasks = [], []
    for side in _SIDES:
        position = mink.FrameTask(side + '_wrist_yaw_link', 'body',
                                  1., 0., gain=.8, lm_damping=0.)
        orientation = mink.FrameTask(side + '_wrist_yaw_link', 'body',
                                     0., 1., gain=.6, lm_damping=0.)
        position.set_target(goals[side])
        orientation.set_target(goals[side])
        position_tasks.append(position)
        orientation_tasks.append(orientation)

    minimum_clearance = initial_clearance
    iterations = 0
    termination = 'iteration_budget'
    for iteration in range(max_iterations):
        if expired():
            termination = 'time_budget'
            break
        poses = _poses(sim)
        errors, angles = _errors(poses, goals)
        if (max(errors.values()) <= POSITION_TOLERANCE_M
                and max(angles.values()) <= ORIENTATION_TOLERANCE_RAD):
            termination = 'converged'
            break
        origin = sim.config.q.copy()
        bounds = _bounds(sim, TRUST_REGION_RAD)
        if bounds is None:
            termination = 'inconsistent_bounds'
            break
        if expired():
            termination = 'time_budget'
            break
        position_step = _solve(position_tasks, sim, bounds)
        if position_step is None:
            termination = 'qp_unavailable'
            break
        if expired():
            termination = 'time_budget'
            break
        jacobian = np.vstack([task.compute_jacobian(sim.config)[:3, sim.dofs]
                              for task in position_tasks])
        step = _solve(orientation_tasks, sim, bounds,
                      equality=(jacobian, jacobian @ position_step))
        if step is None:
            step = position_step
        old_position = sum(value * value for value in errors.values())
        old_rotation = sum(value * value for value in angles.values())
        accepted = False
        # Try the orientation-preserving step, then pure position progress if
        # nonlinear curvature makes the second-stage motion unsuitable.
        for proposal in (step, position_step):
            for scale in (1., .5, .25, .125, .0625):
                if expired():
                    termination = 'time_budget'
                    break
                candidate, clearance = _checked_segment(
                    sim, origin, proposal * scale, minimum_clearance, deadline)
                if expired():
                    termination = 'time_budget'
                    break
                if candidate is None:
                    continue
                sim.config.update(candidate)
                new_errors, new_angles = _errors(_poses(sim), goals)
                new_position = sum(value * value for value in new_errors.values())
                new_rotation = sum(value * value for value in new_angles.values())
                improves_position = new_position < old_position - max(1e-12, old_position * 1e-6)
                preserves_position = (new_position <= old_position + 1e-10
                                      or max(new_errors.values()) <= POSITION_TOLERANCE_M)
                improves_rotation = new_rotation < old_rotation - 1e-9
                if improves_position or (preserves_position and improves_rotation):
                    minimum_clearance = min(minimum_clearance, clearance)
                    accepted = True
                    iterations = iteration + 1
                    break
                sim.config.update(origin)
            if accepted or termination == 'time_budget':
                break
        if not accepted:
            sim.config.update(origin)
            if termination != 'time_budget':
                termination = 'local_stationary'
            break
    poses = _poses(sim)
    errors, angles = _errors(poses, goals)
    converged = (max(errors.values()) <= POSITION_TOLERANCE_M
                 and max(angles.values()) <= ORIENTATION_TOLERANCE_RAD)
    return dict(valid=True,
                status='geometric_goal_converged' if converged else 'geometric_goal_partial',
                termination=termination, q=sim.config.q.copy(), poses=poses,
                iterations=iterations, position_error_m=errors,
                orientation_error_rad=angles,
                minimum_clearance_m=float(minimum_clearance))
