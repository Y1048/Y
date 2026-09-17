from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import math
import mujoco
import mink


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = PROJECT_ROOT / "MuJoCo_G1_Controller" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

from run_mink_g1_right_arm_virtual_center_live import (  # noqa: E402
    ASSIST_ENTER_MARGIN_DEG,
    ASSIST_FULL_MARGIN_DEG,
    ASSIST_MAX,
    ASSIST_RELEASE_MARGIN_DEG,
    ORIENTATION_COST_MIN_SCALE,
    ORIENTATION_ERROR_NORMAL_MAX_DEG,
    ORIENTATION_ERROR_LIMIT_MAX_DEG,
    ORIENTATION_PROXIMAL_DAMPING_MAX,
    ORIENTATION_PROXIMAL_DAMPING_MIN,
    PROXIMAL_MAX_JOINT_VELOCITY_DEG_S,
    WRIST_MAX_JOINT_VELOCITY_DEG_S,
    orientation_limit_policy,
    hierarchical_orientation_damping_costs,
)
import run_mink_g1_right_arm_prototype as base  # noqa: E402
from run_mink_g1_right_arm_virtual_center_live import (  # noqa: E402
    VirtualCenterOrientationTask,
)


class VirtualCenterOrientationPolicyTest(unittest.TestCase):
    def test_live_joint_speed_matches_static_stand_reference(self):
        expected = math.degrees(base.RIGHT_ARM_MAX_VELOCITY_RAD_S)
        self.assertAlmostEqual(PROXIMAL_MAX_JOINT_VELOCITY_DEG_S, expected)
        self.assertAlmostEqual(WRIST_MAX_JOINT_VELOCITY_DEG_S, expected)

    def test_far_from_limit_preserves_wrist_only_behavior(self):
        latched, assist, cost_scale, error_cap = orientation_limit_policy(
            ASSIST_RELEASE_MARGIN_DEG + 1.0,
            False,
        )

        self.assertFalse(latched)
        self.assertEqual(assist, 0.0)
        self.assertEqual(cost_scale, 1.0)
        self.assertGreater(error_cap, ORIENTATION_ERROR_LIMIT_MAX_DEG)

    def test_hard_limit_prioritizes_position_and_full_proximal_assist(self):
        latched, assist, cost_scale, error_cap = orientation_limit_policy(
            ASSIST_FULL_MARGIN_DEG,
            True,
        )

        self.assertTrue(latched)
        self.assertAlmostEqual(assist, ASSIST_MAX)
        self.assertAlmostEqual(cost_scale, 1.0)
        self.assertAlmostEqual(error_cap, ORIENTATION_ERROR_NORMAL_MAX_DEG)

    def test_assist_increases_monotonically_toward_limit(self):
        margins = [28.0, 20.0, 14.0, 8.0, 5.0]
        values = [orientation_limit_policy(value, True) for value in margins]

        assists = [value[1] for value in values]
        costs = [value[2] for value in values]
        caps = [value[3] for value in values]
        self.assertEqual(assists, sorted(assists))
        self.assertTrue(all(value == 1.0 for value in costs))
        self.assertTrue(
            all(value == ORIENTATION_ERROR_NORMAL_MAX_DEG for value in caps)
        )

    def test_proximal_damping_decreases_continuously_with_assist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
            model = mujoco.MjModel.from_xml_path(str(path))
        proximal_dof = int(model.jnt_dofadr[
            base._joint_id(model, "right_shoulder_pitch_joint")
        ])
        wrist_dof = int(model.jnt_dofadr[
            base._joint_id(model, "right_wrist_roll_joint")
        ])

        values = [
            hierarchical_orientation_damping_costs(model, assist)
            for assist in (0.0, 0.5, 1.0)
        ]
        self.assertAlmostEqual(values[0][proximal_dof], ORIENTATION_PROXIMAL_DAMPING_MAX)
        self.assertAlmostEqual(values[-1][proximal_dof], ORIENTATION_PROXIMAL_DAMPING_MIN)
        self.assertGreater(values[0][proximal_dof], values[1][proximal_dof])
        self.assertGreater(values[1][proximal_dof], values[2][proximal_dof])
        self.assertAlmostEqual(values[0][wrist_dof], values[-1][wrist_dof])

    def test_mink_residual_path_applies_limit_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
            model = mujoco.MjModel.from_xml_path(str(path))
        base._apply_operational_joint_limits(model)
        configuration = mink.Configuration(model)
        configuration.update(base._initial_configuration(model))

        q = configuration.q.copy()
        joint_id = base._joint_id(model, "right_wrist_roll_joint")
        qpos = int(model.jnt_qposadr[joint_id])
        q[qpos] = math.radians(-112.0)
        configuration.update(q)

        task = VirtualCenterOrientationTask(model)
        task.set_target_from_configuration(configuration)
        task.compute_qp_residual(configuration)

        self.assertTrue(VirtualCenterOrientationTask.assist_latched)
        self.assertGreater(VirtualCenterOrientationTask.last_assist_gain, 0.95)
        self.assertAlmostEqual(
            VirtualCenterOrientationTask.last_orientation_cost_scale,
            1.0,
        )
        self.assertAlmostEqual(
            VirtualCenterOrientationTask.last_min_wrist_margin_deg,
            1.0,
            places=2,
        )
        self.assertGreaterEqual(
            VirtualCenterOrientationTask.last_wrist_jacobian_sigma_min,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
