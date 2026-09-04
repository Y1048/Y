from __future__ import annotations

import json
import unittest
from pathlib import Path

from g1_mink_command_provenance import (
    LIVE_MINK_PROVENANCE,
    mark_live_mink_packet,
    wrap_state_packet_factory,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]


class MinkCommandProvenanceTests(unittest.TestCase):
    def test_live_packet_marker_is_explicit(self) -> None:
        packet = {"schema": "g1.mink.right_arm.state.v1"}
        result = mark_live_mink_packet(packet)
        self.assertIs(packet, result)
        self.assertEqual(LIVE_MINK_PROVENANCE, result["command_provenance"])

    def test_marker_refuses_to_upgrade_replay(self) -> None:
        with self.assertRaisesRegex(ValueError, "relabel"):
            mark_live_mink_packet(
                {
                    "schema": "g1.mink.right_arm.state.v1",
                    "command_provenance": "recorded_replay",
                }
            )

    def test_factory_wrapper_marks_every_new_packet(self) -> None:
        def factory(sequence: int):
            return {
                "schema": "g1.mink.right_arm.state.v1",
                "sequence": sequence,
            }

        wrapped = wrap_state_packet_factory(factory)
        packet = wrapped(7)
        self.assertEqual(7, packet["sequence"])
        self.assertEqual(LIVE_MINK_PROVENANCE, packet["command_provenance"])

    def test_supported_live_entrypoints_install_marker(self) -> None:
        virtual_source = (
            HERE / "run_mink_g1_right_arm_virtual_center_live_entry.py"
        ).read_text(encoding="utf-8")
        baseline_source = (
            HERE / "run_mink_g1_right_arm_prototype_entry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("wrap_state_packet_factory", virtual_source)
        self.assertIn("base._state_packet", virtual_source)
        self.assertIn("wrap_state_packet_factory", baseline_source)
        self.assertIn("controller._state_packet", baseline_source)

    def test_root_launcher_uses_provenance_entrypoints(self) -> None:
        launcher = (PROJECT_ROOT / "START_VR_HAND_TO_MUJOCO.bat").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "run_mink_g1_right_arm_virtual_center_live_entry.py",
            launcher,
        )
        self.assertIn("run_mink_g1_right_arm_prototype_entry.py", launcher)
        self.assertNotIn(
            'set "MUJOCO_SCRIPT=%CONTROLLER_ROOT%\\scripts\\run_mink_g1_right_arm_virtual_center_live.py"',
            launcher,
        )
        self.assertIn('set "COLLISION_PROFILE=mink-default"', launcher)
        self.assertIn(
            'if /I "%~1"=="--mink-default" set "COLLISION_PROFILE=mink-default"',
            launcher,
        )
        self.assertIn(
            'if /I "%DISPLAY_MODE%"=="hardware" set "COLLISION_PROFILE=hardware-guarded"',
            launcher,
        )

        hardware_launcher = (
            PROJECT_ROOT / "tools" / "START_G1_GATE7_LIVE_HARDWARE.bat"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'START_VR_HAND_TO_MUJOCO.bat" --hardware-display',
            hardware_launcher,
        )

    def test_relay_requires_explicit_live_marker(self) -> None:
        guard = (
            PROJECT_ROOT
            / "hardware"
            / "g1_arm_bridge"
            / "gate7_relay_provenance_guard.py"
        ).read_text(encoding="utf-8")
        self.assertIn("live_mink_provenance_required", guard)
        self.assertNotIn("missing field is accepted", guard)


if __name__ == "__main__":
    unittest.main(verbosity=2)
