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
    collision_step_scale,
    dangerous_contact_clearance_m,
    get_runtime_collision_policy,
    has_runtime_right_arm_collision,
    install_runtime_collision_policy,
)


class FakeContact:
    def __init__(self, geom1: int, geom2: int, dist: float = 0.0) -> None:
        self.geom1 = geom1
        self.geom2 = geom2
        self.dist = dist


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
        self.xpos = [[0.0, 0.0, 0.0] for _ in range(7)]


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
        self.context = {"right_arm_body_ids": {2, 3, 4, 5}, "position_body": 5}

    def test_runtime_policy_matches_two_hop_exclusion(self):
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

    def test_clearance_uses_only_dangerous_pairs(self):
        # geom 1/body2 vs geom3/body4 is two-hop and ignored; geom1/body2 vs
        # geom4/body5 is a dangerous three-hop right-arm pair.
        data = FakeData(
            [
                FakeContact(1, 3, 0.001),
                FakeContact(1, 4, 0.009),
                FakeContact(4, 5, 0.006),
            ]
        )
        self.assertAlmostEqual(
            dangerous_contact_clearance_m(
                self.model,
                data,
                self.context,
                structural_neighbor_distance=2,
            ),
            0.006,
        )

    def test_collision_step_scale_is_smooth(self):
        self.assertEqual(collision_step_scale(None, 0.015), 1.0)
        self.assertEqual(collision_step_scale(0.015, 0.015), 1.0)
        self.assertEqual(collision_step_scale(0.0, 0.015), 0.0)
        self.assertAlmostEqual(collision_step_scale(0.0075, 0.015), 0.5)
        self.assertLess(collision_step_scale(0.003, 0.015), 0.2)

    def test_installer_hard_stops_only_at_physical_contact(self):
        base = SimpleNamespace(has_right_arm_core_contact=lambda *_: False)
        install_runtime_collision_policy(base, make_config(2))

        near = FakeData([FakeContact(1, 4, 0.008)])
        touching = FakeData([FakeContact(1, 4, 0.0)])
        penetrating = FakeData([FakeContact(1, 4, -0.001)])
        self.assertFalse(base.has_right_arm_core_contact(self.model, near, self.context))
        self.assertTrue(base.has_right_arm_core_contact(self.model, touching, self.context))
        self.assertTrue(base.has_right_arm_core_contact(self.model, penetrating, self.context))
        self.assertEqual(base.RUNTIME_COLLISION_POLICY, "RightArmCollisionPolicy")
        self.assertAlmostEqual(base.RUNTIME_COLLISION_SLOWDOWN_DISTANCE_M, 0.015)

    def test_solver_wrapper_scales_step_gain_and_restores_nominal_gain(self):
        observed = []

        def solver(model, data, *args, context=None, **kwargs):
            observed.append(base.IK_STEP_GAIN)
            return data.xpos[context["position_body"]]

        base = SimpleNamespace(
            has_right_arm_core_contact=lambda *_: False,
            solve_right_arm_target=solver,
            IK_STEP_GAIN=0.5,
        )
        install_runtime_collision_policy(base, make_config(2))
        data = FakeData([FakeContact(1, 4, 0.0075)])
        base.solve_right_arm_target(self.model, data, context=self.context)
        self.assertAlmostEqual(observed[0], 0.25)
        self.assertAlmostEqual(base.IK_STEP_GAIN, 0.5)
        self.assertAlmostEqual(self.context["collision_step_scale"], 0.5)

    def test_status_writer_receives_distance_metrics(self):
        written = []
        base = SimpleNamespace(
            has_right_arm_core_contact=lambda *_: False,
            write_runtime_status=lambda value: written.append(value),
        )
        install_runtime_collision_policy(base, make_config(2))
        base.RUNTIME_COLLISION_CLEARANCE_M = 0.01
        base.RUNTIME_COLLISION_STEP_SCALE = 0.74
        base.write_runtime_status({"ok": True})
        self.assertAlmostEqual(written[0]["collision_clearance_m"], 0.01)
        self.assertAlmostEqual(written[0]["collision_step_scale"], 0.74)
        self.assertAlmostEqual(written[0]["collision_slowdown_distance_m"], 0.015)


if __name__ == "__main__":
    unittest.main()
