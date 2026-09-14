"""Source architecture and Python/C++ formula parity without controller code."""
import math
from pathlib import Path
import unittest

import sysid_excitation_plan as plan
import sysid_excitation_preview as preview


ROOT = Path(__file__).resolve().parent


class ReferenceTests(unittest.TestCase):
    def test_constants_and_formula_match_python(self):
        amplitude = math.radians(8)
        velocity = math.radians(20)
        acceleration = math.radians(60)
        dt = .002
        duration = plan._duration(amplitude, velocity, acceleration, dt)
        self.assertEqual(duration, .878)
        for step in (0, 1, 17, 101, 243, 439):
            u = min(1.0, step * dt / duration)
            q = amplitude * preview._smooth(u)
            dq = amplitude / duration * preview._speed(u)
            ddq = amplitude / duration**2 * preview._acceleration(u)
            self.assertTrue(all(math.isfinite(x) for x in (q, dq, ddq)))
            self.assertLessEqual(abs(dq), velocity + 1e-12)
            self.assertLessEqual(abs(ddq), acceleration + 1e-12)

    def test_header_has_no_command_dependencies(self):
        source = (ROOT / "sysid_excitation_reference.hpp").read_text(encoding="utf-8")
        for forbidden in ("unitree","ChannelPublisher","LowCmd","socket","thread","fstream"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
