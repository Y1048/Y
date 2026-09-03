from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import (  # noqa: E402
    load_teleop_config,
)


VALID_CONFIG = {
    "network": {
        "udp_host": "0.0.0.0",
        "udp_port": 5005,
        "unity_state_host": "127.0.0.1",
        "unity_state_port": 5006,
        "unity_state_hz": 60.0,
    },
    "runtime": {
        "input_timeout_s": 0.75,
        "workspace_exit_confirm_s": 0.8,
        "status_hz": 2.0,
        "head_camera_fps": 30.0,
        "neutral_solve_iterations": 600,
    },
    "motion": {
        "position_max_speed_mps": 0.12,
        "rotation_max_speed_deg_s": 70.0,
    },
    "ik": {
        "position_damping": 0.045,
        "orientation_damping": 0.035,
        "ik_step_gain": 0.5,
        "ik_max_step_deg": 1.5,
        "posture_gain": 0.08,
        "elbow_pole_gain": 0.65,
        "elbow_pole_damping": 0.08,
        "elbow_avoidance_weight": 0.85,
    },
    "collision": {
        "margin_m": 0.015,
        "structural_neighbor_distance": 2,
        "environment_obstacles_enabled": True,
        "tangential_slide_enabled": True,
        "task_contact": {
            "enabled": True,
            "tool_body_names": ["inspection_tool_tip_body"],
            "target_geom_names": ["inspection_panel"],
        },
    },
    "workspace": {
        "voxel_size_m": 0.01,
        "allowed_classes": [1, 2],
        "workspace_file": "logs/workspace/right_arm_workspace.npz",
        "clutch_delta_min_m": [-0.2, -0.3, -0.28],
        "clutch_delta_max_m": [0.2, 0.45, 0.34],
        "right_elbow_lateral_limit_m": -0.3,
        "right_wrist_lateral_limit_m": -0.3,
        "torso_keep_out_x_m": [-0.18, 0.22],
        "torso_keep_out_z_m": [0.45, 1.3],
    },
}


class TeleopConfigTest(unittest.TestCase):
    def _load(self, payload):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "teleop.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return load_teleop_config(path)

    def test_valid_config_loads_typed_values(self):
        config = self._load(VALID_CONFIG)
        self.assertEqual(config.network.udp_port, 5005)
        self.assertEqual(config.workspace.allowed_classes, (1, 2))
        self.assertAlmostEqual(config.motion.position_max_speed_mps, 0.12)
        self.assertEqual(config.collision.structural_neighbor_distance, 2)
        self.assertTrue(config.collision.environment_obstacles_enabled)
        self.assertTrue(config.collision.tangential_slide_enabled)
        self.assertTrue(config.collision.task_contact_enabled)
        self.assertEqual(config.collision.task_contact_tool_body_names, ("inspection_tool_tip_body",))

    def test_enabled_task_contact_requires_tool_and_target(self):
        payload = json.loads(json.dumps(VALID_CONFIG))
        payload["collision"]["task_contact"]["target_geom_names"] = []
        with self.assertRaises(ValueError):
            self._load(payload)

    def test_invalid_collision_boolean_is_rejected(self):
        payload = json.loads(json.dumps(VALID_CONFIG))
        payload["collision"]["environment_obstacles_enabled"] = "yes"
        with self.assertRaises(ValueError):
            self._load(payload)

    def test_invalid_speed_is_rejected(self):
        payload = json.loads(json.dumps(VALID_CONFIG))
        payload["motion"]["position_max_speed_mps"] = -1.0
        with self.assertRaises(ValueError):
            self._load(payload)

    def test_invalid_port_is_rejected(self):
        payload = json.loads(json.dumps(VALID_CONFIG))
        payload["network"]["udp_port"] = 70000
        with self.assertRaises(ValueError):
            self._load(payload)

    def test_invalid_workspace_classes_are_rejected(self):
        payload = json.loads(json.dumps(VALID_CONFIG))
        payload["workspace"]["allowed_classes"] = [0, 2]
        with self.assertRaises(ValueError):
            self._load(payload)

    def test_missing_config_is_not_silently_defaulted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                load_teleop_config(Path(temp_dir) / "missing.json")


if __name__ == "__main__":
    unittest.main()
