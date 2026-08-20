from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import (  # noqa: E402
    CollisionConfig, IKConfig, MotionConfig, NetworkConfig,
    RuntimeConfig, TeleopConfig, WorkspaceConfig,
)
from g1_teleop.runtime_collision import (  # noqa: E402
    RuntimeContactInfo,
    classify_runtime_contact,
    collision_step_scale,
    install_runtime_collision_policy,
    scan_runtime_contacts,
    slide_target_along_contact,
)


class FakeContact:
    def __init__(self, geom1: int, geom2: int, dist: float = 0.0,
                 frame=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)) -> None:
        self.geom1 = geom1
        self.geom2 = geom2
        self.dist = dist
        self.frame = frame


class FakeModel:
    def __init__(self) -> None:
        self.nbody = 8
        self.body_parentid = [0, 0, 1, 2, 3, 4, 1, 5]
        self.geom_bodyid = [1, 2, 3, 4, 5, 6, 0, 0, 7]
        self.body_names = [
            "world", "torso_link", "right_shoulder_pitch_link",
            "right_shoulder_roll_link", "right_elbow_link",
            "right_wrist_roll_link", "left_shoulder_link",
            "inspection_tool_tip_body",
        ]
        self.geom_names = [
            "torso_geom", "shoulder_geom", "shoulder_roll_geom",
            "elbow_geom", "wrist_geom", "left_arm_geom",
            "pipe_obstacle", "inspection_panel", "inspection_tool_tip",
        ]


class FakeData:
    def __init__(self, contacts) -> None:
        self.contact = contacts
        self.ncon = len(contacts)
        self.xpos = np.zeros((8, 3), dtype=float)


def make_config(*, environment_obstacles_enabled=True, tangential_slide_enabled=True) -> TeleopConfig:
    return TeleopConfig(
        network=NetworkConfig("0.0.0.0", 5005, "127.0.0.1", 5006, 60.0),
        runtime=RuntimeConfig(0.75, 0.8, 2.0, 30.0, 600),
        motion=MotionConfig(0.08, 70.0),
        ik=IKConfig(0.045, 0.035, 0.5, 1.5, 0.08, 0.65, 0.08, 0.85),
        collision=CollisionConfig(
            0.015, 2, environment_obstacles_enabled, tangential_slide_enabled,
            True, ("inspection_tool_tip_body",), ("inspection_panel",),
        ),
        workspace=WorkspaceConfig(
            0.01, (1, 2), "logs/workspace/right_arm_workspace.npz",
            (-0.2, -0.3, -0.28), (0.2, 0.45, 0.34), -0.3, -0.3,
            (-0.18, 0.22), (0.45, 1.30),
        ),
    )


class RuntimeCollisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = FakeModel()
        self.context = {"right_arm_body_ids": {2, 3, 4, 5, 7}, "position_body": 5}

    def _policy(self):
        from g1_teleop.runtime_collision import get_runtime_collision_policy
        return get_runtime_collision_policy(self.model, self.context, structural_neighbor_distance=2)

    def test_environment_obstacle_is_dangerous(self):
        status = classify_runtime_contact(self.model, FakeContact(4, 6, 0.01), self._policy(), make_config())
        self.assertEqual(status, "environment_obstacle")

    def test_environment_can_be_disabled(self):
        status = classify_runtime_contact(
            self.model, FakeContact(4, 6, 0.01), self._policy(),
            make_config(environment_obstacles_enabled=False),
        )
        self.assertEqual(status, "environment")

    def test_only_configured_tool_target_pair_is_task_contact(self):
        self.assertEqual(
            classify_runtime_contact(self.model, FakeContact(8, 7, 0.0), self._policy(), make_config()),
            "task_contact",
        )
        self.assertEqual(
            classify_runtime_contact(self.model, FakeContact(4, 7, 0.0), self._policy(), make_config()),
            "environment_obstacle",
        )

    def test_scan_reports_task_contact_without_making_it_dangerous(self):
        nearest, task_active = scan_runtime_contacts(
            self.model, FakeData([FakeContact(8, 7, -0.001)]), self.context, make_config()
        )
        self.assertIsNone(nearest)
        self.assertTrue(task_active)

    def test_scan_finds_nearest_forbidden_environment_contact(self):
        # Both contacts must involve a right-arm geom and an environment geom.
        # The previous fixture accidentally used left_arm_geom vs world for the
        # 0.006 m sample, so it was correctly excluded by the runtime scanner.
        nearest, task_active = scan_runtime_contacts(
            self.model,
            FakeData([FakeContact(4, 6, 0.012), FakeContact(8, 6, 0.006)]),
            self.context, make_config(),
        )
        self.assertFalse(task_active)
        self.assertEqual(nearest.status, "environment_obstacle")
        self.assertAlmostEqual(nearest.clearance_m, 0.006)

    def test_collision_step_scale_is_smooth(self):
        self.assertEqual(collision_step_scale(None, 0.015), 1.0)
        self.assertEqual(collision_step_scale(0.015, 0.015), 1.0)
        self.assertEqual(collision_step_scale(0.0, 0.015), 0.0)
        self.assertAlmostEqual(collision_step_scale(0.0075, 0.015), 0.5)

    def test_slide_preserves_tangent_and_scales_inward_motion(self):
        contact = RuntimeContactInfo(
            "environment_obstacle", 0.0075, 5, 0, 4, 6,
            np.array([1.0, 0.0, 0.0]),
        )
        adjusted = slide_target_along_contact(
            np.zeros(3), np.array([0.10, 0.20, 0.0]), contact, 0.5
        )
        np.testing.assert_allclose(adjusted, [0.05, 0.20, 0.0])

    def test_slide_does_not_block_motion_away_from_obstacle(self):
        contact = RuntimeContactInfo(
            "environment_obstacle", 0.001, 5, 0, 4, 6,
            np.array([1.0, 0.0, 0.0]),
        )
        target = np.array([-0.10, 0.20, 0.0])
        np.testing.assert_allclose(
            slide_target_along_contact(np.zeros(3), target, contact, 0.0), target
        )

    def test_installer_enriches_status_with_task_aware_fields(self):
        written = []
        base = SimpleNamespace(
            has_right_arm_core_contact=lambda *_: False,
            write_runtime_status=lambda value: written.append(value),
        )
        install_runtime_collision_policy(base, make_config())
        base.RUNTIME_COLLISION_NEAREST_STATUS = "environment_obstacle"
        base.RUNTIME_TASK_CONTACT_ACTIVE = True
        base.write_runtime_status({"ok": True})
        self.assertEqual(written[0]["collision_nearest_status"], "environment_obstacle")
        self.assertTrue(written[0]["task_contact_active"])
        self.assertTrue(written[0]["environment_obstacles_enabled"])
        self.assertTrue(written[0]["tangential_slide_enabled"])


if __name__ == "__main__":
    unittest.main()
