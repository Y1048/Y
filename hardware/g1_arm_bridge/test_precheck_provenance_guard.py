#!/usr/bin/env python3
"""Offline tests for provenance/state-bound startup-precheck consumption."""

from __future__ import annotations

import copy
import unittest

from precheck_provenance_guard import require_provenance_bound_precheck
from startup_state_binding_guard import build_state_binding


class PrecheckProvenanceGuardTests(unittest.TestCase):
    def _payload(self) -> dict[str, object]:
        return {
            "lowstate_packet_count": 20,
            "lowstate_forward_provenance": {
                "mode": "per_run_token",
                "forward_token_verified": True,
                "verified_packet_count": 20,
            },
            "startup_state_binding": build_state_binding(),
            "latest_base_state": {
                "valid": True,
                "topic": "rt/sportmodestate",
                "received_packets": 20,
                "invalid_packets": 0,
                "last_packet_age_s": 0.01,
                "position_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "velocity_mps": [0.0, 0.0, 0.0],
                "yaw_speed_rad_s": 0.0,
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

    def test_missing_or_invalid_base_state_is_rejected(self) -> None:
        payload = self._payload()
        payload.pop("latest_base_state")
        with self.assertRaisesRegex(ValueError, "base-state"):
            require_provenance_bound_precheck(payload)

        payload = self._payload()
        payload["latest_base_state"]["valid"] = False
        with self.assertRaisesRegex(ValueError, "base-state"):
            require_provenance_bound_precheck(payload)

    def test_model_or_config_hash_mismatch_is_rejected(self) -> None:
        payload = copy.deepcopy(self._payload())
        payload["startup_state_binding"]["g1_model_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match current checkout"):
            require_provenance_bound_precheck(payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
