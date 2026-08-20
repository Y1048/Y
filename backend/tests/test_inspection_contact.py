from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.inspection_contact import (  # noqa: E402
    InspectionContactState,
    InspectionContactStateMachine,
)


class InspectionContactStateMachineTest(unittest.TestCase):
    def test_disabled_machine_never_changes_runtime_behavior(self):
        machine = InspectionContactStateMachine(enabled=False, approach_distance_m=0.015)
        transition = machine.update(task_contact_active=True, surface_follow_requested=True)
        self.assertEqual(transition.current, InspectionContactState.FREE_SPACE)
        self.assertEqual(transition.reason, "disabled")

    def test_approach_state_is_observational(self):
        machine = InspectionContactStateMachine(enabled=True, approach_distance_m=0.015)
        transition = machine.update(
            task_contact_active=False,
            tool_target_distance_m=0.010,
            now_s=1.0,
        )
        self.assertEqual(transition.current, InspectionContactState.APPROACH)

    def test_contact_can_be_confirmed_without_motion_command(self):
        machine = InspectionContactStateMachine(
            enabled=True,
            approach_distance_m=0.015,
            contact_confirm_s=0.1,
        )
        first = machine.update(task_contact_active=True, now_s=1.0)
        second = machine.update(task_contact_active=True, now_s=1.11)
        self.assertEqual(first.current, InspectionContactState.CONTACT_ACQUIRE)
        self.assertEqual(second.current, InspectionContactState.INSPECTION_CONTACT)

    def test_surface_follow_requires_explicit_request(self):
        machine = InspectionContactStateMachine(enabled=True, approach_distance_m=0.015)
        contact = machine.update(task_contact_active=True, now_s=1.0)
        follow = machine.update(
            task_contact_active=True,
            surface_follow_requested=True,
            now_s=1.1,
        )
        self.assertEqual(contact.current, InspectionContactState.INSPECTION_CONTACT)
        self.assertEqual(follow.current, InspectionContactState.SURFACE_FOLLOW)

    def test_retract_is_explicit(self):
        machine = InspectionContactStateMachine(enabled=True, approach_distance_m=0.015)
        transition = machine.update(
            task_contact_active=False,
            retract_requested=True,
            now_s=1.0,
        )
        self.assertEqual(transition.current, InspectionContactState.RETRACT)


if __name__ == "__main__":
    unittest.main()
