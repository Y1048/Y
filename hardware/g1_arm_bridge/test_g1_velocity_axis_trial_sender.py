import unittest

from .g1_velocity_axis_trial_sender import velocity_for


class AxisTrialSenderTests(unittest.TestCase):
    def test_axis_mapping(self):
        self.assertEqual(velocity_for("vx", 0.05), (0.05, 0.0, 0.0))
        self.assertEqual(velocity_for("vy", -0.05), (0.0, -0.05, 0.0))
        self.assertEqual(velocity_for("yaw", 0.05), (0.0, 0.0, 0.05))


if __name__ == "__main__":
    unittest.main()
