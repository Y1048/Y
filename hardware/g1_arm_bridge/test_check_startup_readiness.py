#!/usr/bin/env python3
"""Offline tests for the read-only G1 startup readiness decision."""

from __future__ import annotations

import time
import unittest
from pathlib import Path

from check_startup_readiness import (
    EXPECTED_G1_29_JOINT_NAMES,
    Blocker,
    PrecheckConfig,
    TimedPacket,
    evaluate_readiness,
    latest_full_body_snapshot,
    percentile_nearest_rank,
    summarize_settling,
)
from gate5_lowstate_safety_monitor import LowStateTelemetry


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
SAFE_Q = (
    0.291,
    -0.229,
    0.017,
    0.986,
    -0.177,
    0.028,
    0.015,
)


def _config() -> PrecheckConfig:
    return PrecheckConfig(
        expected_form="0",
        expected_name="ai",
        expected_mode_machine=5,
        expected_mode_pr=0,
        observation_window_s=1.0,
        minimum_packet_count=20,
        maximum_packet_age_s=0.25,
        maximum_pose_span_deg=0.5,
        maximum_velocity_p95_deg_s=3.0,
        minimum_collision_distance_m=0.012,
        maximum_motion_mode_query_age_s=15.0,
    )


def _timed_packet(sequence: int, dq_deg_s: float = 0.2) -> TimedPacket:
    full_q = [0.0] * 29
    full_q[22:29] = SAFE_Q
    packet = LowStateTelemetry(
        bridge_session_id="startup-readiness-test",
        sequence=sequence,
        sent_at_unix_ns=time.time_ns(),
        mode_pr=0,
        mode_machine=5,
        measured_q_rad=SAFE_Q,
        measured_dq_rad_s=tuple([dq_deg_s * 3.141592653589793 / 180.0] * 7),
        all_joint_names=EXPECTED_G1_29_JOINT_NAMES,
        all_joint_q_rad=tuple(full_q),
        all_joint_dq_rad_s=tuple([0.0] * 29),
    )
    return TimedPacket(packet, age_s=0.01)


def _mode_query(name: str = "ai") -> dict[str, object]:
    return {
        "schema": "g1.motion_mode.query.v1",
        "queried_at_unix_ns": time.time_ns(),
        "operation": "MotionSwitcherClient.CheckMode",
        "result_code": 0,
        "form": "0",
        "name": name,
        "state_mutation_requested": False,
        "motor_command_publisher_present": False,
        "command_output_enabled": False,
    }


class StartupReadinessTests(unittest.TestCase):
    def test_latest_full_body_snapshot_uses_nested_telemetry(self) -> None:
        packet = _timed_packet(1)
        snapshot = latest_full_body_snapshot(packet)
        self.assertEqual(
            list(EXPECTED_G1_29_JOINT_NAMES),
            snapshot["latest_all_joint_names"],
        )
        self.assertEqual(29, len(snapshot["latest_all_joint_q_rad"]))
        self.assertEqual(29, len(snapshot["latest_all_joint_dq_rad_s"]))

    def test_collision_precheck_includes_both_arms(self) -> None:
        source = (HERE / "check_startup_readiness.py").read_text(encoding="utf-8")
        self.assertIn("RIGHT_ARM_BODY_NAMES", source)
        self.assertIn("LEFT_ARM_BODY_NAMES", source)
        self.assertIn("controlled_body_names=dual_arm_body_names", source)

    def test_percentile_uses_nearest_rank(self) -> None:
        self.assertEqual(5.0, percentile_nearest_rank([1, 2, 3, 4, 5], 0.95))

    def test_stable_window_is_direct_ready(self) -> None:
        packets = [_timed_packet(index) for index in range(20)]
        collision = {"minimum_distance_m": 0.027}
        decision, blockers, metrics = evaluate_readiness(
            packets,
            [],
            _mode_query(),
            _config(),
            collision,
            time.time_ns(),
        )
        self.assertEqual("DIRECT_TELEOP_READY", decision)
        self.assertEqual([], blockers)
        self.assertLess(metrics["maximum_right_arm_pose_span_deg"], 0.001)

    def test_non_regular_service_blocks_startup(self) -> None:
        packets = [_timed_packet(index) for index in range(20)]
        decision, blockers, _metrics = evaluate_readiness(
            packets,
            [],
            _mode_query("advanced"),
            _config(),
            {"minimum_distance_m": 0.027},
            time.time_ns(),
        )
        self.assertEqual("REGULAR_MODE_REQUIRED", decision)
        self.assertIn("regular_mode_required", {item.code for item in blockers})

    def test_high_velocity_waits_instead_of_authorizing(self) -> None:
        packets = [_timed_packet(index, dq_deg_s=4.0) for index in range(20)]
        decision, blockers, _metrics = evaluate_readiness(
            packets,
            [],
            _mode_query(),
            _config(),
            {"minimum_distance_m": 0.027},
            time.time_ns(),
        )
        self.assertEqual("WAIT_AND_RETRY", decision)
        self.assertIn("right_arm_velocity_high", {item.code for item in blockers})

    def test_mutating_mode_query_contract_is_blocked(self) -> None:
        packets = [_timed_packet(index) for index in range(20)]
        mode_query = _mode_query()
        mode_query["state_mutation_requested"] = True
        decision, blockers, _metrics = evaluate_readiness(
            packets,
            [],
            mode_query,
            _config(),
            {"minimum_distance_m": 0.027},
            time.time_ns(),
        )
        self.assertEqual("STARTUP_BLOCKED", decision)
        self.assertIn(
            "unsafe_motion_mode_query_contract",
            {item.code for item in blockers},
        )

    def test_collision_violation_requires_recovery(self) -> None:
        packets = [_timed_packet(index) for index in range(20)]
        decision, blockers, _metrics = evaluate_readiness(
            packets,
            [],
            _mode_query(),
            _config(),
            {"minimum_distance_m": 0.011},
            time.time_ns(),
        )
        self.assertEqual("RECOVERY_REQUIRED", decision)
        self.assertIn(
            "collision_clearance_below_minimum",
            {item.code for item in blockers},
        )

    def test_motion_mode_query_has_no_mutating_call(self) -> None:
        source = (HERE / "query_motion_mode.py").read_text(encoding="utf-8")
        self.assertNotIn(".SelectMode(", source)
        self.assertNotIn(".ReleaseMode(", source)
        self.assertNotIn("ChannelPublisher", source)
        self.assertNotIn("LowCmd", source)

    def test_settling_summary_reports_velocity(self) -> None:
        summary = summarize_settling([_timed_packet(index) for index in range(20)])
        self.assertAlmostEqual(
            0.2,
            summary["maximum_right_arm_velocity_p95_deg_s"],
            places=6,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
