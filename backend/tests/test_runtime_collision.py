from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.config import (  # noqa: E402
    CollisionConfig,
    IKConfig,
    MotionConfig,
    NetworkConfig,
    RuntimeConfig,
    TeleopConfig,
    WorkspaceConfig,
)
from g1_teleop.runtime_collision import (  # noqa: E402
    get_runtime_collision_policy,
    has_runtime_right_arm_collision,
    install_runtime_collision_policy,
)


class FakeContact:
    def __init__(self, geom1: int, geom2: int) -> None:
        self.geom1 = geom1
        self.geom2 = geom2


class FakeModel:
    def __init__(self) -> None:
        # 0=world, 1=torso, 2=shoulder_pitch, 3=shoulder_roll,
        # 4=elbow, 5=wrist, 6=left_arm
        self.nbody = 7
        self.body_parentid = [0, 0, 1, 2, 3, 4, 1]
        self.geom_bodyid = [1, 2, 3, 4, 5, 6, 0]


class FakeData:
    def __init__(self, contacts) -> None:
        self.contact = contacts
        self.ncon = len(contacts)


def make_config(structural_neighbor_distance: int = 2) -> TeleopConfig:
    return TeleopConfig(
        network=NetworkConfig("0.0.0.0", 5005, "127.0.0.1", 5006, 60.0),
        runtime=RuntimeConfig(0.75, 0.8, 2.0, 30.0, 600),
        motion=MotionConfig(0.08, 70.0),
        ik=IKConfig(0.045, 0.035, 0.5, 1.5, 0.08, 0.65, 0.08, 0.85),
        collision=CollisionConfig(0.015, structural_neighbor_distance),
        workspace=WorkspaceConfig(
            0.01,
            (1, 2),
            "logs/workspace/right_arm_workspace.npz",
            (-0.2, -0.3, -0.28),
            (0.2, 0.45, 0.34),
            -0.3,
            -0.3,
            (-0.18, 0.22),
            (0.45, 1.30),
        ),
    )


class RuntimeCollisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = FakeModel()
        self.context = {"right_arm_body_ids": {2, 3, 4, 5}}

    def test_runtime_policy_matches_two_hop_exclusion(self):
        # shoulder_pitch(body 2) -> shoulder_roll(body 3) -> elbow(body 4)
        data = FakeData([FakeContact(1, 3)])
        self.assertFalse(
            has_runtime_right_arm_collision(
                self.model,
                data,
                self.context,
                structural_neighbor_distance=2,
            )
        )

    def test_runtime_policy_rejects_three_hop_right_arm_self_collision(self):
        # shoulder_pitch(body 2) -> shoulder_roll(3) -> elbow(4) -> wrist(5)
        data = FakeData([FakeContact(1, 4)])
        self.assertTrue(
            has_runtime_right_arm_collision(
                self.model,
                data,
                self.context,
                structural_neighbor_distance=2,
            )
        )

    def test_runtime_policy_rejects_right_arm_to_other_robot_contact(self):
        # wrist(body 5) vs left_arm(body 6)
        data = FakeData([FakeContact(4, 5)])
        self.assertTrue(
            has_runtime_right_arm_collision(
                self.model,
                data,
                self.context,
                structural_neighbor_distance=2,
            )
        )

    def test_policy_is_cached_per_context_and_model(self):
        first = get_runtime_collision_policy(
            self.model,
            self.context,
            structural_neighbor_distance=2,
        )
        second = get_runtime_collision_policy(
            self.model,
            self.context,
            structural_neighbor_distance=2,
        )
        self.assertIs(first, second)

    def test_installer_replaces_legacy_solver_hook(self):
        base = SimpleNamespace(has_right_arm_core_contact=lambda *_: False)
        install_runtime_collision_policy(base, make_config(2))
        data = FakeData([FakeContact(1, 4)])
        self.assertTrue(base.has_right_arm_core_contact(self.model, data, self.context))
        self.assertEqual(base.RUNTIME_COLLISION_POLICY, "RightArmCollisionPolicy")
        self.assertEqual(base.RUNTIME_COLLISION_STRUCTURAL_NEIGHBOR_DISTANCE, 2)


if __name__ == "__main__":
    unittest.main()
