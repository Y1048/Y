import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import diagnose_recorded_reach as diagnosis


class RecordedReachBoundTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = diagnosis.probe
        p.base._prepare_mink_xml()
        cls.model = p.mujoco.MjModel.from_xml_path(str(p.base.g1.DEMO_XML))
        p.base._apply_operational_joint_limits(cls.model)

    def test_official_model_chain_upper_bound(self):
        self.assertAlmostEqual(diagnosis.GetReachUpperBound(self.model), 0.4103940645343519, places=10)

    def test_sampled_joint_poses_do_not_exceed_proven_bound(self):
        p = diagnosis.probe
        bound = diagnosis.GetReachUpperBound(self.model)
        configuration = p.mink.Configuration(self.model)
        rng = np.random.default_rng(1701)
        for _ in range(1000):
            q = p.base._initial_configuration(self.model)
            for name in p.base.g1.RIGHT_ARM_JOINTS:
                joint = p.base._joint_id(self.model, name)
                q[self.model.jnt_qposadr[joint]] = rng.uniform(*self.model.jnt_range[joint])
            configuration.update(q)
            shoulder = configuration.get_transform_frame_to_world("right_shoulder_pitch_link", "body").translation()
            wrist = configuration.get_transform_frame_to_world("right_wrist_yaw_link", "body").translation()
            self.assertLessEqual(np.linalg.norm(wrist - shoulder), bound + 1e-10)

    def test_unrelated_branch_is_rejected(self):
        with self.assertRaises(ValueError):
            diagnosis.GetReachUpperBound(self.model, wrist_name="left_wrist_yaw_link")

    def test_offset_joint_requires_different_proof(self):
        joint = diagnosis.probe.base._joint_id(self.model, "right_elbow_joint")
        old = self.model.jnt_pos[joint].copy()
        try:
            self.model.jnt_pos[joint, 0] = 0.01
            with self.assertRaises(ValueError):
                diagnosis.GetReachUpperBound(self.model)
        finally:
            self.model.jnt_pos[joint] = old


if __name__ == "__main__":
    unittest.main()
