"""Architecture checks for the detached excitation runtime coordinator."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class RuntimeSourceTests(unittest.TestCase):
    def test_runtime_has_no_robot_transport_or_full_body_output(self):
        source = (ROOT / "sysid_excitation_runtime.hpp").read_text(
            encoding="utf-8")
        for forbidden in (
                "unitree", "ChannelPublisher", "LowCmd", "ChannelFactory",
                "socket", "Write(", "Send(", "set_proximal_pd",
                "std::array<double, kJointCount> target"):
            self.assertNotIn(forbidden, source)

    def test_provenance_and_hold_states_are_explicit(self):
        source = (ROOT / "sysid_excitation_runtime.hpp").read_text(
            encoding="utf-8")
        for required in (
                "plan_file_sha256", "request_sha256", "contract_id",
                "termination_owner_status", "episode", "kCompleteHold",
                "kFaultHold"):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
