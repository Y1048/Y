"""Static checks for the file-only native excitation-plan adapter."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class PlanAdapterSourceTests(unittest.TestCase):
    def test_adapter_has_no_robot_or_transport_path(self):
        sources = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "sysid_excitation_plan_adapter.hpp",
                "sysid_excitation_plan_check.cpp",
            )
        )
        for forbidden in (
                "unitree", "ChannelPublisher", "LowCmd", "ChannelFactory",
                "socket", "Client", "Write(", "Send("):
            self.assertNotIn(forbidden, sources)

    def test_adapter_requires_nonexecuting_markers(self):
        source = (ROOT / "sysid_excitation_plan_adapter.hpp").read_text(
            encoding="utf-8")
        for required in (
                "command_capable", "execution_authorized",
                "recommended_hardware_gains"):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
