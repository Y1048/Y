#!/usr/bin/env python3
"""Offline tests for provenance-bound startup-precheck consumption (R51)."""

from __future__ import annotations

import unittest

from precheck_provenance_guard import require_provenance_bound_precheck


class PrecheckProvenanceGuardTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "lowstate_packet_count": 20,
            "lowstate_forward_provenance": {
                "mode": "per_run_token",
                "forward_token_verified": True,
                "verified_packet_count": 20,
            },
        }

    def test_valid_provenance_is_accepted(self) -> None:
        payload = self._payload()
        self.assertIs(payload, require_provenance_bound_precheck(payload))

    def test_missing_or_unverified_provenance_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            require_provenance_bound_precheck({})
        payload = self._payload()
        payload["lowstate_forward_provenance"]["forward_token_verified"] = False
        with self.assertRaises(ValueError):
            require_provenance_bound_precheck(payload)

    def test_verified_count_must_match_accepted_count(self) -> None:
        payload = self._payload()
        payload["lowstate_forward_provenance"]["verified_packet_count"] = 19
        with self.assertRaisesRegex(ValueError, "does not match"):
            require_provenance_bound_precheck(payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
