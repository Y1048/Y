"""Staged joint-home return for the fixed-base bimanual simulation only.

Use the established right-arm waypoint and Ruckig profile on both arms. Every
published segment still needs the shared bilateral geometry and stopping-tail
checks. This is neither a global motion planner nor a physical braking model.
"""
import numpy as np
import mujoco
import run_mink_g1_right_arm_prototype as base
from g1_mink_return_cycle import SAFE_RIGHT_ARM_RAD
from g1_virtual_center_tasks import JOINT_MAX_JERK_RAD_S3
from g1_mink_trajectory import RuckigJointMotionLimiter
from g1_bimanual_limits import JOINT_ACCELERATION_LIMIT_RAD_S2


class BimanualReturnMotion:
    policy = 'bimanual_staged_return_v2'
    settle_s = .5
    maximum_duration_s = 30.
    maximum_replans = 2
    near_hands_threshold_m = .012
    separation_probe_maximum_s = 10.

    def __init__(self, simulation):
        self.sim = simulation
        # Mirror the original seven-joint intermediate pose, not a new pose.
        mirrored = SAFE_RIGHT_ARM_RAD * np.array([1., -1., -1., 1., -1., 1., -1.])
        self.waypoint = np.r_[mirrored, SAFE_RIGHT_ARM_RAD].copy()
        self.acceleration_limits = np.full(14, JOINT_ACCELERATION_LIMIT_RAD_S2)
        self.jerk_limits = np.full(14, JOINT_MAX_JERK_RAD_S3)
        left_pairs = {tuple(map(int, pair)) for pair in simulation.policy_pairs['left']}
        right_pairs = {tuple(map(int, pair)) for pair in simulation.policy_pairs['right']}
        self.inter_arm_pairs = [tuple(map(int, pair)) for pair in simulation.pairs
                                if tuple(map(int, pair)) in left_pairs
                                and tuple(map(int, pair)) in right_pairs]
        if not self.inter_arm_pairs:
            raise ValueError('missing inter-arm return collision pairs')
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
        self.near_hands_recovery = False
        self.return_start_clearance_m = None
        self.near_hands_start_clearance_m = None
        self.separation_side = ''
        self.separation_target = None
        self.separation_probe_clearance_m = {}
        self.tried_separation_sides = []
        self.retry_separation_after_stop = False

    def diagnostics(self):
        return dict(policy=self.policy, stage=self.stage,
                    elapsed_simulation_s=self.elapsed_ticks*self.sim.dt,
                    settle_elapsed_s=self.settled_ticks*self.sim.dt,
                    replans=self.replans, recovering_checked_tail=self.recovering,
                    rejected_reason=self.rejected_reason,
                    fault_reason=self.fault_reason,
                    near_hands_recovery=self.near_hands_recovery,
                    return_start_clearance_m=self.return_start_clearance_m,
                    near_hands_start_clearance_m=self.near_hands_start_clearance_m,
                    separation_side=self.separation_side,
                    separation_probe_clearance_m=dict(self.separation_probe_clearance_m))

    def _target(self):
        if self.stage.startswith('separate_'):
            return self.separation_target
        return self.waypoint if self.stage == 'safe_waypoint' else self.sim.home[self.sim.qids]

    def _inter_arm_clearance(self, q):
        s = self.sim
        s.check_data.qpos[:] = q
        mujoco.mj_forward(s.model, s.check_data)
        nearest = base._nearest_pair_distance(
            s.model, s.check_data, self.inter_arm_pairs)
        return .2 if nearest is None else nearest[0]

    def _separation_target_for(self, side):
        if side not in ('left', 'right'):
            raise ValueError('unknown separation side')
        target = self.sim.config.q[self.sim.qids].copy()
        selection = slice(0, 7) if side == 'left' else slice(7, 14)
        target[selection] = self.waypoint[selection]
        return target

    def _probe_separation_side(self, side):
        s = self.sim
        target = self._separation_target_for(side)
        limiter = RuckigJointMotionLimiter(
            s.config.q[s.qids], s.caps, self.acceleration_limits,
            self.jerk_limits, s.dt,
            initial_velocity_rad_s=s.velocity[s.dofs],
            initial_acceleration_rad_s2=np.clip(
                s.acceleration[s.dofs], -self.acceleration_limits, self.acceleration_limits))
        base_q = s.config.q.copy()
        minimum = s.clearance(base_q, threshold=s.clearance_m)
        if not np.isfinite(minimum):
            return float('nan')
        max_ticks = int(np.ceil(self.separation_probe_maximum_s / s.dt))
        try:
            for _ in range(max_ticks):
                proposed = np.asarray(limiter.Step(target, s.dt))
                if not np.isfinite(proposed).all():
                    return float('nan')
                # This is route selection only. Published motion is still
                # checked by checked_stop_plan with its 0.25-degree substeps.
                q = base_q.copy()
                q[s.qids] = proposed
                clearance = s.clearance(q, threshold=s.clearance_m)
                if not np.isfinite(clearance):
                    return float('nan')
                minimum = min(minimum, clearance)
                if minimum < s.clearance_m:
                    return minimum
                if (np.max(np.abs(proposed-target)) < 1e-6
                        and np.max(np.abs(np.asarray(limiter.velocity_rad_s))) < 1e-6):
                    return minimum
        except RuntimeError:
            return float('nan')
        return float('nan')

    def _choose_separation_side(self):
        available = [side for side in ('left', 'right')
                     if side not in self.tried_separation_sides]
        current = self.sim.config.q[self.sim.qids]
        available.sort(key=lambda side: float(np.max(np.abs(
            self._separation_target_for(side)-current))))
        for side in available:
            minimum = self._probe_separation_side(side)
            self.separation_probe_clearance_m[side] = float(minimum)
            if np.isfinite(minimum) and minimum >= self.sim.clearance_m:
                return side
        return None

    def _begin_separation(self):
        side = self._choose_separation_side()
        if side is None:
            self.fault_reason = 'return_path_blocked:near_hands_no_separation_route'
            self.stage = 'fault'
            self.sim.state, self.sim.reason = 'blocked', self.fault_reason
            return False
        self.separation_side = side
        self.tried_separation_sides.append(side)
        self.separation_target = self._separation_target_for(side)
        self.stage = 'separate_' + side
        self.limiter = None
        self.rejected_reason = ''
        self.sim.reason = ''
        return True

    def _step_near_hands_stop(self):
        s = self.sim
        if np.any(s.velocity):
            if not s.brake('return_near_hands_stop', returning=True):
                return False
            if np.any(s.velocity):
                return True
        return self._begin_separation()

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
            # The first zero-velocity command still has braking acceleration.
            # Consume one checked stationary sample before seeding Ruckig again,
            # otherwise that acceleration can push a joint outward from rest.
            if np.any(s.acceleration[s.dofs]):
                return True
            self.recovering = False
            self.limiter = None
            if self.retry_separation_after_stop:
                self.retry_separation_after_stop = False
                self.stage = 'near_hands_stop'
        return True

    def _reject(self, reason):
        self.rejected_reason = reason
        self.replans += 1
        self.limiter = None
        self.recovering = True
        if self.stage.startswith('separate_') and reason == 'return_swept_clearance':
            self.retry_separation_after_stop = True
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
            for target in (self.waypoint, s.home[s.qids]):
                q = s.home.copy()
                q[s.qids] = target
                clearance = s.clearance(q)
                if (not np.isfinite(clearance) or clearance < s.clearance_m
                        or np.any(target < s.ranges[:, 0])
                        or np.any(target > s.ranges[:, 1])):
                    self.fault_reason = 'invalid_return_waypoint'
                    return self._stop()
            start_clearance = s.clearance(s.config.q)
            if not np.isfinite(start_clearance) or start_clearance < s.clearance_m:
                self.fault_reason = 'invalid_return_start_clearance'
                return self._stop()
            inter_arm_clearance = self._inter_arm_clearance(s.config.q)
            if not np.isfinite(inter_arm_clearance):
                self.fault_reason = 'invalid_return_inter_arm_clearance'
                return self._stop()
            self.return_start_clearance_m = float(start_clearance)
            self.near_hands_start_clearance_m = float(inter_arm_clearance)
            if inter_arm_clearance < self.near_hands_threshold_m:
                self.near_hands_recovery = True
                self.stage = 'near_hands_stop'
            else:
                self.stage = 'safe_waypoint'
        if self.stage == 'near_hands_stop':
            return self._step_near_hands_stop()
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
        if reached and self.stage.startswith('separate_'):
            self.stage = 'safe_waypoint'
            self.limiter = None
            self.replans = 0
            self.rejected_reason = ''
        elif reached and self.stage == 'safe_waypoint':
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
