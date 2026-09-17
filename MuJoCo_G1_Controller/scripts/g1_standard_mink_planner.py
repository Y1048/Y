"""Standard 6D Mink QP behind the shared live planner/trajectory contract.

No hierarchy, virtual-center correction or local detour. Project safety checks
still apply; this is not an unchanged upstream demo or hardware authorization.
"""

import mink
import numpy as np

from g1_mink_feasible_target import FeasiblePlan, FeasibleTargetPlanner, base


class StandardMinkPlanner(FeasibleTargetPlanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wrist_task = mink.FrameTask(
            "right_wrist_yaw_link", "body", base.POSITION_COST,
            base.ORIENTATION_COST, gain=base.FRAME_GAIN,
            lm_damping=base.LM_DAMPING,
        )
        self.posture_task = mink.PostureTask(self.model, cost=base.POSTURE_COST)
        self.standard_tasks = [self.wrist_task, self.posture_task,
                               mink.DampingTask(self.model, cost=base._damping_costs(self.model))]
        self.posture_reference = None

    def ResetDetour(self):
        super().ResetDetour()
        self.posture_reference = None

    def Plan(self, current_q, goal, position_target=None):
        """Full qpos + world wrist-yaw SE3 -> checked look-ahead joint target."""
        self.configuration.update(current_q)
        pose = self.configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        result = FeasiblePlan(current_q.copy(), current_q.copy(),
                              pose.translation().copy(), False, "invalid_start", 0)
        if not self.CheckConfiguration(current_q):
            return result
        if not np.isfinite(goal.as_matrix()).all():
            result.status = "invalid_goal"
            return result
        if position_target is not None and not np.allclose(
                position_target, goal.translation(), atol=1e-10, rtol=0):
            raise ValueError("standard Mink requires a wrist-yaw position target")
        if self.posture_reference is None:
            self.posture_reference = current_q.copy()
            self.posture_task.set_target(self.posture_reference)
        self.wrist_task.set_target(goal)
        result.valid = True
        result.status = "holding"
        for _ in range(self.horizon_steps):
            origin = self.configuration.q.copy()
            velocity = mink.solve_ik(
                self.configuration, self.standard_tasks, base.DT,
                solver=self.solver, damping=base.QP_DAMPING,
                limits=self.limits, constraints=self.constraints,
            )
            if not self._VelocityValid(velocity, self.right_dofs):
                result.status = "invalid_velocity"
                break
            accepted = False
            for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
                self.configuration.update(origin)
                duration = base.DT * fraction
                if not self._PathClear(origin, velocity, duration):
                    continue
                self.configuration.integrate_inplace(velocity, duration)
                candidate = self.configuration.q.copy()
                if result.accepted_steps == 0:
                    result.next_q = candidate.copy()
                result.target_q = candidate
                result.target_position = self.configuration.get_transform_frame_to_world(
                    "right_wrist_yaw_link", "body").translation().copy()
                result.accepted_steps += 1
                result.status = "standard_mink_following"
                accepted = True
                break
            if not accepted:
                self.configuration.update(origin)
                result.status = "collision_hold"
                break
        return result
