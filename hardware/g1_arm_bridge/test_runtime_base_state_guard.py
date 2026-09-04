#!/usr/bin/env python3
"""SDK-neutral tests for runtime base/odometry supervision (R40/R50)."""

from __future__ import annotations

import math
import unittest
from pathlib import Path
from types import SimpleNamespace

from runtime_base_state_guard import (
    RuntimeBaseStateMonitor,
    validate_runtime_base_snapshot,
)


class _Message:
    def __init__(
        self,
        *,
        position=(0.0, 0.0, 0.0),
        quaternion_wxyz=(1.0, 0.0, 0.0, 0.0),
        velocity=(0.0, 0.0, 0.0),
        yaw_speed=0.0,
    ) -> None:
        self.position = list(position)
        self.imu_state = SimpleNamespace(quaternion=list(quaternion_wxyz))
        self.velocity = list(velocity)
        self.yaw_speed = yaw_speed


def _yaw_quaternion_wxyz(yaw_rad: float):
    return (
        math.cos(yaw_rad / 2.0),
        0.0,
        0.0,
        math.sin(yaw_rad / 2.0),
    )


class RuntimeBaseStateGuardTests(unittest.TestCase):
    def test_nominal_three_sample_runtime_base_passes(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message(position=(0.005, 0.0, 0.0)))
        monitor.callback(_Message(position=(0.010, 0.0, 0.0)))
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        validate_runtime_base_snapshot(
            snapshot,
            now_monotonic_s=snapshot.received_monotonic_s,
        )

    def test_stale_runtime_base_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        for _ in range(3):
            monitor.callback(_Message())
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        with self.assertRaisesRegex(RuntimeError, "stale"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s + 0.30,
            )

    def test_translation_drift_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message())
        monitor.callback(_Message(position=(0.06, 0.0, 0.0)))
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        with self.assertRaisesRegex(RuntimeError, "translation"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s,
            )

    def test_linear_speed_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message())
        monitor.callback(_Message(velocity=(0.16, 0.0, 0.0)))
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        with self.assertRaisesRegex(RuntimeError, "speed"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s,
            )

    def test_yaw_speed_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message())
        monitor.callback(_Message(yaw_speed=0.30))
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        with self.assertRaisesRegex(RuntimeError, "yaw speed"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s,
            )

    def test_yaw_drift_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message())
        monitor.callback(_Message(quaternion_wxyz=_yaw_quaternion_wxyz(math.radians(9.0))))
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        with self.assertRaisesRegex(RuntimeError, "yaw drift"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s,
            )

    def test_invalid_packet_count_fails(self) -> None:
        monitor = RuntimeBaseStateMonitor()
        monitor.callback(_Message())
        monitor.callback(_Message())
        monitor.callback(_Message(position=(float("nan"), 0.0, 0.0)))
        monitor.callback(_Message())
        snapshot = monitor.snapshot()
        self.assertIsNotNone(snapshot)
        self.assertGreater(snapshot.invalid_packets, 0)
        with self.assertRaisesRegex(RuntimeError, "invalid packet"):
            validate_runtime_base_snapshot(
                snapshot,
                now_monotonic_s=snapshot.received_monotonic_s,
            )

    def test_source_is_read_only_subscriber_only(self) -> None:
        source = (
            Path(__file__).resolve().parent / "runtime_base_state_guard.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ChannelSubscriber", source)
        self.assertIn("rt/odommodestate", source)
        self.assertNotIn("ChannelPublisher", source)
        self.assertNotIn("LowCmd_", source)

    def test_supported_physical_entries_install_and_require_base_guard(self) -> None:
        here = Path(__file__).resolve().parent
        for filename in (
            "gate6_arm_sdk_hold_entry.py",
            "gate7_live_arm_sdk_entry.py",
            "g1_right_arm_jog_entry.py",
        ):
            source = (here / filename).read_text(encoding="utf-8")
            self.assertIn("runtime_base_state_guard", source)
            self.assertIn("install_unitree_base_state_subscription", source)
            self.assertIn("require_latest_runtime_base_state", source)

    def test_validate_only_paths_do_not_require_unitree_base_import(self) -> None:
        here = Path(__file__).resolve().parent
        gate6 = (here / "gate6_arm_sdk_hold_entry.py").read_text(encoding="utf-8")
        jog = (here / "g1_right_arm_jog_entry.py").read_text(encoding="utf-8")
        self.assertIn('"--validate-only" not in sys.argv[1:]', gate6)
        self.assertIn('"--validate-only" not in argv', jog)


if __name__ == "__main__":
    unittest.main(verbosity=2)
