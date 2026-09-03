from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.command_adapter import InternalCommand  # noqa: E402
from g1_teleop.runtime_state import TeleopRuntimeStateMachine  # noqa: E402


def command(mode: str, valid: bool = False) -> InternalCommand:
    return InternalCommand(
        session_id="session-a",
        sequence=1,
        mode=mode,
        valid=valid,
        position_m=np.zeros(3),
        quaternion_xyzw=np.array([0.0, 0.0, 0.0, 1.0]),
        source_time_ns=None,
        frame_id="test",
        protocol="test",
    )


class RuntimeArchitectureTest(unittest.TestCase):
    def test_active_hold_active_transition(self):
        machine = TeleopRuntimeStateMachine()
        self.assertEqual(machine.apply(command("active", True)).current, "active")
        self.assertEqual(machine.apply(command("hold", False)).current, "hold")
        self.assertEqual(machine.apply(command("active", True)).current, "active")

    def test_workspace_fault_requires_acknowledgement(self):
        machine = TeleopRuntimeStateMachine()
        machine.apply(command("active", True))
        machine.trip_workspace_fault()

        self.assertEqual(machine.apply(command("active", True)).current, "workspace_fault")
        machine.acknowledge_workspace_reset()
        self.assertEqual(machine.apply(command("active", True)).current, "active")

    def test_workspace_exit_packet_arms_reengagement(self):
        machine = TeleopRuntimeStateMachine()
        transition = machine.apply(command("workspace_exit", False))
        self.assertEqual(transition.current, "workspace_fault")
        self.assertTrue(machine.workspace_reset_armed)
        self.assertEqual(machine.apply(command("active", True)).current, "active")

    def test_shutdown_is_terminal(self):
        machine = TeleopRuntimeStateMachine()
        self.assertEqual(machine.apply(command("shutdown", False)).current, "shutdown")
        self.assertEqual(machine.apply(command("active", True)).current, "shutdown")


if __name__ == "__main__":
    unittest.main()
