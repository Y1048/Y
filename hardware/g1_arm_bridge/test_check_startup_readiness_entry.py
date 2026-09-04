#!/usr/bin/env python3
"""Offline tests for supported startup token/raw-odometry guard (R40/R51)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import check_startup_readiness_entry as entry


def _raw_base_state() -> dict[str, object]:
    return {
        "valid": True,
        "odom_position_m": [1.0, -0.2, 0.75],
        "odom_quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
    }


class StartupPrecheckEntryTests(unittest.TestCase):
    def test_token_format_accepts_uuid_hex(self) -> None:
        token = "0123456789abcdef0123456789abcdef"
        self.assertEqual(token, entry.validate_forward_token(token))

    def test_token_format_rejects_short_or_punctuated_values(self) -> None:
        with self.assertRaises(ValueError):
            entry.validate_forward_token("short")
        with self.assertRaises(ValueError):
            entry.validate_forward_token("0123456789abcdef-with-dash")

    def test_guard_rejects_wrong_token_before_canonical_parser(self) -> None:
        original_parse = entry.precheck.parse_lowstate_telemetry
        expected = "a" * 32
        try:
            state = entry.install_forward_token_guard(expected)
            payload = json.dumps(
                {
                    "forward_token": "b" * 32,
                    "schema": "irrelevant-for-token-test",
                }
            ).encode("utf-8")
            with self.assertRaisesRegex(
                entry.precheck.LowStatePacketError,
                "forward_token_mismatch",
            ):
                entry.precheck.parse_lowstate_telemetry(payload)
            self.assertEqual(0, state["verified_packets"])
        finally:
            entry.precheck.parse_lowstate_telemetry = original_parse

    def test_matching_token_without_raw_odom_is_rejected(self) -> None:
        original_parse = entry.precheck.parse_lowstate_telemetry
        try:
            state = entry.install_forward_token_guard("c" * 32)
            payload = json.dumps(
                {
                    "forward_token": "c" * 32,
                    "base_state": {"valid": True},
                }
            ).encode("utf-8")
            with self.assertRaisesRegex(
                entry.precheck.LowStatePacketError,
                "odom_position_m",
            ):
                entry.precheck.parse_lowstate_telemetry(payload)
            self.assertEqual(0, state["verified_packets"])
        finally:
            entry.precheck.parse_lowstate_telemetry = original_parse

    def test_guard_counts_only_token_and_raw_odom_bound_packets(self) -> None:
        original_parse = entry.precheck.parse_lowstate_telemetry
        calls = []

        def fake_parser(payload: bytes):
            calls.append(payload)
            return object()

        try:
            entry.precheck.parse_lowstate_telemetry = fake_parser
            state = entry.install_forward_token_guard("d" * 32)
            payload = json.dumps(
                {
                    "forward_token": "d" * 32,
                    "base_state": _raw_base_state(),
                }
            ).encode("utf-8")
            result = entry.precheck.parse_lowstate_telemetry(payload)
            self.assertIsNotNone(result)
            self.assertEqual(1, len(calls))
            self.assertEqual(1, state["verified_packets"])
            self.assertEqual(
                [1.0, -0.2, 0.75],
                state["latest_raw_odom"]["odom_position_m"],
            )
        finally:
            entry.precheck.parse_lowstate_telemetry = original_parse

    def test_supported_read_only_entry_forwards_raw_odom_fields(self) -> None:
        source = (
            Path(__file__).resolve().parent / "read_only_lowstate_entry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("install_raw_odom_binding", source)
        self.assertIn("odom_position_m", source)
        self.assertIn("odom_quaternion_xyzw", source)
        self.assertNotIn("ChannelPublisher", source)
        self.assertNotIn("LowCmd_", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
