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
        # 0=world, 1=torso, 2=shoulder_pitch, 3=shoulder_roll,
        # 4=elbow, 5=wrist, 6=left_arm
        self.nbody = 7
        self.body_parentid = [0, 0, 1, 2, 3, 4, 1]
        # one geom per non-world body, plus one world geom
        self.geom_bodyid = [1, 2, 3, 4, 5, 6, 0]


class FakeData:
    def __init__(self, contacts) -> None:
        self.contact = contacts
        self.ncon = len(contacts)


class CollisionPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model = FakeModel()
        self.policy = RightArmCollisionPolicy(
            right_arm_body_ids={2, 3, 4, 5},
            robot_body_ids={1, 2, 3, 4, 5, 6},
            body_parent_ids=self.model.body_parentid,
        )

    def test_kinematic_distance_uses_body_tree(self):
        self.assertEqual(self.policy.kinematic_distance(2, 3), 1)
        self.assertEqual(self.policy.kinematic_distance(2, 4), 2)
        self.assertEqual(self.policy.kinematic_distance(2, 5), 3)
        self.assertEqual(self.policy.kinematic_distance(1, 3), 2)

    def test_adjacent_robot_links_are_not_collisions(self):
        self.assertEqual(self.policy.classify_body_pair(1, 2), "adjacent")
        self.assertEqual(self.policy.classify_body_pair(3, 4), "adjacent")

    def test_two_hop_structural_neighbors_are_not_collisions(self):
        self.assertEqual(self.policy.classify_body_pair(1, 3), "near_adjacent")
        self.assertEqual(self.policy.classify_body_pair(2, 4), "near_adjacent")
        self.assertEqual(self.policy.classify_body_pair(3, 5), "near_adjacent")

    def test_three_hop_right_arm_self_contact_remains_collision(self):
        self.assertEqual(
            self.policy.classify_body_pair(2, 5),
            "right_arm_self_collision",
        )

    def test_right_arm_contact_with_other_robot_body_is_collision(self):
        self.assertEqual(
            self.policy.classify_body_pair(5, 6),
            "right_arm_robot_collision",
        )

    def test_environment_and_irrelevant_contacts_are_not_self_collision(self):
        self.assertEqual(self.policy.classify_body_pair(5, 0), "environment")
        self.assertEqual(self.policy.classify_body_pair(1, 6), "irrelevant")

    def test_has_collision_uses_geom_body_mapping(self):
        # geom 1 -> shoulder_pitch(body 2), geom 4 -> wrist(body 5): 3-hop collision
        data = FakeData([FakeContact(1, 4)])
        self.assertTrue(self.policy.has_collision(self.model, data))

        # geom 0 -> torso(body 1), geom 2 -> shoulder_roll(body 3): 2-hop structural neighbor
        data = FakeData([FakeContact(0, 2)])
        self.assertFalse(self.policy.has_collision(self.model, data))

    def test_structural_neighbor_distance_is_configurable(self):
        strict_policy = RightArmCollisionPolicy(
            right_arm_body_ids={2, 3, 4, 5},
            robot_body_ids={1, 2, 3, 4, 5, 6},
            body_parent_ids=self.model.body_parentid,
            structural_neighbor_distance=1,
        )
        self.assertEqual(
            strict_policy.classify_body_pair(2, 4),
            "right_arm_self_collision",
        )

        with self.assertRaises(ValueError):
            RightArmCollisionPolicy(
                right_arm_body_ids={2},
                robot_body_ids={1, 2},
                body_parent_ids=self.model.body_parentid,
                structural_neighbor_distance=0,
            )


if __name__ == "__main__":
    unittest.main()
