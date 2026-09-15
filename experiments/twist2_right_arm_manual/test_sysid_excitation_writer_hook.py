"""Architecture checks for the detached 500-Hz writer-hook candidate."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class WriterHookSourceTests(unittest.TestCase):
    def test_hook_has_no_robot_transport_or_gain_mutation_path(self):
        source = (ROOT / "sysid_excitation_writer_hook.hpp").read_text(
            encoding="utf-8")
        for forbidden in (
                "unitree", "ChannelPublisher", "LowCmd", "ChannelFactory",
                "socket", "Write(", "Send(", "set_proximal_pd"):
            self.assertNotIn(forbidden, source)

    def test_controller_seam_is_dormant_without_a_caller(self):
        source = (ROOT / "twist2_mink_cycle_trial.cpp").read_text()
        self.assertEqual(
            source.count("install_sysid_excitation_for_review("), 1)
        self.assertNotIn("--sysid-excitation", source)
        self.assertIn(
            'context.termination_owner_status != "reviewed"', source
        )
        self.assertIn('G1_SYSID_CAPTURE_V2', source)


if __name__ == "__main__":
    unittest.main()
