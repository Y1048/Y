"""Numerical examples for docs/CODE_GUIDE.md; no robot, model or network."""

from types import SimpleNamespace
import unittest

import numpy as np
from mink.tasks.task import Task


class ExampleTask(Task):
    def compute_error(self, configuration):
        return np.array([0.1, -0.2])

    def compute_jacobian(self, configuration):
        return np.array([[1.0, 2.0], [0.0, 1.0]])


class MinkTaskCostContractTest(unittest.TestCase):
    def setUp(self):
        self.configuration = SimpleNamespace(_eye_nv=np.eye(2))

    def test_cost_weights_both_error_and_jacobian(self):
        task = ExampleTask(cost=np.array([8.0, 2.0]), gain=0.35)
        objective = task.compute_qp_objective(self.configuration)
        weighted_jacobian = np.diag(task.cost) @ task.compute_jacobian(None)
        weighted_error = -task.cost * 0.35 * task.compute_error(None)
        np.testing.assert_allclose(objective.H, weighted_jacobian.T @ weighted_jacobian)
        np.testing.assert_allclose(objective.c, -weighted_jacobian.T @ weighted_error)

    def test_doubling_all_costs_quadruples_the_objective(self):
        first = ExampleTask(cost=np.ones(2), gain=0.35).compute_qp_objective(self.configuration)
        second = ExampleTask(cost=2 * np.ones(2), gain=0.35).compute_qp_objective(self.configuration)
        np.testing.assert_allclose(second.H, 4 * first.H)
        np.testing.assert_allclose(second.c, 4 * first.c)

    def test_lm_term_depends_on_weighted_feedback_error(self):
        task = ExampleTask(cost=np.array([8.0, 2.0]), gain=0.35, lm_damping=1e-5)
        objective = task.compute_qp_objective(self.configuration)
        weighted_jacobian = np.diag(task.cost) @ task.compute_jacobian(None)
        weighted_error = -task.cost * task.gain * task.compute_error(None)
        expected = weighted_jacobian.T @ weighted_jacobian
        expected += 1e-5 * float(weighted_error @ weighted_error) * np.eye(2)
        np.testing.assert_allclose(objective.H, expected)


if __name__ == "__main__":
    unittest.main()
