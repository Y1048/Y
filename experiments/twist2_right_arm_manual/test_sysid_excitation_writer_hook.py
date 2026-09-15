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

    def test_physical_controller_source_is_not_modified_in_this_step(self):
        source = ROOT / "twist2_mink_cycle_trial.cpp"
        self.assertEqual(
            __import__("hashlib").sha256(source.read_bytes()).hexdigest(),
            "aa38a2e7d7e1686493b9c535ee2d13636856025f1a67928ef4c9290da5e01359",
        )


if __name__ == "__main__":
    unittest.main()
