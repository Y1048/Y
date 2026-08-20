from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from g1_teleop.collision_policy import RightArmCollisionPolicy  # noqa: E402


class FakeContact:
    def __init__(self, geom1: int, geom2: int) -> None:
        self.geom1 = geom1
        self.geom2 = geom2


class FakeModel:
    def __init__(self) -> None:
        # body 0=world, 1=torso, 2=shoulder, 3=elbow, 4=wrist, 5=left arm
        self.nbody = 6
        self.body_parentid = [0, 0, 1, 2, 3, 1]
        # one geom per body for the tests
        self.geom_bodyid = [1, 2, 3, 4, 5, 0]


class FakeData:
    def __init__(self, contacts) -> None:
        self.contact = contacts
        self.ncon = len(contacts)


class CollisionPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = FakeModel()
        self.policy = RightArmCollisionPolicy(
            right_arm_body_ids={2, 3, 4},
            robot_body_ids={1, 2, 3, 4, 5},
            body_parent_ids=self.model.body_parentid,
        )

    def test_adjacent_robot_links_are_not_collisions(self):
        self.assertEqual(self.policy.classify_body_pair(1, 2), "adjacent")
        self.assertEqual(self.policy.classify_body_pair(2, 3), "adjacent")

    def test_non_adjacent_right_arm_self_contact_is_collision(self):
        self.assertEqual(
            self.policy.classify_body_pair(2, 4),
            "right_arm_self_collision",
        )

    def test_right_arm_contact_with_other_robot_body_is_collision(self):
        self.assertEqual(
            self.policy.classify_body_pair(4, 5),
            "right_arm_robot_collision",
        )

    def test_environment_and_irrelevant_contacts_are_not_self_collision(self):
        self.assertEqual(self.policy.classify_body_pair(4, 0), "environment")
        self.assertEqual(self.policy.classify_body_pair(1, 5), "irrelevant")

    def test_has_collision_uses_geom_body_mapping(self):
        # geom 1 -> shoulder(body 2), geom 3 -> wrist(body 4): non-adjacent
        data = FakeData([FakeContact(1, 3)])
        self.assertTrue(self.policy.has_collision(self.model, data))

        # geom 0 -> torso(body 1), geom 1 -> shoulder(body 2): parent-child
        data = FakeData([FakeContact(0, 1)])
        self.assertFalse(self.policy.has_collision(self.model, data))


if __name__ == "__main__":
    unittest.main()
