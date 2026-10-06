"""Test-only reconstruction of the limits used by the September 18 fixtures."""
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

import mink
import numpy as np
import g1_bimanual_motion_policy as motion_policy
import g1_bimanual_sim as simulator
import g1_mink_shared as base


RECORDED_ACCELERATION_RAD_S2 = float(np.deg2rad(60.))
_CURRENT_PREPARE = motion_policy.ArmMotionPolicy.prepare


def _historical_prepare(self, goal, clearance):
    tasks = _CURRENT_PREPARE(self, goal, clearance)
    # Reconstruct the old single SE(3) FrameTask exactly: position and
    # orientation shared one gain before the current split-task controller.
    self.orientation_task.set_position_cost(base.POSITION_COST)
    tasks = [task for task in tasks if task is not self.position_task]
    error = self.orientation_task.compute_error(self.configuration)
    jacobian = self.orientation_task.compute_jacobian(
        self.configuration)[:, self.dofs]
    correction = np.linalg.lstsq(jacobian, -error, rcond=1e-4)[0]
    rate = min(1., float(np.min(np.sqrt(
        self.acceleration_limits /
        (2. * np.maximum(np.abs(correction), 1e-6))))))
    self.position_approach_rate_s = rate
    self.orientation_approach_rate_s = rate
    self.orientation_task.gain = min(
        base.FRAME_GAIN, self.dt_s * rate)
    self.posture_task.gain = (
        self.orientation_task.gain / base.FRAME_GAIN)
    self.shoulder_comfort_task.gain = self.orientation_task.gain
    return tasks


@contextmanager
def historical_recording_profile():
    """Keep exact fixture replay independent of the current default profile."""
    historical_profile = replace(
        simulator.PROFILE,
        position_tracking_rate_s=1.5,
        orientation_tracking_rate_s=1.5,
        joint_acceleration_limit_rad_s2=RECORDED_ACCELERATION_RAD_S2,
        shoulder_comfort_cost=.6,
        shoulder_comfort_yaw_band_rad=float(np.deg2rad(45.)),
        wrist_priority_proximal_damping_scale=5.0)
    historical_return = replace(
        simulator.RETURN_PROFILE,
        joint_acceleration_limit_rad_s2=RECORDED_ACCELERATION_RAD_S2)
    with patch.object(simulator, 'PROFILE', historical_profile), patch.object(
            simulator, 'RETURN_PROFILE', historical_return), patch.object(
            motion_policy, 'PROFILE', historical_profile), patch.object(
            motion_policy.ArmMotionPolicy, 'prepare', _historical_prepare):
        sim = simulator.BimanualSimulation()
        sim.caps = np.tile(np.deg2rad([90.] * 4 + [180.] * 3), 2)
        velocity_indices = [i for i, limit in enumerate(sim.limits)
                            if isinstance(limit, mink.VelocityLimit)]
        if len(velocity_indices) != 1:
            raise AssertionError('Expected exactly one bilateral velocity limit')
        sim.limits[velocity_indices[0]] = mink.VelocityLimit(
            sim.model, dict(zip(sim.names, sim.caps)))
        for policy in sim.motion.values():
            policy.acceleration_limits[:] = RECORDED_ACCELERATION_RAD_S2
        sim.return_motion.acceleration_limits[:] = RECORDED_ACCELERATION_RAD_S2
        yield sim
