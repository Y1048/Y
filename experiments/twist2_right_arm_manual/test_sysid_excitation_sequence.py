"""Static boundary checks for the offline-only native sequence core."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class SequenceSourceTests(unittest.TestCase):
    def test_sequence_has_no_robot_or_transport_dependency(self):
        source = (ROOT / "sysid_excitation_sequence.hpp").read_text(encoding="utf-8")
        for forbidden in (
                "unitree", "ChannelPublisher", "LowCmd", "ChannelFactory",
                "socket", "Client", "Write(", "Send("):
            self.assertNotIn(forbidden, source)

    def test_sequence_exposes_exact_joint_shape(self):
        source = (ROOT / "sysid_excitation_sequence.hpp").read_text(encoding="utf-8")
        self.assertIn("kJointCount = 29", source)
        self.assertIn("kRightArmFirst = 22", source)
        self.assertIn("kRightArmLast = 28", source)


if __name__ == "__main__":
    unittest.main()
