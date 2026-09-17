import unittest

from upper_body_conditioned_env import recorded_scale_at_step


class RecordedCurriculumTest(unittest.TestCase):
    def test_linear_ramp_and_clamp(self):
        self.assertEqual(recorded_scale_at_step(0, 0.25, 1.0, 100), 0.25)
        self.assertAlmostEqual(recorded_scale_at_step(50, 0.25, 1.0, 100), 0.625)
        self.assertEqual(recorded_scale_at_step(200, 0.25, 1.0, 100), 1.0)

    def test_zero_ramp_uses_end(self):
        self.assertEqual(recorded_scale_at_step(0, 1.0, 1.0, 0), 1.0)

    def test_invalid_range_fails_closed(self):
        with self.assertRaises(ValueError):
            recorded_scale_at_step(0, 0.8, 0.2, 100)


if __name__ == "__main__":
    unittest.main()
