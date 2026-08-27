from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_ROOT = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))

import edit_startup_ready_pose as editor  # noqa: E402


class StartupReadyPoseEditorTest(unittest.TestCase):
    def test_save_preserves_other_config_and_creates_previous_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "startup_recovery.json"
            backup_path = root / "previous.json"
            original = {
                "safe_ready_pose_deg": {
                    name: 0.0 for name in editor.JOINT_NAMES
                },
                "viewer": {"playback_speed": 1.5, "initial_hold_s": 3.0},
                "future_setting": {"preserve": True},
            }
            config_path.write_text(
                json.dumps(original, indent=2),
                encoding="utf-8",
            )
            pose = np.asarray([10.0, -30.0, 5.0, 55.0, 2.0, -3.0, 4.0])

            editor.SavePose(config_path, pose, backup_path)

            saved = json.loads(config_path.read_text(encoding="utf-8"))
            backup = json.loads(backup_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["viewer"], original["viewer"])
            self.assertEqual(saved["future_setting"], original["future_setting"])
            self.assertEqual(backup, original)
            self.assertEqual(
                editor.LoadPose(config_path).tolist(),
                pose.tolist(),
            )

    def test_save_rejects_pose_outside_safety_gate_range(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "startup_recovery.json"
            backup_path = root / "previous.json"
            config_path.write_text(
                json.dumps(
                    {
                        "safe_ready_pose_deg": {
                            name: 0.0 for name in editor.JOINT_NAMES
                        }
                    }
                ),
                encoding="utf-8",
            )
            pose = np.asarray([200.0, -30.0, 0.0, 55.0, 0.0, 0.0, 0.0])

            with self.assertRaisesRegex(RuntimeError, "outside Safety Gate"):
                editor.SavePose(config_path, pose, backup_path)

            self.assertFalse(backup_path.exists())


if __name__ == "__main__":
    unittest.main()
