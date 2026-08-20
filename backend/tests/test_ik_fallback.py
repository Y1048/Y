from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.ik_fallback import (  # noqa: E402
    IKFallbackSettings,
    IKFallbackSupervisor,
    MultiSeedSettings,
    load_ik_fallback_settings,
)


def multiseed(**overrides):
    values = dict(
        enabled=True,
        iterations_per_seed=8,
        shoulder_yaw_offset_rad=math.radians(22.0),
        elbow_offset_rad=math.radians(25.0),
        ready_seed_enabled=True,
        joint_motion_weight=0.12,
        joint_margin_weight=0.08,
        min_improvement_ratio=0.99,
    )
    values.update(overrides)
    return MultiSeedSettings(**values)


def settings(**overrides):
    values = dict(
        enabled=True,
        position_error_enter_m=0.035,
        rotation_error_enter_rad=math.radians(12.0),
        position_error_exit_m=0.018,
        rotation_error_exit_rad=math.radians(6.0),
        enter_frames=3,
        inspection_enter_frames=5,
        exit_frames=2,
        damping=0.06,
        orientation_weight_m_per_rad=0.12,
        min_improvement_ratio=0.995,
        allow_during_inspection_contact=False,
        multiseed=multiseed(),
    )
    values.update(overrides)
    return IKFallbackSettings(**values)


def fallback_payload():
    return {
        "ik": {
            "fallback": {
                "enabled": True,
                "position_error_enter_m": 0.035,
                "rotation_error_enter_deg": 12.0,
                "position_error_exit_m": 0.018,
                "rotation_error_exit_deg": 6.0,
                "enter_frames": 5,
                "inspection_enter_frames": 12,
                "exit_frames": 15,
                "damping": 0.06,
                "orientation_weight_m_per_rad": 0.12,
                "min_improvement_ratio": 0.995,
                "allow_during_inspection_contact": False,
                "multiseed": {
                    "enabled": True,
                    "iterations_per_seed": 8,
                    "shoulder_yaw_offset_deg": 22.0,
                    "elbow_offset_deg": 25.0,
                    "ready_seed_enabled": True,
                    "joint_motion_weight": 0.12,
                    "joint_margin_weight": 0.08,
                    "min_improvement_ratio": 0.99,
                },
            }
        }
    }


class IKFallbackSupervisorTest(unittest.TestCase):
    def test_persistent_error_enters_fallback(self):
        supervisor = IKFallbackSupervisor(settings())
        self.assertFalse(supervisor.update(0.05, 0.0, inspection_contact=False).active)
        self.assertFalse(supervisor.update(0.05, 0.0, inspection_contact=False).active)
        transition = supervisor.update(0.05, 0.0, inspection_contact=False)
        self.assertTrue(transition.active)
        self.assertEqual(transition.reason, "persistent_pose_error")

    def test_single_bad_frame_does_not_switch(self):
        supervisor = IKFallbackSupervisor(settings())
        supervisor.update(0.05, 0.0, inspection_contact=False)
        transition = supervisor.update(0.01, 0.0, inspection_contact=False)
        self.assertFalse(transition.active)
        self.assertEqual(transition.bad_frames, 0)

    def test_inspection_contact_uses_more_conservative_entry_count(self):
        supervisor = IKFallbackSupervisor(settings())
        for _ in range(4):
            transition = supervisor.update(0.05, 0.0, inspection_contact=True)
            self.assertFalse(transition.active)
        self.assertTrue(supervisor.update(0.05, 0.0, inspection_contact=True).active)

    def test_fallback_exits_only_after_stable_recovery(self):
        supervisor = IKFallbackSupervisor(settings(enter_frames=1, exit_frames=2))
        self.assertTrue(supervisor.update(0.05, 0.0, inspection_contact=False).active)
        self.assertTrue(supervisor.update(0.01, math.radians(2), inspection_contact=False).active)
        transition = supervisor.update(0.01, math.radians(2), inspection_contact=False)
        self.assertFalse(transition.active)
        self.assertEqual(transition.reason, "decoupled_recovered")

    def test_disabled_supervisor_never_enters_fallback(self):
        supervisor = IKFallbackSupervisor(settings(enabled=False, enter_frames=1))
        transition = supervisor.update(1.0, math.pi, inspection_contact=False)
        self.assertFalse(transition.active)
        self.assertEqual(transition.reason, "disabled")

    def test_loader_reads_multiseed_settings(self):
        payload = fallback_payload()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "teleop.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_ik_fallback_settings(path)
        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.enter_frames, 5)
        self.assertAlmostEqual(loaded.rotation_error_enter_rad, math.radians(12.0))
        self.assertTrue(loaded.multiseed.enabled)
        self.assertEqual(loaded.multiseed.iterations_per_seed, 8)
        self.assertAlmostEqual(loaded.multiseed.shoulder_yaw_offset_rad, math.radians(22.0))
        self.assertAlmostEqual(loaded.multiseed.elbow_offset_rad, math.radians(25.0))
        self.assertAlmostEqual(loaded.multiseed.min_improvement_ratio, 0.99)

    def test_loader_rejects_exit_threshold_above_enter_threshold(self):
        payload = fallback_payload()
        payload["ik"]["fallback"]["position_error_enter_m"] = 0.02
        payload["ik"]["fallback"]["position_error_exit_m"] = 0.03
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "teleop.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_ik_fallback_settings(path)

    def test_loader_rejects_invalid_multiseed_ratio(self):
        payload = fallback_payload()
        payload["ik"]["fallback"]["multiseed"]["min_improvement_ratio"] = 1.1
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "teleop.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_ik_fallback_settings(path)

    def test_multiseed_can_be_disabled_without_disabling_coupled_fallback(self):
        payload = fallback_payload()
        payload["ik"]["fallback"]["multiseed"]["enabled"] = False
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "teleop.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_ik_fallback_settings(path)
        self.assertTrue(loaded.enabled)
        self.assertFalse(loaded.multiseed.enabled)


if __name__ == "__main__":
    unittest.main()
