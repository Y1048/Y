"""Test-only reconstruction of the limits used by the September 18 fixtures."""
from contextlib import contextmanager
from unittest.mock import patch

import mink
import numpy as np
import g1_bimanual_sim as simulator


RECORDED_ACCELERATION_RAD_S2 = float(np.deg2rad(60.))


@contextmanager
def historical_recording_profile():
    """Keep exact fixture replay independent of the current default profile."""
    with patch.object(simulator, 'JOINT_ACCELERATION_LIMIT_RAD_S2',
                      RECORDED_ACCELERATION_RAD_S2):
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
