from __future__ import annotations

import sys
import unittest
from pathlib import Path

import mujoco


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import run_mink_g1_right_arm_prototype as base  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
