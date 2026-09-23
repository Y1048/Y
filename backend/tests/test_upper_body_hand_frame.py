"""Offline contract checks: wrist anatomy, world basis, Omni-independent arms."""
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'Unity_G1_VR/Assets/G1Teleop'
BASIS = np.array([[0., 0., 1.], [-1., 0., 0.], [0., 1., 0.]])

class UpperBodyFrameTests(unittest.TestCase):
    def test_palm_down_both_hands_and_body_turns(self):
        # Synthetic measured anatomy: forward fingers, thumb toward body's midline.
        # G1's neutral mesh has fingers +X, thumb +Z, dorsal +Y left / -Y right.
        for angle in (0., np.pi/2, -np.pi/2, np.pi):
            c, s = np.cos(angle), np.sin(angle)
            turn = np.array([[c,0,s],[0,1,0],[-s,0,c]])
            for left in (True, False):
                forward = turn @ np.array([0.,0.,1.])
                across = turn @ np.array([1. if left else -1.,0.,0.])
                # Quaternion.LookRotation(forward, across) columns.
                unity_r = np.column_stack((np.cross(across, forward), across, forward))
                robot_r = BASIS @ unity_r @ BASIS.T
                np.testing.assert_allclose(robot_r @ [1,0,0], BASIS @ forward, atol=1e-12)
                np.testing.assert_allclose(robot_r @ [0,0,1], BASIS @ across, atol=1e-12)
                np.testing.assert_allclose(robot_r @ [0,1 if left else -1,0], [0,0,1], atol=1e-12)
                self.assertAlmostEqual(np.linalg.det(robot_r), 1.)
        binder = (CS/'G1ExistingHandTargetBinder.cs').read_text(encoding='utf-8')
        self.assertIn('Quaternion.LookRotation(finger_direction, palm_across)', binder)
        self.assertIn('DisplayedWristRotation = current_wrist_rotation;', binder)
        sender = (CS/'G1BimanualSimulationSender.cs').read_text(encoding='utf-8')
        self.assertIn('Quaternion q = binder.DisplayedWristRotation;', sender)
        self.assertIn('Quaternion rawQ = binder.SourceWristRotation;', sender)

    def test_omni_cannot_gate_head_or_hand_engagement(self):
        sender = (CS/'G1BimanualSimulationSender.cs').read_text(encoding='utf-8')
        self.assertNotIn('omniReady', sender)
        self.assertNotIn('Omni.IsReady', sender)
        camera = (CS/'G1HeadLockedCamera.cs').read_text(encoding='utf-8')
        start = camera.index('IsHeadTrackingReady = current_time')
        readiness = camera[start:camera.index('return IsHeadTrackingReady;', start)]
        self.assertNotIn('Omni', readiness)

if __name__ == '__main__':
    unittest.main()
