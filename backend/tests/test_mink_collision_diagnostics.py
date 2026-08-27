from __future__ import annotations

import sys
import unittest
from pathlib import Path

import mujoco
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
BRIDGE_ROOT = PROJECT_ROOT / "hardware" / "g1_arm_bridge"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
if str(BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(BRIDGE_ROOT))

import run_mink_g1_right_arm_prototype as base  # noqa: E402
import diagnose_initial_pose_collision as collision_diag  # noqa: E402


class MinkCollisionDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base._prepare_mink_xml()
        cls.model = mujoco.MjModel.from_xml_path(str(base.g1.DEMO_XML))
        base._apply_operational_joint_limits(cls.model)
        cls.data = mujoco.MjData(cls.model)
        cls.data.qpos[:] = base._initial_configuration(cls.model)
        mujoco.mj_forward(cls.model, cls.data)
        _, cls.geom_pairs = base._build_collision_pairs(cls.model)

    def test_nearest_pair_preserves_distance_and_identity(self):
        detail = base._nearest_pair_distance(
            self.model,
            self.data,
            self.geom_pairs,
        )
        self.assertIsNotNone(detail)
        distance, first_geom, second_geom = detail
        self.assertAlmostEqual(
            distance,
            base._min_pair_distance(self.model, self.data, self.geom_pairs),
        )
        self.assertIsNotNone(
            mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, first_geom
            )
        )
        self.assertIsNotNone(
            mujoco.mj_id2name(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, second_geom
            )
        )

    def test_inspection_target_is_outboard_for_right_arm(self):
        target = base.g1.SCENES["control"]["inspection_target_pos"]
        self.assertEqual(target, (0.435, -0.28, 1.05))
        panel_position = base.g1.SCENES["control"]["panel_pos"]
        panel_half_size = base.g1.SCENES["control"]["panel_size"]
        self.assertLessEqual(
            abs(target[1] - panel_position[1]),
            panel_half_size[1],
        )

    def test_isolated_zero_mesh_distance_is_rechecked_without_hiding_contact(self):
        before = np.asarray(
            [
                0.22117133380352155,
                -0.3863857538233292,
                -0.6577224460510368,
                1.0029829619870072,
                0.06599266925745523,
                -0.41103103490601195,
                0.296409701553704,
            ]
        )
        candidate = np.asarray(
            [
                0.22091600716342982,
                -0.38612986062971877,
                -0.6574665528574264,
                1.0032388551806175,
                0.06573677606384483,
                -0.41077514171240154,
                0.2961538083600936,
            ]
        )
        pose = before + (7.0 / 15.0) * (candidate - before)
        first_geom = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_GEOM,
            "mink_collision_torso_link_0_19",
        )
        second_geom = mujoco.mj_name2id(
            self.model,
            mujoco.mjtObj.mjOBJ_GEOM,
            "mink_collision_right_shoulder_yaw_link_0_32",
        )
        self.assertGreaterEqual(first_geom, 0)
        self.assertGreaterEqual(second_geom, 0)

        try:
            collision_diag._joint_pose(
                self.model,
                self.data,
                base,
                pose,
            )
            fromto = np.empty(6, dtype=float)
            raw_distance = float(
                mujoco.mj_geomDistance(
                    self.model,
                    self.data,
                    first_geom,
                    second_geom,
                    0.2,
                    fromto,
                )
            )
            self.assertEqual(raw_distance, 0.0)
            self.assertFalse(
                collision_diag._has_exact_geom_contact(
                    self.data,
                    first_geom,
                    second_geom,
                )
            )

            corrected_distance = collision_diag._robust_geom_distance(
                self.model,
                self.data,
                base,
                first_geom,
                second_geom,
                0.2,
                fromto,
            )
            self.assertGreater(corrected_distance, 0.039)
        finally:
            self.data.qpos[:] = base._initial_configuration(self.model)
            mujoco.mj_forward(self.model, self.data)

    def test_only_measured_local_arm_pair_is_exempted(self):
        body_pairs = {
            frozenset(
                (
                    mujoco.mj_id2name(
                        self.model,
                        mujoco.mjtObj.mjOBJ_BODY,
                        int(self.model.geom_bodyid[first_geom]),
                    ),
                    mujoco.mj_id2name(
                        self.model,
                        mujoco.mjtObj.mjOBJ_BODY,
                        int(self.model.geom_bodyid[second_geom]),
                    ),
                )
            )
            for first_geom, second_geom in self.geom_pairs
        }

        self.assertNotIn(
            frozenset(("right_elbow_link", "right_wrist_yaw_link")),
            body_pairs,
        )
        self.assertIn(
            frozenset(("torso_link", "right_shoulder_yaw_link")),
            body_pairs,
        )
        self.assertIn(
            frozenset(("torso_link", "right_elbow_link")),
            body_pairs,
        )

        self.assertEqual(
            base.COLLISION_BODY_PAIR_EXEMPTIONS,
            {frozenset(("right_elbow_link", "right_wrist_yaw_link"))},
        )


if __name__ == "__main__":
    unittest.main()
