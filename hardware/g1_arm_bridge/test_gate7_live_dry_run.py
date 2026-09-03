#!/usr/bin/env python3
"""Gate 7 live dry-run core tests; no socket, SDK, DDS or publisher."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from arm_sdk_hold_contract import DUAL_ARM_INDICES
from arm_sdk_teleop_contract import (
    load_gate7_config,
    load_regular_arm_pose,
    parse_mink_arm_sample,
)
from g1_joint_contract import G1_29_JOINT_NAMES
from gate7_live_dry_run import Gate7LiveDryRunSession
from ruckig_gate7_controller import RuckigGate7TeleopController

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"


def _replace_dual(all_q, dual_q):
    result = list(all_q)
    for index, value in zip(DUAL_ARM_INDICES, dual_q):
        result[index] = value
    return tuple(result)


def _sample(
    regular,
    sequence,
    mode,
    *,
    right_offset_deg=0.0,
    collision_limited=False,
    minimum_clearance_m=0.040,
):
    dual = list(regular.dual_arm_q_rad)
    dual[7] += math.radians(right_offset_deg)
    all_q = _replace_dual(regular.reference_all_joint_q_rad, dual)
    active = mode == "active"
    return parse_mink_arm_sample(
        json.dumps(
            {
                "schema": "g1.mink.right_arm.state.v1",
                "sequence": sequence,
                "state_source": "mink_simulation",
                "all_joint_names": list(G1_29_JOINT_NAMES),
                "all_joint_q_rad": list(all_q),
                "right_arm": {
                    "joints": list(all_q[22:29]),
                    "active": active,
                    "workspace_limited": False,
                    "collision_limited": collision_limited,
                    "minimum_clearance_m": minimum_clearance_m,
                    "nearest_collision_geoms": ["test_geom_a", "test_geom_b"],
                    "nearest_collision_bodies": ["test_body_a", "test_body_b"],
                    "command_state": "active" if active else "idle",
                },
                "input_command_mode": mode,
                "session_id": "live-dry-run-test",
                "input_packet_age_s": 0.0,
                "timestamp": 1.0,
            }
        )
    )


class Gate7LiveDryRunTests(unittest.TestCase):
    def setUp(self):
        self.config = load_gate7_config(CONFIG_PATH)
        self.regular = load_regular_arm_pose(REGULAR_PATH)
        self.measured = _replace_dual(
            self.regular.reference_all_joint_q_rad,
            self.regular.dual_arm_q_rad,
        )

    def _session(self, source="mink"):
        return Gate7LiveDryRunSession(
            self.regular,
            self.config,
            measured_source=source,
            return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
        )

    def _engage(self, session):
        first = _sample(self.regular, 0, "active")
        measured = session.ResolveMeasuredState(first, self.measured)
        self.assertIsNotNone(measured)
        session.Step(
            first,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        second = _sample(self.regular, 1, "active", right_offset_deg=1.0)
        measured = session.ResolveMeasuredState(second, self.measured)
        return session.Step(
            second,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )

    def test_mink_source_builds_locked_arm_only_candidate(self):
        session = self._session()
        tick = self._engage(session)
        self.assertEqual("TRACK_MINK_RIGHT", tick.decision.state)
        self.assertTrue(tick.validation_allowed)
        self.assertIsNotNone(tick.frame)
        self.assertEqual(0.2, tick.frame.weight)
        for index in range(29):
            if index not in DUAL_ARM_INDICES:
                self.assertEqual(0, tick.frame.motor_mode[index])
                self.assertEqual(0.0, tick.frame.motor_kp[index])
                self.assertEqual(0.0, tick.frame.motor_kd[index])

    def test_collision_diagnostics_survive_packet_parsing(self):
        sample = _sample(self.regular, 0, "active")
        self.assertEqual(
            ("test_geom_a", "test_geom_b"),
            sample.nearest_collision_geoms,
        )
        self.assertEqual(
            ("test_body_a", "test_body_b"),
            sample.nearest_collision_bodies,
        )

    def test_mink_source_runs_ten_second_fallback(self):
        session = self._session()
        self._engage(session)
        lost = _sample(self.regular, 2, "tracking_disengaged")
        measured = session.ResolveMeasuredState(lost, None)
        hold = session.Step(
            lost,
            measured,
            5.0,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("SAFETY_HOLD", hold.decision.state)
        measured = session.ResolveMeasuredState(None, None)
        returning = session.Step(
            None,
            measured,
            5.0,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("REGULAR_RETURN", returning.decision.state)
        self.assertEqual(
            "unintended_hold_timeout_return",
            returning.decision.reason,
        )

    def test_pinch_return_starts_at_latest_visible_mujoco_pose(self):
        session = self._session()
        self._engage(session)
        pinch = _sample(
            self.regular,
            2,
            "pinch_disengaged",
            right_offset_deg=12.0,
        )
        measured = session.ResolveMeasuredState(pinch, None)
        self.assertEqual(pinch.all_joint_q_rad, measured)
        tick = session.Step(
            pinch,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("REGULAR_RETURN", tick.decision.state)
        self.assertEqual("intentional_pinch_return", tick.decision.reason)
        self.assertEqual(0.0, tick.decision.return_progress)
        self.assertEqual(
            tuple(measured[index] for index in DUAL_ARM_INDICES),
            tick.decision.target_dual_arm_q_rad,
        )

    def test_active_packets_keep_rate_limited_shadow_measurement(self):
        session = self._session()
        previous_tick = self._engage(session)
        active = _sample(
            self.regular,
            2,
            "active",
            right_offset_deg=30.0,
        )
        measured = session.ResolveMeasuredState(active, None)
        self.assertNotEqual(active.all_joint_q_rad, measured)
        self.assertEqual(
            previous_tick.decision.target_dual_arm_q_rad,
            tuple(measured[index] for index in DUAL_ARM_INDICES),
        )
        tick = session.Step(
            active,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("TRACK_MINK_RIGHT", tick.decision.state)
        self.assertTrue(tick.validation_allowed)
        self.assertIsNotNone(tick.frame)

    def test_nearby_collision_does_not_replace_active_shadow(self):
        session = self._session()
        previous_tick = self._engage(session)
        nearby = _sample(
            self.regular,
            2,
            "active",
            right_offset_deg=20.0,
            collision_limited=True,
            minimum_clearance_m=0.020,
        )
        measured = session.ResolveMeasuredState(nearby, None)
        self.assertEqual(
            previous_tick.decision.target_dual_arm_q_rad,
            tuple(measured[index] for index in DUAL_ARM_INDICES),
        )
        tick = session.Step(
            nearby,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("TRACK_MINK_RIGHT", tick.decision.state)
        self.assertTrue(tick.validation_allowed)

    def test_regular_hold_rearms_from_new_aligned_active_sample(self):
        session = self._session()
        self._engage(session)
        pinch = _sample(self.regular, 2, "pinch_disengaged")
        measured = session.ResolveMeasuredState(pinch, None)
        tick = session.Step(
            pinch,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        for _ in range(100):
            measured = session.ResolveMeasuredState(None, None)
            tick = session.Step(
                None,
                measured,
                0.1,
                lowstate_age_s=0.0,
                mode_pr=0,
                mode_machine=5,
            )
            if tick.decision.state == "REGULAR_HOLD":
                break
        self.assertEqual("REGULAR_HOLD", tick.decision.state)

        active = _sample(
            self.regular,
            3,
            "active",
            right_offset_deg=2.0,
        )
        measured = session.ResolveMeasuredState(active, None)
        tick = session.Step(
            active,
            measured,
            0.01,
            lowstate_age_s=0.0,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertEqual("TRACK_MINK_RIGHT", tick.decision.state)
        self.assertTrue(tick.validation_allowed)
        self.assertIsNotNone(tick.frame)

    def test_stale_lowstate_removes_candidate_frame(self):
        session = self._session("lowstate")
        sample = _sample(self.regular, 0, "active")
        measured = session.ResolveMeasuredState(sample, self.measured)
        tick = session.Step(
            sample,
            measured,
            0.01,
            lowstate_age_s=0.251,
            mode_pr=0,
            mode_machine=5,
        )
        self.assertFalse(tick.validation_allowed)
        self.assertEqual("lowstate_stale", tick.validation_reason)
        self.assertIsNone(tick.frame)

    def test_lowstate_source_requires_full_measured_state(self):
        session = self._session("lowstate")
        self.assertIsNone(session.ResolveMeasuredState(None, None))

    def test_lowstate_no_output_shadow_follows_candidate_without_false_error(self):
        controller = RuckigGate7TeleopController(
            self.regular,
            self.config,
            return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
        )
        session = Gate7LiveDryRunSession(
            self.regular,
            self.config,
            measured_source="lowstate",
            return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
            controller=controller,
            simulate_command_following=True,
        )
        for sequence in range(500):
            sample = _sample(
                self.regular,
                sequence,
                "active",
                right_offset_deg=30.0,
            )
            measured = session.ResolveMeasuredState(sample, self.measured)
            tick = session.Step(
                sample,
                measured,
                0.004,
                lowstate_age_s=0.0,
                mode_pr=0,
                mode_machine=5,
            )
        self.assertEqual("TRACK_MINK_RIGHT", tick.decision.state)
        self.assertTrue(tick.validation_allowed)
        self.assertIsNotNone(tick.frame)
        shadow = session.ResolveMeasuredState(None, self.measured)
        self.assertNotEqual(self.measured, shadow)

    def test_command_following_simulation_rejects_non_lowstate_source(self):
        with self.assertRaisesRegex(ValueError, "requires measured_source=lowstate"):
            Gate7LiveDryRunSession(
                self.regular,
                self.config,
                measured_source="mink",
                return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
                simulate_command_following=True,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
