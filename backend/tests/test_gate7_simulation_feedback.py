from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.gate7_simulation_feedback import (
    DUAL_ARM_JOINT_INDICES,
    Gate7SimulationFeedbackError,
    build_packet,
    parse_packet,
    should_apply,
)


class Gate7SimulationFeedbackTest(unittest.TestCase):
    def _packet(self, state: str = "REGULAR_RETURN") -> bytes:
        return build_packet(
            stream_id="test-stream",
            sequence=7,
            source_time_s=12.5,
            state=state,
            reason="test",
            return_progress=0.4,
            dual_arm_q_rad=[0.01 * index for index in range(14)],
        )

    def test_round_trip_keeps_simulation_boundary_locked(self) -> None:
        payload = self._packet()
        raw = json.loads(payload)
        self.assertTrue(raw["simulation_only"])
        self.assertFalse(raw["hardware_output_authorized"])
        self.assertEqual(list(DUAL_ARM_JOINT_INDICES), raw["dual_arm_joint_indices"])
        parsed = parse_packet(payload)
        self.assertEqual("test-stream", parsed.stream_id)
        self.assertEqual(7, parsed.sequence)
        self.assertEqual("REGULAR_RETURN", parsed.state)

    def test_hardware_authorization_is_rejected(self) -> None:
        raw = json.loads(self._packet())
        raw["hardware_output_authorized"] = True
        with self.assertRaises(Gate7SimulationFeedbackError):
            parse_packet(json.dumps(raw))

    def test_only_fresh_inactive_regular_states_apply(self) -> None:
        regular = parse_packet(self._packet("REGULAR_RETURN"))
        active = parse_packet(self._packet("TRACK_MINK_RIGHT"))
        self.assertTrue(
            should_apply(
                regular,
                command_active=False,
                packet_age_s=0.05,
                timeout_s=0.25,
            )
        )
        self.assertFalse(
            should_apply(
                regular,
                command_active=True,
                packet_age_s=0.05,
                timeout_s=0.25,
            )
        )
        self.assertFalse(
            should_apply(
                regular,
                command_active=False,
                packet_age_s=0.30,
                timeout_s=0.25,
            )
        )
        self.assertFalse(
            should_apply(
                active,
                command_active=False,
                packet_age_s=0.05,
                timeout_s=0.25,
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
