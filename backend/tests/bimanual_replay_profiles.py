"""Test-only reconstruction of the limits used by the September 18 fixtures."""
from contextlib import contextmanager
from unittest.mock import patch

import mink
import numpy as np
import g1_bimanual_motion_policy as motion_policy
import g1_bimanual_sim as simulator
import run_mink_g1_right_arm_prototype as base


RECORDED_ACCELERATION_RAD_S2 = float(np.deg2rad(60.))
_CURRENT_PREPARE = motion_policy.ArmMotionPolicy.prepare


def _historical_prepare(self, goal, clearance):
    tasks = _CURRENT_PREPARE(self, goal, clearance)
    error = self.wrist_task.compute_error(self.configuration)
    jacobian = self.wrist_task.compute_jacobian(self.configuration)[:, self.dofs]
    correction = np.linalg.lstsq(jacobian, -error, rcond=1e-4)[0]
    rate = min(1., float(np.min(np.sqrt(
        self.acceleration_limits /
        (2. * np.maximum(np.abs(correction), 1e-6))))))
    self.approach_rate_s = rate
    self.wrist_task.gain = min(base.FRAME_GAIN, self.dt_s * rate)
    self.posture_task.gain = self.wrist_task.gain / base.FRAME_GAIN
    self.shoulder_comfort_task.gain = self.wrist_task.gain
    return tasks


@contextmanager
def historical_recording_profile():
    """Keep exact fixture replay independent of the current default profile."""
    with patch.object(simulator, 'JOINT_ACCELERATION_LIMIT_RAD_S2',
                      RECORDED_ACCELERATION_RAD_S2), patch.object(
                          motion_policy.ArmMotionPolicy, 'prepare',
                          _historical_prepare):
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
