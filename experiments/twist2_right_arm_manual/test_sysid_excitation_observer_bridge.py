"""Static checks for the detached excitation-to-observer bridge."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class ObserverBridgeSourceTests(unittest.TestCase):
    def test_bridge_has_no_robot_transport_or_command_write(self):
        source = (ROOT / "sysid_excitation_observer_bridge.hpp").read_text()
        forbidden = (
            "ChannelPublisher",
            "ChannelFactory",
            "MotionSwitcherClient",
            "publisher_->Write",
            "rt/lowcmd",
            "rt/lowstate",
            "motor_cmd()",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_bridge_only_assigns_observer_excitation_tag(self):
        source = (ROOT / "sysid_excitation_observer_bridge.hpp").read_text()
        self.assertIn("frame.excitation = tag", source)
        for field in ("frame.target_q", "frame.command_q", "frame.command_dq",
                      "frame.kp", "frame.kd", "frame.tau_ff"):
            self.assertNotIn(field, source)

    def test_existing_controller_is_not_connected(self):
        controller = (ROOT / "twist2_mink_cycle_trial.cpp").read_text()
        self.assertNotIn("sysid_excitation_observer_bridge.hpp", controller)
        self.assertNotIn("sysid_excitation_runtime.hpp", controller)


if __name__ == "__main__":
    unittest.main()
