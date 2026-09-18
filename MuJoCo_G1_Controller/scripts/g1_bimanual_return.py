"""Staged joint-home return for the fixed-base bimanual simulation only.

Use the established right-arm waypoint and Ruckig profile on both arms. Every
published segment still needs the shared bilateral geometry and stopping-tail
checks. This is neither a global motion planner nor a physical braking model.
"""
import numpy as np
from g1_mink_return_cycle import SAFE_RIGHT_ARM_RAD
from g1_virtual_center_tasks import JOINT_MAX_JERK_RAD_S3
from g1_mink_trajectory import RuckigJointMotionLimiter


class BimanualReturnMotion:
    policy = 'bimanual_staged_return_v1'
    settle_s = .5
    maximum_duration_s = 30.
    maximum_replans = 2

    def __init__(self, simulation):
        self.sim = simulation
        # Mirror the original seven-joint intermediate pose, not a new pose.
        mirrored = SAFE_RIGHT_ARM_RAD * np.array([1., -1., -1., 1., -1., 1., -1.])
        self.waypoint = np.r_[mirrored, SAFE_RIGHT_ARM_RAD].copy()
        self.acceleration_limits = np.full(14, np.deg2rad(60.))
        self.jerk_limits = np.full(14, JOINT_MAX_JERK_RAD_S3)
        self.reset()

    def reset(self):
        self.stage = 'inactive'
        self.elapsed_ticks = 0
        self.settled_ticks = 0
        self.replans = 0
        self.rejected_reason = ''
        self.fault_reason = ''
        self.recovering = False
        self.limiter = None

    def diagnostics(self):
        return dict(policy=self.policy, stage=self.stage,
                    elapsed_simulation_s=self.elapsed_ticks*self.sim.dt,
                    settle_elapsed_s=self.settled_ticks*self.sim.dt,
                    replans=self.replans, recovering_checked_tail=self.recovering,
                    rejected_reason=self.rejected_reason,
                    fault_reason=self.fault_reason)

    def _target(self):
        return self.waypoint if self.stage == 'safe_waypoint' else self.sim.home[self.sim.qids]

    def _make_limiter(self):
        s = self.sim
        self.limiter = RuckigJointMotionLimiter(
            s.config.q[s.qids], s.caps, self.acceleration_limits,
            self.jerk_limits, s.dt,
            initial_velocity_rad_s=s.velocity[s.dofs],
            initial_acceleration_rad_s2=np.clip(
                s.acceleration[s.dofs], -self.acceleration_limits, self.acceleration_limits))

    def _stop(self):
        s = self.sim
        # Keep the prevalidated tail. Never freeze q or zero velocity at speed.
        if not s.brake(self.fault_reason or self.rejected_reason, returning=True):
            return False
        if not np.any(s.velocity):
            if self.fault_reason:
                self.stage = 'fault'
                s.state, s.reason = 'blocked', self.fault_reason
                return False
            self.recovering = False
            self.limiter = None
        return True

    def _reject(self, reason):
        self.rejected_reason = reason
        self.replans += 1
        self.limiter = None
        self.recovering = True
        if self.replans > self.maximum_replans:
            self.fault_reason = 'return_path_blocked:' + reason
        return self._stop()

    def step(self):
        s = self.sim
        if self.stage == 'complete':
            # Repeated return calls after completion must not start another trip.
            s.state = 'ready'
            return True
        self.elapsed_ticks += 1
        if self.elapsed_ticks*s.dt > self.maximum_duration_s:
            self.fault_reason = 'return_timeout'
        if self.fault_reason or self.recovering:
            return self._stop()
        if self.stage == 'inactive':
            self.stage = 'safe_waypoint'
            for target in (self.waypoint, s.home[s.qids]):
                q = s.home.copy()
                q[s.qids] = target
                clearance = s.clearance(q)
                if (not np.isfinite(clearance) or clearance < s.clearance_m
                        or np.any(target < s.ranges[:, 0])
                        or np.any(target > s.ranges[:, 1])):
                    self.fault_reason = 'invalid_return_waypoint'
                    return self._stop()
        if self.limiter is None:
            self._make_limiter()
        try:
            target = self._target()
            proposed = np.asarray(self.limiter.Step(target, s.dt))
        except RuntimeError as error:
            return self._reject('return_trajectory_error:' + str(error)[:160])
        # Store interval-average velocity, which is exactly the published q
        # difference / dt, rather than Ruckig's instantaneous endpoint velocity.
        displacement = proposed - s.config.q[s.qids]
        if (np.max(np.abs(displacement)) < 1e-12
                and np.max(np.abs(self.limiter.velocity_rad_s)) < 1e-9):
            displacement = np.zeros_like(displacement)  # Only roundoff at rest.
        velocity = np.zeros(s.model.nv)
        velocity[s.dofs] = displacement/s.dt
        plan, reason = s.checked_stop_plan(velocity)
        if plan is None:
            return self._reject('return_' + reason)
        candidate, velocity = plan.pop(0)
        s.brake_plan = plan
        s.reason = ''
        s.last_solver_error = None
        s._apply_command(candidate, velocity, returning=True)
        reached = (np.max(np.abs(candidate[s.qids]-target)) < 1e-6
                   and not np.any(velocity)
                   and np.max(np.abs(self.limiter.velocity_rad_s)) < 1e-6)
        if reached and self.stage == 'safe_waypoint':
            self.stage = 'home'
            self.limiter = None
            self.replans = 0
        elif reached:
            self.settled_ticks += 1
            if self.settled_ticks*s.dt >= self.settle_s:
                self.stage = 'complete'
                s.state = 'ready'
        else:
            self.settled_ticks = 0
        return True
