#!/usr/bin/env python3
"""Offline tests for the supported startup-precheck token guard (R51)."""

from __future__ import annotations

import json
import unittest

import check_startup_readiness_entry as entry


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

    def test_guard_counts_only_packets_with_matching_token(self) -> None:
        original_parse = entry.precheck.parse_lowstate_telemetry
        calls = []

        def fake_parser(payload: bytes):
            calls.append(payload)
            return object()

        try:
            entry.precheck.parse_lowstate_telemetry = fake_parser
            state = entry.install_forward_token_guard("c" * 32)
            payload = json.dumps({"forward_token": "c" * 32}).encode("utf-8")
            result = entry.precheck.parse_lowstate_telemetry(payload)
            self.assertIsNotNone(result)
            self.assertEqual(1, len(calls))
            self.assertEqual(1, state["verified_packets"])
        finally:
            entry.precheck.parse_lowstate_telemetry = original_parse


if __name__ == "__main__":
    unittest.main(verbosity=2)
