"""Offline-only task-priority research prototype; never selected by a launcher.

First solve the wrist pose task with the existing kinematic constraints, then
minimize proximal velocity while preserving its achieved linearized 6D motion.
Uses temporary process-local function interception to reuse the exact current
constraint assembly; this is a benchmark implementation, NOT runtime code.
"""
from unittest.mock import patch

import numpy as np
import mink
import qpsolvers

from replay_upstream_mink import UpstreamMinkTracking


class TaskPriorityPrototype(UpstreamMinkTracking):
    def __init__(self, *args):
        super().__init__(*args)
        self.priority_diagnostics = {
            'secondary_failed': 0, 'secondary_solved': 0,
            'linear_task_preservation_error_max': 0.,
        }

    def _solve_velocity(self):
        build = mink.build_ik
        solve = qpsolvers.solve_problem
        planner = self.planner
        jacobian = None

        def primary_build(configuration, tasks, dt, **kwargs):
            nonlocal jacobian
            jacobian = planner.wrist_task.compute_jacobian(configuration)[:, planner.right_dofs].copy()
            return build(configuration, [planner.wrist_task], dt, **kwargs)

        def solve_priorities(problem, **kwargs):
            first = solve(problem, **kwargs)
            if not first.found or first.x is None:
                return first
            # Independent equality rows avoid a rank-deficient solver KKT
            # system. Preserve the entire reachable row space of the task.
            _, singular, vt = np.linalg.svd(jacobian, full_matrices=False)
            rank = int(np.sum(singular > max(singular[0]*1e-10, 1e-12)))
            rows = vt[:rank]
            target = rows @ first.x
            weights = np.array([1., 1., 1., 1., 1e-6, 1e-6, 1e-6])
            second = solve(qpsolvers.Problem(
                np.diag(weights), np.zeros(7), problem.G, problem.h,
                rows, target), **kwargs)
            if not second.found or second.x is None:
                self.priority_diagnostics['secondary_failed'] += 1
                return first
            error = float(np.max(np.abs(jacobian @ (second.x-first.x))))
            self.priority_diagnostics['linear_task_preservation_error_max'] = max(
                error, self.priority_diagnostics['linear_task_preservation_error_max'])
            if error > 1e-7:
                self.priority_diagnostics['secondary_failed'] += 1
                return first
            self.priority_diagnostics['secondary_solved'] += 1
            return second

        with patch.object(mink, 'build_ik', primary_build), patch.object(
                qpsolvers, 'solve_problem', solve_priorities):
            return super()._solve_velocity()
