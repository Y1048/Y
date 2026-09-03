#!/usr/bin/env python3
"""Offline contract tests for the locked Gate 7 hardware adapter."""

from __future__ import annotations

import unittest
import json
import ast
import socket
import threading
import time
from dataclasses import replace
from pathlib import Path

from gate7_live_arm_sdk import (
    AcquireWeight,
    BuildUnityLowStateTelemetry,
    CreateHardwareTrajectoryController,
    LoadLiveHardwareConfig,
    ReleaseWeight,
    ValidateHardwareAuthorization,
    ValidateRuckigRuntime,
    WaitForFirstActiveMink,
)
from gate6_arm_sdk_hold import LowStateSnapshot
from arm_sdk_teleop_contract import load_gate7_config, load_regular_arm_pose
from g1_joint_contract import G1_29_JOINT_NAMES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "g1_gate7_live_hardware_output.json"
GATE7_CONFIG_PATH = PROJECT_ROOT / "config" / "g1_gate7_mink_arm_sdk.json"
REGULAR_PATH = PROJECT_ROOT / "config" / "g1_regular_arm_pose.json"


class Gate7LiveArmSdkTests(unittest.TestCase):
    def setUp(self):
        self.config = LoadLiveHardwareConfig(CONFIG_PATH)

    def test_repository_config_is_physically_locked(self):
        self.assertFalse(self.config.hardware_output_authorized)
        self.assertEqual(120.0, self.config.mink_startup_timeout_s)
        self.assertEqual(180.0, self.config.precheck_max_age_s)
        self.assertEqual("ruckig", self.config.trajectory_generator)
        self.assertEqual("0.19.4", ValidateRuckigRuntime(self.config))
        self.assertEqual(1.0, self.config.trajectory_velocity_scale)
        self.assertEqual(1.0, self.config.trajectory_acceleration_scale)
        self.assertEqual(1.0, self.config.trajectory_jerk_scale)
        with self.assertRaisesRegex(PermissionError, "authorized is false"):
            ValidateHardwareAuthorization(
                self.config,
                enable_hardware_output=True,
                confirmation=self.config.hardware_confirmation_phrase,
                grounded_confirmation=(
                    self.config.grounded_regular_confirmation_phrase
                ),
            )

    def test_all_authorization_conditions_are_required(self):
        unlocked = replace(self.config, hardware_output_authorized=True)
        with self.assertRaisesRegex(PermissionError, "enable-hardware-output"):
            ValidateHardwareAuthorization(
                unlocked,
                enable_hardware_output=False,
                confirmation=unlocked.hardware_confirmation_phrase,
                grounded_confirmation=(
                    unlocked.grounded_regular_confirmation_phrase
                ),
            )
        with self.assertRaisesRegex(PermissionError, "confirmation phrase"):
            ValidateHardwareAuthorization(
                unlocked,
                enable_hardware_output=True,
                confirmation="wrong",
                grounded_confirmation=(
                    unlocked.grounded_regular_confirmation_phrase
                ),
            )

    def test_weight_schedules_are_bounded_and_monotonic(self):
        acquire = [AcquireWeight(t, 5.0, 0.2) for t in (0.0, 1.0, 5.0, 8.0)]
        release = [ReleaseWeight(t, 2.0, 0.2) for t in (0.0, 1.0, 2.0, 4.0)]
        for actual, expected in zip(acquire, (0.0, 0.04, 0.2, 0.2)):
            self.assertAlmostEqual(expected, actual)
        for actual, expected in zip(release, (0.2, 0.1, 0.0, 0.0)):
            self.assertAlmostEqual(expected, actual)

    def test_publisher_import_is_after_authorization_call(self):
        source = (
            PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "gate7_live_arm_sdk.py"
        ).read_text(encoding="utf-8")
        authorization = source.index("ValidateHardwareAuthorization(", source.index("def main"))
        publisher_import = source.index("ChannelPublisher,", authorization)
        publisher_create = source.index("publisher = ChannelPublisher", publisher_import)
        self.assertLess(authorization, publisher_import)
        self.assertLess(publisher_import, publisher_create)

    def test_hardware_candidate_uses_unscaled_ruckig_limits(self):
        gate7_config = load_gate7_config(GATE7_CONFIG_PATH)
        regular = load_regular_arm_pose(REGULAR_PATH)
        controller = CreateHardwareTrajectoryController(
            regular,
            gate7_config,
            self.config,
            return_path_validator=lambda _trajectory, _all_q: (True, "ok"),
        )
        self.assertEqual(gate7_config.velocity_limits_rad_s, controller.velocity_limits_rad_s)
        self.assertEqual(
            gate7_config.acceleration_limits_rad_s2,
            controller.acceleration_limits_rad_s2,
        )
        self.assertEqual(gate7_config.jerk_limits_rad_s3, controller.jerk_limits_rad_s3)

    def test_publisher_boundary_ignores_idle_until_active_command(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.setblocking(False)
        address = receiver.getsockname()
        regular = load_regular_arm_pose(REGULAR_PATH)

        def packet(sequence, active):
            all_q = list(regular.reference_all_joint_q_rad)
            value = {
                "schema": "g1.mink.right_arm.state.v1",
                "sequence": sequence,
                "state_source": "mink_simulation",
                "all_joint_names": list(G1_29_JOINT_NAMES),
                "all_joint_q_rad": all_q,
                "right_arm": {
                    "joints": all_q[22:29],
                    "active": active,
                    "workspace_limited": False,
                    "collision_limited": False,
                    "minimum_clearance_m": 0.05,
                    "nearest_collision_geoms": [],
                    "nearest_collision_bodies": [],
                    "command_state": "active" if active else "idle",
                },
                "input_command_mode": "active" if active else "idle",
                "session_id": "publisher-boundary-test",
                "input_packet_age_s": 0.0,
                "timestamp": 1.0,
            }
            return json.dumps(value).encode("utf-8")

        idle_packet = packet(1, False)
        active_packet = packet(2, True)

        def send_packets():
            sender.sendto(idle_packet, address)
            time.sleep(0.05)
            sender.sendto(active_packet, address)

        thread = threading.Thread(target=send_packets)
        thread.start()
        try:
            sample = WaitForFirstActiveMink(receiver, 0.5)
        finally:
            thread.join()
            sender.close()
            receiver.close()
        self.assertEqual("active", sample.input_command_mode)
        self.assertEqual("active", sample.controller_state)

    def test_gate7_lowstate_is_forwarded_as_full_body_unity_state(self):
        all_q = tuple(float(index) / 100.0 for index in range(29))
        all_dq = tuple(float(index) / 1000.0 for index in range(29))
        snapshot = LowStateSnapshot(
            received_monotonic_s=1.0,
            received_unix_ns=123456789,
            sequence=42,
            mode_pr=0,
            mode_machine=5,
            all_q_rad=all_q,
            all_dq_rad_s=all_dq,
        )
        packet = BuildUnityLowStateTelemetry(snapshot, "gate7-unity-test")
        self.assertEqual(G1_29_JOINT_NAMES, packet.all_joint_names)
        self.assertEqual(all_q, packet.all_joint_q_rad)
        self.assertEqual(all_dq, packet.all_joint_dq_rad_s)
        self.assertEqual(all_q[22:29], packet.measured_q_rad)
        self.assertEqual("gate7-unity-test", packet.bridge_session_id)
        self.assertEqual(42, packet.sequence)

    def test_unity_mirror_does_not_own_the_acquire_control_else_branch(self):
        source_path = (
            PROJECT_ROOT / "hardware" / "g1_arm_bridge" / "gate7_live_arm_sdk.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        elapsed_branch = None
        unity_branch = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            condition = ast.unparse(node.test)
            if condition == "elapsed < hardware_config.acquire_ramp_s":
                elapsed_branch = node
            if condition == "now >= next_unity_state":
                unity_branch = node
        self.assertIsNotNone(elapsed_branch)
        self.assertIsNotNone(unity_branch)
        self.assertTrue(elapsed_branch.orelse)
        self.assertFalse(unity_branch.orelse)
        self.assertLess(elapsed_branch.end_lineno, unity_branch.lineno)


if __name__ == "__main__":
    unittest.main()
