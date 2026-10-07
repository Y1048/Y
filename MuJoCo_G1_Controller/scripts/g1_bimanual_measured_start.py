"""Engagement-only measured initialization. No sockets or continuous feedback.

The v5 Unity owner supplies validated LowState snapshots. Receipt age is the
bridge's excess-delay estimate plus local elapsed time, NOT synchronized age.
The inactive model may be reseeded; tracking/returning commands may never be.
"""
import math

import mink
import mujoco
import numpy as np

JOINT_NAMES = tuple(
    side + '_' + joint
    for side in ('left', 'right')
    for joint in ('hip_pitch', 'hip_roll', 'hip_yaw', 'knee',
                  'ankle_pitch', 'ankle_roll')
) + ('waist_yaw', 'waist_roll', 'waist_pitch') + tuple(
    side + '_' + joint
    for side in ('left', 'right')
    for joint in ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw',
                  'elbow', 'wrist_roll', 'wrist_pitch', 'wrist_yaw'))
MAX_AGE_S = .10
SETTLE_S = .35
MAX_SAMPLE_GAP_S = .10
# The recorded stationary knee dq reaches .075 rad/s while q spans only
# .0123 degrees. Keep a .1 rad/s instantaneous guard AND the .005 rad
# whole-pose drift limit over .35 s; do not add a command/input filter.
STATIONARY_SPEED_RAD_S = .10
MAX_DRIFT_RAD = .005


def validate_snapshot(value):
    """Validate format without clipping positions or inventing fresh samples."""
    if value is None:
        return
    if (not isinstance(value, dict)
            or value.get('schema') != 'g1.lowstate.view.v1'
            or value.get('crc_valid') is not True
            or not isinstance(value.get('joint_names'), list)
            or tuple(value['joint_names']) != JOINT_NAMES):
        raise ValueError('measured_start_contract')
    if (not isinstance(value.get('session'), str)
            or not 1 <= len(value['session']) <= 64
            or type(value.get('sequence')) is not int
            or not 0 <= value['sequence'] <= 2**53 - 1):
        raise ValueError('measured_start_identity')
    for key in ('source_monotonic_s', 'receipt_age_s'):
        if (type(value.get(key)) not in (int, float)
                or not math.isfinite(value[key]) or value[key] < 0):
            raise ValueError('measured_start_' + key)
    for key in ('q_rad', 'dq_rad_s'):
        a = value.get(key)
        if (not isinstance(a, list) or len(a) != 29
                or any(type(x) not in (int, float) or not math.isfinite(x)
                       for x in a)):
            raise ValueError('measured_start_' + key)


def initialize_inactive_model(sim, positions):
    """Adopt one stationary joint snapshot atomically before activation.

    Keep authored arm home/waypoint, prescribed base and all motion limits.
    The 15 uncontrolled joints are frozen at this snapshot for this cycle.
    This does not publish an active command or certify the physical stop.
    """
    if (sim.state != 'ready' or np.any(np.abs(sim.velocity) > 1e-9)
            or np.any(np.abs(sim.acceleration) > 1e-8)):
        raise ValueError('command_not_at_rest')
    positions = np.asarray(positions, dtype=float)
    if positions.shape != (29,) or not np.isfinite(positions).all():
        raise ValueError('measured_start_positions')
    joints = [mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_JOINT,
                              name + '_joint') for name in JOINT_NAMES]
    if min(joints) < 0 or len(set(joints)) != 29:
        raise ValueError('measured_start_model_contract')
    ids = sim.model.jnt_qposadr[joints]
    limits = sim.model.jnt_range[joints]
    if np.any(positions < limits[:, 0]) or np.any(positions > limits[:, 1]):
        raise ValueError('measured_start_joint_range')
    candidate = sim.config.q.copy()
    candidate[ids] = positions
    home = sim.home.copy()
    home[ids[:15]] = positions[:15]
    waypoint = home.copy()
    waypoint[sim.qids] = sim.return_motion.waypoint
    for name, q in (('pose', candidate), ('home', home), ('waypoint', waypoint)):
        clearance = sim.clearance(q)
        if not np.isfinite(clearance) or clearance < sim.clearance_m:
            raise ValueError('measured_start_' + name + '_clearance')
    # Evaluate authored home FK in the original base frame, before committing.
    home_zero_yaw = home.copy()
    a = sim.base_qadr
    home_zero_yaw[a:a+7] = sim.initial_base_pose
    scratch = mink.Configuration(sim.model)
    scratch.update(home_zero_yaw)
    home_targets = {s: scratch.get_transform_frame_to_world(
        s + '_wrist_yaw_link', 'body') for s in ('left', 'right')}
    sim.home[:] = home
    sim.home_targets = home_targets
    sim.config.update(candidate)
    sim.velocity[:] = 0.
    sim.acceleration[:] = 0.
    sim.brake_plan = [(candidate.copy(), sim.velocity.copy()) for _ in range(2)]
    sim.return_motion.reset()
    sim._motion_returning = False
    for policy in sim.motion.values():
        policy.reset(candidate)
    sim.last_solver_error = None
    sim.reason = ''


class MeasuredStartGate:
    """One acknowledged seed per stable idle pose; fail closed before engage."""
    def __init__(self):
        self.revision = 0
        self.announced_revision = 0
        self.latest = None
        self.latest_at = None
        self.deadline = float('-inf')
        self.retired = set()
        self.seed = None
        self.body = None
        self.seed_session = None
        self.invalidate('waiting_measurement')

    def invalidate(self, reason):
        self.ready = False
        self.reason = reason
        self.anchor = None
        self.stable_at = None
        self.stable_source = None
        self.sample_count = 0

    def fresh(self, now):
        return (self.latest_at is not None and self.latest_at <= now
                and now <= self.deadline)

    def status(self, now):
        ready = self.ready and self.fresh(now)
        return dict(ready=ready, revision=self.revision,
                    reason=self.reason if self.fresh(now) else 'waiting_fresh_measurement',
                    session=self.seed_session,
                    body_q_rad=None if self.body is None else self.body.tolist())

    def observe(self, sample, now, sim, *, allow_initialize, aligned):
        validate_snapshot(sample)
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError('measured_start_local_clock')
        if sample is None or not aligned:
            self.invalidate('waiting_measurement' if sample is None else 'waiting_head_alignment')
            return
        if sample['receipt_age_s'] > MAX_AGE_S:
            self.invalidate('measurement_too_old')
            return
        if sample['session'] in self.retired:
            self.invalidate('retired_measurement_session')
            return
        previous = self.latest
        if previous is not None and sample['session'] != previous['session']:
            self.retired.add(previous['session'])
            self.invalidate('measurement_session_changed')
            previous = None
        if previous is not None:
            if (sample['sequence'] < previous['sequence']
                    or sample['source_monotonic_s'] < previous['source_monotonic_s']):
                self.invalidate('measurement_order')
                return
            if sample['sequence'] == previous['sequence']:
                # Repeated Unity packets are not new LowState observations.
                keys = ('source_monotonic_s', 'q_rad', 'dq_rad_s')
                if any(sample[k] != previous[k] for k in keys):
                    self.invalidate('measurement_duplicate_changed')
                self.deadline = min(self.deadline, now + MAX_AGE_S - sample['receipt_age_s'])
                if not self.fresh(now):
                    self.invalidate('measurement_stale')
                return
            source_gap = sample['source_monotonic_s'] - previous['source_monotonic_s']
            if source_gap <= 0:
                self.invalidate('measurement_order')
                return
            if (source_gap > MAX_SAMPLE_GAP_S
                    or now - self.latest_at > MAX_SAMPLE_GAP_S or now < self.latest_at):
                self.invalidate('measurement_gap')
        # Copy values so callers cannot change an acknowledged seed via aliasing.
        self.latest = dict(sample, q_rad=list(sample['q_rad']), dq_rad_s=list(sample['dq_rad_s']))
        self.latest_at = now
        self.deadline = now + MAX_AGE_S - sample['receipt_age_s']
        q = np.asarray(sample['q_rad'], dtype=float)
        if np.max(np.abs(sample['dq_rad_s'])) > STATIONARY_SPEED_RAD_S:
            self.invalidate('robot_not_stationary')
            return
        if self.ready:
            if (sample['session'] == self.seed_session
                    and np.max(np.abs(q - self.seed)) <= MAX_DRIFT_RAD):
                return
            self.invalidate('measured_pose_changed')
        if self.anchor is None or np.max(np.abs(q - self.anchor)) > MAX_DRIFT_RAD:
            self.anchor = q.copy()
            self.stable_at = now
            self.stable_source = sample['source_monotonic_s']
            self.sample_count = 0
        self.sample_count += 1
        self.reason = 'settling_measurement'
        if (not allow_initialize or self.sample_count < 3
                or now - self.stable_at < SETTLE_S
                or sample['source_monotonic_s'] - self.stable_source < SETTLE_S):
            return
        try:
            initialize_inactive_model(sim, q)
        except ValueError as error:
            self.invalidate(str(error))
            return
        self.seed = q.copy()
        self.body = q[:15].copy()
        self.seed_session = sample['session']
        self.revision += 1
        self.ready, self.reason = True, 'synchronized'

    def can_engage(self, now, revision):
        return (self.ready and self.fresh(now)
                and revision == self.revision == self.announced_revision)
